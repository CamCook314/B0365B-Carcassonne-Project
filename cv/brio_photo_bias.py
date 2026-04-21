"""
brio_photo_bias.py — Compute a bias vector from pre-photographed Brio images.

This is more accurate than live-camera calibration because you can photograph
each tile under controlled conditions, take multiple shots, and confirm at your
own pace without the camera running.

Usage:
    1. Photograph individual tiles flat on the table under normal game lighting.
       One tile per photo.  Save them to cv/brio_photos/ (jpg or png).
    2. Run:
           python cv/brio_photo_bias.py
       Optionally pass a different photo directory:
           python cv/brio_photo_bias.py --dir path/to/photos

For each photo the top-8 reference matches are shown side-by-side.
Press 1-8 to confirm the correct match, 's' to skip, 'q' to quit and save.

Bias is saved to cv/bias.pt and loaded automatically by Project_CV at startup.
"""

import cv2 as cv
import numpy as np
import torch
import sys, os, argparse
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cv import image_match

ASSETS_DIR   = Path(__file__).parent.parent / "assets" / "tile_photos" / "edit"
BIAS_PATH    = Path(__file__).parent / "bias.pt"
DEFAULT_DIR  = Path(__file__).parent / "brio_photos"
IMG_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}

NUM_MATCHES  = 8
THUMB_W      = 120
THUMB_H      = 100
PHOTO_DISP   = 320   # Display size for the Brio photo panel


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


def _make_composite(photo_bgr: np.ndarray, filename: str,
                    matches: list, confirmed: int, total: int) -> np.ndarray:
    """Left: Brio photo.  Right: top-8 reference thumbnails in 2 columns of 4."""
    panel_h = (NUM_MATCHES // 2) * THUMB_H   # 4 rows × THUMB_H

    photo_r = cv.resize(photo_bgr, (PHOTO_DISP, PHOTO_DISP))
    cv.putText(photo_r, os.path.basename(filename), (6, 20),
               cv.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)
    cv.putText(photo_r, f"Confirmed {confirmed}/{total}", (6, 40),
               cv.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    cv.putText(photo_r, "Press 1-8  or  's'  or  'q'", (6, PHOTO_DISP - 10),
               cv.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    if photo_r.shape[0] < panel_h:
        pad = np.zeros((panel_h - photo_r.shape[0], PHOTO_DISP, 3), dtype=np.uint8)
        photo_r = np.vstack([photo_r, pad])

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

    return np.hstack([photo_r, col_a, col_b])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=str(DEFAULT_DIR),
                        help="Directory containing Brio tile photos")
    args = parser.parse_args()

    photo_dir = Path(args.dir)
    if not photo_dir.exists():
        photo_dir.mkdir(parents=True)
        print(f"Created {photo_dir}  — add your Brio tile photos there and re-run.")
        return

    photos = sorted(p for p in photo_dir.iterdir()
                    if p.suffix.lower() in IMG_SUFFIXES)
    if not photos:
        print(f"No images found in {photo_dir}")
        print(f"  Add jpg/png photos of individual tiles and re-run.")
        return

    print(f"Found {len(photos)} photo(s) in {photo_dir}")

    model, preprocess = image_match.model_setup()
    embeddings = image_match.load_embeddings()
    display_bias = image_match.load_bias()

    bias_pairs: list[torch.Tensor] = []
    quit_early = False

    for idx, photo_path in enumerate(photos):
        img = cv.imread(str(photo_path))
        if img is None:
            print(f"  Could not read {photo_path.name} — skipping.")
            continue

        # Save to temp path so get_embedding can read it
        tmp = str(photo_dir / "_tmp_brio.png")
        cv.imwrite(tmp, img)

        matches = image_match.match_image(tmp, model, preprocess, embeddings,
                                          bias=display_bias)

        composite = _make_composite(img, photo_path.name, matches,
                                    len(bias_pairs), len(photos))
        cv.imshow("Brio Photo Bias", composite)
        cv.waitKey(1)

        print(f"\n[{idx + 1}/{len(photos)}]  {photo_path.name}")
        print(f"  Top {NUM_MATCHES} matches:")
        for i, (s, tid) in enumerate(matches[:NUM_MATCHES]):
            print(f"    {i + 1}: {tid}  ({s:.4f})")
        print(f"  Press 1–8 to confirm, 's' to skip, 'q' to quit and save.")

        while True:
            k = cv.waitKey(0) & 0xFF
            if ord('1') <= k <= ord('8'):
                i = k - ord('1')
                if i < len(matches):
                    score, correct_id = matches[i]
                    ref_path  = str(ASSETS_DIR / f"{correct_id}.jpg")
                    query_emb = image_match.get_embedding(tmp, model, preprocess)
                    ref_emb   = image_match.get_embedding(ref_path, model, preprocess)
                    bias_pairs.append(ref_emb - query_emb)
                    print(f"  -> Confirmed: {correct_id}  (score={score:.4f})  "
                          f"total pairs: {len(bias_pairs)}")
                    break
            elif k == ord('s'):
                print("  -> Skipped.")
                break
            elif k == ord('q'):
                quit_early = True
                break

        if os.path.exists(tmp):
            os.remove(tmp)

        if quit_early:
            break

    cv.destroyAllWindows()

    if not bias_pairs:
        print("\nNo pairs confirmed — bias not saved.")
        return

    bias = torch.stack(bias_pairs).mean(dim=0)
    torch.save(bias, str(BIAS_PATH))
    print(f"\nBias vector saved to {BIAS_PATH}")
    print(f"  Computed from {len(bias_pairs)} confirmed tile(s)")
    print(f"  Bias L2 norm: {bias.norm().item():.4f}")


if __name__ == "__main__":
    main()
