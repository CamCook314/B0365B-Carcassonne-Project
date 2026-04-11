"""
generate_augmented_embeddings.py — Build camera-aware embeddings from reference tile images.

Applies random augmentations to each reference image to simulate real camera
conditions (perspective warp, lighting variation, blur, brown border from the
wood table visible at crop edges), then averages the embeddings across all
augmented versions. The result matches camera crops much better than
embeddings computed from clean studio images alone.

Usage (from project root, on main branch):
    python cv/generate_augmented_embeddings.py

Output: cv/embeddings_augmented.pt
Test:   python cv/test_match_crops.py cv/tile_crops_auto/ cv/embeddings_augmented.pt
"""

import sys
import random
import torch
import torch.nn.functional as F
import open_clip
import numpy as np
import cv2 as cv
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path

REFERENCE_DIR    = Path("assets/tile_photos/edit")
OUTPUT_PATH      = Path("cv/embeddings_augmented.pt")
NUM_AUGMENTS     = 10   # augmented versions per tile (+ 1 clean original)
BORDER_MAX_FRAC  = 0.12 # max brown border as fraction of tile size
WARP_MAX         = 0.04 # max perspective warp as fraction of tile size


# ---------------------------------------------------------------------------
# Augmentation helpers
# ---------------------------------------------------------------------------

def add_border(img: np.ndarray) -> np.ndarray:
    """Paste tile onto a random brown/wood-coloured canvas."""
    h, w = img.shape[:2]
    border = random.randint(0, int(min(w, h) * BORDER_MAX_FRAC))
    if border == 0:
        return img
    r = random.randint(80, 140)
    g = random.randint(55,  95)
    b = random.randint(30,  65)
    canvas = np.full((h + 2*border, w + 2*border, 3), (b, g, r), dtype=np.uint8)  # BGR
    canvas[border:border+h, border:border+w] = img
    return canvas


def perspective_warp(img: np.ndarray) -> np.ndarray:
    """Apply a slight random perspective distortion."""
    h, w = img.shape[:2]
    m = int(min(w, h) * WARP_MAX)

    def jitter(): return random.randint(-m, m)

    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([
        [jitter(), jitter()],
        [w + jitter(), jitter()],
        [w + jitter(), h + jitter()],
        [jitter(), h + jitter()],
    ])
    M = cv.getPerspectiveTransform(src, dst)
    return cv.warpPerspective(img, M, (w, h),
                              flags=cv.INTER_LINEAR,
                              borderMode=cv.BORDER_REPLICATE)


def augment(pil_img: Image.Image) -> Image.Image:
    """Apply a random combination of camera-simulation augmentations."""
    # Work in numpy/cv2 for perspective, then switch to PIL for colour
    img_bgr = cv.cvtColor(np.array(pil_img), cv.COLOR_RGB2BGR)

    # Brown border (wood table visible at crop edges)
    img_bgr = add_border(img_bgr)

    # Perspective warp
    if random.random() > 0.3:
        img_bgr = perspective_warp(img_bgr)

    img = Image.fromarray(cv.cvtColor(img_bgr, cv.COLOR_BGR2RGB))

    # Brightness
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.75, 1.25))
    # Contrast
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.80, 1.20))
    # Colour saturation
    img = ImageEnhance.Color(img).enhance(random.uniform(0.70, 1.30))
    # Sharpness / slight blur
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.30, 1.50))

    return img


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ref_images = sorted(REFERENCE_DIR.glob("*.jpg"))
    if not ref_images:
        print(f"No reference images found in {REFERENCE_DIR}")
        sys.exit(1)

    print(f"Found {len(ref_images)} reference images.")
    print(f"Generating {NUM_AUGMENTS} augmentations per tile ({NUM_AUGMENTS+1} embeddings averaged).\n")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading CLIP model on {device}...")
    model, _, preprocess = open_clip.create_model_and_transforms(
        'ViT-B-32', pretrained='laion2b_s34b_b79k')
    model = model.to(device)
    model.eval()

    embeddings: dict[Path, torch.Tensor] = {}

    for i, img_path in enumerate(ref_images):
        base_img = Image.open(img_path).convert('RGB')

        # Build batch: clean original + augmented versions
        variants = [preprocess(base_img)]
        for _ in range(NUM_AUGMENTS):
            variants.append(preprocess(augment(base_img)))

        batch = torch.stack(variants).to(device)
        with torch.no_grad():
            embs = model.encode_image(batch)
            embs = F.normalize(embs, dim=1)

        # Average across variants and re-normalise
        mean_emb = F.normalize(embs.mean(dim=0), dim=0).cpu()
        embeddings[img_path] = mean_emb

        print(f"  [{i+1:>3}/{len(ref_images)}] {img_path.stem}")

    torch.save(embeddings, str(OUTPUT_PATH))
    print(f"\nSaved → {OUTPUT_PATH}")
    print(f"Test with:")
    print(f"  python cv/test_match_crops.py cv/tile_crops_auto/ {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
