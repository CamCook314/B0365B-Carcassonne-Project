"""
calibrate_bias.py — Compute an embedding bias vector to correct for the
domain gap between studio reference photos and live Brio camera crops.

Usage:
    python cv/calibrate_bias.py

Workflow:
    1. Hold a Carcassonne tile in front of the camera (on its own, no board)
    2. Press SPACE to capture the current crop
    3. The top-8 matching reference tiles are shown alongside the capture
    4. Press 1-8 to confirm the correct match, or 's' to skip
    5. Repeat for 10-20 tiles for a stable bias estimate
    6. Press 'q' to compute the mean bias and save it to cv/bias.pt

The saved bias vector is automatically loaded by Project_CV at startup.
Re-run this script whenever lighting conditions change significantly.
"""

import cv2 as cv
import numpy as np
import torch
import sys, os
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cv import image_match
from cv.blob_pipeline import process_frame, find_contours
from cv.Project_CV import extract_tile_crop

ASSETS_DIR  = Path(__file__).parent.parent / "assets" / "tile_photos" / "edit"
BIAS_PATH   = Path(__file__).parent / "bias.pt"
TMP_CROP    = str(Path(__file__).parent / "_calib_tmp.png")

NUM_MATCHES = 8
THUMB_W     = 120   # Width of each reference thumbnail
THUMB_H     = 100   # Height of each reference thumbnail
THUMB_COLS  = 2     # Thumbnails arranged in 2 columns of 4
THUMB_ROWS  = NUM_MATCHES // THUMB_COLS   # = 4
CROP_DISP   = 320   # Width of the captured-crop panel


def _load_ref_thumb(tile_id: str) -> np.ndarray:
    path = ASSETS_DIR / f"{tile_id}.jpg"
    if path.exists():
        img = cv.imread(str(path))
        if img is not None:
            return cv.resize(img, (THUMB_W, THUMB_H))
    blank = np.zeros((THUMB_H, THUMB_W, 3), dtype=np.uint8)
    cv.putText(blank, "no image", (4, THUMB_H // 2),
               cv.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 100), 1)
    return blank


def _make_composite(crop_bgr: np.ndarray, matches: list) -> np.ndarray:
    """Left: captured crop.  Right: top-8 reference thumbnails in 2 columns of 4."""
    panel_h = THUMB_ROWS * THUMB_H   # total height of thumbnail block

    crop_r = cv.resize(crop_bgr, (CROP_DISP, CROP_DISP))
    cv.putText(crop_r, "Captured tile", (6, 22),
               cv.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 0), 1)
    cv.putText(crop_r, "Press 1-8  or  's' to skip", (6, CROP_DISP - 10),
               cv.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)
    # Pad crop to match thumbnail block height if needed
    if crop_r.shape[0] < panel_h:
        pad = np.zeros((panel_h - crop_r.shape[0], CROP_DISP, 3), dtype=np.uint8)
        crop_r = np.vstack([crop_r, pad])

    # Build two columns: indices 0-3 left, 4-7 right
    def make_thumb(i):
        score, tile_id = matches[i]
        thumb = _load_ref_thumb(tile_id)
        label = f"{i + 1}: {tile_id}  {score:.3f}"
        cv.putText(thumb, label, (3, 13), cv.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
        cv.rectangle(thumb, (0, 0), (THUMB_W - 1, THUMB_H - 1), (150, 150, 150), 1)
        return thumb

    col_a = np.vstack([make_thumb(i) for i in range(0, 4)])
    col_b = np.vstack([make_thumb(i) for i in range(4, min(8, len(matches)))])
    if col_b.shape[0] < col_a.shape[0]:
        pad = np.zeros((col_a.shape[0] - col_b.shape[0], THUMB_W, 3), dtype=np.uint8)
        col_b = np.vstack([col_b, pad])

    return np.hstack([crop_r, col_a, col_b])


def _save_bias(bias_pairs, path):
    bias = torch.stack(bias_pairs).mean(dim=0)
    torch.save(bias, str(path))
    print(f"\nBias vector saved to {path}")
    print(f"  Computed from {len(bias_pairs)} confirmed tile(s)")
    print(f"  Bias L2 norm: {bias.norm().item():.4f}")


def main():
    model, preprocess = image_match.model_setup()
    embeddings = image_match.load_embeddings()

    # Load existing bias for display — improves match scores shown to the user so
    # more tiles can be confirmed.  Bias pairs are still computed from raw (unbiased)
    # embeddings so the saved bias.pt is a clean independent estimate each run.
    display_bias = image_match.load_bias()

    cap = cv.VideoCapture(0)
    cap.set(cv.CAP_PROP_FRAME_WIDTH,  3840)
    cap.set(cv.CAP_PROP_FRAME_HEIGHT, 2160)
    if not cap.isOpened():
        print("Error: camera not opened")
        return

    actual_w = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera opened at {actual_w}x{actual_h}")

    PROC_W, PROC_H = 1920, 1080
    proc_scale = PROC_W / actual_w

    bias_pairs: list[torch.Tensor] = []
    win_live = "Calibration  (SPACE=capture  Q=save+quit)"

    print("\nInstructions:")
    print("  Hold one Carcassonne tile in front of the camera.")
    print("  Press SPACE to capture it.")
    print("  Then press 1–8 to confirm the correct match, or 's' to skip.")
    print("  Do 15–25 tiles, then press Q to compute and save the bias.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv.flip(frame, -1)

        proc_frame = cv.resize(frame, (PROC_W, PROC_H))
        _, _, blobs, _ = process_frame(proc_frame)
        valid = find_contours(blobs)

        display = proc_frame.copy()
        for cnt in valid:
            box = np.intp(cv.boxPoints(cv.minAreaRect(cnt)))
            cv.drawContours(display, [box], -1, (0, 255, 0), 2)

        cv.putText(display,
                   f"Confirmed: {len(bias_pairs)} pairs  |  SPACE=capture  Q=save+quit",
                   (10, 32), cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)
        cv.imshow(win_live, cv.resize(display, (960, 540)))

        key = cv.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        if key == ord(' '):
            if not valid:
                print("No tile detected — move the tile so it's clearly visible.")
                continue

            cnt  = max(valid, key=cv.contourArea)
            crop = extract_tile_crop(frame, cnt, proc_scale)
            cv.imwrite(TMP_CROP, crop)

            matches = image_match.match_image(TMP_CROP, model, preprocess, embeddings,
                                              bias=display_bias)
            composite = _make_composite(crop, matches)
            cv.imshow("Match Results", composite)
            cv.waitKey(1)

            print(f"\nTop {NUM_MATCHES} matches:")
            for i, (s, tid) in enumerate(matches[:NUM_MATCHES]):
                print(f"  {i + 1}: {tid}  ({s:.4f})")
            print(f"Press 1–{NUM_MATCHES} in the window to confirm, or 's' to skip.")

            while True:
                k = cv.waitKey(0) & 0xFF
                if ord('1') <= k <= ord('8'):
                    idx = k - ord('1')
                    if idx < len(matches):
                        score, correct_id = matches[idx]
                        ref_path  = str(ASSETS_DIR / f"{correct_id}.jpg")
                        query_emb = image_match.get_embedding(TMP_CROP, model, preprocess)
                        ref_emb   = image_match.get_embedding(ref_path,  model, preprocess)
                        bias_pairs.append(ref_emb - query_emb)
                        print(f"  -> Confirmed: {correct_id}  (score={score:.4f})  "
                              f"total pairs: {len(bias_pairs)}")
                        break
                elif k == ord('s'):
                    print("  -> Skipped.")
                    break

            cv.destroyWindow("Match Results")

    cap.release()
    cv.destroyAllWindows()

    if os.path.exists(TMP_CROP):
        os.remove(TMP_CROP)

    if not bias_pairs:
        print("\nNo pairs confirmed — bias not saved.")
        return

    _save_bias(bias_pairs, BIAS_PATH)


if __name__ == "__main__":
    main()
