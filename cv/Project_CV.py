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
import requests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cv import image_match
from cv.rotation_classifier import load_rotation_model, match_rotation_resnet
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
grid_c            = None         # y-step x-component (grid_tracker.c); None until 6-param fit
grid_d            = None         # y-step y-component (grid_tracker.d); None until 6-param fit
meeple_placed          = False   # CV sets when meeple detected; bridge clears after POST /meeple
meeple_colour          = None    # "red","blue","green","yellow","black"
meeple_direction       = None    # "up","down","left","right","centre"
meeple_skip            = False   # CV sets on timeout/skip; bridge clears after POST /meeple/skip
meeple_handled         = False   # Set by bridge when website button handled the meeple/skip
expected_meeple_colour = None    # Bridge sets to current player colour at start of each turn
remaining_families     = None    # Bridge updates after each placement; set of family base IDs still in bag
valid_meeple_sides     = None    # Bridge sets after placement: list of valid sides for the tile
last_id_crop_path      = None    # Path to the most recently saved identification crop (set by CV, read by bridge)
last_placed_crop_path  = None    # Path to the most recently saved placed-slot crop (set during WAIT_MEEPLE, read by bridge)
valid_placements       = None    # Bridge sets from /pending response: set of (gx, gy) coords valid for the current tile
tile_blob_area         = None    # Area of the origin tile blob in proc pixels; used as dynamic area filter reference
proj_clear_requested   = False   # CV sets when a tile is confirmed; bridge clears projection and resets this
placement_override     = None    # Set by /force_place API: (gx, gy) to use as confirmed slot on next growth event
invalid_slot_detected  = False   # CV sets when a confident placement lands on a non-valid slot; bridge drives projector
calib_dots_found       = False   # True once 4 green calibration dots are stably detected
calib_cam_points       = None    # List of 4 (x, y) camera proc-frame centroids (unordered)
calib_complete         = False   # Set True by bridge once H is computed/loaded; gates tile detection


# ── Calibration parameters ────────────────────────────────────────────────────
_CALIB_STABLE_FRAMES  = 15    # consecutive frames with 4 dots found before committing
_CALIB_TIMEOUT_FRAMES = 300   # frames before auto-skip (~10s); avoids blocking if dots undetected
# HSV range for projected green dots — wide enough for dim projector corners on table surface.
# H=35-85 covers yellow-green to cyan-green; S/V lower bounds kept low for dim projections.
_CALIB_GREEN_LO = (35, 40, 30)
_CALIB_GREEN_HI = (85, 255, 255)


def _detect_calib_dots(proc_frame):
    """Detect 4 projected green calibration dots in the camera frame.

    Uses a green-specific HSV filter rather than the general blob pipeline so
    table-surface edges and wood grain cannot compete with the projected dots.

    Returns a list of 4 (x, y) float centroids, or None if not found.
    Requirements: 4 blobs, similarly sized, forming a convex quadrilateral.
    """
    hsv = cv.cvtColor(proc_frame, cv.COLOR_BGR2HSV)
    # Projected green (BGR 0,255,0) → HSV H≈60 in OpenCV's 0-179 scale.
    # Range is generous to handle projector colour rendering on various surfaces.
    green = cv.inRange(hsv, _CALIB_GREEN_LO, _CALIB_GREEN_HI)
    # Small open to remove single-pixel noise without distorting blob shapes.
    k     = cv.getStructuringElement(cv.MORPH_ELLIPSE, (3, 3))
    green = cv.morphologyEx(green, cv.MORPH_OPEN, k)

    contours, _ = cv.findContours(green, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    if len(contours) < 4:
        return None

    top4  = sorted(contours, key=cv.contourArea, reverse=True)[:4]
    areas = [cv.contourArea(c) for c in top4]

    # Reject if any dot is tiny (< 200px² at proc-frame scale)
    if any(a < 200 for a in areas):
        return None

    # Reject if dots vary wildly in size (likely false positives mixed in)
    med = sorted(areas)[1]   # second-smallest of 4 — robust median-ish
    if not all(0.2 * med <= a <= 5.0 * med for a in areas):
        return None

    pts = []
    for cnt in top4:
        M = cv.moments(cnt)
        if M['m00'] < 1:
            return None
        pts.append((M['m10'] / M['m00'], M['m01'] / M['m00']))

    # Require the 4 centroids to form a convex quadrilateral.
    hull = cv.convexHull(np.array(pts, dtype=np.float32).reshape(-1, 1, 2))
    if len(hull) < 4:
        return None

    return pts


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

    if center_px is not None:
        dx, dy = center_px[0] - slot_px[0], center_px[1] - slot_px[1]
        src_label = f"centroid (offset {dx:+.0f},{dy:+.0f} PROC px from grid)"
    else:
        src_label = "grid"
    print(f"  [crop_placed_slot] using={src_label}  "
          f"grid_proc=({slot_px[0]:.0f},{slot_px[1]:.0f})  "
          f"crop_proc=({src[0]:.0f},{src[1]:.0f})  full-res=({cx:.0f},{cy:.0f})"
          f"  tile_size_px={tile_size_px:.1f}  side={side}"
          f"  ROI=({x1_roi},{y1_roi})->({x2_roi},{y2_roi})  angle={board_angle_deg:.1f}°")

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
    classifier         = image_match.load_classifier()
    if classifier:
        print("[CV] DINOv2 MLP classifier loaded — using for family identification")
    else:
        print("[CV] No classifier_head.pt found — falling back to CLIP embedding matching")

    try:
        rot_model = load_rotation_model()
    except FileNotFoundError:
        print("[CV] rotation_model.pth not found — falling back to embedding-based rotation")
        rot_model = None

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
    MEEPLE_BASELINE_SETTLE = 30   # Frames to roll baseline before locking (~2s); arm must clear
    MEEPLE_CONFIRM_FRAMES  = 20   # Consecutive frames with meeple to commit     (~1s at 30fps)
    MEEPLE_SKIP_FRAMES     = 15   # Consecutive frames with a new unplaced tile to skip (~1s)
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
    GROWTH_CONFIRM_FRAMES     = 40   # Consecutive frames of growth needed to commit    (~1s at 30fps)
    REMOVAL_CONFIRM_FRAMES    = 25   # Consecutive frames of shrinkage to confirm removal (~1.3s)
    PLACEMENT_COOLDOWN_FRAMES = 60  # Frames to ignore growth after identification (~4s); lets player move tile

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
    rotation_pending    = False
    pending_family_id   = None
    pending_refitted_px = None

    # stable_board_mask: the committed board state — only updated on a confirmed
    # tile placement (with a valid grid slot).  Used as the diff baseline so that
    # arm/hand contamination (which inflates the live board_mask but never gets
    # committed) never corrupts pre_growth_mask or prev_board_area.
    stable_board_mask = None

    # Count consecutive non-growth frames; require 2 in a row before resetting
    # the growth counter, so one flickering frame doesn't undo 2+ growth frames.
    non_growth_count = 0

    # Calibration state — local to cv_main_loop, reset on re-entry.
    _calib_stable       = 0   # consecutive frames with 4 green dots found
    _calib_total_frames = 0   # total frames spent waiting for calibration

    global tile_checked, tile_id, tile_candidates, tile_id_override, grid_checked, grid_coord, cv_to_engine, game_response, meeple_placed, meeple_colour, meeple_direction, meeple_skip, meeple_handled, expected_meeple_colour, remaining_families, grid_origin, grid_tile_size, grid_angle, grid_c, grid_d, valid_meeple_sides, last_id_crop_path, last_placed_crop_path, valid_placements, tile_blob_area, proj_clear_requested, placement_override, calib_dots_found, calib_cam_points, calib_complete, invalid_slot_detected

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
        if key == ord('c') and not calib_complete:
            calib_complete = True
            print("[CV] Calibration skipped by user — using linear projection fallback.")

        if frame_count % DISPLAY_EVERY_N_FRAMES != 0:
            continue

        proc_frame = cv.resize(frame, (PROC_W, PROC_H))
        edges, density, blobs, sat_blobs = process_frame(proc_frame)
        _area_min = int(tile_blob_area * 0.5) if tile_blob_area else None
        valid  = find_contours(blobs, area_min=_area_min)
        result = proc_frame.copy()

        # ── Board not set yet ─────────────────────────────────────────────────
        if board_mask is None:
            # ── Projector calibration (runs until calib_complete is True) ────
            # Detect 4 projected green dots → bridge computes homography → saved
            # to config.json so subsequent sessions load it and skip this phase.
            # Auto-skips after _CALIB_TIMEOUT_FRAMES with a warning.
            if not calib_complete:
                _calib_total_frames += 1
                if not calib_dots_found:
                    dots = _detect_calib_dots(proc_frame)
                    if dots is not None:
                        _calib_stable += 1
                        if _calib_stable >= _CALIB_STABLE_FRAMES:
                            calib_cam_points = [(round(x), round(y)) for x, y in dots]
                            calib_dots_found = True
                            print(f"[CV] Calibration dots found: {calib_cam_points}")
                    else:
                        _calib_stable = 0

                if _calib_total_frames > _CALIB_TIMEOUT_FRAMES:
                    calib_complete = True
                    reason = ("bridge did not complete after dots found"
                              if calib_dots_found else "no dots detected")
                    print(f"[CV] Calibration timeout ({reason})"
                          f" — using linear projection fallback.")
                else:
                    # Show green-filter debug on left, camera frame on right.
                    _hsv_dbg   = cv.cvtColor(proc_frame, cv.COLOR_BGR2HSV)
                    _green_dbg = cv.inRange(_hsv_dbg, _CALIB_GREEN_LO, _CALIB_GREEN_HI)
                    cv.putText(result,
                               f"Calibrating... ({_calib_stable}/{_CALIB_STABLE_FRAMES})"
                               f"  C=skip  ({_calib_total_frames}/{_CALIB_TIMEOUT_FRAMES})",
                               (10, 30), cv.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                    panel_w = DISP_W // 2
                    panel_h = DISP_H // 2
                    p_green  = cv.resize(cv.cvtColor(_green_dbg, cv.COLOR_GRAY2BGR),
                                         (panel_w, panel_h))
                    p_result = cv.resize(result, (panel_w, panel_h))
                    cv.imshow("CV Debug", np.hstack([p_green, p_result]))
                    continue   # block tile detection until calibration done

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
                tile_blob_area    = cv.contourArea(first)
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
                grid_tracker.c  = 0.0
                grid_tracker.d  = -grid_tracker.a
                grid_origin    = (int(grid_tracker.origin_px[0]), int(grid_tracker.origin_px[1]))
                grid_tile_size = grid_tracker.tile_size_px
                grid_angle     = 0.0
                grid_c         = grid_tracker.c
                grid_d         = grid_tracker.d
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

                if classifier is not None:
                    results = image_match.match_image_classifier(path, classifier,
                                                                  remaining_families=remaining_families)
                else:
                    results = image_match.match_image(path, model, preprocess, embeddings,
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
                            last_placed_crop_path = placed_path
                            print(f"Rotation detection for origin tile (family {family_id}):")
                            if rot_model is not None:
                                tile_id, rot_conf = match_rotation_resnet(
                                    placed_path, family_id, rot_model)
                            else:
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
                            if classifier is not None:
                                results = image_match.match_image_classifier(path, classifier,
                                                                              remaining_families=remaining_families)
                            else:
                                results = image_match.match_image(path, model, preprocess, embeddings,
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
                # ── Immediate manual placement override from frontend click ──
                # Fires right away without needing growth detection.
                if placement_override is not None and grid_tracker is not None:
                    _ov_slot       = placement_override
                    placement_override = None
                    print(f"  Grid: manual placement override → {_ov_slot} (immediate)")
                    grid_tracker.snapshot()
                    rollback_prev_board_area   = prev_board_area
                    rollback_prev_sat_area     = prev_sat_area
                    rollback_last_coord        = last_placed_coord
                    rollback_stable_board_mask = stable_board_mask.copy() \
                        if stable_board_mask is not None else None
                    slot_px = grid_tracker.grid_to_px(*_ov_slot)
                    # Use current board contour as new stable mask.
                    if new_board_cnt is not None:
                        _ov_mask = np.zeros(blobs.shape, dtype=np.uint8)
                        cv.drawContours(_ov_mask, [new_board_cnt], -1, 255, -1)
                    elif stable_board_mask is not None:
                        _ov_mask = stable_board_mask.copy()
                    else:
                        _ov_mask = np.zeros(blobs.shape, dtype=np.uint8)
                    stable_board_mask  = _ov_mask.copy()
                    prev_board_area    = cv.countNonZero(_ov_mask)
                    prev_sat_area      = cv.countNonZero(
                        cv.bitwise_and(sat_blobs, _ov_mask))
                    tile_saved            = False
                    proj_clear_requested  = True
                    phase                 = WAIT_MEEPLE
                    meeple_frame_count    = 0
                    meeple_detect_count   = 0
                    meeple_skip_count     = 0
                    candidate_meeple_dir    = None
                    candidate_meeple_colour = None
                    meeple_baseline       = proc_frame.copy()
                    growth_frame_count    = 0
                    non_growth_count      = 0
                    candidate_board_cnt   = None
                    pre_growth_mask       = None
                    # Use observed sat-blob centroid within the slot bounding box
                    # if available and close enough; otherwise fall back to the
                    # grid-predicted centre so the refit gets real data rather than
                    # the circular predicted position.
                    _obs_cx, _obs_cy = grid_tracker.slot_centroid(sat_blobs, *_ov_slot)
                    if _obs_cx is not None:
                        _obs_dist = float(np.hypot(_obs_cx - slot_px[0],
                                                    _obs_cy - slot_px[1]))
                        if _obs_dist < grid_tracker.tile_size_px * 0.35:
                            refit_cx, refit_cy = _obs_cx, _obs_cy
                            print(f"  [override-centroid] ({_obs_cx:.0f},{_obs_cy:.0f})"
                                  f"  Δ={_obs_dist:.0f}px → using observed")
                        else:
                            refit_cx, refit_cy = float(slot_px[0]), float(slot_px[1])
                            print(f"  [override-centroid] ({_obs_cx:.0f},{_obs_cy:.0f})"
                                  f"  Δ={_obs_dist:.0f}px — too far, using predicted")
                    else:
                        refit_cx, refit_cy = float(slot_px[0]), float(slot_px[1])
                        print(f"  [override-centroid] no sat blob — using predicted"
                              f"  ({slot_px[0]:.0f},{slot_px[1]:.0f})")
                    grid_tracker.confirm_placement(_ov_slot, refit_cx, refit_cy, weight=10.0)
                    grid_origin    = (int(grid_tracker.origin_px[0]),
                                      int(grid_tracker.origin_px[1]))
                    grid_tile_size = grid_tracker.tile_size_px
                    grid_angle     = float(np.degrees(
                        np.arctan2(grid_tracker.b, grid_tracker.a)))
                    grid_c         = grid_tracker.c
                    grid_d         = grid_tracker.d
                    last_placed_coord = _ov_slot
                    refitted_px = grid_tracker.grid_to_px(*_ov_slot)
                    print(f"Tile placed at grid {_ov_slot} (manual override).")
                    _oslots = grid_tracker.open_slots()
                    print(f"  [open-slots] origin=({grid_tracker.origin_px[0]:.0f},"
                          f"{grid_tracker.origin_px[1]:.0f})"
                          f"  a={grid_tracker.a:.2f}  b={grid_tracker.b:.2f}"
                          f"  tile_size={grid_tracker.tile_size_px:.1f}px"
                          f"  angle={grid_angle:.1f}°")
                    for _s in sorted(_oslots):
                        _pt = grid_tracker.grid_to_px(*_s)
                        print(f"  [open-slots]   {_s} → PROC px "
                              f"({_pt[0]:.0f},{_pt[1]:.0f})")
                    pending_family_id        = (tile_id_override
                                                if tile_id_override is not None
                                                else tile_id)
                    tile_id_override    = None
                    pending_refitted_px = refitted_px
                    rotation_pending    = True
                    print(f"Placement confirmed at {_ov_slot} — "
                          f"rotation detection deferred to settle period.")
                elif placement_cooldown > 0:
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
                        # Guard against board-boundary and hand-contaminated blobs
                        # corrupting new_mask/prev_board_area. Only update candidate
                        # if the contour is within 3× the committed tile cluster footprint.
                        _max_cnt_area = (cv.countNonZero(stable_board_mask) * 3
                                         if stable_board_mask is not None else float('inf'))
                        if cv.contourArea(new_board_cnt) < _max_cnt_area or candidate_board_cnt is None:
                            candidate_board_cnt = new_board_cnt
                        remaining = GROWTH_CONFIRM_FRAMES - growth_frame_count
                        cv.putText(result, f"Confirming placement... ({remaining} frames)",
                                   (10, 60), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

                        if growth_frame_count >= GROWTH_CONFIRM_FRAMES:
                            # Diagnostic: log stable_board_mask state so state corruption is visible.
                            if grid_tracker is not None and stable_board_mask is not None:
                                sm_px = cv.countNonZero(stable_board_mask)
                                print(f"  [diag] stable_board_mask={sm_px}px  "
                                      f"placed_tiles={len(grid_tracker.placed_tiles)}  "
                                      f"open_slots={len(list(grid_tracker.open_slots()))}")

                            new_mask  = np.zeros(blobs.shape, dtype=np.uint8)
                            cv.drawContours(new_mask, [candidate_board_cnt], -1, 255, -1)
                            diff_mask = cv.subtract(new_mask, pre_growth_mask) \
                                        if pre_growth_mask is not None else new_mask

                            # Clip diff to the expected board region: open slots + existing
                            # board area.  When the player's arm extends away from the board
                            # during placement, the filled candidate_board_cnt can cover a
                            # huge interior region (arm-to-tile polygon fill) that contaminates
                            # slot coverage scores — particularly spreading coverage into
                            # intermediate open slots and failing the margin check.
                            if grid_tracker is not None:
                                _rgn = np.zeros_like(diff_mask)
                                _r   = int(grid_tracker.tile_size_px)
                                for _slot in grid_tracker.open_slots():
                                    _sx, _sy = grid_tracker.grid_to_px(*_slot)
                                    _sx, _sy = int(_sx), int(_sy)
                                    _rgn[max(0, _sy-_r):min(_rgn.shape[0], _sy+_r),
                                         max(0, _sx-_r):min(_rgn.shape[1], _sx+_r)] = 255
                                if stable_board_mask is not None:
                                    _rgn = cv.bitwise_or(_rgn, stable_board_mask)
                                _clipped = cv.bitwise_and(diff_mask, _rgn)
                                if cv.countNonZero(_clipped) > 0:
                                    diff_mask = _clipped

                            diff_total = cv.countNonZero(diff_mask)
                            new_total  = cv.countNonZero(new_mask)
                            pre_total  = cv.countNonZero(pre_growth_mask) if pre_growth_mask is not None else 0
                            print(f"  [diag] new_mask={new_total}px  pre_growth={pre_total}px  "
                                  f"diff={diff_total}px")

                            # Diff centroid — diagnostic only.  Slot detection uses
                            # sat_in_diff coverage (immune to MORPH_CLOSE halo bias).
                            diff_M  = cv.moments(diff_mask)
                            diff_cx = diff_M['m10'] / diff_M['m00'] if diff_M['m00'] > 200 else None
                            diff_cy = diff_M['m01'] / diff_M['m00'] if diff_M['m00'] > 200 else None

                            if diff_cx is not None:
                                print(f"  diff centroid px=({diff_cx:.0f},{diff_cy:.0f})  "
                                      f"origin=({grid_tracker.origin_px[0]:.0f},"
                                      f"{grid_tracker.origin_px[1]:.0f})")

                            # Print every open slot with its camera pixel position so the
                            # terminal output can be compared against the camera feed.
                            print(f"  [open-slot-px] {len(list(grid_tracker.open_slots()))} open slots:")
                            for _sl in sorted(grid_tracker.open_slots()):
                                _slx, _sly = grid_tracker.grid_to_px(*_sl)
                                _mark = " ← VALID" if (valid_placements and _sl in valid_placements) else ""
                                print(f"    {_sl} → cam=({_slx:.0f},{_sly:.0f}){_mark}")

                            # Primary slot detection: saturation-filtered coverage per slot.
                            # sat_in_diff = sat_blobs & diff_mask — keeps only real tile pixels.
                            # MORPH_CLOSE halos are empty table surface (zero saturation) so they
                            # score exactly 0, eliminating halo contamination entirely.
                            # Minimum slot coverage: 15% of tile bounding box area.
                            # Lowered from 25% to tolerate partial occlusion (hand) or
                            # projector-magenta filter chewing into the placed tile blob.
                            # The 20% margin check below still guards against false
                            # positives from arm/hand blobs spreading across slots.
                            min_slot_cov = max(200, int(grid_tracker.tile_size_px ** 2 * 0.15))

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
                                    # Per-slot scores for diagnosis
                                    if diff_cx is not None:
                                        print(f"  [slot-scores] diff_centroid=({diff_cx:.0f},{diff_cy:.0f})")
                                    for _dbg_s in sorted(grid_tracker.open_slots()):
                                        _dbg_sx, _dbg_sy = grid_tracker.grid_to_px(*_dbg_s)
                                        _dbg_sat  = grid_tracker.cell_coverage(sat_in_diff, *_dbg_s)
                                        _dbg_diff = grid_tracker.cell_coverage(diff_mask, *_dbg_s)
                                        _dbg_dist = (float(np.hypot(_dbg_sx - diff_cx, _dbg_sy - diff_cy))
                                                     if diff_cx is not None else -1)
                                        print(f"    slot {_dbg_s}: sat={_dbg_sat}  diff={_dbg_diff}"
                                              f"  cam=({_dbg_sx:.0f},{_dbg_sy:.0f})"
                                              f"  dist={_dbg_dist:.0f}px")
                                    best_slot = None
                                else:
                                    print(f"  Grid: best slot → {best_slot} "
                                          f"({top_cov} {label}-px, {margin:.0%} margin)")

                            # Reject any slot not in the engine's valid positions.
                            # When the detection was confident (margin >= 0.2 passed above),
                            # treat this as a definitive invalid placement rather than an
                            # arm/hand transient — notify immediately via INVALID_DISPLAY.
                            _confident_invalid = False
                            if best_slot is not None and valid_placements is not None \
                                    and len(valid_placements) > 0:
                                if best_slot not in valid_placements:
                                    print(f"  Grid: slot {best_slot} detected confidently but "
                                          f"is NOT a valid position — invalid placement.")
                                    _confident_invalid     = True
                                    invalid_slot_detected  = True
                                    rollback_prev_board_area   = prev_board_area
                                    rollback_prev_sat_area     = prev_sat_area
                                    rollback_last_coord        = last_placed_coord
                                    rollback_stable_board_mask = (
                                        stable_board_mask.copy()
                                        if stable_board_mask is not None else None)
                                    phase               = INVALID_DISPLAY
                                    removal_frame_count = 0
                                    best_slot = None

                            # Final fallback: manual placement override from frontend click.
                            # Used when auto-detection is ambiguous or the slot was rejected.
                            _slot_is_manual = False
                            if best_slot is None and placement_override is not None:
                                _ov = placement_override
                                placement_override = None
                                if valid_placements is None or _ov in valid_placements:
                                    best_slot = _ov
                                    top_cov   = 0
                                    used_sat  = False
                                    _slot_is_manual = True
                                    print(f"  Grid: manual placement override → {best_slot}")
                                else:
                                    print(f"  Grid: manual override {_ov} rejected — "
                                          f"not in valid positions")

                            # Diagnostic only: log if the raw diff centroid and coverage
                            # disagree, but do NOT reject on that basis.
                            # The raw centroid is unreliable as a gate because:
                            #   • MORPH_CLOSE fill drags it toward the board centre
                            #   • The player's arm in frame biases it toward the edge
                            # Arm/hand protection is provided by min_slot_cov (25% tile area
                            # of high-sat pixels required) + the margin check (>20%).
                            if best_slot is not None and diff_cx is not None:
                                centroid_slot = grid_tracker.closest_slot(diff_cx, diff_cy)
                                if centroid_slot is not None and centroid_slot != best_slot:
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

                                # Use the actual blob contour fill as the committed baseline.
                                # Padded rectangles were used previously but don't match the
                                # MORPH_CLOSE blob shape, leaving large off-centre regions in
                                # the next diff (spurious pixels that bias the centroid and
                                # coverage scores away from the actual new tile).  Using
                                # new_mask directly means next turn's diff = next_blob -
                                # this_blob, which cleanly shows only genuinely new pixels
                                # regardless of how MORPH_CLOSE fills gaps between tiles.
                                slot_px           = grid_tracker.grid_to_px(*best_slot)
                                stable_board_mask = new_mask.copy()

                                # Use new_mask (current board contour fill) as the growth
                                # baseline — it matches the same measurement used each frame,
                                # so the margin stays consistent regardless of how much padding
                                # stable_board_mask adds for diff accuracy.
                                prev_board_area = cv.countNonZero(new_mask)
                                prev_sat_area   = cv.countNonZero(
                                    cv.bitwise_and(sat_blobs, new_mask))
                                tile_saved           = False
                                proj_clear_requested = True   # ask bridge to kill projection now so crop is clean
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

                                refit_cx = use_cx if use_cx is not None else float(slot_px[0])
                                refit_cy = use_cy if use_cy is not None else float(slot_px[1])
                                _refit_weight = 10.0 if _slot_is_manual else 1.0
                                grid_tracker.confirm_placement(best_slot, refit_cx, refit_cy,
                                                               weight=_refit_weight)
                                grid_origin    = (int(grid_tracker.origin_px[0]), int(grid_tracker.origin_px[1]))
                                grid_tile_size = grid_tracker.tile_size_px
                                grid_angle     = float(np.degrees(np.arctan2(grid_tracker.b, grid_tracker.a)))
                                grid_c         = grid_tracker.c
                                grid_d         = grid_tracker.d
                                last_placed_coord = best_slot
                                print(f"Tile placed at grid {best_slot} — ready for next tile.")
                                _oslots = grid_tracker.open_slots()
                                print(f"  [open-slots] origin=({grid_tracker.origin_px[0]:.0f},{grid_tracker.origin_px[1]:.0f})"
                                      f"  a={grid_tracker.a:.2f}  b={grid_tracker.b:.2f}"
                                      f"  tile_size={grid_tracker.tile_size_px:.1f}px  angle={grid_angle:.1f}°")
                                for _s in sorted(_oslots):
                                    _pt = grid_tracker.grid_to_px(*_s)
                                    print(f"  [open-slots]   {_s} → PROC px ({_pt[0]},{_pt[1]})")

                                # Store post-refit grid prediction as the initial crop centre.
                                # The post-settle measurement at frame 30 will update this to
                                # the real measured centroid once the arm has cleared and
                                # the projection is off.
                                pending_refitted_px = grid_tracker.grid_to_px(*best_slot)
                                pending_family_id   = tile_id_override if tile_id_override is not None else tile_id
                                tile_id_override    = None
                                rotation_pending    = True
                                print(f"Placement confirmed at {best_slot} — "
                                      f"rotation detection deferred to settle period.")
                            elif _confident_invalid:
                                pass  # Already entered INVALID_DISPLAY above.
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

                    if meeple_frame_count == MEEPLE_BASELINE_SETTLE:
                        # ── Step 1: measure real tile centre FIRST ────────────────
                        # Projection is off, arm has cleared — cleanest centroid we
                        # can get.  Update pending_refitted_px so the rotation crop
                        # and ongoing meeple box are centred on the actual tile.
                        if last_placed_coord is not None:
                            _exp_px  = grid_tracker.grid_to_px(*last_placed_coord)
                            _half    = max(1, int(grid_tracker.tile_size_px * 0.42))
                            _rx1 = max(_exp_px[0] - _half, 0)
                            _ry1 = max(_exp_px[1] - _half, 0)
                            _rx2 = min(_exp_px[0] + _half, sat_blobs.shape[1])
                            _ry2 = min(_exp_px[1] + _half, sat_blobs.shape[0])
                            if _rx2 > _rx1 and _ry2 > _ry1:
                                _roi_M = cv.moments(sat_blobs[_ry1:_ry2, _rx1:_rx2])
                                if _roi_M['m00'] > 300:
                                    _rcx = _rx1 + _roi_M['m10'] / _roi_M['m00']
                                    _rcy = _ry1 + _roi_M['m01'] / _roi_M['m00']
                                    _delta = float(np.hypot(_rcx - _exp_px[0], _rcy - _exp_px[1]))
                                    if _delta < grid_tracker.tile_size_px * 0.50:
                                        grid_tracker.update_centroid(last_placed_coord, _rcx, _rcy)
                                        grid_origin    = (int(grid_tracker.origin_px[0]),
                                                          int(grid_tracker.origin_px[1]))
                                        grid_tile_size = grid_tracker.tile_size_px
                                        grid_angle     = float(np.degrees(
                                            np.arctan2(grid_tracker.b, grid_tracker.a)))
                                        grid_c         = grid_tracker.c
                                        grid_d         = grid_tracker.d
                                        pending_refitted_px = (int(round(_rcx)), int(round(_rcy)))
                                        print(f"  [refit] Post-settle {last_placed_coord}: "
                                              f"ideal=({_exp_px[0]},{_exp_px[1]}) "
                                              f"actual=({_rcx:.0f},{_rcy:.0f}) "
                                              f"Δ=({_rcx-_exp_px[0]:+.1f},{_rcy-_exp_px[1]:+.1f})"
                                              f" — crop centre updated")
                                    else:
                                        print(f"  [refit] Post-settle {last_placed_coord}: "
                                              f"centroid {_delta:.0f}px from grid — skipped, "
                                              f"using grid prediction for crop")

                        # ── Step 2: rotation crop, centred on real tile position ──
                        if rotation_pending and pending_family_id is not None:
                            board_angle = np.degrees(np.arctan2(grid_tracker.b, grid_tracker.a))
                            placed_crop = crop_placed_slot(
                                frame, pending_refitted_px, grid_tracker.tile_size_px,
                                proc_scale, board_angle,
                                center_px=None)
                            placed_path = os.path.join(CROPS_DIR, f"placed_{save_count - 1:04d}.png")
                            cv.imwrite(placed_path, placed_crop)
                            last_placed_crop_path = placed_path
                            print(f"Rotation detection for family {pending_family_id} (arm cleared):")
                            if rot_model is not None:
                                tile_id, rot_conf = match_rotation_resnet(
                                    placed_path, pending_family_id, rot_model)
                            else:
                                tile_id, rot_conf = image_match.match_rotation(
                                    placed_path, model, preprocess, embeddings,
                                    pending_family_id, bias=bias, game_embeddings=game_embeddings)
                            if rot_conf < ROT_CONF_THRESHOLD:
                                print(f"  Low rotation confidence ({rot_conf:.4f}) — using family ID")
                                tile_id = pending_family_id
                            else:
                                print(f"  -> {tile_id}  (conf={rot_conf:.4f})")
                        if rotation_pending:
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
                        meeple_detect_count = max(0, meeple_detect_count - 1)
                        if meeple_detect_count == 0:
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
                            prev_board_area       = current_board_area
                            prev_sat_area         = cv.countNonZero(cv.bitwise_and(sat_blobs, board_mask))
                            phase                 = WAIT_PLACEMENT
                            removal_frame_count   = 0
                            invalid_slot_detected = False
                            print("Tile removed — waiting for valid re-placement.")
                    else:
                        removal_frame_count = max(0, removal_frame_count - 1)

        # --- Grid dot overlay ---
        # Red dots   = grid model prediction (grid_to_px)
        # Yellow dots = open slot predictions
        # Blue dots  = actual observed centroid fed to the refit
        # A line connects red→blue so the fit error is immediately visible.
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
                # Observed centroid (bright blue) — shows what the camera actually measured
                if coord in grid_tracker.tile_centroids:
                    obs_x, obs_y = grid_tracker.tile_centroids[coord]
                    obs_pt = (int(round(obs_x)), int(round(obs_y)))
                    cv.line(result, pt, obs_pt, (255, 80, 0), 1)
                    cv.circle(result, obs_pt, 4, (255, 0, 0), -1)

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
                    rotation_pending    = False
                    pending_family_id   = None
                    pending_refitted_px = None
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
                rotation_pending    = False
                pending_family_id   = None
                pending_refitted_px = None
                tile_saved          = True
                phase               = INVALID_DISPLAY
                removal_frame_count = 0
                print("Placement rejected. Remove tile and reposition.")
                requests.post("http://127.0.0.1:1234/notify", json={"type": "cv_invalid_placement"}, timeout=1)

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
