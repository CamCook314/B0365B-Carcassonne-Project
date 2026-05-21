"""
blob_pipeline.py — Image preprocessing for tile detection.

Converts a raw camera frame into blob masks and classified contours.
All tunable CV parameters live here so they're in one place.

Parameters can be overridden at runtime by cv/config.json (written by
calibrate_blob.py). The hardcoded values below are the fallback defaults.
"""

import cv2 as cv
import numpy as np
import json
import os

# --- Default parameters (overridden by config.json if present) ---
BLUR_KERNEL        = 11   # Suppresses wood grain before edge detection
CANNY_LOW          = 30
CANNY_HIGH         = 80
DENSITY_BLUR       = 21   # Keeps edge density concentrated around tile edges
DENSITY_THRESHOLD  = 10   # Raised vs original to compensate for more sensitive Canny (30/80)
MORPH_OPEN_KERNEL  = 7    # Removes isolated noise blobs smaller than this
MORPH_CLOSE_KERNEL = 45   # Fills intra-tile gaps; must stay < tile_size/2
SAT_THRESHOLD      = 90   # Min HSV saturation (0–255) to count as tile colour
TILE_AREA_MIN      = 3000
TILE_AREA_MAX      = 100_000_000
TILE_ASPECT_MAX    = 3.0   # Max bounding-box aspect ratio; rejects elongated non-tile blobs

# --- Load overrides from config.json if it exists ---
_CFG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
if os.path.exists(_CFG_PATH):
    with open(_CFG_PATH) as _f:
        _cfg = json.load(_f)
    BLUR_KERNEL        = _cfg.get("BLUR_KERNEL",        BLUR_KERNEL)
    CANNY_LOW          = _cfg.get("CANNY_LOW",          CANNY_LOW)
    CANNY_HIGH         = _cfg.get("CANNY_HIGH",         CANNY_HIGH)
    DENSITY_BLUR       = _cfg.get("DENSITY_BLUR",       DENSITY_BLUR)
    DENSITY_THRESHOLD  = _cfg.get("DENSITY_THRESHOLD",  DENSITY_THRESHOLD)
    MORPH_OPEN_KERNEL  = _cfg.get("MORPH_OPEN_KERNEL",  MORPH_OPEN_KERNEL)
    MORPH_CLOSE_KERNEL = _cfg.get("MORPH_CLOSE_KERNEL", MORPH_CLOSE_KERNEL)
    SAT_THRESHOLD      = _cfg.get("SAT_THRESHOLD",      SAT_THRESHOLD)
    TILE_AREA_MIN      = _cfg.get("TILE_AREA_MIN",      TILE_AREA_MIN)
    TILE_AREA_MAX      = _cfg.get("TILE_AREA_MAX",      TILE_AREA_MAX)
    TILE_ASPECT_MAX    = _cfg.get("TILE_ASPECT_MAX",    TILE_ASPECT_MAX)


def process_frame(frame, sat_threshold=SAT_THRESHOLD):
    """Run the full blob detection pipeline on a frame.

    Returns (edges, density, blobs, sat_blobs) — all single-channel uint8.
    """
    grey    = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    blurred = cv.GaussianBlur(grey, (BLUR_KERNEL, BLUR_KERNEL), 0)
    edges   = cv.Canny(blurred, CANNY_LOW, CANNY_HIGH)
    density = cv.GaussianBlur(edges, (DENSITY_BLUR, DENSITY_BLUR), 0)
    _, edge_blobs = cv.threshold(density, DENSITY_THRESHOLD, 255, cv.THRESH_BINARY)

    hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
    _, sat_blobs = cv.threshold(hsv[:, :, 1], sat_threshold, 255, cv.THRESH_BINARY)

    # Suppress projected magenta (valid-placement markers, borders) from both detection paths.
    # Wide HSV range + dilation to catch edge-of-projector artifacts where the reflected
    # light is oblique and loses both hue accuracy and saturation.
    proj_magenta = cv.inRange(hsv, (130, 40, 40), (175, 255, 255))
    proj_magenta = cv.dilate(proj_magenta,
                             cv.getStructuringElement(cv.MORPH_RECT, (5, 5)))
    edge_blobs[proj_magenta > 0] = 0
    sat_blobs[proj_magenta > 0]  = 0

    # Suppress projected orange event tiles (BGR 0,165,255 → HSV H≈20).
    proj_orange = cv.inRange(hsv, (8, 60, 60), (28, 255, 255))
    proj_orange = cv.dilate(proj_orange,
                            cv.getStructuringElement(cv.MORPH_RECT, (5, 5)))
    edge_blobs[proj_orange > 0] = 0
    sat_blobs[proj_orange > 0]  = 0

    blobs   = cv.bitwise_or(edge_blobs, sat_blobs)
    open_k  = cv.getStructuringElement(cv.MORPH_RECT, (MORPH_OPEN_KERNEL,  MORPH_OPEN_KERNEL))
    close_k = cv.getStructuringElement(cv.MORPH_RECT, (MORPH_CLOSE_KERNEL, MORPH_CLOSE_KERNEL))
    blobs   = cv.morphologyEx(blobs, cv.MORPH_OPEN,  open_k)
    blobs   = cv.morphologyEx(blobs, cv.MORPH_CLOSE, close_k)

    return edges, density, blobs, sat_blobs


def mask_centroid(mask):
    """Return the (x, y) centroid of a binary mask, or None if the mask is empty."""
    M = cv.moments(mask)
    if M['m00'] > 0:
        return (M['m10'] / M['m00'], M['m01'] / M['m00'])
    return None


def find_contours(blobs, area_min=None):
    """Find external contours and filter by area and aspect ratio."""
    if area_min is None:
        area_min = TILE_AREA_MIN
    contours, _ = cv.findContours(blobs, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    valid = []
    for c in contours:
        if not (area_min < cv.contourArea(c) < TILE_AREA_MAX):
            continue
        _, _, w, h = cv.boundingRect(c)
        if w == 0 or h == 0:
            continue
        if max(w, h) / min(w, h) > TILE_ASPECT_MAX:
            continue
        valid.append(c)
    return valid


def classify_contours(valid, board_mask, blob_shape):
    """Split contours into the board contour and unplaced tile contours.

    The board contour is whichever valid contour has the greatest overlap with
    board_mask.  Any contour with zero overlap is treated as an unplaced tile.

    Returns (new_board_cnt, unplaced_list).  new_board_cnt is None if nothing
    overlaps the board at all.
    """
    if not valid:
        return None, []

    overlaps = []
    for cnt in valid:
        m = np.zeros(blob_shape, dtype=np.uint8)
        cv.drawContours(m, [cnt], -1, 255, -1)
        overlap = cv.countNonZero(cv.bitwise_and(board_mask, m))
        overlaps.append((overlap, cnt))

    # Among contours with board overlap, filter to ratio >= 0.5 to exclude the
    # physical board edge (near-zero ratio).  Then pick by largest absolute overlap
    # so the full cluster+new_tile (large overlap, ratio ~0.85) beats a small
    # fragment (tiny overlap, ratio ~1.0) that can appear when the magenta
    # projection filter removes pixels from the placed tile.
    scored = [
        (ov / max(cv.contourArea(cnt), 1), ov, cnt)
        for ov, cnt in overlaps if ov > 0
    ]
    if scored:
        candidates = [(r, ov, cnt) for r, ov, cnt in scored if r >= 0.5]
        if not candidates:
            candidates = scored  # fallback: all overlapping contours
        _, _, board_cnt = max(candidates, key=lambda x: x[1])
        new_board_cnt = board_cnt
    else:
        new_board_cnt = None

    unplaced = [cnt for overlap, cnt in overlaps if overlap == 0]
    return new_board_cnt, unplaced
