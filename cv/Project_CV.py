import cv2 as cv
import numpy as np
import os, sys
# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cv import image_match
import time

# --- Communication flags ---
tile_checked    = False  # Flag to check if the tile has been checked by AI model
tile_id         = None   # Store the tile id number
grid_checked    = False  # Flag to check if a tile has been placed and coords recorded
grid_coord      = None   # Store the grid coordinates of a placed tile
cv_to_engine    = False  # Flag to check if CV is communicating to game engine

game_response   = (False, 1)  # Flag to check if game engine has process communication, 1 means valid move, 0 means invalid move check again

# ── Helpers ──────────────────────────────────────────────────────────────────

def maskCentroid(mask):
    """Return the (x, y) centroid of a binary mask, or None if the mask is empty."""
    M = cv.moments(mask)
    if M['m00'] > 0:
        return (M['m10'] / M['m00'], M['m01'] / M['m00'])
    return None


def openSlots(placed):
    """Return grid cells adjacent to any placed tile that are not yet occupied."""
    candidates = set()
    for (gx, gy) in placed:
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            neighbour = (gx + dx, gy + dy)
            if neighbour not in placed:
                candidates.add(neighbour)
    return candidates


def cellCoverage(blob_mask, gx, gy, origin, tile_size):
    """Count blob pixels inside the expected bounding box of grid cell (gx, gy).
    Used to score candidate placement slots — highest coverage wins."""
    cx   = int(origin[0] + gx * tile_size)
    cy   = int(origin[1] - gy * tile_size)  # Y is inverted in pixel space
    half = int(tile_size * 0.5)
    x1 = max(cx - half, 0)
    y1 = max(cy - half, 0)
    x2 = min(cx + half, blob_mask.shape[1])
    y2 = min(cy + half, blob_mask.shape[0])
    if x2 <= x1 or y2 <= y1:
        return 0
    return cv.countNonZero(blob_mask[y1:y2, x1:x2])


# ── Main loop ─────────────────────────────────────────────────────────────────

def cv_main_loop():

    # load AI model embeddings
    model, preprocess = image_match.model_setup()
    embeddings = image_match.load_embeddings()

    cap = cv.VideoCapture(0)
    if not cap.isOpened():
        print("Error, camera not opened")
        exit()

    # --- Tunable parameters ---
    BLUR_KERNEL = 5
    CANNY_LOW   = 10
    CANNY_HIGH  = 40

    DENSITY_BLUR      = 31
    DENSITY_THRESHOLD = 20

    MORPH_OPEN_KERNEL  = 25   # Removes isolated noise blobs smaller than this kernel
    MORPH_CLOSE_KERNEL = 15   # Fills gaps within blobs and smooths edges

    TILE_AREA_MIN = 2000
    TILE_AREA_MAX = 100_000_000

    DISPLAY_EVERY_N_FRAMES = 30

    CROPS_DIR = os.path.join(os.path.dirname(__file__), "tile_crops")
    os.makedirs(CROPS_DIR, exist_ok=True)

    # --- Phase constants ---
    IDENTIFY       = "identify"       # Waiting to see and save the next unplaced tile
    WAIT_PLACEMENT = "wait_placement" # Tile saved, waiting for it to be placed on the board

    # --- State ---
    board_mask  = None  # Binary mask of the board blob
    prev_board_area = 0
    phase      = IDENTIFY
    tile_saved = False
    save_count = 0
    frame_count = 0
    set_board  = False

    # --- Board growth detection ---
    # A placement is only confirmed once the blob has grown for several consecutive frames
    BOARD_GROWTH_THRESHOLD = 1000  # Min pixel area increase to count as growth
    GROWTH_CONFIRM_FRAMES  = 8     # Frames growth must persist before committing
    growth_frame_count  = 0
    candidate_board_cnt = None     # Contour candidate during growth confirmation window

    # --- Tile identification stability ---
    # The tile must stay roughly still for several frames before being saved
    TILE_CONFIRM_FRAMES = 8   # Frames tile must be stable before saving
    TILE_STABLE_DIST    = 20  # Max pixel movement still considered "stable"
    tile_frame_count    = 0
    candidate_tile_cnt    = None
    candidate_tile_center = None

    # --- Grid coordinate tracking ---
    origin_px       = None   # Pixel position of tile (0,0), set when board is initialised
    tile_size_px    = None   # Pixel width/height of one tile, calibrated on first placement
    last_placed_coord = None
    grid_calibrated = False
    placed_tiles    = set()  # (gx, gy) for every tile confirmed on the board

    # Communication Variables
    # Making sure no local variables are created for these communication variables
    global tile_checked
    global tile_id
    global grid_checked
    global grid_coord
    global cv_to_engine
    global game_response

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

        if frame_count % DISPLAY_EVERY_N_FRAMES != 0:  # Only process every Nth frame to reduce CPU load
            continue

        # --- Image preprocessing ---
        grey    = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)                    # Greyscale
        blurred = cv.GaussianBlur(grey, (BLUR_KERNEL, BLUR_KERNEL), 0)     # First blur
        edges   = cv.Canny(blurred, CANNY_LOW, CANNY_HIGH)                 # Detects edges of blur
        density = cv.GaussianBlur(edges, (DENSITY_BLUR, DENSITY_BLUR), 0)  # Calculates density for blobs
        _, blobs = cv.threshold(density, DENSITY_THRESHOLD, 255, cv.THRESH_BINARY)  # Makes blobs
        open_k  = cv.getStructuringElement(cv.MORPH_RECT, (MORPH_OPEN_KERNEL,  MORPH_OPEN_KERNEL))
        close_k = cv.getStructuringElement(cv.MORPH_RECT, (MORPH_CLOSE_KERNEL, MORPH_CLOSE_KERNEL))
        blobs   = cv.morphologyEx(blobs, cv.MORPH_OPEN,  open_k)   # Remove noise blobs
        blobs   = cv.morphologyEx(blobs, cv.MORPH_CLOSE, close_k)  # Fill gaps, smooth edges

        contours, _ = cv.findContours(blobs, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)  # Finds contours of blobs
        valid = [c for c in contours if TILE_AREA_MIN < cv.contourArea(c) < TILE_AREA_MAX]  # Filter by area

        result   = frame.copy()  # Working copy for display annotations
        unplaced = []             # Contours not overlapping the board blob

        # ── Board not set yet ─────────────────────────────────────────────────────
        if board_mask is None:
            # Highlight all detected blobs so the user can see what will be captured
            for cnt in valid:
                rect = cv.minAreaRect(cnt)
                box  = np.intp(cv.boxPoints(rect))
                cv.drawContours(result, [box], -1, (0, 255, 255), 2)

            cv.putText(result, "Press 'b' to set board origin", (10, 30),
                    cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            if set_board and valid:
                first = max(valid, key=cv.contourArea)  # Assume the largest blob is the first tile
                board_mask      = np.zeros(blobs.shape, dtype=np.uint8)
                cv.drawContours(board_mask, [first], -1, 255, -1)
                prev_board_area = cv.contourArea(first)
                placed_tiles    = {(0, 0)}  # Seed the grid with the origin tile
                set_board       = False
                c = maskCentroid(board_mask)
                origin_px = c
                print(f"Board origin set at pixel ({c[0]:.0f}, {c[1]:.0f}) — place next tile to identify.")

        # ── Board exists ──────────────────────────────────────────────────────────
        else:
            # Find which contour best overlaps the existing board mask — that's the updated board blob
            new_board_cnt = None
            best_overlap  = 0
            for cnt in valid:
                m = np.zeros(blobs.shape, dtype=np.uint8)
                cv.drawContours(m, [cnt], -1, 255, -1)
                overlap = cv.countNonZero(cv.bitwise_and(board_mask, m))  # Pixel overlap with known board
                if overlap > best_overlap:
                    best_overlap  = overlap
                    new_board_cnt = cnt
                else:
                    unplaced.append(cnt)  # No overlap → likely an unplaced tile in hand

            if new_board_cnt is not None:
                rect = cv.minAreaRect(new_board_cnt)
                box  = np.intp(cv.boxPoints(rect))
                cv.drawContours(result, [box], -1, (0, 0, 255), 2)
                (cx, cy), _, angle = rect
                cv.putText(result, f"BOARD [{phase}] {angle:.0f}deg", (int(cx) - 40, int(cy) - 10),
                        cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

                # Update board_mask each frame so overlap detection stays accurate
                board_mask = np.zeros(blobs.shape, dtype=np.uint8)
                cv.drawContours(board_mask, [new_board_cnt], -1, 255, -1)

            # ── Phase 1: identify and save the next tile ──────────────────────────
            if phase == IDENTIFY:
                if unplaced and not tile_saved:
                    cnt  = unplaced[0]
                    rect = cv.minAreaRect(cnt)
                    box  = np.intp(cv.boxPoints(rect))
                    (cx, cy), _, angle = rect

                    # Reset stability counter if the tile has moved significantly
                    if candidate_tile_center is not None:
                        dist = np.hypot(cx - candidate_tile_center[0], cy - candidate_tile_center[1])
                        if dist > TILE_STABLE_DIST:
                            tile_frame_count = 0

                    candidate_tile_cnt    = cnt
                    candidate_tile_center = (cx, cy)
                    tile_frame_count     += 1

                    remaining = TILE_CONFIRM_FRAMES - tile_frame_count
                    colour = (0, 255, 0) if remaining <= 0 else (0, 255, 255)
                    cv.drawContours(result, [box], -1, colour, 2)
                    cv.putText(result, f"Identifying... ({remaining} frames)" if remaining > 0 else "Saving...",
                            (int(cx) - 40, int(cy) - 10), cv.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1)

                    if tile_frame_count >= TILE_CONFIRM_FRAMES:
                        # Crop and save the tile image
                        x, y, w, h = cv.boundingRect(candidate_tile_cnt)
                        x1, y1 = max(x, 0), max(y, 0)
                        x2, y2 = min(x + w, frame.shape[1]), min(y + h, frame.shape[0])
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
                        print("Tile found using AI model to get id")
                        results = image_match.match_image(path, model, preprocess, embeddings)
                        temp = results[0]
                        tile_id = temp[1]   # (Score, id) want id to be saved
                        tile_checked = True
                        print("Tile identified — waiting for it to be placed on the board.")

                elif candidate_tile_center is None:
                    tile_frame_count = 0  # No tile in view, reset
                # else: mid-identification but tile not visible this frame — hold the count

            # ── Phase 2: wait for board blob to grow ──────────────────────────────
            elif phase == WAIT_PLACEMENT:
                if new_board_cnt is not None:
                    current_board_area = cv.contourArea(new_board_cnt)

                    if current_board_area - prev_board_area > BOARD_GROWTH_THRESHOLD:
                        # Board has grown — accumulate confirmation frames
                        growth_frame_count  += 1
                        candidate_board_cnt  = new_board_cnt
                        remaining = GROWTH_CONFIRM_FRAMES - growth_frame_count
                        cv.putText(result, f"Confirming placement... ({remaining} frames)",
                                (10, 60), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

                        if growth_frame_count >= GROWTH_CONFIRM_FRAMES:
                            # Build the confirmed new board mask
                            new_mask = np.zeros(blobs.shape, dtype=np.uint8)
                            cv.drawContours(new_mask, [candidate_board_cnt], -1, 255, -1)

                            # --- Calibrate tile size from the first placement ---
                            # With 2 tiles side-by-side the bounding rect is ~2:1,
                            # so the shorter side ≈ one tile width
                            if not grid_calibrated:
                                _, (w, h), _ = cv.minAreaRect(candidate_board_cnt)
                                tile_size_px    = min(w, h)
                                grid_calibrated = True
                                print(f"Tile size calibrated: {tile_size_px:.0f}px")

                            # --- Determine placement by grid cell coverage ---
                            # Score every legal open slot by how many blob pixels fall
                            # inside its expected pixel bounding box — highest wins
                            slots     = openSlots(placed_tiles)
                            best_slot = None
                            best_cov  = 0
                            for slot in slots:
                                cov = cellCoverage(new_mask, slot[0], slot[1], origin_px, tile_size_px)
                                if cov > best_cov:
                                    best_cov  = cov
                                    best_slot = slot

                            # Commit the board update
                            board_mask          = new_mask
                            prev_board_area     = cv.contourArea(candidate_board_cnt)
                            tile_saved          = False
                            phase               = IDENTIFY
                            growth_frame_count  = 0
                            candidate_board_cnt = None

                            if best_slot is not None:
                                placed_tiles.add(best_slot)
                                last_placed_coord = best_slot
                                print(f"Tile placed at grid ({best_slot[0]}, {best_slot[1]}) — ready for next tile.")

                                # Save best grid slot for the placed tile
                                # grid_coord = (best_slot[0], best_slot[1])
                                grid_coord = (3, 3) # Test variable
                                grid_checked = True

                            else:
                                print("Board updated — could not determine grid position.")
                    else:
                        # Growth was below threshold — treat as transient noise
                        if growth_frame_count > 0:
                            print("Growth was transient — ignored.")
                        growth_frame_count  = 0
                        candidate_board_cnt = None

        # --- Display overlay ---
        if last_placed_coord is not None:
            coord_text = f"Last placed: ({last_placed_coord[0]}, {last_placed_coord[1]})"
            cv.putText(result, coord_text, (10, 30),
                    cv.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
        # Communication section
        if grid_checked and tile_checked:
            print("Communicating")
            # Means we have a tile id and the tile has been placed into the grid
            # send message to game engine
            cv_to_engine = True
            while not game_response[0]:
                # Wait until game engine has responded
                # Could add if statement to remove incorrect move img
                pass
            grid_coord = None
            tile_id = None
            grid_checked = False
            tile_checked = False
            cv_to_engine = False
            if (game_response[1] == 0):
                ## Invalid move
                pass

            game_response[0] = False
            print("Finished communicating")
            

        cv.imshow("1: Edges (Canny)", edges)
        cv.imshow("2: Density map", density)
        cv.imshow("3: Blobs + threshold", blobs)
        cv.imshow("4: Tile outlines", result)

        time.sleep(1)