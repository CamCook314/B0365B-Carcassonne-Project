"""
rotation_classifier.py, fast ResNet-18 rotation inference.

Replacement for the CLIP-based match_rotation() in image_match.py.
Call load_rotation_model() once at startup, then use predict_rotation() anywhere
you previously called match_rotation().

"""

from pathlib import Path
import torch
import torch.nn.functional as F
from torchvision import transforms, models
from PIL import Image, ImageEnhance

# path to the trained checkpoint and the input size the model expects
MODEL_PATH = Path(__file__).parent / "rotation_model.pth"
IMG_SIZE = 224

# inference pipeline, matches the val transforms used during training
_INFERENCE_TRANSFORM = transforms.Compose([
    # resize so the tile fills the input window and crop for the size
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.CenterCrop(IMG_SIZE),
    # convert PIL image to a tensor for the model
    transforms.ToTensor(),
    # normalise with imagenet stats since the backbone was pretrained on it
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])


def load_rotation_model(model_path: str | Path = MODEL_PATH,
                        device: str | None = None) -> dict:
    """
    Load the trained ResNet-18 checkpoint.
    """
    # loads using gpu if not cpu
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device)

    # no checkpoint
    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"Rotation model not found at {model_path}.\n"
        )

    # load checkpoint and rebuild the same architecture used in training
    ckpt = torch.load(str(model_path), map_location=device)
    model = models.resnet18(weights=None)

    # swap the final layer to match the 4 rotation classes
    model.fc = torch.nn.Linear(model.fc.in_features, 4)
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()

    # print loaded checkpoint
    val_acc = ckpt.get("val_acc", 0.0)
    print(f"Loaded rotation model  (val_acc={val_acc:.1%}  epoch={ckpt.get('epoch','?')})")

    return {"model": model, "device": device, "val_acc": val_acc}


# augmentation variants to average result 
_TTA_VARIANTS = [
    lambda img: img,
    # slightly darker
    lambda img: ImageEnhance.Brightness(img).enhance(0.85),
    # slightly brighter
    lambda img: ImageEnhance.Brightness(img).enhance(1.15),
    # lower contrast
    lambda img: ImageEnhance.Contrast(img).enhance(0.80),
    # higher contrast
    lambda img: ImageEnhance.Contrast(img).enhance(1.20),
]


def predict_rotation(image_path: str | Path,
                     rot_model: dict) -> tuple[int, float]:
    """Predict rotation (0-3)"""
    model = rot_model["model"]
    device = rot_model["device"]

    # load the image
    base_img = Image.open(str(image_path)).convert("RGB")
    probs_sum = None

    # no gradients needed during inference
    with torch.no_grad():
        for fn in _TTA_VARIANTS:
            # apply the variant
            tensor = _INFERENCE_TRANSFORM(fn(base_img)).unsqueeze(0).to(device)
            # converts to prob for interpratibility
            probs = F.softmax(model(tensor), dim=1).squeeze(0)

            # accumulate probabilities across all variants
            probs_sum = probs if probs_sum is None else probs_sum + probs

    # average across variants then pick the most likely class
    probs_avg = probs_sum / len(_TTA_VARIANTS)
    rotation = int(probs_avg.argmax().item())
    confidence = float(probs_avg[rotation].item())
    return rotation, confidence


def match_rotation_resnet(path: str, family_id: str,
                          rot_model: dict) -> tuple[str, float]:
    # find the base ID for this tile family, rotations are the next 3 IDs
    base = (int(family_id.replace("ID", "")) // 4) * 4

    # run the model and figure out the rotated tile ID
    rotation, confidence = predict_rotation(path, rot_model)
    tile_id = f"ID{base + rotation}"
    print(f" ResNet rotation: {rotation} conf={confidence:.4f} → {tile_id}")
    return tile_id, confidence


# python cv/rotation_classifier.py path/to/crop.jpg [family_id]
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python cv/rotation_classifier.py <image_path> [family_id]")
        sys.exit(1)

    img_path = sys.argv[1]
    family_id = sys.argv[2] if len(sys.argv) > 2 else "ID0"

    # load model once then run a single prediction
    rot_model = load_rotation_model()
    tile_id, conf = match_rotation_resnet(img_path, family_id, rot_model)
    print(f"\nResult: {tile_id}  (confidence {conf:.1%})")