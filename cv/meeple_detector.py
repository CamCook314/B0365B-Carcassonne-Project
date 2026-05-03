"""
meeple_detector.py — Diff-based meeple detection on a placed tile.

Primary signal: absolute difference between a baseline frame (taken at WAIT_MEEPLE
entry, before any meeple) and the current frame.  Only pixels that are NEW since the
baseline contribute — tile artwork is subtracted out entirely.

Colour is identified by applying HSV ranges only within the diff region, so dark
rooftops / borders / shadows in the tile art don't interfere.

Call detect_meeple() each frame during the WAIT_MEEPLE phase.
Returns (colour_name, direction) or (None, None).
"""
import cv2 as cv
import numpy as np

# HSV colour ranges.  Red wraps 0°, so it needs two entries.
# Black: value < 70 (raised from 50 — black plastic reflects some light).
COLOUR_RANGES = {
    "red":    [((0,   100, 60),  (10,  255, 255)),
               ((165, 100, 60),  (180, 255, 255))],
    "blue":   [((100, 80,  60),  (130, 255, 255))],
    "green":  [((55,  120, 60),  (80,  255, 255))],
    "yellow": [((20,  100, 60),  (35,  255, 255))],
    "black":  [((0,   0,   0),   (180, 80,  70))],
}

# Diff thresholds
DIFF_THRESHOLD   = 20    # abs pixel change to count as "new"
MIN_BLOB_AREA    = 60    # px² — smallest diff blob that could be a meeple
MAX_BLOB_AREA_FRAC = 0.20  # fraction of tile area — rejects hands/arms


def _colour_mask(hsv_crop, colour):
    mask = None
    for lo, hi in COLOUR_RANGES[colour]:
        m = cv.inRange(hsv_crop,
                       np.array(lo, dtype=np.uint8),
                       np.array(hi, dtype=np.uint8))
        mask = m if mask is None else cv.bitwise_or(mask, m)
    return mask


def detect_meeple(proc_frame, slot_px, tile_size_px,
                  baseline_frame=None, centre_frac=0.25):
    """Detect a meeple on the last-placed tile.

    proc_frame     : current 1920×1080 BGR frame.
    slot_px        : (cx, cy) grid-predicted tile centre, proc coords.
    tile_size_px   : side length of one tile in proc coords.
    baseline_frame : proc_frame captured when WAIT_MEEPLE started (no meeple).
                     If None, falls back to the old pure-colour method.
    centre_frac    : displacement fraction below which centroid → 'centre'.

    Returns (colour_name, direction) or (None, None).
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

    tile_area = tile_size_px ** 2
    max_blob  = tile_area * MAX_BLOB_AREA_FRAC

    # ── Diff-based detection ──────────────────────────────────────────────────
    if baseline_frame is not None:
        base_crop = baseline_frame[y1:y2, x1:x2]
        if base_crop.shape != crop.shape:
            return None, None

        diff      = cv.absdiff(crop, base_crop)
        diff_grey = cv.cvtColor(diff, cv.COLOR_BGR2GRAY)
        _, diff_mask = cv.threshold(diff_grey, DIFF_THRESHOLD, 255, cv.THRESH_BINARY)

        # Small open to remove single-pixel noise
        k = cv.getStructuringElement(cv.MORPH_ELLIPSE, (3, 3))
        diff_mask = cv.morphologyEx(diff_mask, cv.MORPH_OPEN, k)

        diff_area = cv.countNonZero(diff_mask)
        if diff_area < MIN_BLOB_AREA or diff_area > max_blob:
            return None, None

        # Centroid of the diff blob
        M = cv.moments(diff_mask)
        if M["m00"] == 0:
            return None, None
        mcx = M["m10"] / M["m00"]
        mcy = M["m01"] / M["m00"]

        # Classify colour of the diff region
        hsv = cv.cvtColor(crop, cv.COLOR_BGR2HSV)
        best_colour = None
        best_count  = 0
        for colour in COLOUR_RANGES:
            colour_mask = _colour_mask(hsv, colour)
            overlap     = cv.countNonZero(cv.bitwise_and(colour_mask, diff_mask))
            if overlap > best_count:
                best_count  = overlap
                best_colour = colour

        # Require at least 30% of the diff blob to match a colour
        if best_colour is None or best_count < diff_area * 0.30:
            return None, None

    # ── Fallback: pure colour detection (no baseline) ────────────────────────
    else:
        hsv    = cv.cvtColor(crop, cv.COLOR_BGR2HSV)
        kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (3, 3))

        best_colour = None
        best_area   = MIN_BLOB_AREA - 1
        mcx = mcy   = None

        for colour in COLOUR_RANGES:
            mask = _colour_mask(hsv, colour)
            mask = cv.morphologyEx(mask, cv.MORPH_OPEN, kernel)
            M    = cv.moments(mask)
            area = M["m00"]
            if area < MIN_BLOB_AREA or area > max_blob or area <= best_area:
                continue
            best_colour = colour
            best_area   = area
            mcx         = M["m10"] / M["m00"]
            mcy         = M["m01"] / M["m00"]

        if best_colour is None:
            return None, None

    # ── Direction ─────────────────────────────────────────────────────────────
    crop_cx   = (x2 - x1) / 2.0
    crop_cy   = (y2 - y1) / 2.0
    dx        = mcx - crop_cx
    dy        = mcy - crop_cy
    threshold = tile_size_px * centre_frac

    if abs(dx) < threshold and abs(dy) < threshold:
        direction = "centre"
    elif abs(dx) >= abs(dy):
        direction = "right" if dx > 0 else "left"
    else:
        direction = "down" if dy > 0 else "up"

    return best_colour, direction
