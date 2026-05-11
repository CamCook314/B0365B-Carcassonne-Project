## setup
import torch
import torch.nn.functional as F
import open_clip
from PIL import Image, ImageEnhance
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


def _get_augmented_embedding(path: Path, model, preprocess) -> torch.Tensor:
    """Mean embedding over 5 photometric variants — more robust reference centre."""
    base_img = Image.open(path).convert("RGB")
    variants = [
        base_img,
        ImageEnhance.Brightness(base_img).enhance(0.85),
        ImageEnhance.Brightness(base_img).enhance(1.15),
        ImageEnhance.Contrast(base_img).enhance(0.80),
        ImageEnhance.Contrast(base_img).enhance(1.20),
    ]
    embs = []
    for img in variants:
        tensor = preprocess(img).unsqueeze(0)
        with torch.no_grad():
            emb = model.encode_image(tensor).squeeze(0)
        embs.append(F.normalize(emb, dim=0))
    mean_emb = torch.stack(embs).mean(dim=0)
    return F.normalize(mean_emb, dim=0)


## preprocess all images in search dir
def preprocess_embeddings(model, preprocess, search_dir=None,
                          augment=False) -> dict[Path, torch.Tensor]:
    if search_dir is None:
        search_dir = Path("assets/tile_photos/edit")
    else:
        search_dir = Path(search_dir)
    embeddings = {}
    count = 0
    for img_path in sorted(search_dir.rglob("*.jpg")):
        try:
            if augment:
                embeddings[img_path] = _get_augmented_embedding(img_path, model, preprocess)
            else:
                embeddings[img_path] = get_embedding(img_path, model, preprocess)
            label = "aug" if augment else "ok"
            print(count, label, img_path.stem)
            count += 1
        except Exception as e:
            print("failed", img_path, "->", e)
    return embeddings


## save embeddings
def save_embeddings(embeddings, path="cv/embeddings.pt"):
    torch.save(embeddings, path)

## load embeddings
def load_embeddings() -> dict[Path, torch.Tensor]:
    embeddings = torch.load("cv/embeddings.pt", weights_only=False)
    return embeddings

## load game-style reference embeddings (returns None if cv/game_embeddings.pt does not exist)
def load_game_embeddings() -> dict[Path, torch.Tensor] | None:
    game_path = Path(__file__).parent / "game_embeddings.pt"
    if game_path.exists():
        embs = torch.load(str(game_path), weights_only=False)
        print(f"Loaded game embeddings ({len(embs)} refs)")
        return embs
    return None

## load bias vector (returns None if cv/bias.pt does not exist)
def load_bias() -> torch.Tensor | None:
    bias_path = Path(__file__).parent / "bias.pt"
    if bias_path.exists():
        bias = torch.load(str(bias_path), weights_only=True)
        print(f"Loaded bias vector (norm={bias.norm().item():.4f})")
        return bias
    print("No bias.pt found — running without bias correction.")
    return None


def load_classifier() -> dict | None:
    """Load trained classifier head (linear or MLP). Returns None if cv/classifier_head.pt doesn't exist."""
    path = Path(__file__).parent / "classifier_head.pt"
    if not path.exists():
        return None
    ckpt = torch.load(str(path), weights_only=True)
    num_classes = ckpt["num_classes"]
    if ckpt.get("architecture") == "mlp":
        head = torch.nn.Sequential(
            torch.nn.Linear(768, 256),
            torch.nn.GELU(),
            torch.nn.Dropout(0.3),
            torch.nn.Linear(256, num_classes),
        )
        head.load_state_dict(ckpt["head_state_dict"])
        print(f"Loaded MLP classifier head ({num_classes} families)")
    else:
        head = torch.nn.Linear(768, num_classes)
        head.weight.data = ckpt["weight"]
        head.bias.data   = ckpt["bias"]
        print(f"Loaded linear classifier head ({num_classes} families)")
    head.eval()
    return {"head": head, "label_to_family": ckpt["label_to_family"]}


_dino_backbone   = None
_dino_preprocess = None

def _get_dino_backbone():
    """Lazy-load DINOv2-base backbone for classifier inference (cached after first call)."""
    global _dino_backbone, _dino_preprocess
    if _dino_backbone is None:
        from transformers import AutoModel
        from torchvision import transforms as T
        print("[image_match] Loading DINOv2-base backbone for classifier inference...")
        _dino_backbone = AutoModel.from_pretrained("facebook/dinov2-base")
        _dino_backbone.eval()
        for p in _dino_backbone.parameters():
            p.requires_grad = False
        _dino_preprocess = T.Compose([
            T.Resize(256, interpolation=T.InterpolationMode.BICUBIC),
            T.CenterCrop(224),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        print("[image_match] DINOv2 backbone ready.")
    return _dino_backbone, _dino_preprocess


def match_image_classifier(path: str, classifier: dict,
                            remaining_families: set | None = None) -> list[tuple[float, str]]:
    """Classify a tile image using the trained DINOv2+MLP head.

    Averages logits over all 4 rotations (rotation-invariant family ID).
    Returns [(prob, tile_id), ...] in the same format as match_image.
    tile_id is the family base ID e.g. 'ID0', 'ID4'.
    """
    backbone, dino_pre = _get_dino_backbone()
    head            = classifier["head"]
    label_to_family = classifier["label_to_family"]

    image = Image.open(path).convert("RGB")
    logits_sum = None
    for angle in [0, 90, 180, 270]:
        img    = image.rotate(angle) if angle > 0 else image
        tensor = dino_pre(img).unsqueeze(0)
        with torch.no_grad():
            feats  = backbone(pixel_values=tensor).last_hidden_state[:, 0, :]
            logits = head(feats).squeeze(0)
        logits_sum = logits if logits_sum is None else logits_sum + logits

    probs = F.softmax(logits_sum, dim=0)

    results = []
    for label_idx, prob in enumerate(probs):
        family_base = label_to_family[label_idx]
        if remaining_families is not None and family_base not in remaining_families:
            continue
        results.append((prob.item(), f"ID{family_base}"))

    results.sort(reverse=True)
    return results


def _score_query_vs_embeddings(Q: torch.Tensor,
                                emb_dict: dict[Path, torch.Tensor]) -> dict[str, float]:
    """Score 4-rotation query Q (4, D) against an embedding dict.

    Returns {id_stem -> best_rotation_score} for every key in emb_dict.
    """
    ref_paths = list(emb_dict.keys())
    R = torch.stack([emb_dict[p] for p in ref_paths])   # (N, D)
    per_ref = (Q @ R.T).max(dim=0).values                # (N,) max over query rotations
    return {p.stem: per_ref[i].item() for i, p in enumerate(ref_paths)}


## score images, return list of ranked results
# model and preprocess from model_setup()
# bias: optional tensor from load_bias(); shifts query embedding to match reference distribution
# game_embeddings: optional dict from load_game_embeddings(); scored alongside studio embeddings.
#   Per-ID score = max(studio, game) so the better-matching domain wins each rotation candidate.
# Returns families ranked by the sum of their 4 rotation scores — more robust than ranking
# individual references because a genuine match scores consistently across all 4 rotations,
# while a false positive typically has one lucky high score and three low ones.
# Each result is (family_sum_score, best_rotation_id_within_family).
def match_image(path: str, model, preprocess, embeddings, bias=None,
                game_embeddings=None,
                remaining_families: set | None = None) -> list[tuple[float, str]]:
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

    Q = torch.stack(query_embs)   # (4, D)

    studio_scores = _score_query_vs_embeddings(Q, embeddings)
    if game_embeddings is not None:
        game_scores = _score_query_vs_embeddings(Q, game_embeddings)
        all_ids = set(studio_scores) | set(game_scores)
        per_id = {rid: max(studio_scores.get(rid, -1.0),
                           game_scores.get(rid, -1.0))
                  for rid in all_ids}
    else:
        per_id = studio_scores

    # Restrict to families still in the tile bag (when bridge provides this info).
    if remaining_families is not None:
        per_id = {rid: s for rid, s in per_id.items()
                  if (int(rid.replace("ID", "")) // 4) * 4 in remaining_families}

    # Aggregate by family: sum 4 rotation scores; track best individual rotation.
    family_sum  = {}
    family_best = {}
    for rid, s in per_id.items():
        base = (int(rid.replace("ID", "")) // 4) * 4
        family_sum[base]  = family_sum.get(base, 0.0) + s
        if base not in family_best or s > family_best[base][0]:
            family_best[base] = (s, rid)

    results = [(family_sum[base], family_best[base][1])
               for base in family_sum]
    results.sort(reverse=True)
    return results


def match_rotation(path: str, model, preprocess, embeddings, family_id: str,
                   bias=None, game_embeddings=None) -> tuple[str, float]:
    """Match a placed-tile crop against only the 4 rotations of the confirmed family.

    Unlike match_image, this does NOT augment rotations — we want the model to be
    rotation-sensitive so we can distinguish ID0/ID1/ID2/ID3 from each other.
    The crop should already be deskewed to the board's axis before calling this.

    If game_embeddings are provided, per-rotation score = max(studio, game) so
    the better-matching domain wins.

    Returns (tile_id, confidence_score).  tile_id falls back to family_id if no
    candidates are found in the embedding store.
    """
    base = (int(family_id.replace("ID", "")) // 4) * 4
    candidates = {f"ID{base + r}" for r in range(4)}

    studio_refs = {p: embeddings[p] for p in embeddings if p.stem in candidates}
    game_refs   = ({p: game_embeddings[p]
                    for p in game_embeddings if p.stem in candidates}
                   if game_embeddings is not None else {})

    if not studio_refs and not game_refs:
        print(f"  match_rotation: no embeddings found for family {family_id} — using family ID")
        return family_id, 0.0

    image = Image.open(path).convert("RGB")
    tensor = preprocess(image).unsqueeze(0)
    with torch.no_grad():
        emb = model.encode_image(tensor).squeeze(0)
    emb = F.normalize(emb, dim=0)
    if bias is not None:
        emb = F.normalize(emb + bias, dim=0)

    # Collect per-rotation scores from both sources; take max per rotation ID.
    rot_scores: dict[str, float] = {}

    if studio_refs:
        R = torch.stack([studio_refs[p] for p in studio_refs])
        scores = emb @ R.T
        for i, p in enumerate(studio_refs):
            rid = p.stem
            rot_scores[rid] = max(rot_scores.get(rid, -1.0), scores[i].item())

    if game_refs:
        R = torch.stack([game_refs[p] for p in game_refs])
        scores = emb @ R.T
        for i, p in enumerate(game_refs):
            rid = p.stem
            rot_scores[rid] = max(rot_scores.get(rid, -1.0), scores[i].item())

    ranked = sorted(rot_scores.items(), key=lambda x: x[1], reverse=True)
    for rid, score in ranked:
        print(f"  {score:.4f}  {rid}")

    best_id, best_score = ranked[0]
    return best_id, best_score


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build CLIP embeddings for tile reference photos")
    parser.add_argument("--augment", action="store_true",
                        help="Mean-pool 5 photometric variants per image for a more robust reference")
    parser.add_argument("--dir", default=None,
                        help="Source image directory (default: assets/tile_photos/edit)")
    parser.add_argument("--out", default=None,
                        help="Output .pt path (default: cv/embeddings.pt, or cv/game_embeddings.pt when --dir is set)")
    args = parser.parse_args()

    src = args.dir or "assets/tile_photos/edit"
    if args.out:
        out = args.out
    elif args.dir:
        out = "cv/game_embeddings.pt"
    else:
        out = "cv/embeddings.pt"

    label = "augmented " if args.augment else ""
    print(f"Building {label}embeddings from {src} → {out} ...")
    model, preprocess = model_setup()
    embeddings = preprocess_embeddings(model, preprocess, search_dir=src, augment=args.augment)
    save_embeddings(embeddings, path=out)
    print(f"Saved {len(embeddings)} embeddings → {out}")
