"""
Train a DINOv2 + MLP-head tile family classifier.

Strategy: extract all features once (backbone frozen), then train only the
MLP head on cached tensors — ~50× faster than re-running the backbone
every batch.  Use --refresh N to re-extract every N epochs so augmentation
provides genuinely fresh signal and the head doesn't memorise cached vectors.

Usage:
    python cv/train.py
    python cv/train.py --dir assets/tile_photos/edit --epochs 40 --augments 60
    python cv/train.py --refresh 5   (re-extract features every 5 epochs)

Output:
    cv/classifier_head.pt
"""
import argparse
import random
import re
import torch
import torch.nn as nn
from collections import defaultdict
from torch.utils.data import Dataset, DataLoader, TensorDataset
from torchvision import transforms as T
from PIL import Image
from pathlib import Path


class _RandomDegrade:
    """Simulate live-crop blur: downsample to a random small size then back up."""
    def __init__(self, min_px=56, max_px=112):
        self.min_px = min_px
        self.max_px = max_px

    def __call__(self, img):
        size = random.randint(self.min_px, self.max_px)
        w, h = img.size
        return img.resize((size, size), Image.BILINEAR).resize((w, h), Image.BILINEAR)


AUGMENT_TRAIN = T.Compose([
    T.RandomRotation(degrees=10),
    T.ColorJitter(brightness=0.40, contrast=0.40, saturation=0.15),
    T.RandomHorizontalFlip(),
    T.RandomPerspective(distortion_scale=0.15, p=0.5),
    _RandomDegrade(min_px=56, max_px=112),
    T.Resize(256, interpolation=T.InterpolationMode.BICUBIC),
    T.RandomCrop(224),
    T.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5)),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

CLEAN_PREPROCESS = T.Compose([
    T.Resize(256, interpolation=T.InterpolationMode.BICUBIC),
    T.CenterCrop(224),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class TileDataset(Dataset):
    def __init__(self, paths, labels, transform):
        self.samples = list(zip(paths, labels))
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        return self.transform(Image.open(path).convert("RGB")), label


def _build_split(image_dir, augments_per_image, extra_dirs=None):
    """Return (train_dataset, val_dataset, label_to_family, num_classes).

    Val:   last studio reference per family, no augmentation.
    Train: all other studio refs + all live crops, with AUGMENT_TRAIN.
    """
    studio_dir   = Path(image_dir)
    studio_paths = sorted(studio_dir.rglob("*.jpg"))
    if not studio_paths:
        raise FileNotFoundError(f"No .jpg files in {image_dir}")

    family_paths = defaultdict(list)
    for p in studio_paths:
        base = (int(re.sub(r"\D", "", p.stem)) // 4) * 4
        family_paths[base].append(p)

    families        = sorted(family_paths.keys())
    family_to_label = {f: i for i, f in enumerate(families)}
    label_to_family = {i: f for f, i in family_to_label.items()}
    num_classes     = len(families)

    train_paths, train_labels = [], []
    val_paths,   val_labels   = [], []

    for base, paths in family_paths.items():
        label = family_to_label[base]
        val_paths.append(paths[-1])
        val_labels.append(label)
        for p in paths[:-1]:
            train_paths.extend([p] * augments_per_image)
            train_labels.extend([label] * augments_per_image)

    # Live crops go to train only — never val
    live_dir  = Path(__file__).parent / "live_id_crops"
    live_dirs = [live_dir] if live_dir.exists() else []
    for d in (extra_dirs or []):
        d = Path(d)
        if d != live_dir and d.exists():
            live_dirs.append(d)

    live_count = 0
    for d in live_dirs:
        for p in sorted(d.rglob("*.jpg")):
            try:
                base = (int(re.sub(r"\D", "", p.stem)) // 4) * 4
            except ValueError:
                continue
            if base not in family_to_label:
                continue
            label = family_to_label[base]
            train_paths.extend([p] * augments_per_image)
            train_labels.extend([label] * augments_per_image)
            live_count += 1

    if live_count:
        print(f"  Including {live_count} live crops in training")

    train_ds = TileDataset(train_paths, train_labels, AUGMENT_TRAIN)
    val_ds   = TileDataset(val_paths,   val_labels,   CLEAN_PREPROCESS)
    return train_ds, val_ds, label_to_family, num_classes


def _extract_features(backbone, dataset, device, batch_size=64, desc=""):
    """Run backbone once over every sample; return (N, 768) features + labels."""
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    all_feats, all_labels = [], []
    total = len(dataset)
    done  = 0
    backbone.eval()
    with torch.no_grad():
        for imgs, labels in loader:
            imgs  = imgs.to(device)
            feats = backbone(pixel_values=imgs).last_hidden_state[:, 0, :]
            all_feats.append(feats.cpu())
            all_labels.append(labels)
            done += len(labels)
            print(f"\r  {desc}Extracting features {done}/{total} ({100*done/total:.0f}%)",
                  end="", flush=True)
    print()
    return torch.cat(all_feats), torch.cat(all_labels)


def _build_mlp(num_classes: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Linear(768, 256),
        nn.GELU(),
        nn.Dropout(0.3),
        nn.Linear(256, num_classes),
    )


def train(image_dir, out_path, epochs, augments, refresh):
    from transformers import AutoModel

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on {device}  (feature refresh every {refresh} epoch(s))")

    backbone = AutoModel.from_pretrained("facebook/dinov2-base").to(device)
    backbone.eval()
    for p in backbone.parameters():
        p.requires_grad = False

    train_ds, val_ds, label_to_family, num_classes = _build_split(image_dir, augments)
    print(f"  {num_classes} families  |  {len(train_ds)} train samples  |  {len(val_ds)} val samples")

    print("  Extracting val features (once)...")
    val_feats, val_labels = _extract_features(backbone, val_ds, device, desc="val ")
    val_feats   = val_feats.to(device)
    val_labels  = val_labels.to(device)

    head    = _build_mlp(num_classes).to(device)
    opt     = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss()

    best_val_acc = -1.0
    best_state   = None
    best_epoch   = 0
    loader       = None

    for epoch in range(1, epochs + 1):
        # Re-extract train features every `refresh` epochs (new random augments each time)
        if (epoch - 1) % refresh == 0:
            print(f"  [epoch {epoch}] Re-extracting train features with fresh augmentations...")
            train_feats, train_labels_t = _extract_features(backbone, train_ds, device, desc="train ")
            train_feats    = train_feats.to(device)
            train_labels_t = train_labels_t.to(device)
            loader = DataLoader(TensorDataset(train_feats, train_labels_t),
                                batch_size=256, shuffle=True)

        head.train()
        total_loss, correct, total = 0.0, 0, 0
        for f, lbl in loader:
            logits = head(f)
            loss   = loss_fn(logits, lbl)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += loss.item() * len(lbl)
            correct    += (logits.argmax(1) == lbl).sum().item()
            total      += len(lbl)

        head.eval()
        with torch.no_grad():
            val_logits  = head(val_feats)
            val_correct = (val_logits.argmax(1) == val_labels).sum().item()
            val_acc     = val_correct / len(val_labels)

        marker = ""
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state   = {k: v.cpu().clone() for k, v in head.state_dict().items()}
            best_epoch   = epoch
            marker       = "  ← best"

        print(f"  epoch {epoch:3d}/{epochs}  loss={total_loss/total:.4f}"
              f"  train_acc={correct/total:.3f}  val_acc={val_acc:.3f}{marker}")

    backbone.cpu()
    del backbone
    if device.type == "cuda":
        torch.cuda.empty_cache()

    print(f"Best val_acc={best_val_acc:.3f} at epoch {best_epoch} — saving that checkpoint.")
    torch.save({
        "architecture":    "mlp",
        "head_state_dict": best_state,
        "label_to_family": label_to_family,
        "num_classes":     num_classes,
    }, out_path)
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir",      default="assets/tile_photos/edit")
    parser.add_argument("--out",      default="cv/classifier_head.pt")
    parser.add_argument("--epochs",   type=int, default=50)
    parser.add_argument("--augments", type=int, default=70)
    parser.add_argument("--refresh",  type=int, default=5,
                        help="Re-extract train features every N epochs (default 5)")
    args = parser.parse_args()
    train(args.dir, args.out, args.epochs, args.augments, args.refresh)
