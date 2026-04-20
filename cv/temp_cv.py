"""
Project_CV.py — Main CV loop and engine communication globals.

Drives the phase state machine and owns all board-level state.
Image processing lives in blob_pipeline.py.
Grid coordinate logic lives in grid_tracker.py.
"""

import requests
import cv2 as cv
import numpy as np
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


def cv_main_loop():
    requests.post("http://127.0.0.1:1234/reset")
    requests.post("http://127.0.0.1:1234/start", json={"players": 3})

    model, preprocess = image_match.model_setup()
    embeddings        = image_match.load_embeddings()

    cap = cv.VideoCapture(0)
    if not cap.isOpened():
        print("Error, camera not opened")
        exit()

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
    GROWTH_CONFIRM_FRAMES  = 6      # Consecutive frames of growth needed to commit
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
    rollback_prev_board_area = 0
    rollback_prev_sat_area   = 0
    rollback_last_coord      = None

    global tile_checked, tile_id, grid_checked, grid_coord, cv_to_engine, game_response

    print("Place the first tile then click any OpenCV window and press 'b'.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Camera turned off, exiting")
            break

        frame_count += 1
        key = cv.waitKey(1)
        if key == ord('q'):
            break
        if key == ord('b'):
            set_board = True

        if frame_count % DISPLAY_EVERY_N_FRAMES != 0:
            continue

        edges, density, blobs, sat_blobs = process_frame(frame)
        valid  = find_contours(blobs)
        result = frame.copy()

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
                prev_board_area = cv.contourArea(first)
                prev_sat_area   = cv.countNonZero(cv.bitwise_and(sat_blobs, board_mask))
                set_board       = False

                origin       = mask_centroid(board_mask)
                grid_tracker = GridTracker(origin)
                print(f"Board origin set at pixel ({origin[0]:.0f}, {origin[1]:.0f}) — identifying first tile.")

                # Identify the origin tile immediately so the engine knows what (0, 0) is.
                x, y, w, h = cv.boundingRect(first)
                pad = max(w, h) // 3
                x1 = max(x - pad, 0);          y1 = max(y - pad, 0)
                x2 = min(x + w + pad, frame.shape[1]); y2 = min(y + h + pad, frame.shape[0])
                crop = frame[y1:y2, x1:x2]
                path = os.path.join(CROPS_DIR, f"tile_{save_count:04d}.png")
                cv.imwrite(path, crop)
                print(f"Saved origin tile: {path}")
                save_count += 1

                results      = image_match.match_image(path, model, preprocess, embeddings)
                tile_id      = results[0][1].stem   # Path → bare ID, e.g. "ID43"
                tile_checked = True
                grid_coord   = (0, 0)
                grid_checked = True
                print("Origin tile identified — communicating (0, 0).")

        # ── Board exists ──────────────────────────────────────────────────────
        else:
            old_board_mask            = board_mask.copy()
            new_board_cnt, unplaced   = classify_contours(valid, board_mask, blobs.shape)

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
                        x, y, w, h = cv.boundingRect(candidate_tile_cnt)
                        pad = max(w, h) // 3
                        x1 = max(x - pad, 0);          y1 = max(y - pad, 0)
                        x2 = min(x + w + pad, frame.shape[1]); y2 = min(y + h + pad, frame.shape[0])
                        crop = frame[y1:y2, x1:x2]
                        path = os.path.join(CROPS_DIR, f"tile_{save_count:04d}.png")
                        cv.imwrite(path, crop)
                        print(f"Saved tile: {path}")
                        save_count           += 1
                        tile_saved            = True
                        tile_frame_count      = 0
                        candidate_tile_cnt    = None
                        candidate_tile_center = None
                        phase                 = WAIT_PLACEMENT
                        results      = image_match.match_image(path, model, preprocess, embeddings)
                        tile_id      = results[0][1].stem
                        tile_checked = True
                        print("Tile identified — waiting for it to be placed on the board.")

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
                        if growth_frame_count == 0:
                            pre_growth_mask = old_board_mask

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

                            # Diff centroid — used for tile_size calibration and drift
                            # correction only, not for coordinate detection.
                            diff_M  = cv.moments(diff_mask)
                            diff_cx = diff_M['m10'] / diff_M['m00'] if diff_M['m00'] > 200 else None
                            diff_cy = diff_M['m01'] / diff_M['m00'] if diff_M['m00'] > 200 else None

                            if diff_cx is not None:
                                grid_tracker.calibrate(diff_cx, diff_cy)
                                print(f"  diff centroid px=({diff_cx:.0f},{diff_cy:.0f})  "
                                      f"origin=({grid_tracker.origin_px[0]:.0f},{grid_tracker.origin_px[1]:.0f})")

                            # Primary: coverage scoring against known open slots.
                            # Use sat_blobs masked to the diff region: actual tile pixels
                            # are colourful, but MORPH_CLOSE fill-in is empty air and has
                            # no saturation — this eliminates phantom coverage in adjacent
                            # empty slots caused by morphological expansion.
                            sat_in_diff = cv.bitwise_and(sat_blobs, diff_mask)
                            best_slot = grid_tracker.best_coverage_slot(sat_in_diff)

                            # Fallback: if exactly one slot has all 4 neighbours placed,
                            # it must be the centre tile (diff mask is empty in that case).
                            if best_slot is None:
                                enclosed = grid_tracker.enclosed_slots()
                                if len(enclosed) == 1:
                                    best_slot = enclosed[0]

                            # Save rollback snapshot before committing.
                            grid_tracker.snapshot()
                            rollback_prev_board_area = prev_board_area
                            rollback_prev_sat_area   = prev_sat_area
                            rollback_last_coord      = last_placed_coord

                            # Commit board update.
                            board_mask          = new_mask
                            prev_board_area     = cv.contourArea(candidate_board_cnt)
                            prev_sat_area       = cv.countNonZero(cv.bitwise_and(sat_blobs, board_mask))
                            tile_saved          = False
                            phase               = IDENTIFY
                            growth_frame_count  = 0
                            candidate_board_cnt = None
                            pre_growth_mask     = None

                            if best_slot is not None:
                                slot_cx, slot_cy = grid_tracker.slot_centroid(sat_in_diff, *best_slot)
                                grid_tracker.confirm_placement(best_slot, slot_cx, slot_cy)
                                last_placed_coord = best_slot
                                print(f"Tile placed at grid {best_slot} — ready for next tile.")
                                grid_coord   = best_slot
                                grid_checked = True
                            else:
                                print("Board updated — could not determine grid position.")
                    else:
                        if growth_frame_count > 0:
                            growth_frame_count = 0
                            candidate_board_cnt = None
                            pre_growth_mask     = None
                            print("Growth was transient — ignored.")

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
        # if grid_checked and tile_checked:
        #     print("Communicating")
        #     cv_to_engine = True
        #     is_valid      = (game_response[1] == 1)
        #     game_response = (False, game_response[1])
        #     cv_to_engine  = False
        #     grid_coord    = None
        #     grid_checked  = False

        #     if is_valid:
        #         tile_id      = None
        #         tile_checked = False
        #         print("Finished communicating — placement accepted.")
        #     else:
        #         grid_tracker.restore()
        #         prev_board_area   = rollback_prev_board_area
        #         prev_sat_area     = rollback_prev_sat_area
        #         last_placed_coord = rollback_last_coord
        #         tile_saved        = True   # Tile identity already known — skip re-scan
        #         phase             = INVALID_DISPLAY
        #         removal_frame_count = 0
        #         print("Finished communicating — placement rejected. Remove tile and reposition.")
        
        # --- Engine communication ---
        # tile just identified
        if tile_checked:
            try:
                r = requests.post("http://127.0.0.1:1234/pending",
                                json={"tile_id": tile_id}, timeout=5)
                if not r.ok:
                    print(f"/pending rejected: {r.json().get('error')}")
            except requests.RequestException as e:
                print(f"API error on /pending: {e}")
            tile_checked = False

        # placement detected
        if grid_checked:
            try:
                r = requests.post("http://127.0.0.1:1234/place",
                                json={"x": int(grid_coord[0]),
                                        "y": int(grid_coord[1])}, timeout=5)
                is_valid = r.ok
            except requests.RequestException as e:
                print(f"API error on /place: {e}")
                is_valid = False

            grid_coord   = None
            grid_checked = False

            if is_valid:
                tile_id = None
                print("Placement accepted.")
            else:
                grid_tracker.restore()
                prev_board_area = rollback_prev_board_area
                prev_sat_area = rollback_prev_sat_area
                last_placed_coord = rollback_last_coord
                tile_saved = True
                phase = INVALID_DISPLAY
                removal_frame_count = 0
                print("Placement rejected. Remove tile and reposition.")


        cv.imshow("1: Edges (Canny)", edges)
        cv.imshow("2: Density map", density)
        cv.imshow("3: Blobs + threshold", blobs)
        cv.imshow("4: Tile outlines", result)

        time.sleep(1)

if __name__ == "__main__":
    cv_main_loop()