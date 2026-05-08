"""
Train a DINOv2 + linear-head tile family classifier.

Usage:
    python cv/train.py
    python cv/train.py --dir assets/tile_photos/edit --epochs 40 --augments 60

Output:
    cv/classifier_head.pt
"""
import argparse
import re
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms as T
from PIL import Image
from pathlib import Path


AUGMENT = T.Compose([
    T.RandomRotation(degrees=10),
    T.ColorJitter(brightness=0.35, contrast=0.35, saturation=0.1),
    T.RandomHorizontalFlip(),
    T.Resize(256, interpolation=T.InterpolationMode.BICUBIC),
    T.RandomCrop(224),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class TileDataset(Dataset):
    def __init__(self, image_dir, transform, augments_per_image):
        paths = sorted(Path(image_dir).rglob("*.jpg"))
        if not paths:
            raise FileNotFoundError(f"No .jpg files found in {image_dir}")

        families = sorted({(int(re.sub(r"\D", "", p.stem)) // 4) * 4 for p in paths})
        self.family_to_label = {f: i for i, f in enumerate(families)}
        self.label_to_family = {i: f for f, i in self.family_to_label.items()}
        self.num_classes = len(families)
        self.transform = transform
        self.samples = [
            (p, self.family_to_label[(int(re.sub(r"\D", "", p.stem)) // 4) * 4])
            for p in paths
            for _ in range(augments_per_image)
        ]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        return self.transform(Image.open(path).convert("RGB")), label


def train(image_dir, out_path, epochs, augments):
    from transformers import AutoModel

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on {device}")

    backbone = AutoModel.from_pretrained("facebook/dinov2-base").to(device)
    backbone.eval()
    for p in backbone.parameters():
        p.requires_grad = False

    dataset = TileDataset(image_dir, AUGMENT, augments_per_image=augments)
    loader  = DataLoader(dataset, batch_size=32, shuffle=True, num_workers=0)
    print(f"  {dataset.num_classes} families  |  {len(dataset)} augmented samples")

    head    = nn.Linear(768, dataset.num_classes).to(device)
    opt     = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(1, epochs + 1):
        total_loss, correct, total = 0.0, 0, 0
        for imgs, labels in loader:
            imgs, labels = imgs.to(device), labels.to(device)
            with torch.no_grad():
                feats = backbone(pixel_values=imgs).last_hidden_state[:, 0, :]
            logits = head(feats)
            loss   = loss_fn(logits, labels)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += loss.item() * len(labels)
            correct    += (logits.argmax(1) == labels).sum().item()
            total      += len(labels)
        print(f"  epoch {epoch:3d}/{epochs}  loss={total_loss/total:.4f}  acc={correct/total:.3f}")

    torch.save({
        "weight":          head.weight.data.cpu(),
        "bias":            head.bias.data.cpu(),
        "label_to_family": dataset.label_to_family,
        "num_classes":     dataset.num_classes,
    }, out_path)
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir",      default="assets/tile_photos/edit")
    parser.add_argument("--out",      default="cv/classifier_head.pt")
    parser.add_argument("--epochs",   type=int, default=30)
    parser.add_argument("--augments", type=int, default=50)
    args = parser.parse_args()
    train(args.dir, args.out, args.epochs, args.augments)
