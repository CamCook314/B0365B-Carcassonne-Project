"""
rotation_classifier.py — Fast ResNet-18 rotation inference.

Drop-in replacement for the CLIP-based match_rotation() in image_match.py.
Call load_rotation_model() once at startup, then use predict_rotation() anywhere
you previously called match_rotation().

Example:
    from cv.rotation_classifier import load_rotation_model, predict_rotation

    rot_model = load_rotation_model()

    # Instead of: tile_id, conf = match_rotation(crop_path, ...)
    rotation, confidence = predict_rotation(crop_path, rot_model)
    tile_id = f"ID{family_base + rotation}"
"""

from pathlib import Path
import torch
import torch.nn.functional as F
from torchvision import transforms, models
from PIL import Image

MODEL_PATH = Path(__file__).parent / "rotation_model.pth"
IMG_SIZE = 224

_INFERENCE_TRANSFORM = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.CenterCrop(IMG_SIZE),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])


def load_rotation_model(model_path: str | Path = MODEL_PATH,
                        device: str | None = None) -> dict:
    """
    Load the trained ResNet-18 checkpoint.
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device)

    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Rotation model not found at {model_path}.\n"
        )

    ckpt  = torch.load(str(model_path), map_location=device)
    model = models.resnet18(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, 4)
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()

    val_acc = ckpt.get("val_acc", 0.0)
    print(f"Loaded rotation model  (val_acc={val_acc:.1%}  epoch={ckpt.get('epoch','?')})")

    return {"model": model, "device": device, "val_acc": val_acc}


def predict_rotation(image_path: str | Path,
                     rot_model: dict) -> tuple[int, float]:
    """
    Predict the rotation (0-3) of a tile crop.

    """
    model  = rot_model["model"]
    device = rot_model["device"]

    img = Image.open(str(image_path)).convert("RGB")
    tensor = _INFERENCE_TRANSFORM(img).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(tensor)
        probs  = F.softmax(logits, dim=1).squeeze(0)

    rotation = int(probs.argmax().item())
    confidence = float(probs[rotation].item())
    return rotation, confidence


def match_rotation_resnet(path: str, family_id: str,
                          rot_model: dict) -> tuple[str, float]:
    """
    replacement for image_match.match_rotation().

    Has the same signature shape just pass rot_model instead of
    model/preprocess/embeddings/bias/game_embeddings.

    Returns (tile_id, confidence_score) exactly like the original.
    """
    base = (int(family_id.replace("ID", "")) // 4) * 4
    rotation, confidence = predict_rotation(path, rot_model)
    tile_id  = f"ID{base + rotation}"
    print(f" ResNet rotation: {rotation} conf={confidence:.4f} → {tile_id}")
    return tile_id, confidence


# python cv/rotation_classifier.py path/to/crop.jpg [family_id]
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python cv/rotation_classifier.py <image_path> [family_id]")
        sys.exit(1)

    img_path  = sys.argv[1]
    family_id = sys.argv[2] if len(sys.argv) > 2 else "ID0"

    rot_model = load_rotation_model()
    tile_id, conf = match_rotation_resnet(img_path, family_id, rot_model)
    print(f"\nResult: {tile_id}  (confidence {conf:.1%})")