"""
calibrate_blob.py — Live interactive tuner for blob_pipeline parameters.

Run with:
    python cv/calibrate_blob.py

Controls:
    Trackbars  — adjust parameters and see the effect immediately
    s          — save current values to cv/config.json
    r          — reset all sliders to blob_pipeline.py defaults
    q / Esc    — quit

The saved config.json is loaded by blob_pipeline.py at import time, so the
main CV pipeline picks up the new values on next run (no code changes needed).
"""

import cv2 as cv
import numpy as np
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

FOCUS_DISTANCE = 14
CAM_INDEX      = 0
DISPLAY_W      = 960   # width of each panel in the composite display
DISPLAY_H      = 540

CFG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# ── Defaults (must match blob_pipeline.py hardcoded values) ──────────────────
DEFAULTS = {
    "CANNY_LOW":          30,
    "CANNY_HIGH":         80,
    "DENSITY_THRESHOLD":  10,
    "SAT_THRESHOLD":      90,
    "MORPH_CLOSE_KERNEL": 45,
}

WIN = "Blob Calibration  |  s=save  r=reset  q=quit"


def _odd(v):
    """Return v rounded up to the nearest odd integer (≥ 1)."""
    v = max(1, int(v))
    return v if v % 2 == 1 else v + 1


def _nothing(_):
    pass


def _init_trackbars():
    cv.createTrackbar("Canny high",       WIN, DEFAULTS["CANNY_HIGH"],         200, _nothing)
    cv.createTrackbar("Canny low",        WIN, DEFAULTS["CANNY_LOW"],          100, _nothing)
    cv.createTrackbar("Edge density thr", WIN, DEFAULTS["DENSITY_THRESHOLD"],   30, _nothing)
    cv.createTrackbar("Sat threshold",    WIN, DEFAULTS["SAT_THRESHOLD"],       255, _nothing)
    cv.createTrackbar("Morph close",      WIN, DEFAULTS["MORPH_CLOSE_KERNEL"], 120, _nothing)


def _read_trackbars():
    return {
        "CANNY_HIGH":         cv.getTrackbarPos("Canny high",       WIN),
        "CANNY_LOW":          cv.getTrackbarPos("Canny low",        WIN),
        "DENSITY_THRESHOLD":  cv.getTrackbarPos("Edge density thr", WIN),
        "SAT_THRESHOLD":      cv.getTrackbarPos("Sat threshold",    WIN),
        "MORPH_CLOSE_KERNEL": cv.getTrackbarPos("Morph close",      WIN),
    }


def _reset_trackbars():
    cv.setTrackbarPos("Canny high",       WIN, DEFAULTS["CANNY_HIGH"])
    cv.setTrackbarPos("Canny low",        WIN, DEFAULTS["CANNY_LOW"])
    cv.setTrackbarPos("Edge density thr", WIN, DEFAULTS["DENSITY_THRESHOLD"])
    cv.setTrackbarPos("Sat threshold",    WIN, DEFAULTS["SAT_THRESHOLD"])
    cv.setTrackbarPos("Morph close",      WIN, DEFAULTS["MORPH_CLOSE_KERNEL"])


def _process(frame, p):
    blur_k  = 11
    density_blur = 21
    open_k  = 7

    grey    = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    blurred = cv.GaussianBlur(grey, (_odd(blur_k), _odd(blur_k)), 0)

    canny_high = max(1, p["CANNY_HIGH"])
    canny_low  = min(p["CANNY_LOW"], canny_high - 1)
    edges   = cv.Canny(blurred, canny_low, canny_high)

    density = cv.GaussianBlur(edges, (_odd(density_blur), _odd(density_blur)), 0)
    _, edge_blobs = cv.threshold(density, max(1, p["DENSITY_THRESHOLD"]), 255, cv.THRESH_BINARY)

    hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
    _, sat_blobs = cv.threshold(hsv[:, :, 1], p["SAT_THRESHOLD"], 255, cv.THRESH_BINARY)

    blobs = cv.bitwise_or(edge_blobs, sat_blobs)
    ok    = _odd(open_k)
    ck    = _odd(max(3, p["MORPH_CLOSE_KERNEL"]))
    blobs = cv.morphologyEx(blobs, cv.MORPH_OPEN,  cv.getStructuringElement(cv.MORPH_RECT, (ok, ok)))
    blobs = cv.morphologyEx(blobs, cv.MORPH_CLOSE, cv.getStructuringElement(cv.MORPH_RECT, (ck, ck)))

    return edges, blobs


def _build_display(frame, edges, blobs):
    h, w = frame.shape[:2]

    # Panel 1: edges (grey → BGR)
    edge_bgr  = cv.cvtColor(edges, cv.COLOR_GRAY2BGR)
    # Panel 2: blobs (grey → BGR)
    blob_bgr  = cv.cvtColor(blobs, cv.COLOR_GRAY2BGR)
    # Panel 3: camera with contours overlaid
    overlay   = frame.copy()
    cnts, _   = cv.findContours(blobs, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        area = cv.contourArea(c)
        if area < 3000:
            continue
        _, _, cw, ch = cv.boundingRect(c)
        ratio = max(cw, ch) / max(min(cw, ch), 1)
        colour = (0, 255, 0) if ratio <= 3.0 else (0, 0, 255)  # green=valid, red=rejected
        cv.drawContours(overlay, [c], -1, colour, 2)

    # Stack panels side-by-side, resized for display
    dw, dh = DISPLAY_W, DISPLAY_H
    p1 = cv.resize(edge_bgr, (dw, dh))
    p2 = cv.resize(blob_bgr, (dw, dh))
    p3 = cv.resize(overlay,  (dw, dh))

    # Add labels
    for img, label in [(p1, "Edges"), (p2, "Blobs"), (p3, "Contours (green=valid)")]:
        cv.putText(img, label, (10, 30), cv.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

    return np.hstack([p1, p2, p3])


def _save(p):
    # Merge with any existing config keys we don't expose (e.g. TILE_AREA_MIN)
    existing = {}
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH) as f:
            existing = json.load(f)
    existing.update(p)
    with open(CFG_PATH, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"[calibrate] Saved to {CFG_PATH}")
    for k, v in p.items():
        print(f"  {k}: {v}")


def main():
    cap = cv.VideoCapture(CAM_INDEX)
    cap.set(cv.CAP_PROP_FRAME_WIDTH,  3840)
    cap.set(cv.CAP_PROP_FRAME_HEIGHT, 2160)
    cap.set(cv.CAP_PROP_AUTOFOCUS, 0)
    if FOCUS_DISTANCE >= 0:
        cap.set(cv.CAP_PROP_FOCUS, FOCUS_DISTANCE)

    if not cap.isOpened():
        print("ERROR: could not open camera")
        return

    cv.namedWindow(WIN, cv.WINDOW_NORMAL)
    cv.resizeWindow(WIN, DISPLAY_W * 3, DISPLAY_H + 120)  # +120 for trackbar area
    _init_trackbars()

    # If config.json exists, load its values into the trackbars
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH) as f:
            saved = json.load(f)
        for tb, key in [("Canny high", "CANNY_HIGH"), ("Canny low", "CANNY_LOW"),
                        ("Edge density thr", "DENSITY_THRESHOLD"),
                        ("Sat threshold", "SAT_THRESHOLD"),
                        ("Morph close", "MORPH_CLOSE_KERNEL")]:
            if key in saved:
                cv.setTrackbarPos(tb, WIN, int(saved[key]))
        print(f"[calibrate] Loaded existing config from {CFG_PATH}")

    print("Controls: s=save  r=reset to defaults  q/Esc=quit")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("ERROR: frame read failed")
            break
        frame = cv.flip(frame, -1)

        p       = _read_trackbars()
        edges, blobs = _process(frame, p)
        display = _build_display(frame, edges, blobs)
        cv.imshow(WIN, display)

        key = cv.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        elif key == ord('s'):
            _save(p)
        elif key == ord('r'):
            _reset_trackbars()
            print("[calibrate] Reset to defaults")

    cap.release()
    cv.destroyAllWindows()


if __name__ == "__main__":
    main()
