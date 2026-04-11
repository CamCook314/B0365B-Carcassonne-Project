"""
test_match_crops.py — Quick test of image_match against saved tile crops.

Usage (from project root, on main branch):
    python cv/test_match_crops.py <crops_dir> [embeddings_path]

    crops_dir       — folder of PNG crops to test (default: cv/tile_crops)
    embeddings_path — path to embeddings .pt file (default: cv/embeddings.pt)

Prints the top 3 matches for each crop so you can verify whether the
edited-reference embeddings correctly identify real-camera crops.
"""

import sys
import torch
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent))
import image_match

TOP_N = 3


def main():
    crops_dir  = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("cv/tile_crops")
    embed_path = sys.argv[2] if len(sys.argv) > 2 else None

    crops = sorted(crops_dir.glob("*.png"))
    if not crops:
        print(f"No PNG files found in {crops_dir}")
        return

    print("Loading model and embeddings...")
    model, preprocess = image_match.model_setup()
    if embed_path:
        embeddings = torch.load(embed_path, weights_only=False)
    else:
        embeddings = image_match.load_embeddings()
    print(f"Loaded {len(embeddings)} reference embeddings.\n")

    for crop in crops:
        results = image_match.match_image(str(crop), model, preprocess, embeddings)
        print(f"{crop.name}:")
        for score, ref_path in results[:TOP_N]:
            stem = Path(ref_path).stem
            print(f"  {score:.4f}  {stem}")
        print()


if __name__ == "__main__":
    main()
