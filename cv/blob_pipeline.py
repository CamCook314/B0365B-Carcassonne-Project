"""
blob_pipeline.py — Image preprocessing for tile detection.

Converts a raw camera frame into blob masks and classified contours.
All tunable CV parameters live here so they're in one place.
"""

import cv2 as cv
import numpy as np

# --- Tunable parameters ---
BLUR_KERNEL        = 11   # Suppresses wood grain before edge detection
CANNY_LOW          = 40
CANNY_HIGH         = 100
DENSITY_BLUR       = 21   # Keeps edge density concentrated around tile edges
DENSITY_THRESHOLD  = 8    # Background grain stays below this
MORPH_OPEN_KERNEL  = 7    # Removes isolated noise blobs smaller than this
MORPH_CLOSE_KERNEL = 45   # Fills intra-tile gaps; must stay < tile_size/2
                           # (~40px for 80-90px tiles at 1080p processing res)
SAT_THRESHOLD      = 70   # Min HSV saturation (0–255) to count as tile colour
TILE_AREA_MIN      = 3000
TILE_AREA_MAX      = 100_000_000


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


def find_contours(blobs):
    """Find external contours and filter by area."""
    contours, _ = cv.findContours(blobs, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    return [c for c in contours if TILE_AREA_MIN < cv.contourArea(c) < TILE_AREA_MAX]


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

    best_overlap, board_cnt = max(overlaps, key=lambda x: x[0])
    new_board_cnt = board_cnt if best_overlap > 0 else None
    unplaced      = [cnt for overlap, cnt in overlaps if overlap == 0]

    return new_board_cnt, unplaced
