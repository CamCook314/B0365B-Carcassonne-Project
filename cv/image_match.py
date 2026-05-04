## setup
import torch
import torch.nn.functional as F
import open_clip
from PIL import Image
from pathlib import Path
import platform
import pathlib
if platform.system() != 'Windows':
    pathlib.WindowsPath = pathlib.PosixPath
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def model_setup():
    model_name = 'ViT-B-32'
    pretrained_model = 'laion2b_s34b_b79k'
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained_model)
    model.eval()

    return (model, preprocess)

## convert image to embedding
# model and preprocess from model_setup()
def get_embedding(path: Path, model, preprocess) -> torch.Tensor:
    image = preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        emb = model.encode_image(image).squeeze(0)
    return F.normalize(emb, dim=0)

## preprocess all images in search dir
def preprocess_embeddings(model, preprocess) -> dict[Path, torch.Tensor]:
    search_dir = Path("assets/tile_photos/edit")
    embeddings = {}
    count = 0
    for img_path in sorted(search_dir.rglob("*.jpg")):
        try:
            embeddings[img_path] = get_embedding(img_path, model, preprocess)
            print(count, "success", img_path.stem)
            count += 1
        except Exception as e:
            print("failed", img_path, "->", e)
    return embeddings


## save embeddings
def save_embeddings(embeddings):
    torch.save(embeddings, "cv/embeddings.pt")

## load embeddings
def load_embeddings() -> dict[Path, torch.Tensor]:
    embeddings = torch.load("cv/embeddings.pt", weights_only=False)
    return embeddings

## load bias vector (returns None if cv/bias.pt does not exist)
def load_bias() -> torch.Tensor | None:
    bias_path = Path(__file__).parent / "bias.pt"
    if bias_path.exists():
        bias = torch.load(str(bias_path), weights_only=True)
        print(f"Loaded bias vector (norm={bias.norm().item():.4f})")
        return bias
    print("No bias.pt found — running without bias correction.")
    return None

## score images, return list of ranked results
# model and preprocess from model_setup()
# bias: optional tensor from load_bias(); shifts query embedding to match reference distribution
# Returns families ranked by the sum of their 4 rotation scores — more robust than ranking
# individual references because a genuine match scores consistently across all 4 rotations,
# while a false positive typically has one lucky high score and three low ones.
# Each result is (family_sum_score, best_rotation_id_within_family).
def match_image(path: str, model, preprocess, embeddings, bias=None) -> list[tuple[float, str]]:
    image = Image.open(path).convert("RGB")
    angles = [0, 90, 180, 270]

    query_embs = []
    for angle in angles:
        img = image.rotate(angle) if angle > 0 else image
        tensor = preprocess(img).unsqueeze(0)
        with torch.no_grad():
            emb = model.encode_image(tensor).squeeze(0)
        emb = F.normalize(emb, dim=0)
        if bias is not None:
            emb = F.normalize(emb + bias, dim=0)
        query_embs.append(emb)

    # Q: (4, D) — one row per query rotation.
    # scores[r, i] = dot(Q[r], ref[i]) → max over r gives best-aligned query per reference.
    Q = torch.stack(query_embs)
    ref_paths = list(embeddings.keys())
    R = torch.stack([embeddings[p] for p in ref_paths])   # (N, D)
    per_ref = (Q @ R.T).max(dim=0).values                 # (N,) rotation-invariant per ref

    # Aggregate: sum all 4 rotation scores within each family.
    # A genuine match has all 4 references scoring well; a false positive has one high
    # outlier and three low scores, so its family sum loses to the true family.
    family_sum  = {}   # family_base → cumulative score
    family_best = {}   # family_base → (best_individual_score, rid)
    for i, p in enumerate(ref_paths):
        rid  = p.stem
        base = (int(rid.replace("ID", "")) // 4) * 4
        s    = per_ref[i].item()
        family_sum[base]  = family_sum.get(base, 0.0) + s
        if base not in family_best or s > family_best[base][0]:
            family_best[base] = (s, rid)

    results = [(family_sum[base], family_best[base][1])
               for base in family_sum]
    results.sort(reverse=True)
    return results


def match_rotation(path: str, model, preprocess, embeddings, family_id: str,
                   bias=None) -> str:
    """Match a placed-tile crop against only the 4 rotations of the confirmed family.

    Unlike match_image, this does NOT augment rotations — we want the model to be
    rotation-sensitive so we can distinguish ID0/ID1/ID2/ID3 from each other.
    The crop should already be deskewed to the board's axis before calling this.

    Returns the specific tile ID string with the best rotation match, e.g. "ID9".
    Falls back to family_id if no candidates are found in the embedding store.
    """
    base = (int(family_id.replace("ID", "")) // 4) * 4
    candidates = {f"ID{base + r}" for r in range(4)}
    ref_paths = [p for p in embeddings.keys() if p.stem in candidates]
    if not ref_paths:
        print(f"  match_rotation: no embeddings found for family {family_id} — using family ID")
        return family_id

    image = Image.open(path).convert("RGB")
    tensor = preprocess(image).unsqueeze(0)
    with torch.no_grad():
        emb = model.encode_image(tensor).squeeze(0)
    emb = F.normalize(emb, dim=0)
    if bias is not None:
        emb = F.normalize(emb + bias, dim=0)

    R = torch.stack([embeddings[p] for p in ref_paths])
    scores = emb @ R.T
    ranked = sorted([(scores[i].item(), ref_paths[i].stem) for i in range(len(ref_paths))],
                    reverse=True)
    for score, rid in ranked:
        print(f"  {score:.4f}  {rid}")
    return ranked[0][1]


if __name__ == "__main__":
    # Run from project root:  python cv/image_match.py
    # Regenerates cv/embeddings.pt from assets/tile_photos/edit/
    print("Building embeddings from assets/tile_photos/edit/ ...")
    model, preprocess = model_setup()
    embeddings = preprocess_embeddings(model, preprocess)
    save_embeddings(embeddings)
    print(f"Saved {len(embeddings)} embeddings -> cv/embeddings.pt")
