"""
meeple_detector.py — Colour-based meeple detection on a placed tile.

Call detect_meeple() each frame during the WAIT_MEEPLE phase.
Returns the meeple colour and its position relative to the tile centre.
"""
import cv2 as cv
import numpy as np

# HSV colour ranges for each player colour.
# Red wraps around 0°, so it needs two ranges.
# Green meeples are vivid (high saturation, hue 55-80°); Carcassonne field art
# is more yellow-green and less saturated, so the saturation floor is raised to 130.
COLOUR_RANGES = {
    "red":    [((0,   100, 80),  (10,  255, 255)),
               ((165, 100, 80),  (180, 255, 255))],
    "blue":   [((100, 100, 80),  (130, 255, 255))],
    "green":  [((55,  130, 80),  (80,  255, 255))],
    "yellow": [((20,  100, 80),  (35,  255, 255))],
    "black":  [((0,   0,   0),   (180, 255, 50))],
}

MIN_BLOB_AREA = 80    # px² — minimum coloured blob to count as a meeple
# A meeple covers at most ~15% of the tile area; anything larger is tile artwork.
MAX_BLOB_AREA_FRAC = 0.15


def _colour_mask(hsv, colour):
    mask = None
    for lo, hi in COLOUR_RANGES[colour]:
        m = cv.inRange(hsv, np.array(lo, dtype=np.uint8),
                            np.array(hi, dtype=np.uint8))
        mask = m if mask is None else cv.bitwise_or(mask, m)
    return mask


def detect_meeple(proc_frame, slot_px, tile_size_px, centre_frac=0.25):
    """Detect a meeple on the last-placed tile.

    proc_frame   : 1920×1080 BGR frame (processed resolution, not full-res).
    slot_px      : (cx, cy) grid-predicted centre of the placed tile, proc coords.
    tile_size_px : side length of one tile in proc coords.
    centre_frac  : displacement fraction below which centroid is classified 'centre'.

    Returns (colour_name, direction) where direction is one of
    'up', 'down', 'left', 'right', 'centre', or (None, None) if no meeple.
    """
    cx, cy = int(slot_px[0]), int(slot_px[1])
    half = int(tile_size_px * 0.45)

    x1 = max(cx - half, 0)
    y1 = max(cy - half, 0)
    x2 = min(cx + half, proc_frame.shape[1])
    y2 = min(cy + half, proc_frame.shape[0])
    crop = proc_frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None, None

    hsv = cv.cvtColor(crop, cv.COLOR_BGR2HSV)
    kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (3, 3))

    max_area = tile_size_px ** 2 * MAX_BLOB_AREA_FRAC

    best_colour = None
    best_area   = MIN_BLOB_AREA - 1
    best_mcx    = None
    best_mcy    = None

    for colour in COLOUR_RANGES:
        mask = _colour_mask(hsv, colour)
        mask = cv.morphologyEx(mask, cv.MORPH_OPEN, kernel)

        M = cv.moments(mask)
        area = M["m00"]
        if area < MIN_BLOB_AREA or area > max_area:
            continue
        if area <= best_area:
            continue

        best_colour = colour
        best_area   = area
        best_mcx    = M["m10"] / M["m00"]
        best_mcy    = M["m01"] / M["m00"]

    if best_colour is None:
        return None, None

    # Direction relative to the crop centre
    crop_cx = (x2 - x1) / 2.0
    crop_cy = (y2 - y1) / 2.0
    dx = best_mcx - crop_cx
    dy = best_mcy - crop_cy    # positive = downward in image space
    threshold = tile_size_px * centre_frac

    if abs(dx) < threshold and abs(dy) < threshold:
        direction = "centre"
    elif abs(dx) >= abs(dy):
        direction = "right" if dx > 0 else "left"
    else:
        direction = "down" if dy > 0 else "up"

    return best_colour, direction
