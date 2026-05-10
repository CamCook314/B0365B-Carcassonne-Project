"""
train_rotation.py — Train a ResNet-18 to classify tile rotation (0, 1, 2, 3).

Usage:
    python cv/train_rotation.py
    python cv/train_rotation.py --epochs 40 --lr 0.0005
    python cv/train_rotation.py --eval-only   # test an existing checkpoint

Outputs:
    cv/rotation_model.pth   — best checkpoint (use with rotation_classifier.py)

Data sources (auto-discovered):
    assets/tile_photos/edit/   — studio reference shots  (ID0.jpg … ID335.jpg)
    cv/game_refs/              — in-situ game captures   (same naming, optional)

Label = ID_number % 4  →  rotation 0, 1, 2, or 3.

Key design points:
  * NO horizontal/vertical flips — they invalidate the rotation label.
  * On-the-fly 90°-multiple rotation augmentation: each training sample is
    randomly rotated by k*90° (k in {0,1,2,3}) and the label is shifted by k.
    This gives perfectly-correct extra labels and ~4x effective data.
  * ±10° rotation jitter for minor board-misalignment robustness.
  * Stratified train/val split per rotation class so val accuracy is meaningful.
"""

import os, sys, argparse, random
from pathlib import Path
from collections import defaultdict, Counter

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from torchvision.transforms import functional as TF
from PIL import Image
import numpy as np

# path
ROOT = Path(__file__).resolve().parent.parent
STUDIO_DIR  = ROOT / "assets" / "tile_photos" / "edit"
GAME_DIR = ROOT / "cv" / "game_refs"
OUT_MODEL = ROOT / "cv" / "rotation_model.pth"

# hyperparameters
IMG_SIZE = 224
BATCH_SIZE = 16
EPOCHS = 50
LR = 1e-3
WEIGHT_DECAY = 1e-4
VAL_SPLIT = 0.15
SEED = 42


# Dataset

class TileRotationDataset(Dataset):
    """
    Loads tile images from one or more directories. and performs rotation augmentation
    for more data
    """
    def __init__(self, samples: list[tuple[Path, int]],
                 transform=None,
                 random_quarter_turns: bool = False):
        self.samples  = samples
        self.transform = transform
        self.random_quarter_turns = random_quarter_turns

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")

        if self.random_quarter_turns:
            k = random.randint(0, 3)
            img   = TF.rotate(img, angle=90 * k)
            label = (label + k) % 4

        if self.transform:
            img = self.transform(img)
        return img, label


def _collect_samples(dirs: list[Path]) -> list[tuple[Path, int]]:
    """Scan directories for files and get the rotation labels."""
    samples = []
    for d in dirs:
        if not d.exists():
            print(f"  [skip] {d} not found")
            continue
        found = 0
        for p in sorted(d.rglob("*.jpg")):
            stem = p.stem  # e.g. "ID5"
            if not stem.upper().startswith("ID"):
                continue
            try:
                n = int(stem[2:])
                label = n % 4
                samples.append((p, label))
                found += 1
            except ValueError:
                pass
        print(f"  {d.name}: {found} images")
    return samples


def _stratified_split(samples: list[tuple[Path, int]],
                      val_frac: float
                      ) -> tuple[list, list]:
    """Split keeping per-class proportions equal in train/val."""
    by_class = defaultdict(list)
    for s in samples:
        by_class[s[1]].append(s)

    train_set, val_set = [], []
    for label, items in by_class.items():
        random.shuffle(items)
        n_val = max(1, int(round(len(items) * val_frac)))
        val_set.extend(items[:n_val])
        train_set.extend(items[n_val:])

    random.shuffle(train_set)
    random.shuffle(val_set)
    return train_set, val_set


def _make_transforms(train: bool):
    """
    Strong augmentation for training to compensate for limited data.
    validation uses only resize, centre-crop, normalise.
    """
    mean = [0.485, 0.456, 0.406]
    std  = [0.229, 0.224, 0.225]

    if train:
        return transforms.Compose([
            transforms.Resize((IMG_SIZE + 32, IMG_SIZE + 32)),
            transforms.RandomCrop(IMG_SIZE),
            transforms.ColorJitter(brightness=0.4, contrast=0.4,
                                   saturation=0.3, hue=0.05),
            transforms.RandomGrayscale(p=0.05),
            transforms.RandomApply(
                [transforms.GaussianBlur(kernel_size=3)], p=0.3),
            transforms.RandomRotation(degrees=10),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
            transforms.RandomErasing(p=0.2, scale=(0.02, 0.10)),
        ])
    else:
        return transforms.Compose([
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.CenterCrop(IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])


# Model
def build_model(num_classes: int = 4, pretrained: bool = True) -> nn.Module:
    """ResNet-18 with ImageNet weights, final FC replaced for 4-class output."""
    weights = models.ResNet18_Weights.DEFAULT if pretrained else None
    model   = models.resnet18(weights=weights)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


# Training loop
def train(args):
    torch.manual_seed(SEED)
    random.seed(SEED)
    np.random.seed(SEED)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    # collect data samples and split into train/val sets
    print("\nScanning data sources:")
    all_samples = _collect_samples([STUDIO_DIR, GAME_DIR])
    if not all_samples:
        print("ERROR: no images found. Check STUDIO_DIR path.")
        sys.exit(1)

    counts = Counter(label for _, label in all_samples)
    print(f"\nTotal samples: {len(all_samples)}")
    print(f"Class distribution: { {f'rot{k}': v for k, v in sorted(counts.items())} }")

    #stratified split so val set has same class distribution as train
    train_set, val_set = _stratified_split(all_samples, VAL_SPLIT)
    print(f"Train: {len(train_set)}  Val: {len(val_set)}")
    val_counts = Counter(label for _, label in val_set)
    print(f"Val class distribution: { {f'rot{k}': v for k, v in sorted(val_counts.items())} }")

    # Train and val datasets and loaders
    train_ds = TileRotationDataset(
        train_set,
        transform=_make_transforms(train=True),
        random_quarter_turns=True,
    )
    val_ds = TileRotationDataset(
        val_set,
        transform=_make_transforms(train=False),
        random_quarter_turns=False,
    )

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE,
                              shuffle=True,  num_workers=0, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE,
                              shuffle=False, num_workers=0, pin_memory=True)

    # model loss and optimiser
    model     = build_model(num_classes=4, pretrained=True).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=args.lr,
                            weight_decay=WEIGHT_DECAY)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    # training loop with validation and checkpoint saving
    best_val_acc = 0.0
    print(f"\n{'Epoch':>5}  {'Train Loss':>10}  {'Train Acc':>9}  {'Val Acc':>7}  {'LR':>8}")
    print("─" * 52)

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss, correct, total = 0.0, 0, 0
        for imgs, labels in train_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            optimizer.zero_grad()
            out  = model(imgs)
            loss = criterion(out, labels)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * imgs.size(0)
            correct    += (out.argmax(1) == labels).sum().item()
            total      += imgs.size(0)

        train_acc = correct / total
        avg_loss  = total_loss / total
        scheduler.step()

        # validation
        model.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for imgs, labels in val_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                out = model(imgs)
                val_correct += (out.argmax(1) == labels).sum().item()
                val_total   += imgs.size(0)
        val_acc = val_correct / val_total

        lr_now = scheduler.get_last_lr()[0]
        marker = "  ← best" if val_acc > best_val_acc else ""
        print(f"{epoch:>5}  {avg_loss:>10.4f}  {train_acc:>8.1%}  {val_acc:>7.1%}  "
              f"{lr_now:>8.6f}{marker}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save({
                "epoch":      epoch,
                "state_dict": model.state_dict(),
                "val_acc":    val_acc,
                "train_acc":  train_acc,
            }, str(OUT_MODEL))

    print(f"\nBest val accuracy: {best_val_acc:.1%}")
    print(f"Model saved → {OUT_MODEL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ResNet-18 rotation classifier")
    parser.add_argument("--epochs", type=int,   default=EPOCHS, help=f"Training epochs (default {EPOCHS})")
    parser.add_argument("--lr", type=float, default=LR, help=f"Learning rate (default {LR})")
    args = parser.parse_args()

    train(args)