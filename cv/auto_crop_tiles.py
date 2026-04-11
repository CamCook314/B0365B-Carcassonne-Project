"""
auto_crop_tiles.py — Detect and crop individual tiles from a full overhead photo.

Usage (from project root):
    python cv/auto_crop_tiles.py <photo.jpg> <output_dir> [--debug]

Tiles are saved as tile_0000.png, tile_0001.png, ... sorted top-left to bottom-right.
"""

import cv2 as cv
import numpy as np
import sys
from pathlib import Path

# --- Tunable parameters ---
# Green hue range (OpenCV HSV: H is 0-179, so 360° green ~60° maps to ~30-85)
GREEN_HUE_LO   = np.array([30,  60,  60])   # H, S, V lower bound
GREEN_HUE_HI   = np.array([85, 255, 255])   # H, S, V upper bound

# Morphology: close fills within-tile gaps (city tiles have little green at corners).
# Keep this < half the gap between tiles to avoid bridging adjacent tiles.
CLOSE_PX       = 180   # pixels — tune down if adjacent tiles are merging

MIN_AREA_FRAC  = 0.003 # Min tile area as fraction of total image area
MAX_AREA_FRAC  = 0.08  # Max tile area as fraction of total image area
MAX_ASPECT     = 1.6   # Max width/height ratio (tiles are roughly square)
CROP_MARGIN    = 0.55  # Crop half-size as fraction of detected tile size (>0.5 adds padding)


def auto_crop_tiles(image_path: str, output_dir: str, debug: bool = False) -> int:
    img = cv.imread(image_path)
    if img is None:
        print(f"Could not load: {image_path}")
        return 0

    h, w = img.shape[:2]
    print(f"Image: {w}x{h}")

    # --- Segment tiles using green hue ---
    # The bright green field on Carcassonne tiles is distinct from the brown wood table.
    # Even mostly-city tiles have green at corners — MORPH_CLOSE fills the rest.
    hsv  = cv.cvtColor(img, cv.COLOR_BGR2HSV)
    mask = cv.inRange(hsv, GREEN_HUE_LO, GREEN_HUE_HI)

    close_k = cv.getStructuringElement(cv.MORPH_RECT, (CLOSE_PX, CLOSE_PX))
    mask    = cv.morphologyEx(mask, cv.MORPH_CLOSE, close_k)

    if debug:
        scale     = 800 / max(h, w)
        small_msk = cv.resize(mask, (int(w * scale), int(h * scale)))
        small_img = cv.resize(img,  (int(w * scale), int(h * scale)))
        cv.imwrite("debug_mask.png", small_msk)
        cv.imwrite("debug_img.png",  small_img)
        hue = hsv[:, :, 0]
        green_px = ((hue >= GREEN_HUE_LO[0]) & (hue <= GREEN_HUE_HI[0])).sum()
        print(f"Saved debug_mask.png — green pixels: {green_px:,} / {hue.size:,}")

    # --- Find contours and filter to tile-sized squares ---
    contours, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    img_area    = h * w
    print(f"Raw contours: {len(contours)}")

    candidates = []
    for cnt in contours:
        area = cv.contourArea(cnt)
        if not (img_area * MIN_AREA_FRAC <= area <= img_area * MAX_AREA_FRAC):
            continue
        rect = cv.minAreaRect(cnt)
        _, (rw, rh), _ = rect
        if min(rw, rh) < 1:
            continue
        if max(rw, rh) / min(rw, rh) > MAX_ASPECT:
            continue
        candidates.append((rect, cnt))

    if not candidates:
        print("No tiles found.")
        print("  — If tiles are mostly city (little green), increase CLOSE_PX.")
        print("  — Run with --debug to inspect debug_mask.png.")
        return 0

    print(f"Found {len(candidates)} tile candidates.")

    # --- Sort into rows then columns ---
    median_h = float(np.median([max(cv.minAreaRect(c[1])[1]) for c in candidates]))
    row_gap  = median_h * 0.5
    candidates.sort(key=lambda c: cv.minAreaRect(c[1])[0][1])

    rows: list = []
    current_row = [candidates[0]]
    for c in candidates[1:]:
        cy     = cv.minAreaRect(c[1])[0][1]
        row_cy = cv.minAreaRect(current_row[0][1])[0][1]
        if abs(cy - row_cy) < row_gap:
            current_row.append(c)
        else:
            current_row.sort(key=lambda c: cv.minAreaRect(c[1])[0][0])
            rows.append(current_row)
            current_row = [c]
    current_row.sort(key=lambda c: cv.minAreaRect(c[1])[0][0])
    rows.append(current_row)

    # --- Crop and save ---
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    count = 0
    for row in rows:
        for rect, _ in row:
            (cx, cy), (rw, rh), _ = rect
            half   = int(max(rw, rh) * CROP_MARGIN)
            cx_i, cy_i = int(cx), int(cy)
            x1 = max(0, cx_i - half); y1 = max(0, cy_i - half)
            x2 = min(w, cx_i + half); y2 = min(h, cy_i + half)
            crop = img[y1:y2, x1:x2]
            path = out / f"tile_{count:04d}.png"
            cv.imwrite(str(path), crop)
            print(f"  tile_{count:04d}.png  centre=({cx_i},{cy_i})  "
                  f"detected={int(max(rw,rh))}px  crop={x2-x1}x{y2-y1}")
            count += 1

    print(f"\nSaved {count} tiles to {out}/")
    return count


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python cv/auto_crop_tiles.py <photo.jpg> <output_dir> [--debug]")
        sys.exit(1)
    debug = "--debug" in sys.argv
    auto_crop_tiles(sys.argv[1], sys.argv[2], debug=debug)
