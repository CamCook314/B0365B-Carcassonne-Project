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
import time

# --- Communication globals ---
# Written by CV, read by the engine (or cv_test_interface.py during development).
tile_checked  = False        # True once a tile has been identified
tile_id       = None         # Bare tile ID string, e.g. "ID43"
grid_checked  = False        # True once placement coordinates are ready
grid_coord    = None         # (gx, gy) tuple in CV coordinate space
cv_to_engine  = False        # Raised when CV has a placement ready for the engine
game_response = (False, 1)   # (responded_bool, result_int); 1 = valid, 0 = invalid


def crop_placed_slot(frame, slot_px, tile_size_px, proc_scale, board_angle_deg,
                     center_px=None, padding=0.85):
    """Crop and deskew the placed tile at the confirmed grid slot.

    slot_px and center_px are in processed-frame (1920×1080) coordinates.
    center_px is the observed saturation centroid; falls back to slot_px (grid
    prediction) when not available.  Scales up to full-res, deskews by the
    board rotation angle, and returns a tight square crop for match_rotation().
    padding < 1.0 intentionally clips tile edges to exclude table and adjacent tiles.
    """
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

    cx_roi = cx - x1_roi
    cy_roi = cy - y1_roi
    M = cv.getRotationMatrix2D((cx_roi, cy_roi), board_angle_deg, 1.0)
    rotated = cv.warpAffine(roi, M, (roi.shape[1], roi.shape[0]),
                            flags=cv.INTER_LINEAR)

    x1 = max(int(cx_roi) - side // 2, 0)
    y1 = max(int(cy_roi) - side // 2, 0)
    x2 = min(int(cx_roi) + side // 2, rotated.shape[1])
    y2 = min(int(cy_roi) + side // 2, rotated.shape[0])
    return rotated[y1:y2, x1:x2]


def extract_tile_crop(frame, contour, proc_scale, padding=0.85):
    """Return a rotation-corrected square crop of the tile from the full-res frame.

    Uses minAreaRect to find the tile's true rotation, rotates a ROI around the
    tile to deskew it, then crops a tight square — minimising table in corners.
    padding: multiplier on the tile side length (1.02 = ~2% border each side).
    """
    rect = cv.minAreaRect(contour)
    (cx, cy), (rw, rh), angle = rect

    # Scale to full-res coords
    cx  = cx / proc_scale;  cy  = cy / proc_scale
    rw  = rw / proc_scale;  rh  = rh / proc_scale

    # Normalise angle: minAreaRect picks an arbitrary axis for square-ish rects.
    # Ensure we always rotate by the long-side angle so crops are consistently oriented.
    if rw < rh:
        angle += 90

    side = int(max(rw, rh) * padding)

    # Extract a ROI large enough to contain the rotated tile
    margin = int(side * 0.8)
    x1_roi = max(int(cx) - side - margin, 0)
    y1_roi = max(int(cy) - side - margin, 0)
    x2_roi = min(int(cx) + side + margin, frame.shape[1])
    y2_roi = min(int(cy) + side + margin, frame.shape[0])
    roi    = frame[y1_roi:y2_roi, x1_roi:x2_roi]

    # Tile centre in ROI space
    cx_roi = cx - x1_roi
    cy_roi = cy - y1_roi

    # Deskew: rotate ROI so tile sides are axis-aligned
    M       = cv.getRotationMatrix2D((cx_roi, cy_roi), angle, 1.0)
    rotated = cv.warpAffine(roi, M, (roi.shape[1], roi.shape[0]),
                            flags=cv.INTER_LINEAR)

    # Crop tight square centred on tile
    x1 = max(int(cx_roi) - side // 2, 0)
    y1 = max(int(cy_roi) - side // 2, 0)
    x2 = min(int(cx_roi) + side // 2, rotated.shape[1])
    y2 = min(int(cy_roi) + side // 2, rotated.shape[0])
    return rotated[y1:y2, x1:x2]


def cv_main_loop():

    model, preprocess = image_match.model_setup()
    embeddings        = image_match.load_embeddings()
    bias              = image_match.load_bias()

    cap = cv.VideoCapture(0)
    cap.set(cv.CAP_PROP_FRAME_WIDTH,  3840)
    cap.set(cv.CAP_PROP_FRAME_HEIGHT, 2160)
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

    DISPLAY_EVERY_N_FRAMES = 10
    CROPS_DIR = os.path.join(os.path.dirname(__file__), "tile_crops")
    os.makedirs(CROPS_DIR, exist_ok=True)

    # --- Phase constants ---
    IDENTIFY        = "identify"        # Waiting to see and save the next unplaced tile
    WAIT_PLACEMENT  = "wait_placement"  # Tile saved — watching for it to land on the board
    INVALID_DISPLAY = "invalid_display" # Engine rejected — show warning, wait for removal

    # --- Board growth / removal detection ---
    BOARD_GROWTH_THRESHOLD = 1000   # Min pixel area increase to count as growth
    SAT_GROWTH_THRESHOLD   = 500    # Min new saturation pixels inside board (catches centre tiles)
    GROWTH_CONFIRM_FRAMES  = 5      # Consecutive frames of growth needed to commit
    REMOVAL_CONFIRM_FRAMES = 4      # Consecutive frames of shrinkage needed to confirm removal

    # --- Tile identification stability ---
    TILE_CONFIRM_FRAMES = 4    # Frames the unplaced tile must stay still before saving
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

    growth_frame_count  = 0
    candidate_board_cnt = None
    pre_growth_mask     = None
    removal_frame_count = 0

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

    # stable_board_mask: the committed board state — only updated on a confirmed
    # tile placement (with a valid grid slot).  Used as the diff baseline so that
    # arm/hand contamination (which inflates the live board_mask but never gets
    # committed) never corrupts pre_growth_mask or prev_board_area.
    stable_board_mask = None

    # Count consecutive non-growth frames; require 2 in a row before resetting
    # the growth counter, so one flickering frame doesn't undo 2+ growth frames.
    non_growth_count = 0

    global tile_checked, tile_id, grid_checked, grid_coord, cv_to_engine, game_response

    print("Place the first tile then click any OpenCV window and press 'b'.")

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
            cv.putText(result, "Press 'b' to set board origin", (10, 30),
                       cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            if set_board and valid:
                first = max(valid, key=cv.contourArea)
                board_mask      = np.zeros(blobs.shape, dtype=np.uint8)
                cv.drawContours(board_mask, [first], -1, 255, -1)
                prev_board_area   = cv.contourArea(first)
                prev_sat_area     = cv.countNonZero(cv.bitwise_and(sat_blobs, board_mask))
                stable_board_mask = board_mask.copy()   # Committed baseline for diff
                set_board         = False

                origin       = mask_centroid(board_mask)
                grid_tracker = GridTracker(origin)

                # Seed tile size from the origin blob's minAreaRect dimensions.
                # This is more reliable than using the diff centroid on the second
                # tile: MORPH_CLOSE fills the gap between adjacent tiles, pulling
                # the diff centroid ~25% further than the actual tile centre and
                # making calibrate() overestimate a.  A single solid tile blob is
                # not significantly expanded by MORPH_CLOSE.
                rect_f          = cv.minAreaRect(first)
                (_, _), (rw_f, rh_f), _ = rect_f
                grid_tracker.a  = float(max(rw_f, rh_f))
                grid_tracker.b  = 0.0
                print(f"Board origin set at pixel ({origin[0]:.0f}, {origin[1]:.0f})"
                      f"  tile_size={grid_tracker.a:.0f}px  — identifying first tile.")

                # Identify the origin tile immediately so the engine knows what (0, 0) is.
                crop = extract_tile_crop(frame, first, proc_scale)
                path = os.path.join(CROPS_DIR, f"tile_{save_count:04d}.png")
                cv.imwrite(path, crop)
                print(f"Saved origin tile: {path}")
                save_count += 1

                results      = image_match.match_image(path, model, preprocess, embeddings, bias=bias)
                tile_id      = results[0][1]   # bare ID string, e.g. "ID43"
                tile_checked = True
                grid_coord   = (0, 0)
                grid_checked = True
                print("Origin tile identified — communicating (0, 0).")
                for score, rid in results[:3]:
                    print(f"  {score:.4f}  {rid}")

        # ── Board exists ──────────────────────────────────────────────────────
        else:
            old_board_mask            = board_mask.copy()
            new_board_cnt, unplaced   = classify_contours(valid, board_mask, blobs.shape)

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
                        crop = extract_tile_crop(frame, candidate_tile_cnt, proc_scale)
                        path = os.path.join(CROPS_DIR, f"tile_{save_count:04d}.png")
                        cv.imwrite(path, crop)
                        print(f"Saved tile: {path}")
                        save_count           += 1
                        tile_saved            = True
                        tile_frame_count      = 0
                        candidate_tile_cnt    = None
                        candidate_tile_center = None
                        phase                 = WAIT_PLACEMENT
                        results      = image_match.match_image(path, model, preprocess, embeddings, bias=bias)
                        tile_id      = results[0][1]
                        tile_checked = True
                        print("Tile identified — waiting for it to be placed on the board.")
                        for score, rid in results[:3]:
                            print(f"  {score:.4f}  {rid}")

                elif candidate_tile_center is None:
                    tile_frame_count = 0

            # ── Phase 2: wait for board blob to grow ──────────────────────────
            elif phase == WAIT_PLACEMENT:
                if new_board_cnt is not None:
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
                            sat_in_diff = cv.bitwise_and(sat_blobs, diff_mask)
                            best_slot, top_cov = grid_tracker.best_coverage_slot(sat_in_diff)
                            used_sat = True
                            if top_cov < 200:
                                best_slot = None

                            # Fallback A: muted-colour tile — use raw diff coverage.
                            # MORPH_CLOSE halos contaminate this, but the actual tile area
                            # still dominates (~3-4× more coverage than any adjacent halo).
                            if best_slot is None:
                                best_slot, top_cov = grid_tracker.best_coverage_slot(diff_mask)
                                used_sat = False
                                if top_cov < 200:
                                    best_slot = None

                            # Fallback B: enclosed centre tile — diff is near-empty because
                            # MORPH_CLOSE already filled the ring gap before placement.
                            if best_slot is None:
                                enclosed = grid_tracker.enclosed_slots()
                                if len(enclosed) == 1:
                                    best_slot = enclosed[0]
                                    top_cov   = 0
                                    print(f"  Grid: enclosed slot fallback → {best_slot}")

                            # Coverage margin check — warn if two slots score similarly.
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
                                    print(f"  WARNING: coverage ambiguous ({top_cov} vs "
                                          f"{second_cov} {label}-px, {margin:.0%} margin)"
                                          f" — press 'n' if grid looks wrong")
                                else:
                                    print(f"  Grid: best slot → {best_slot} "
                                          f"({top_cov} {label}-px, {margin:.0%} margin)")

                            # Diagnostic cross-check: log if diff centroid disagrees.
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
                                tile_saved = False
                                phase      = IDENTIFY

                                # Compute the actual observed tile centroid from saturation
                                # pixels — more accurate than the grid-predicted slot centre,
                                # and used both for the refit and as the placed-crop centre.
                                sc_x, sc_y = grid_tracker.slot_centroid(sat_in_diff, *best_slot)
                                if sc_x is None:
                                    sc_x, sc_y = grid_tracker.slot_centroid(diff_mask, *best_slot)
                                use_cx = sc_x if sc_x is not None else diff_cx
                                use_cy = sc_y if sc_y is not None else diff_cy
                                grid_tracker.confirm_placement(best_slot, use_cx, use_cy)
                                last_placed_coord = best_slot
                                print(f"Tile placed at grid {best_slot} — ready for next tile.")

                                # Post-placement rotation detection.
                                # Crop using the observed centroid (not the grid prediction) so
                                # the tile is well-centred even when the grid fit isn't perfect.
                                if tile_id is not None:
                                    family_id    = tile_id
                                    board_angle  = np.degrees(
                                        np.arctan2(grid_tracker.b, grid_tracker.a))
                                    placed_crop  = crop_placed_slot(
                                        frame, slot_px, grid_tracker.tile_size_px,
                                        proc_scale, board_angle,
                                        center_px=(use_cx, use_cy))
                                    placed_path  = os.path.join(
                                        CROPS_DIR, f"placed_{save_count - 1:04d}.png")
                                    cv.imwrite(placed_path, placed_crop)
                                    print(f"Rotation detection for family {family_id}:")
                                    tile_id = image_match.match_rotation(
                                        placed_path, model, preprocess, embeddings,
                                        family_id, bias=bias)
                                    print(f"  → {tile_id}")

                                grid_coord   = best_slot
                                grid_checked = True
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
                            if non_growth_count >= 2:
                                # Two consecutive non-growth frames: genuine transient.
                                growth_frame_count  = 0
                                non_growth_count    = 0
                                candidate_board_cnt = None
                                pre_growth_mask     = None
                                print("Growth was transient — ignored.")
                            # One non-growth frame: keep the counter (tile may be wobbling
                            # at the threshold) and wait for the next frame.

            # ── Phase 3: invalid placement — wait for tile removal ────────────
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
        if grid_checked and tile_checked:
            print("Communicating — waiting for engine response...")
            cv_to_engine = True
            while not game_response[0]:   # Block until interface sets game_response[0] = True
                time.sleep(0.05)
            is_valid      = (game_response[1] == 1)
            game_response = (False, game_response[1])
            cv_to_engine  = False
            grid_coord    = None
            grid_checked  = False

            if is_valid:
                tile_id      = None
                tile_checked = False
                print("Finished communicating — placement accepted.")
            else:
                grid_tracker.restore()
                prev_board_area     = rollback_prev_board_area
                prev_sat_area       = rollback_prev_sat_area
                last_placed_coord   = rollback_last_coord
                stable_board_mask   = rollback_stable_board_mask
                tile_saved        = True   # Tile identity already known — skip re-scan
                phase             = INVALID_DISPLAY
                removal_frame_count = 0
                print("Finished communicating — placement rejected. Remove tile and reposition.")

        panel_w, panel_h = DISP_W // 2, DISP_H // 2
        def to_bgr(img):
            return cv.cvtColor(img, cv.COLOR_GRAY2BGR) if len(img.shape) == 2 else img
        top    = np.hstack([cv.resize(to_bgr(edges),   (panel_w, panel_h)),
                            cv.resize(to_bgr(density), (panel_w, panel_h))])
        bottom = np.hstack([cv.resize(to_bgr(blobs),   (panel_w, panel_h)),
                            cv.resize(to_bgr(result),  (panel_w, panel_h))])
        cv.imshow("CV Debug", np.vstack([top, bottom]))

        time.sleep(1)
