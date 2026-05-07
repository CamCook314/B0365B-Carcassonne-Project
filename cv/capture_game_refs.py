"""
capture_game_refs.py — Capture in-situ game-style reference photos for every
tile rotation using the actual camera and board setup.

These references eliminate the domain gap between studio photos and live crops
because they go through the same camera, lighting, and crop pipeline as
gameplay tile crops — giving match_rotation a like-for-like comparison.

Usage:
    python cv/capture_game_refs.py

Workflow:
    1. Set up the board and camera exactly as for a real game (same tripod,
       same lighting, same table).
    2. Place a tile on an empty area of the board and hold it still.
    3. The live view shows a green box when a tile blob is detected.
    4. Press SPACE to capture the current crop.
    5. The top-8 family matches are shown alongside your capture.
       Press 1–8 to confirm the correct family.
       If the correct family isn't in the top 8, press 'm' and type the tile
       number in the terminal (e.g. 42 or ID42).
    6. The 4 studio rotation thumbnails are shown — press 0, 1, 2, or 3 to
       confirm which rotation you placed the tile in.
    7. Repeat for every tile × rotation you want to cover.  Each capture
       overwrites the previous game_ref for that ID.
    8. Press q to finish.  Run:
           python cv/image_match.py --dir cv/game_refs --augment
       to build cv/game_embeddings.pt from your captured photos.

You do NOT need all 336 tiles — even 40–60 commonly-used tiles noticeably
improve rotation detection.  The studio embeddings fill in as fallback for
any tile not yet captured in game style.
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

FOCUS_DISTANCE  = 14   # Match Project_CV.py; set to -1 to auto-discover
PROC_W, PROC_H  = 1920, 1080

ASSETS_DIR  = Path(__file__).parent.parent / "assets" / "tile_photos" / "edit"
GAME_DIR    = Path(__file__).parent / "game_refs"
TMP_CROP    = str(Path(__file__).parent / "_calib_tmp.png")

NUM_MATCHES = 8
THUMB_W, THUMB_H  = 120, 100
CROP_DISP         = 320
ROT_THUMB_W       = 160
ROT_THUMB_H       = 160


def _load_thumb(tile_id: str, w=THUMB_W, h=THUMB_H) -> np.ndarray:
    path = ASSETS_DIR / f"{tile_id}.jpg"
    if path.exists():
        img = cv.imread(str(path))
        if img is not None:
            return cv.resize(img, (w, h))
    blank = np.zeros((h, w, 3), dtype=np.uint8)
    cv.putText(blank, "no img", (4, h // 2), cv.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 100), 1)
    return blank


def _make_family_composite(crop_bgr: np.ndarray, matches: list,
                            captured: int) -> np.ndarray:
    """Crop on left, top-8 family thumbnails on right."""
    panel_h = (NUM_MATCHES // 2) * THUMB_H

    crop_r = cv.resize(crop_bgr, (CROP_DISP, CROP_DISP))
    cv.putText(crop_r, "Captured tile", (6, 22), cv.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 0), 1)
    cv.putText(crop_r, f"Saved: {captured}  |  SPACE=capture  q=quit",
               (6, CROP_DISP - 10), cv.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)
    if crop_r.shape[0] < panel_h:
        pad = np.zeros((panel_h - crop_r.shape[0], CROP_DISP, 3), dtype=np.uint8)
        crop_r = np.vstack([crop_r, pad])

    def make_thumb(i):
        score, tile_id = matches[i]
        thumb = _load_thumb(tile_id)
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


def _make_rotation_composite(crop_bgr: np.ndarray, family_base: int) -> np.ndarray:
    """Crop on left, the 4 studio rotation thumbnails on right labelled 0–3."""
    crop_r = cv.resize(crop_bgr, (CROP_DISP, CROP_DISP))
    cv.putText(crop_r, "Your tile", (6, 22), cv.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 0), 1)
    cv.putText(crop_r, "Press 0 1 2 3 for rotation", (6, CROP_DISP - 10),
               cv.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

    rot_thumbs = []
    for r in range(4):
        tid = f"ID{family_base + r}"
        thumb = _load_thumb(tid, w=ROT_THUMB_W, h=ROT_THUMB_H)
        cv.putText(thumb, f"rot {r} = {tid}", (4, 15),
                   cv.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 0), 1)
        cv.rectangle(thumb, (0, 0), (ROT_THUMB_W - 1, ROT_THUMB_H - 1), (150, 150, 150), 1)
        rot_thumbs.append(thumb)

    rot_col = np.vstack(rot_thumbs)
    # Pad crop to match rot column height
    if crop_r.shape[0] < rot_col.shape[0]:
        pad = np.zeros((rot_col.shape[0] - crop_r.shape[0], CROP_DISP, 3), dtype=np.uint8)
        crop_r = np.vstack([crop_r, pad])
    elif crop_r.shape[0] > rot_col.shape[0]:
        pad = np.zeros((crop_r.shape[0] - rot_col.shape[0], ROT_THUMB_W, 3), dtype=np.uint8)
        rot_col = np.vstack([rot_col, pad])

    return np.hstack([crop_r, rot_col])


def _uncaptured_families(embeddings: dict) -> set:
    """Return family base IDs that do NOT yet have all 4 rotations saved in GAME_DIR."""
    all_bases = {(int(p.stem.replace("ID", "")) // 4) * 4 for p in embeddings.keys()}
    return {base for base in all_bases
            if not all((GAME_DIR / f"ID{base + r}.jpg").exists() for r in range(4))}


def main():
    GAME_DIR.mkdir(exist_ok=True)

    model, preprocess = image_match.model_setup()
    embeddings        = image_match.load_embeddings()
    # Load existing game_embeddings for display if available (shows improved scores)
    display_game_embs = image_match.load_game_embeddings()
    bias              = image_match.load_bias()

    cap = cv.VideoCapture(0, cv.CAP_DSHOW)
    cap.set(cv.CAP_PROP_FRAME_WIDTH,  3840)
    cap.set(cv.CAP_PROP_FRAME_HEIGHT, 2160)
    cap.set(cv.CAP_PROP_AUTOFOCUS, 0)
    if FOCUS_DISTANCE >= 0:
        cap.set(cv.CAP_PROP_FOCUS, FOCUS_DISTANCE)

    if not cap.isOpened():
        print("ERROR: could not open camera")
        return

    actual_w  = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    actual_h  = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
    proc_scale = PROC_W / actual_w
    print(f"Camera: {actual_w}×{actual_h}  proc_scale={proc_scale:.3f}")

    saved_count  = len(list(GAME_DIR.glob("*.jpg")))
    uncaptured   = _uncaptured_families(embeddings)
    total_fams   = len({(int(p.stem.replace("ID", "")) // 4) * 4 for p in embeddings.keys()})
    done_fams    = total_fams - len(uncaptured)
    win_live = "Game Refs  |  SPACE=capture  q=quit"

    print("\nInstructions:")
    print("  Place a tile on the board in any rotation.")
    print("  Press SPACE to capture it.")
    print("  Confirm the family (1–8, or 'm' to type any ID manually) then the rotation (0–3).")
    print(f"  Crops saved to {GAME_DIR}")
    print(f"  Already captured: {saved_count} refs  |  Families complete: {done_fams}/{total_fams}\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv.flip(frame, -1)
        proc_frame = cv.resize(frame, (PROC_W, PROC_H))
        _, _, blobs, _ = process_frame(proc_frame)
        valid = find_contours(blobs)

        display = proc_frame.copy()
        detected_cnt = None
        if valid:
            detected_cnt = max(valid, key=cv.contourArea)
            box = np.intp(cv.boxPoints(cv.minAreaRect(detected_cnt)))
            cv.drawContours(display, [box], -1, (0, 255, 0), 2)

        done_fams = total_fams - len(uncaptured)
        cv.putText(display,
                   f"Saved: {saved_count}  Fams: {done_fams}/{total_fams}  |  "
                   f"{'Tile detected — SPACE to capture' if detected_cnt is not None else 'No tile detected'}",
                   (10, 32), cv.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)
        cv.imshow(win_live, cv.resize(display, (960, 540)))

        key = cv.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        if key == ord(' '):
            if detected_cnt is None:
                print("No tile detected — place a tile so it's clearly visible.")
                continue

            crop = extract_tile_crop(frame, detected_cnt, proc_scale)
            cv.imwrite(TMP_CROP, crop)

            # ── Step 1: confirm family ────────────────────────────────────────
            matches = image_match.match_image(TMP_CROP, model, preprocess, embeddings,
                                              bias=bias, game_embeddings=display_game_embs,
                                              remaining_families=uncaptured if uncaptured else None)
            composite = _make_family_composite(crop, matches, saved_count)
            cv.imshow("Step 1: Confirm family  (1-8 or 's' to skip)", composite)
            cv.waitKey(1)

            print(f"\nTop {NUM_MATCHES} family matches:")
            for i, (s, tid) in enumerate(matches[:NUM_MATCHES]):
                print(f"  {i + 1}: {tid}  ({s:.4f})")
            print(f"Press 1–{NUM_MATCHES} to confirm family, 'm' to enter ID manually, 's' to skip.")

            confirmed_family = None
            while True:
                k = cv.waitKey(0) & 0xFF
                if ord('1') <= k <= ord('8'):
                    idx = k - ord('1')
                    if idx < len(matches):
                        _, confirmed_family = matches[idx]
                        print(f"  Family confirmed: {confirmed_family}")
                        break
                elif k == ord('m'):
                    # Terminal input — lets user specify any tile ID not in the top 8
                    raw = input("  Enter tile number or ID (e.g. 42 or ID42): ").strip()
                    raw = raw.upper().replace("ID", "")
                    if raw.isdigit():
                        num = int(raw)
                        if 0 <= num <= 335:
                            # Snap to nearest family base so rotation is always rot0 start
                            confirmed_family = f"ID{num}"
                            print(f"  Family set manually: {confirmed_family}")
                            break
                        else:
                            print(f"  ID {num} out of range (0–335) — try again.")
                    else:
                        print("  Not recognised — enter a number like 42 or ID42.")
                elif k == ord('s'):
                    print("  Skipped.")
                    break

            cv.destroyWindow("Step 1: Confirm family  (1-8 or 's' to skip)")

            if confirmed_family is None:
                if os.path.exists(TMP_CROP):
                    os.remove(TMP_CROP)
                continue

            # ── Step 2: confirm rotation ──────────────────────────────────────
            family_base = (int(confirmed_family.replace("ID", "")) // 4) * 4
            rot_composite = _make_rotation_composite(crop, family_base)
            cv.imshow("Step 2: Confirm rotation  (0-3)", rot_composite)
            cv.waitKey(1)

            print(f"  Which rotation did you place the tile in?")
            print(f"  IDs: {family_base}=rot0  {family_base+1}=rot1  {family_base+2}=rot2  {family_base+3}=rot3")
            print(f"  Press 0, 1, 2, or 3.")

            confirmed_rotation = None
            while True:
                k = cv.waitKey(0) & 0xFF
                if ord('0') <= k <= ord('3'):
                    confirmed_rotation = k - ord('0')
                    print(f"  Rotation confirmed: {confirmed_rotation}")
                    break
                elif k == ord('s'):
                    print("  Skipped.")
                    break

            cv.destroyWindow("Step 2: Confirm rotation  (0-3)")

            if confirmed_rotation is None:
                if os.path.exists(TMP_CROP):
                    os.remove(TMP_CROP)
                continue

            # ── Save ──────────────────────────────────────────────────────────
            tile_id   = f"ID{family_base + confirmed_rotation}"
            save_path = GAME_DIR / f"{tile_id}.jpg"
            import shutil
            shutil.copy(TMP_CROP, str(save_path))
            saved_count += 1
            uncaptured = _uncaptured_families(embeddings)
            done_fams  = total_fams - len(uncaptured)
            print(f"  Saved → {save_path}  (total: {saved_count}  |  families complete: {done_fams}/{total_fams})")

            if os.path.exists(TMP_CROP):
                os.remove(TMP_CROP)

    cap.release()
    cv.destroyAllWindows()

    done_fams = total_fams - len(uncaptured)
    print(f"\nDone. {saved_count} game refs in {GAME_DIR}  ({done_fams}/{total_fams} families fully captured)")
    print("To build game_embeddings.pt, run:")
    print("  python cv/image_match.py --dir cv/game_refs --augment")


if __name__ == "__main__":
    main()
