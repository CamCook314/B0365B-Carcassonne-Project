"""
Project_CV.py — Main CV loop and engine communication globals.

Drives the phase state machine and owns all board-level state.
Image processing lives in blob_pipeline.py.
Grid coordinate logic lives in grid_tracker.py.
"""
import cv2 as cv
import numpy as np
import ctypes
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cv import image_match
from cv.blob_pipeline import process_frame, mask_centroid, find_contours, classify_contours
from cv.grid_tracker import GridTracker
from cv.meeple_detector import detect_meeple, CROP_HALF_FRAC
import time

# --- Communication globals ---
# Written by CV, read by the engine (or cv_test_interface.py during development).
tile_checked      = False        # True once a tile has been identified
tile_id           = None         # Bare tile ID string, e.g. "ID43"
tile_candidates   = []           # Top-N (score, tile_id) list from match_image; set alongside tile_checked
tile_id_override  = None         # Set by the bridge when the user corrects the CV's identification
grid_checked      = False        # True once placement coordinates are ready
grid_coord        = None         # (gx, gy) tuple in CV coordinate space
cv_to_engine      = False        # Raised when CV has a placement ready for the engine
game_response     = (False, 1)   # (responded_bool, result_int); 1 = valid, 0 = invalid
grid_origin       = None         # (x, y) pixel centre of tile (0,0) in proc coords (1920×1080)
grid_tile_size    = None         # Pixel distance between adjacent tile centres in proc coords
grid_angle        = None         # Board rotation angle in degrees
meeple_placed          = False   # CV sets when meeple detected; bridge clears after POST /meeple
meeple_colour          = None    # "red","blue","green","yellow","black"
meeple_direction       = None    # "up","down","left","right","centre"
meeple_skip            = False   # CV sets on timeout/skip; bridge clears after POST /meeple/skip
meeple_handled         = False   # Set by bridge when website button handled the meeple/skip
expected_meeple_colour = None    # Bridge sets to current player colour at start of each turn
remaining_families     = None    # Bridge updates after each placement; set of family base IDs still in bag
valid_meeple_sides     = None    # Bridge sets after placement: list of valid sides for the tile
last_id_crop_path      = None    # Path to the most recently saved identification crop (set by CV, read by bridge)


_SIDE_VECTORS = {
    "up":     ( 0.0, -1.0),
    "down":   ( 0.0,  1.0),
    "left":   (-1.0,  0.0),
    "right":  ( 1.0,  0.0),
    "centre": ( 0.0,  0.0),
}

def _nearest_valid_side(dx, dy, valid_sides):
    """Return the side from valid_sides whose direction best matches the (dx, dy) vector."""
    mag = float(np.hypot(dx, dy))
    ndx, ndy = (dx / mag, dy / mag) if mag > 1e-6 else (0.0, 1.0)
    return max(valid_sides, key=lambda s: ndx * _SIDE_VECTORS[s][0] + ndy * _SIDE_VECTORS[s][1])


def crop_placed_slot(frame, slot_px, tile_size_px, proc_scale, board_angle_deg,
                     center_px=None, padding=0.85):
    """Crop and deskew the placed tile at the confirmed grid slot.

    slot_px and center_px are in processed-frame (1920×1080) coordinates.
    center_px is the observed saturation centroid; falls back to slot_px (grid
    prediction) when not available.  Scales up to full-res, deskews by the
    board rotation angle, and returns a tight square crop for match_rotation().
    padding < 1.0 intentionally clips tile edges to exclude table and adjacent tiles.
    """
    if center_px is not None and (center_px[0] is None or center_px[1] is None):
        center_px = None
    src = center_px if center_px is not None else slot_px
    cx = src[0] / proc_scale
    cy = src[1] / proc_scale
    ts = tile_size_px / proc_scale
    side = int(ts * padding)

    margin = int(side * 0.8)
    x1_roi = max(int(cx) - side - margin, 0)
    y1_roi = max(int(cy) - side - margin, 0)
    x2_roi = min(int(cx) + side + margin, frame.shape[1])
    y2_roi = min(int(cy) + side + margin, frame.shape[0])
    roi = frame[y1_roi:y2_roi, x1_roi:x2_roi]

    print(f"  [crop_placed_slot] src={'center' if center_px is not None else 'slot'}"
          f"  proc=({src[0]:.0f},{src[1]:.0f})  full-res=({cx:.0f},{cy:.0f})"
          f"  frame={frame.shape[1]}x{frame.shape[0]}"
          f"  tile_size_px={tile_size_px:.1f}  ts={ts:.1f}  side={side}"
          f"  ROI=({x1_roi},{y1_roi})->({x2_roi},{y2_roi})  roi_shape={roi.shape}"
          f"  angle={board_angle_deg:.1f}°")

    cx_roi = cx - x1_roi
    cy_roi = cy - y1_roi
    M = cv.getRotationMatrix2D((cx_roi, cy_roi), board_angle_deg, 1.0)
    rotated = cv.warpAffine(roi, M, (roi.shape[1], roi.shape[0]),
                            flags=cv.INTER_LINEAR)

    x1 = max(int(cx_roi) - side // 2, 0)
    y1 = max(int(cy_roi) - side // 2, 0)
    x2 = min(int(cx_roi) + side // 2, rotated.shape[1])
    y2 = min(int(cy_roi) + side // 2, rotated.shape[0])
    crop = rotated[y1:y2, x1:x2]
    print(f"  [crop_placed_slot] final crop shape={crop.shape}")
    return crop


# Returns True if a meeple can be placed on a given side of a given tile.
# Sides: "up", "down", "left", "right", "centre".
# Note: Monestary only accepts middle. Other sides need a road or city edge.
# Edge values: 0 = field, 1 = road, 2 = city, 3 = river.
def is_valid_meeple_side(tile, side):
    if side == "centre":
        return tile.attribute == 2

    if side not in ("up", "down", "left", "right"):
        return False

    edge = getattr(tile, side)
    return edge == 1 or edge == 2


def extract_tile_crop(frame, contour, proc_scale,
                      board_angle_deg=0.0, tile_size_px=None, padding=0.85):
    """Return a rotation-corrected square crop of the tile from the full-res frame.

    board_angle_deg: board rotation from grid_tracker (atan2(b, a) in degrees).
      Used to deskew the crop consistently across all tiles.  Defaults to 0 for
      the first tile before the grid angle is calibrated.
    tile_size_px: calibrated tile size in proc-frame pixels; scales to full-res.
      Falls back to the contour's minAreaRect long side when not yet available.
    """
    rect = cv.minAreaRect(contour)
    (cx, cy), (rw, rh), _ = rect

    # Scale centre to full-res coords
    cx = cx / proc_scale
    cy = cy / proc_scale

    # Prefer the calibrated tile size; fall back to contour dimensions
    if tile_size_px is not None:
        ts = tile_size_px / proc_scale
    else:
        ts = max(rw, rh) / proc_scale

    side   = int(ts * padding)
    margin = int(side * 0.8)

    x1_roi = max(int(cx) - side - margin, 0)
    y1_roi = max(int(cy) - side - margin, 0)
    x2_roi = min(int(cx) + side + margin, frame.shape[1])
    y2_roi = min(int(cy) + side + margin, frame.shape[0])
    roi    = frame[y1_roi:y2_roi, x1_roi:x2_roi]

    cx_roi = cx - x1_roi
    cy_roi = cy - y1_roi

    M       = cv.getRotationMatrix2D((cx_roi, cy_roi), board_angle_deg, 1.0)
    rotated = cv.warpAffine(roi, M, (roi.shape[1], roi.shape[0]),
                            flags=cv.INTER_LINEAR)

    x1 = max(int(cx_roi) - side // 2, 0)
    y1 = max(int(cy_roi) - side // 2, 0)
    x2 = min(int(cx_roi) + side // 2, rotated.shape[1])
    y2 = min(int(cy_roi) + side // 2, rotated.shape[0])
    crop = rotated[y1:y2, x1:x2]
    print(f"  [extract_tile_crop] centre=({cx:.0f},{cy:.0f})  ts={ts:.1f}  side={side}"
          f"  angle={board_angle_deg:.1f}°  crop={crop.shape}")
    return crop


def cv_main_loop():

    model, preprocess  = image_match.model_setup()
    embeddings         = image_match.load_embeddings()
    game_embeddings    = image_match.load_game_embeddings()
    bias               = image_match.load_bias()

    # Minimum per-rotation cosine similarity for match_rotation to be trusted.
    # Below this the system falls back to reporting the family ID only.
    ROT_CONF_THRESHOLD = 0.70

    cap = cv.VideoCapture(0, cv.CAP_DSHOW)
    cap.set(cv.CAP_PROP_FRAME_WIDTH,  3840)
    cap.set(cv.CAP_PROP_FRAME_HEIGHT, 2160)
    # Let the camera autofocus on the table surface, then lock and record the value.
    # FOCUS_DISTANCE: if set to a value >= 0, autofocus is skipped and the camera
    # jumps straight to this focus value (faster startup, consistent focus each run).
    # Set to -1 to let autofocus settle first and print the discovered value instead.
    FOCUS_DISTANCE = 14   # Brio MX locked at table distance (~80cm); -1 to re-discover

    if FOCUS_DISTANCE >= 0:
        cap.set(cv.CAP_PROP_AUTOFOCUS, 0)
        cap.set(cv.CAP_PROP_FOCUS, FOCUS_DISTANCE)
        print(f"Focus set to hardcoded value {FOCUS_DISTANCE} (autofocus disabled)")
    else:
        print("Waiting 3s for autofocus to settle on the table...")
        time.sleep(3)
        af_ok = cap.set(cv.CAP_PROP_AUTOFOCUS, 0)
        focus_val = cap.get(cv.CAP_PROP_FOCUS)
        print(f"Autofocus lock: {'OK' if af_ok else 'NOT SUPPORTED'}"
              f"  focus value={focus_val:.0f}"
              f"  (set FOCUS_DISTANCE={focus_val:.0f} to skip settle delay next run)")
    if not cap.isOpened():
        print("Error, camera not opened")
        exit()
    actual_w = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera opened at {actual_w}x{actual_h}")

    # Downsample to 1080p for blob/grid processing; crops saved from full-res frame.
    PROC_W, PROC_H = 1920, 1080
    proc_scale = PROC_W / actual_w   # e.g. 0.5 for 4K, 1.0 for 1080p

    # Each preview window = 1/4 of screen (half width × half height).
    user32 = ctypes.windll.user32
    DISP_W = int(user32.GetSystemMetrics(0) * 0.75)
    DISP_H = int(user32.GetSystemMetrics(1) * 0.75)

    DISPLAY_EVERY_N_FRAMES = 1
    CROPS_DIR = os.path.join(os.path.dirname(__file__), "tile_crops")
    os.makedirs(CROPS_DIR, exist_ok=True)

    # --- Phase constants ---
    IDENTIFY        = "identify"        # Waiting to see and save the next unplaced tile
    WAIT_PLACEMENT  = "wait_placement"  # Tile saved — watching for it to land on the board
    WAIT_MEEPLE     = "wait_meeple"     # Tile placed — watching for meeple or skip
    INVALID_DISPLAY = "invalid_display" # Engine rejected — show warning, wait for removal

    # --- Meeple detection ---
    MEEPLE_BASELINE_SETTLE = 60   # Frames to roll baseline before locking (~2s); arm must clear
    MEEPLE_CONFIRM_FRAMES  = 30   # Consecutive frames with meeple to commit     (~1s at 30fps)
    MEEPLE_SKIP_FRAMES     = 30   # Consecutive frames with a new unplaced tile to skip (~1s)
    MEEPLE_SAFETY_FRAMES   = 600  # Hard safety timeout (~20s) in case neither fires

    meeple_frame_count      = 0
    meeple_detect_count     = 0
    meeple_skip_count       = 0
    candidate_meeple_dir    = None
    candidate_meeple_colour = None
    meeple_baseline         = None
    meeple_dbg              = None   # debug dict from detect_meeple; shown in top panels

    # --- Board growth / removal detection ---
    BOARD_GROWTH_THRESHOLD  = 1000   # Min pixel area increase to count as growth
    SAT_GROWTH_THRESHOLD    = 500    # Min new saturation pixels inside board (catches centre tiles)
    GROWTH_CONFIRM_FRAMES     = 30   # Consecutive frames of growth needed to commit    (~1s at 30fps)
    REMOVAL_CONFIRM_FRAMES    = 40   # Consecutive frames of shrinkage to confirm removal (~1.3s)
    PLACEMENT_COOLDOWN_FRAMES = 120  # Frames to ignore growth after identification (~4s); lets player move tile

    # --- Tile identification stability ---
    TILE_CONFIRM_FRAMES = 40   # Frames the unplaced tile must stay still before saving (~1.3s at 30fps)
    TILE_STABLE_DIST    = 20   # Max pixel movement still considered stable

    # --- State ---
    board_mask      = None
    prev_board_area = 0
    prev_sat_area   = 0
    phase           = IDENTIFY
    tile_saved      = False
    save_count      = 0
    frame_count     = 0
    set_board       = False
    last_placed_coord = None

    # Origin tile auto-detect + override window
    FIRST_TILE_CONFIRM_FRAMES = 80   # stable frames before auto-accepting origin (~2.7s at 30fps)
    first_tile_frame_count    = 0
    origin_id_pending = False  # True until second tile appears in frame
    origin_placement  = False  # True when engine comm is for origin tile

    growth_frame_count    = 0
    candidate_board_cnt   = None
    pre_growth_mask       = None
    removal_frame_count   = 0
    placement_cooldown    = 0   # counts down after identification; growth ignored until 0

    tile_frame_count      = 0
    candidate_tile_cnt    = None
    candidate_tile_center = None

    grid_tracker = None   # GridTracker instance, created when 'b' is pressed

    # Rollback state for the non-grid portions (board area, sat area, last coord).
    # Grid state rollback is handled by grid_tracker.snapshot() / restore().
    rollback_prev_board_area    = 0
    rollback_prev_sat_area      = 0
    rollback_last_coord         = None
    rollback_stable_board_mask  = None

    # Deferred rotation: match_rotation is run at the WAIT_MEEPLE settle boundary
    # (frame 60) so the arm has fully cleared before the crop is taken.
    rotation_pending         = False
    pending_family_id        = None
    pending_refitted_px      = None
    pending_validated_center = None

    # stable_board_mask: the committed board state — only updated on a confirmed
    # tile placement (with a valid grid slot).  Used as the diff baseline so that
    # arm/hand contamination (which inflates the live board_mask but never gets
    # committed) never corrupts pre_growth_mask or prev_board_area.
    stable_board_mask = None

    # Count consecutive non-growth frames; require 2 in a row before resetting
    # the growth counter, so one flickering frame doesn't undo 2+ growth frames.
    non_growth_count = 0

    global tile_checked, tile_id, tile_candidates, tile_id_override, grid_checked, grid_coord, cv_to_engine, game_response, meeple_placed, meeple_colour, meeple_direction, meeple_skip, meeple_handled, expected_meeple_colour, remaining_families, grid_origin, grid_tile_size, grid_angle, valid_meeple_sides, last_id_crop_path

    print("Place the first tile on the board — it will be detected automatically. Press 'b' to force-confirm.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Camera turned off, exiting")
            break
        frame = cv.flip(frame, -1)

        frame_count += 1
        key = cv.waitKey(1)
        if key == ord('q'):
            break
        if key == ord('b'):
            set_board = True

        if frame_count % DISPLAY_EVERY_N_FRAMES != 0:
            continue

        proc_frame = cv.resize(frame, (PROC_W, PROC_H))
        edges, density, blobs, sat_blobs = process_frame(proc_frame)
        valid  = find_contours(blobs)
        result = proc_frame.copy()

        # ── Board not set yet ─────────────────────────────────────────────────
        if board_mask is None:
            for cnt in valid:
                rect = cv.minAreaRect(cnt)
                box  = np.intp(cv.boxPoints(rect))
                cv.drawContours(result, [box], -1, (0, 255, 255), 2)

            if valid:
                first_tile_frame_count += 1
            else:
                first_tile_frame_count = max(0, first_tile_frame_count - 3)

            auto_trigger = first_tile_frame_count >= FIRST_TILE_CONFIRM_FRAMES
            status_text  = (f"Tile detected ({first_tile_frame_count}/{FIRST_TILE_CONFIRM_FRAMES})..."
                            if valid else "Waiting for first tile...")
            cv.putText(result, status_text, (10, 30),
                       cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            if (set_board or auto_trigger) and valid:
                first = max(valid, key=cv.contourArea)
                board_mask      = np.zeros(blobs.shape, dtype=np.uint8)
                cv.drawContours(board_mask, [first], -1, 255, -1)
                prev_board_area   = cv.contourArea(first)
                prev_sat_area     = cv.countNonZero(cv.bitwise_and(sat_blobs, board_mask))
                stable_board_mask = board_mask.copy()   # Committed baseline for diff
                set_board              = False
                first_tile_frame_count = 0

                origin       = mask_centroid(board_mask)
                grid_tracker = GridTracker(origin)

                # Seed tile size from the origin blob's minAreaRect dimensions.
                rect_f          = cv.minAreaRect(first)
                (_, _), (rw_f, rh_f), _ = rect_f
                grid_tracker.a  = float(max(rw_f, rh_f))
                grid_tracker.b  = 0.0
                grid_origin    = tuple(grid_tracker.origin_px)
                grid_tile_size = grid_tracker.tile_size_px
                grid_angle     = 0.0
                print(f"Board origin set at pixel ({origin[0]:.0f}, {origin[1]:.0f})"
                      f"  tile_size={grid_tracker.a:.0f}px  — identifying first tile.")

                # Identify tile family now so website can show candidates.
                # Rotation detection and engine communication are deferred by
                # ORIGIN_OVERRIDE_SECS so the user can override on the website first.
                crop = extract_tile_crop(frame, first, proc_scale,
                                        board_angle_deg=0.0,
                                        tile_size_px=grid_tracker.tile_size_px)
                path = os.path.join(CROPS_DIR, f"tile_{save_count:04d}.png")
                cv.imwrite(path, crop)
                last_id_crop_path = path
                print(f"Saved origin tile: {path}")
                save_count += 1

                results         = image_match.match_image(path, model, preprocess, embeddings,
                                                          bias=bias, game_embeddings=game_embeddings,
                                                          remaining_families=remaining_families)
                tile_id         = results[0][1]
                tile_candidates = [(s, rid) for s, rid in results]
                tile_checked    = True
                last_placed_coord = (0, 0)
                print("Origin tile identified — override window open.")
                for score, rid in results[:3]:
                    print(f"  {score:.4f}  {rid}")

                origin_id_pending = True

        # ── Board exists ──────────────────────────────────────────────────────
        else:
            old_board_mask            = board_mask.copy()
            # Always anchor board identification to the committed stable state.
            # The board never physically moves, so using stable_board_mask prevents
            # arm/hand blobs from stealing the board identity even when MORPH_CLOSE
            # merges them with the board blob.
            _classify_anchor = stable_board_mask if stable_board_mask is not None else board_mask
            new_board_cnt, unplaced   = classify_contours(valid, _classify_anchor, blobs.shape)

            # Drop any "unplaced" blobs larger than 3× the expected tile area.
            # Hands and arms produce large blobs that classify_contours correctly
            # excludes from the board, but they would otherwise be mistaken for
            # tiles in the IDENTIFY phase.
            if grid_tracker is not None and grid_tracker.tile_size_px is not None:
                max_unplaced_area = (grid_tracker.tile_size_px ** 2) * 3
                unplaced = [c for c in unplaced
                            if cv.contourArea(c) < max_unplaced_area]

            if new_board_cnt is not None:
                rect = cv.minAreaRect(new_board_cnt)
                box  = np.intp(cv.boxPoints(rect))
                cv.drawContours(result, [box], -1, (0, 0, 255), 2)
                (cx, cy), _, angle = rect
                cv.putText(result, f"BOARD [{phase}] {angle:.0f}deg",
                           (int(cx) - 40, int(cy) - 10),
                           cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                board_mask = np.zeros(blobs.shape, dtype=np.uint8)
                cv.drawContours(board_mask, [new_board_cnt], -1, 255, -1)

            # ── Origin override hint ──────────────────────────────────────────
            if origin_id_pending:
                cv.putText(result, "Override tile on website, then show next tile",
                           (10, 60), cv.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)

            # ── Phase 1: identify and save the next tile ──────────────────────
            if phase == IDENTIFY:
                if unplaced and not tile_saved:
                    cnt  = unplaced[0]
                    rect = cv.minAreaRect(cnt)
                    box  = np.intp(cv.boxPoints(rect))
                    (cx, cy), _, _ = rect

                    if candidate_tile_center is not None:
                        dist = np.hypot(cx - candidate_tile_center[0], cy - candidate_tile_center[1])
                        if dist > TILE_STABLE_DIST:
                            tile_frame_count = 0

                    candidate_tile_cnt    = cnt
                    candidate_tile_center = (cx, cy)
                    tile_frame_count     += 1

                    remaining = TILE_CONFIRM_FRAMES - tile_frame_count
                    colour    = (0, 255, 0) if remaining <= 0 else (0, 255, 255)
                    cv.drawContours(result, [box], -1, colour, 2)
                    cv.putText(result,
                               f"Identifying... ({remaining} frames)" if remaining > 0 else "Saving...",
                               (int(cx) - 40, int(cy) - 10),
                               cv.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1)

                    if tile_frame_count >= TILE_CONFIRM_FRAMES:
                        if origin_id_pending:
                            # Second tile is stable — commit origin tile now before identifying it.
                            family_id        = tile_id_override if tile_id_override is not None else tile_id
                            tile_id_override = None
                            board_angle      = np.degrees(np.arctan2(grid_tracker.b, grid_tracker.a))
                            placed_crop      = crop_placed_slot(
                                frame, tuple(grid_tracker.origin_px), grid_tracker.tile_size_px,
                                proc_scale, board_angle_deg=board_angle)
                            placed_path = os.path.join(CROPS_DIR, f"placed_{save_count - 1:04d}.png")
                            cv.imwrite(placed_path, placed_crop)
                            print(f"Rotation detection for origin tile (family {family_id}):")
                            tile_id, rot_conf = image_match.match_rotation(
                                placed_path, model, preprocess, embeddings, family_id,
                                bias=bias, game_embeddings=game_embeddings)
                            if rot_conf < ROT_CONF_THRESHOLD:
                                print(f"  Low rotation confidence ({rot_conf:.4f}) — using family ID")
                                tile_id = family_id
                            else:
                                print(f"  → {tile_id}  (conf={rot_conf:.4f})")
                            meeple_baseline   = proc_frame.copy()
                            grid_coord        = (0, 0)
                            grid_checked      = True
                            origin_id_pending = False
                            origin_placement  = True
                            print("Origin tile — communicating (0, 0).")
                            # Don't identify the second tile yet; engine comm fires at
                            # end of this frame, then auto-skip meeple, then loop back
                            # to IDENTIFY to handle the second tile normally.
                        else:
                            _ba = np.degrees(np.arctan2(grid_tracker.b, grid_tracker.a))
                            crop = extract_tile_crop(frame, candidate_tile_cnt, proc_scale,
                                                     board_angle_deg=_ba,
                                                     tile_size_px=grid_tracker.tile_size_px)
                            path = os.path.join(CROPS_DIR, f"tile_{save_count:04d}.png")
                            cv.imwrite(path, crop)
                            last_id_crop_path     = path
                            print(f"Saved tile: {path}")
                            save_count           += 1
                            tile_saved            = True
                            tile_frame_count      = 0
                            candidate_tile_cnt    = None
                            candidate_tile_center = None
                            phase                 = WAIT_PLACEMENT
                            placement_cooldown    = PLACEMENT_COOLDOWN_FRAMES
                            results         = image_match.match_image(path, model, preprocess, embeddings,
                                                                      bias=bias, game_embeddings=game_embeddings,
                                                                      remaining_families=remaining_families)
                            tile_id         = results[0][1]
                            tile_candidates = [(s, rid) for s, rid in results]
                            tile_checked    = True
                            print("Tile identified — waiting for it to be placed on the board.")
                            for score, rid in results[:3]:
                                print(f"  {score:.4f}  {rid}")

                elif candidate_tile_center is None:
                    tile_frame_count = 0

            # ── Phase 2: wait for board blob to grow ──────────────────────────
            elif phase == WAIT_PLACEMENT:
                if placement_cooldown > 0:
                    placement_cooldown -= 1
                    remaining_cd = placement_cooldown
                    cv.putText(result, f"Move tile to board ({remaining_cd} frames)...",
                               (10, 60), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
                elif new_board_cnt is not None:
                    current_board_area = cv.contourArea(new_board_cnt)
                    sat_in_board       = cv.countNonZero(cv.bitwise_and(sat_blobs, board_mask))
                    contour_growth     = current_board_area - prev_board_area > BOARD_GROWTH_THRESHOLD
                    sat_growth         = sat_in_board - prev_sat_area > SAT_GROWTH_THRESHOLD

                    if contour_growth or sat_growth:
                        non_growth_count = 0   # Reset grace-period counter on any growth
                        if growth_frame_count == 0:
                            # Always diff against the last COMMITTED board state, not the
                            # live board_mask which may already include arm contamination.
                            pre_growth_mask = stable_board_mask.copy() \
                                if stable_board_mask is not None else old_board_mask

                        growth_frame_count  += 1
                        candidate_board_cnt  = new_board_cnt
                        remaining = GROWTH_CONFIRM_FRAMES - growth_frame_count
                        cv.putText(result, f"Confirming placement... ({remaining} frames)",
                                   (10, 60), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

                        if growth_frame_count >= GROWTH_CONFIRM_FRAMES:
                            new_mask  = np.zeros(blobs.shape, dtype=np.uint8)
                            cv.drawContours(new_mask, [candidate_board_cnt], -1, 255, -1)
                            diff_mask = cv.subtract(new_mask, pre_growth_mask) \
                                        if pre_growth_mask is not None else new_mask

                            # Diff centroid — diagnostic only.  Slot detection uses
                            # sat_in_diff coverage (immune to MORPH_CLOSE halo bias).
                            diff_M  = cv.moments(diff_mask)
                            diff_cx = diff_M['m10'] / diff_M['m00'] if diff_M['m00'] > 200 else None
                            diff_cy = diff_M['m01'] / diff_M['m00'] if diff_M['m00'] > 200 else None

                            if diff_cx is not None:
                                print(f"  diff centroid px=({diff_cx:.0f},{diff_cy:.0f})  "
                                      f"origin=({grid_tracker.origin_px[0]:.0f},"
                                      f"{grid_tracker.origin_px[1]:.0f})")

                            # Primary slot detection: saturation-filtered coverage per slot.
                            # sat_in_diff = sat_blobs & diff_mask — keeps only real tile pixels.
                            # MORPH_CLOSE halos are empty table surface (zero saturation) so they
                            # score exactly 0, eliminating halo contamination entirely.
                            # Minimum slot coverage: 25% of tile bounding box area.
                            # Scales with tile_size so small transient blobs (arm/hand
                            # near an existing tile) don't trigger a false placement.
                            min_slot_cov = max(200, int(grid_tracker.tile_size_px ** 2 * 0.25))

                            sat_in_diff = cv.bitwise_and(sat_blobs, diff_mask)
                            best_slot, top_cov = grid_tracker.best_coverage_slot(sat_in_diff)
                            used_sat = True
                            if top_cov < min_slot_cov:
                                best_slot = None

                            # Fallback A: muted-colour tile — use raw diff coverage.
                            # MORPH_CLOSE halos contaminate this, but the actual tile area
                            # still dominates (~3-4× more coverage than any adjacent halo).
                            if best_slot is None:
                                best_slot, top_cov = grid_tracker.best_coverage_slot(diff_mask)
                                used_sat = False
                                if top_cov < min_slot_cov:
                                    best_slot = None

                            # Fallback B: enclosed centre tile — diff is near-empty because
                            # MORPH_CLOSE already filled the ring gap before placement.
                            if best_slot is None:
                                enclosed = grid_tracker.enclosed_slots()
                                if len(enclosed) == 1:
                                    best_slot = enclosed[0]
                                    top_cov   = 0
                                    print(f"  Grid: enclosed slot fallback → {best_slot}")

                            # Coverage margin check — reject if two slots score too similarly.
                            # A genuine placement dominates one slot clearly; arm/hand blobs
                            # spread coverage across multiple slots producing a low margin.
                            if best_slot is not None and top_cov > 0:
                                cov_mask = sat_in_diff if used_sat else diff_mask
                                second_cov = max(
                                    (grid_tracker.cell_coverage(cov_mask, *s)
                                     for s in grid_tracker.open_slots() if s != best_slot),
                                    default=0
                                )
                                margin = (top_cov - second_cov) / max(top_cov, 1)
                                label  = "sat" if used_sat else "diff"
                                if margin < 0.2:
                                    print(f"  Coverage ambiguous ({top_cov} vs "
                                          f"{second_cov} {label}-px, {margin:.0%} margin)"
                                          f" — retrying.")
                                    best_slot = None
                                else:
                                    print(f"  Grid: best slot → {best_slot} "
                                          f"({top_cov} {label}-px, {margin:.0%} margin)")

                            # Cross-validate: if the diff centroid isn't near any open slot
                            # the dominant blob is arm/hand, not the placed tile — reject.
                            if best_slot is not None and diff_cx is not None:
                                centroid_slot = grid_tracker.closest_slot(diff_cx, diff_cy)
                                if centroid_slot is None:
                                    print(f"  diff centroid ({diff_cx:.0f},{diff_cy:.0f}) not near "
                                          f"any slot — arm/hand blob, retrying.")
                                    best_slot = None
                                elif centroid_slot != best_slot:
                                    print(f"  NOTE: diff centroid suggests {centroid_slot}, "
                                          f"coverage chose {best_slot}")

                            # Always reset growth counters regardless of outcome.
                            growth_frame_count  = 0
                            non_growth_count    = 0
                            candidate_board_cnt = None
                            pre_growth_mask     = None

                            if best_slot is not None:
                                # Save rollback snapshot before committing.
                                grid_tracker.snapshot()
                                rollback_prev_board_area   = prev_board_area
                                rollback_prev_sat_area     = prev_sat_area
                                rollback_last_coord        = last_placed_coord
                                rollback_stable_board_mask = stable_board_mask.copy() \
                                    if stable_board_mask is not None else None

                                # Build a clean committed mask: previous stable state
                                # plus just the confirmed slot's bounding box.
                                # This avoids baking arm/hand pixels into the baseline.
                                slot_px = grid_tracker.grid_to_px(*best_slot)
                                ts      = int(grid_tracker.tile_size_px)
                                sm      = stable_board_mask.copy() \
                                          if stable_board_mask is not None \
                                          else np.zeros(blobs.shape, dtype=np.uint8)
                                x1s = max(0,              slot_px[0] - ts // 2)
                                y1s = max(0,              slot_px[1] - ts // 2)
                                x2s = min(blobs.shape[1], slot_px[0] + ts // 2)
                                y2s = min(blobs.shape[0], slot_px[1] + ts // 2)
                                sm[y1s:y2s, x1s:x2s] = 255
                                stable_board_mask = sm

                                # board_mask (already set from new_board_cnt on line 244)
                                # reflects the live state — keep it but base the growth
                                # baseline on the clean stable mask so arm pixels don't
                                # inflate prev_board_area.
                                prev_board_area = cv.countNonZero(stable_board_mask)
                                prev_sat_area   = cv.countNonZero(
                                    cv.bitwise_and(sat_blobs, stable_board_mask))
                                tile_saved           = False
                                phase                   = WAIT_MEEPLE
                                meeple_frame_count      = 0
                                meeple_detect_count     = 0
                                meeple_skip_count       = 0
                                candidate_meeple_dir    = None
                                candidate_meeple_colour = None
                                # Baseline captured NOW — tile just confirmed, arm has cleared,
                                # same moment the placed crop is taken for rotation detection.
                                meeple_baseline      = proc_frame.copy()

                                # Compute the actual observed tile centroid from saturation
                                # pixels — more accurate than the grid-predicted slot centre,
                                # and used both for the refit and as the placed-crop centre.
                                sc_x, sc_y = grid_tracker.slot_centroid(sat_in_diff, *best_slot)
                                sat_src = "sat_in_diff"
                                if sc_x is None:
                                    sc_x, sc_y = grid_tracker.slot_centroid(diff_mask, *best_slot)
                                    sat_src = "diff_mask" if sc_x is not None else "NONE"
                                use_cx = sc_x if sc_x is not None else diff_cx
                                use_cy = sc_y if sc_y is not None else diff_cy
                                centroid_src = sat_src if sc_x is not None else "diff_cx/cy (fallback)"
                                print(f"  [centroid] src={centroid_src}  "
                                      f"sc=({sc_x},{sc_y})  diff=({diff_cx},{diff_cy})  "
                                      f"use=({use_cx:.0f},{use_cy:.0f})"
                                      f"  slot_px={slot_px}  tile_size_px={grid_tracker.tile_size_px:.1f}")
                                grid_tracker.confirm_placement(best_slot, use_cx, use_cy)
                                grid_origin    = tuple(grid_tracker.origin_px)
                                grid_tile_size = grid_tracker.tile_size_px
                                grid_angle     = float(np.degrees(np.arctan2(grid_tracker.b, grid_tracker.a)))
                                last_placed_coord = best_slot
                                print(f"Tile placed at grid {best_slot} — ready for next tile.")

                                # Recompute slot centre using the refitted grid model.
                                # The pre-refit slot_px can be off before enough tiles exist
                                # for a reliable fit; post-refit is always at least as good.
                                refitted_px = grid_tracker.grid_to_px(*best_slot)

                                # Validate the observed centroid against the refitted prediction.
                                # Only accept it when within 1 tile — anything further is bad
                                # data (phantom diff blob, wrong mask, etc.).
                                validated_center = None
                                if use_cx is not None and use_cy is not None:
                                    dist = float(np.hypot(use_cx - refitted_px[0],
                                                          use_cy - refitted_px[1]))
                                    if dist <= grid_tracker.tile_size_px:
                                        validated_center = (use_cx, use_cy)
                                        print(f"  [crop] centroid accepted ({dist:.0f}px from grid)")
                                    else:
                                        print(f"  [crop] centroid rejected ({dist:.0f}px from grid)"
                                              f" — using refitted grid {refitted_px}")

                                # Defer rotation detection to WAIT_MEEPLE settle (frame 60)
                                # so the arm has cleared before the crop is taken.
                                pending_family_id        = tile_id_override if tile_id_override is not None else tile_id
                                tile_id_override         = None
                                pending_refitted_px      = refitted_px
                                pending_validated_center = validated_center
                                rotation_pending         = True
                                print(f"Placement confirmed at {best_slot} — "
                                      f"rotation detection deferred to settle period.")
                            else:
                                # Could not map growth to a grid slot — arm or hand likely.
                                # Do NOT update prev_board_area or stable_board_mask:
                                # keeping the old baseline means growth will re-trigger
                                # correctly once the arm leaves and the tile is visible.
                                print("Growth confirmed but no grid slot found "
                                      "(arm/hand likely) — will retry.")
                    else:
                        if growth_frame_count > 0:
                            non_growth_count += 1
                            if non_growth_count >= 30:
                                # Three consecutive non-growth frames: genuine transient.
                                growth_frame_count  = 0
                                non_growth_count    = 0
                                candidate_board_cnt = None
                                pre_growth_mask     = None
                                print("Growth was transient — ignored.")
                            # One non-growth frame: keep the counter (tile may be wobbling
                            # at the threshold) and wait for the next frame.

            # ── Phase 3: wait for meeple or player skip ───────────────────────
            elif phase == WAIT_MEEPLE:
                meeple_frame_count += 1

                slot_px = grid_tracker.grid_to_px(*last_placed_coord)

                # Draw crop region on result so position is always visible
                cx_m  = int(slot_px[0]);  cy_m = int(slot_px[1])
                half_m = int(grid_tracker.tile_size_px * CROP_HALF_FRAC)
                cv.rectangle(result,
                             (cx_m - half_m, cy_m - half_m),
                             (cx_m + half_m, cy_m + half_m),
                             (255, 0, 255), 2)

                if meeple_frame_count <= MEEPLE_BASELINE_SETTLE:
                    # Rolling baseline — keep updating until arm has fully cleared
                    meeple_baseline = proc_frame.copy()
                    meeple_dbg      = None

                    # At the settle boundary the arm has cleared (~2s) — take the
                    # placed-tile crop now and run rotation detection on a clean image.
                    if rotation_pending and meeple_frame_count == MEEPLE_BASELINE_SETTLE:
                        if pending_family_id is not None:
                            board_angle = np.degrees(np.arctan2(grid_tracker.b, grid_tracker.a))
                            placed_crop = crop_placed_slot(
                                frame, pending_refitted_px, grid_tracker.tile_size_px,
                                proc_scale, board_angle,
                                center_px=pending_validated_center)
                            placed_path = os.path.join(CROPS_DIR, f"placed_{save_count - 1:04d}.png")
                            cv.imwrite(placed_path, placed_crop)
                            print(f"Rotation detection for family {pending_family_id} (arm cleared):")
                            tile_id, rot_conf = image_match.match_rotation(
                                placed_path, model, preprocess, embeddings,
                                pending_family_id, bias=bias, game_embeddings=game_embeddings)
                            if rot_conf < ROT_CONF_THRESHOLD:
                                print(f"  Low rotation confidence ({rot_conf:.4f}) — using family ID")
                                tile_id = pending_family_id
                            else:
                                print(f"  -> {tile_id}  (conf={rot_conf:.4f})")
                        grid_coord   = last_placed_coord
                        grid_checked = True

                    cv.putText(result,
                               f"Settling baseline ({meeple_frame_count}/{MEEPLE_BASELINE_SETTLE})...",
                               (10, 60), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
                else:
                    cv.putText(result, "Waiting for meeple...",
                               (10, 60), cv.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)

                    colour, direction, meeple_dbg = detect_meeple(
                        proc_frame, slot_px, grid_tracker.tile_size_px,
                        baseline_frame=meeple_baseline,
                        expected_colour=expected_meeple_colour)

                    # Periodic terminal stats (every ~1s)
                    if meeple_frame_count % 30 == 0:
                        print(f"  [meeple dbg] frame={meeple_frame_count}  {meeple_dbg['stats']}")

                    if colour is not None:
                        if (direction == candidate_meeple_dir
                                and colour == candidate_meeple_colour):
                            meeple_detect_count += 1
                        else:
                            candidate_meeple_dir    = direction
                            candidate_meeple_colour = colour
                            meeple_detect_count     = 1
                        meeple_skip_count = 0
                        print(f"  [meeple] colour={colour}  dir={direction}  "
                              f"stable={meeple_detect_count}/{MEEPLE_CONFIRM_FRAMES}")
                        if meeple_detect_count >= MEEPLE_CONFIRM_FRAMES:
                            # Snap to nearest valid side when detection confidence is low.
                            # Confidence < 0.75 means the meeple centroid is less than
                            # 75% of the crop half-width from centre — common for "centre"
                            # readings on non-monastery tiles and edge meeples placed
                            # near the tile boundary.  High-confidence readings (player
                            # clearly on one side) are passed through unchanged so the
                            # engine can still catch genuinely invalid placements.
                            final_direction = direction
                            if valid_meeple_sides:
                                conf    = meeple_dbg.get("confidence", 1.0)
                                raw_dx  = meeple_dbg.get("dx", 0)
                                raw_dy  = meeple_dbg.get("dy", 0)
                                if conf < 0.75:
                                    snapped = _nearest_valid_side(raw_dx, raw_dy,
                                                                   valid_meeple_sides)
                                    if snapped != direction:
                                        print(f"  Meeple conf={conf:.2f} < 0.75 "
                                              f"→ snapped {direction} → {snapped}")
                                    final_direction = snapped
                            print(f"Meeple confirmed: {colour} at {final_direction}.")
                            meeple_colour    = colour
                            meeple_direction = final_direction
                            meeple_placed    = True
                    else:
                        meeple_detect_count     = 0
                        candidate_meeple_dir    = None
                        candidate_meeple_colour = None
                        # Exclude blobs that overlap committed tile positions —
                        # a placed tile separated from the main blob by a gap
                        # wider than MORPH_CLOSE appears as "unplaced" but is not.
                        truly_unplaced = []
                        for _cnt in unplaced:
                            if stable_board_mask is not None:
                                _m = np.zeros(blobs.shape, dtype=np.uint8)
                                cv.drawContours(_m, [_cnt], -1, 255, -1)
                                if cv.countNonZero(cv.bitwise_and(stable_board_mask, _m)) > 0:
                                    continue
                            truly_unplaced.append(_cnt)
                        if truly_unplaced:
                            meeple_skip_count += 1
                            if meeple_skip_count >= MEEPLE_SKIP_FRAMES:
                                print("Unplaced tile detected — skipping meeple.")
                                meeple_skip = True
                        else:
                            meeple_skip_count = 0

                # Safety timeout so the phase never hangs permanently
                if not meeple_placed and not meeple_skip and meeple_frame_count >= MEEPLE_SAFETY_FRAMES:
                    print("Meeple safety timeout — skipping.")
                    meeple_skip = True

                # Exit WAIT_MEEPLE when meeple/skip is confirmed by any means:
                #   - CV detected → meeple_placed / meeple_skip (bridge clears)
                #   - Website button → meeple_handled (bridge signals directly)
                if meeple_placed or meeple_skip or meeple_handled:
                    if not meeple_handled:
                        # CV path: wait for bridge to ACK and clear the flag
                        while meeple_placed or meeple_skip:
                            time.sleep(0.05)
                    meeple_handled          = False
                    phase                   = IDENTIFY
                    meeple_frame_count      = 0
                    meeple_detect_count     = 0
                    meeple_skip_count       = 0
                    candidate_meeple_dir    = None
                    candidate_meeple_colour = None
                    meeple_colour           = None
                    meeple_direction        = None
                    meeple_dbg              = None
                    print("Meeple phase done — ready for next tile.")

            # ── Phase 4: invalid placement — wait for tile removal ────────────
            elif phase == INVALID_DISPLAY:
                cv.putText(result, "INVALID — REMOVE TILE AND REPOSITION", (10, 60),
                           cv.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

                if new_board_cnt is not None:
                    current_board_area = cv.contourArea(new_board_cnt)
                    if current_board_area < rollback_prev_board_area + BOARD_GROWTH_THRESHOLD:
                        removal_frame_count += 1
                        remaining = REMOVAL_CONFIRM_FRAMES - removal_frame_count
                        cv.putText(result, f"Removing... ({remaining})", (10, 95),
                                   cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                        if removal_frame_count >= REMOVAL_CONFIRM_FRAMES:
                            prev_board_area     = current_board_area
                            prev_sat_area       = cv.countNonZero(cv.bitwise_and(sat_blobs, board_mask))
                            phase               = WAIT_PLACEMENT
                            removal_frame_count = 0
                            print("Tile removed — waiting for valid re-placement.")
                    else:
                        removal_frame_count = max(0, removal_frame_count - 1)

        # --- Grid dot overlay ---
        # Red dots on confirmed placements, yellow dots on open slots.
        # Drawn once tile_size_px is known (after first placement confirmed).
        if grid_tracker is not None and grid_tracker.tile_size_px is not None:
            for slot in grid_tracker.open_slots():
                pt = grid_tracker.grid_to_px(*slot)
                cv.circle(result, pt, 5, (0, 255, 255), -1)
            for coord in grid_tracker.placed_tiles:
                pt     = grid_tracker.grid_to_px(*coord)
                radius = 8 if coord == (0, 0) else 5
                cv.circle(result, pt, radius, (0, 0, 255), -1)
                cv.putText(result, f"{coord}", (pt[0] + 6, pt[1] + 4),
                           cv.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        if last_placed_coord is not None:
            cv.putText(result, f"Last placed: {last_placed_coord}", (10, 30),
                       cv.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # --- Engine communication ---
        # tile_checked: bridge/interface reads this and calls /pending; nothing to do here.

        # placement detected — signal bridge/interface and wait for their response
        if grid_checked:
            cv_to_engine = True
            grid_checked = False

            # Wait for bridge or cv_test_interface to write game_response
            while not game_response[0]:
                time.sleep(0.05)

            is_valid = game_response[1] == 1
            game_response = (False, 1)   # reset for next placement
            cv_to_engine  = False

            grid_coord = None

            if is_valid:
                tile_id = None
                if origin_placement:
                    # No meeple on the first tile — auto-skip and go straight back to IDENTIFY.
                    origin_placement = False
                    phase            = IDENTIFY
                    tile_saved       = False
                    meeple_skip      = True
                    print("Origin tile accepted — auto-skipping meeple, returning to IDENTIFY.")
                    while meeple_skip:
                        time.sleep(0.05)
                elif rotation_pending:
                    # Placement+rotation confirmed from WAIT_MEEPLE settle; arm already cleared —
                    # don't restart the meeple timer, just unlock meeple detection.
                    rotation_pending         = False
                    pending_family_id        = None
                    pending_refitted_px      = None
                    pending_validated_center = None
                    print("Placement accepted — meeple detection active.")
                else:
                    phase                   = WAIT_MEEPLE
                    meeple_frame_count      = 0
                    meeple_detect_count     = 0
                    meeple_skip_count       = 0
                    candidate_meeple_dir    = None
                    candidate_meeple_colour = None
                    print("Placement accepted — entering WAIT_MEEPLE.")
            else:
                grid_tracker.restore()
                prev_board_area          = rollback_prev_board_area
                prev_sat_area            = rollback_prev_sat_area
                last_placed_coord        = rollback_last_coord
                stable_board_mask        = rollback_stable_board_mask
                rotation_pending         = False
                pending_family_id        = None
                pending_refitted_px      = None
                pending_validated_center = None
                tile_saved          = True
                phase               = INVALID_DISPLAY
                removal_frame_count = 0
                print("Placement rejected. Remove tile and reposition.")

        panel_w, panel_h = DISP_W // 2, DISP_H // 2
        def to_bgr(img):
            return cv.cvtColor(img, cv.COLOR_GRAY2BGR) if len(img.shape) == 2 else img

        if phase == WAIT_MEEPLE and meeple_dbg is not None:
            # Replace top panels with meeple debug: baseline (left) and diff+contours (right)
            base_img = meeple_dbg["base_crop"]
            diff_img = meeple_dbg["diff_vis"]
            blank    = np.zeros((panel_h, panel_w, 3), dtype=np.uint8)
            p_base   = cv.resize(to_bgr(base_img), (panel_w, panel_h)) if base_img is not None else blank
            p_diff   = cv.resize(to_bgr(diff_img), (panel_w, panel_h))
            cv.putText(p_base, "Baseline", (10, 28), cv.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
            stats_short = meeple_dbg["stats"][:60]
            cv.putText(p_diff, f"Diff: {stats_short}", (10, 28), cv.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1)
            top = np.hstack([p_base, p_diff])
        else:
            top = np.hstack([cv.resize(to_bgr(edges),   (panel_w, panel_h)),
                             cv.resize(to_bgr(density), (panel_w, panel_h))])

        bottom = np.hstack([cv.resize(to_bgr(blobs),   (panel_w, panel_h)),
                            cv.resize(to_bgr(result),  (panel_w, panel_h))])
        cv.imshow("CV Debug", np.vstack([top, bottom]))
