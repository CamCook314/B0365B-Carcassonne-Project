"""
train_rotation.py, a ResNet-18 to classify tile rotation (0, 1, 2, 3).

Usage:
    python cv/train_rotation.py
Outputs:
    cv/rotation_model.pth which best checkpoint during training.
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

# path setup, points to the tile photo folders and the output model file
ROOT = Path(__file__).resolve().parent.parent
STUDIO_DIR = ROOT / "assets" / "tile_photos" / "edit"
GAME_DIR = ROOT / "cv" / "game_refs"
OUT_MODEL = ROOT / "cv" / "rotation_model.pth"

# hyperparameters for training
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
    Loads tile images and performs rotation augmentation for more data
    """
    def __init__(self, samples: list[tuple[Path, int]],
                 transform=None,
                 random_quarter_turns: bool = False):
        self.samples = samples
        self.transform = transform
        self.random_quarter_turns = random_quarter_turns

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")

        # rotate by a random quarter turn and shift the label to match
        if self.random_quarter_turns:
            k = random.randint(0, 3)
            img = TF.rotate(img, angle=90 * k)
            label = (label + k) % 4

        # apply the resize, crop, normalise pipeline
        if self.transform:
            img = self.transform(img)
        return img, label


def _collect_samples(dirs: list[Path]) -> list[tuple[Path, int]]:
    """Scan directory for files and get the rotation labels."""
    samples = []
    for d in dirs:
        # skip missing folders so the script still runs with partial data
        if not d.exists():
            print(f"  [skip] {d} not found")
            continue

        found = 0
        for p in sorted(d.rglob("*.jpg")):
            stem = p.stem
            # only use files that follow the ID naming pattern
            if not stem.upper().startswith("ID"):
                continue
            try:
                # parse the number after ID and use mod 4 as the rotation label
                n = int(stem[2:])
                label = n % 4
                samples.append((p, label))
                found += 1
            except ValueError:
                pass
        print(f"  {d.name}: {found} images")
    return samples


def _stratified_split(samples: list[tuple[Path, int]], val_frac: float ) :
    """Split keeping class proportions equal in train/val."""

    # group all samples by their class label
    by_class = defaultdict(list)
    for s in samples:
        by_class[s[1]].append(s)

    train_set, val_set = [], []

    # for each class, take a fixed fraction for validation
    for label, items in by_class.items():
        random.shuffle(items)
        n_val = max(1, int(round(len(items) * val_frac)))
        val_set.extend(items[:n_val])
        train_set.extend(items[n_val:])

    # shuffle so doesnt stay grouped
    random.shuffle(train_set)
    random.shuffle(val_set)
    return train_set, val_set


def _make_transforms(train: bool):
    """
    Strong augmentation for training to compensate for limited data.
    validation uses only resize, centre-crop, normalise.
    """
    # standard imagenet normalisation values
    mean = [0.485, 0.456, 0.406]
    std = [0.229, 0.224, 0.225]

    if train:
        # heavy augmentation to help the model generalise from few samples
        return transforms.Compose([
            # resize a bit larger
            transforms.Resize((IMG_SIZE + 32, IMG_SIZE + 32)),
            # crop a random window so also learning parts
            transforms.RandomCrop(IMG_SIZE),
            # vary colour to handle different lighting and camera conditions
            transforms.ColorJitter(brightness=0.4, contrast=0.4,
                                   saturation=0.3, hue=0.05),
            # drop colour so the model relies on shape sometimes
            transforms.RandomGrayscale(p=0.05),
            # mild blur to simulate slightly out of focus phone photos
            transforms.RandomApply(
                [transforms.GaussianBlur(kernel_size=3)], p=0.3),

            # small wobble to simulate tiles not being perfectly square to the camera
            transforms.RandomRotation(degrees=10),
            
            # model prep
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])
    else:
        # plain pipeline for validation
        return transforms.Compose([
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.CenterCrop(IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ])


# Model
def build_model(num_classes: int = 4, pretrained: bool = True) -> nn.Module:
    """ResNet-18 with ImageNet weights, final layer replaced for our 4 rotations."""

    # start with a ResNet-18, optionally loaded with weights already trained on ImageNet
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

    # 4 output final layer
    in_features = model.fc.in_features
    model.fc = nn.Linear(in_features, num_classes)

    return model


# Training loop
def train(args):
    # seed everything so runs are reproducible
    torch.manual_seed(SEED)
    random.seed(SEED)
    np.random.seed(SEED)

    # pick GPU if available otherwise CPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    # collect data samples and split into train val sets
    print("\nScanning data sources:")
    all_samples = _collect_samples([STUDIO_DIR, GAME_DIR])
    if not all_samples:
        print("ERROR: no images found. Check STUDIO_DIR path.")
        sys.exit(1)

    # print how many samples landed in each rotation class (test remove later)
    counts = Counter(label for _, label in all_samples)
    print(f"\nTotal samples: {len(all_samples)}")
    print(f"Class distribution: { {f'rot{k}': v for k, v in sorted(counts.items())} }")

    # stratified split so val set has same class distribution as train
    train_set, val_set = _stratified_split(all_samples, VAL_SPLIT)
    print(f"Train: {len(train_set)}  Val: {len(val_set)}")
    val_counts = Counter(label for _, label in val_set)
    print(f"Val class distribution: { {f'rot{k}': v for k, v in sorted(val_counts.items())} }")

    # build the datasets
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

    # wrap datasets in loaders for batching
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE,
                              shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE,
                            shuffle=False, num_workers=0, pin_memory=True)

    # model, loss function and optimiser
    model = build_model(num_classes=4, pretrained=True).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=LR,
                            weight_decay=WEIGHT_DECAY)

    # training loop with validation and checkpoint saving
    best_val_acc = 0.0
    print(f"\n{'Epoch':>5}  {'Train Loss':>10}  {'Train Acc':>9}  {'Val Acc':>7}  {'LR':>8}")
    print("─" * 52)

    for epoch in range(1, args.epochs + 1):
        # set model to training
        model.train()
        total_loss, correct, total = 0.0, 0, 0
        for imgs, labels in train_loader:
            # move batch to GPU if available
            imgs, labels = imgs.to(device), labels.to(device)

            # forward, loss, backward, step
            optimizer.zero_grad()
            out = model(imgs)
            loss = criterion(out, labels)
            loss.backward()
            optimizer.step()

            # track running totals for epoch stats
            total_loss += loss.item() * imgs.size(0)
            correct += (out.argmax(1) == labels).sum().item()
            total += imgs.size(0)

        train_acc = correct / total
        avg_loss = total_loss / total

        # validation pass
        model.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for imgs, labels in val_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                out = model(imgs)
                val_correct += (out.argmax(1) == labels).sum().item()
                val_total += imgs.size(0)
        val_acc = val_correct / val_total

        # print a row summary for this epoch
        marker = "  <- best" if val_acc > best_val_acc else ""
        print(f"{epoch:>5}  {avg_loss:>10.4f}  {train_acc:>8.1%}  {val_acc:>7.1%} ")

        # save checkpoint whenever val accuracy improves
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save({
                "epoch": epoch,
                "state_dict": model.state_dict(),
                "val_acc": val_acc,
                "train_acc": train_acc,
            }, str(OUT_MODEL))

    print(f"\nBest val accuracy: {best_val_acc:.1%}")
    print(f"Model saved → {OUT_MODEL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ResNet-18 rotation classifier")
    args = parser.parse_args()

    train(args)