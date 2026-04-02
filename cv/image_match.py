## setup
import torch
import torch.nn.functional as F
import open_clip
from PIL import Image
from pathlib import Path
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
def preprocess_embeddings() -> dict[Path, torch.Tensor]:
    search_dir = Path("../assets/tile_photos")
    embeddings = {}
    count = 0
    for img_path in search_dir.rglob("*"):
        try:
            embeddings[img_path] = get_embedding(img_path)
            print(count, "success", img_path)
            count += 1
        except Exception as e:
            print("failed", img_path, "->", e)
    return embeddings


## save embeddings
def save_embeddings(embeddings):
    torch.save(embeddings, "embeddings.pt")

## load embeddings
def load_embeddings() -> dict[Path, torch.Tensor]:
    embeddings = torch.load("cv/embeddings.pt", weights_only=False)
    return embeddings


## score images, return list of ranked results
# model and preprocess from model_setup()
def match_image(path: str, model, preprocess, embeddings) -> list[tuple[float, Path]]:
    #query_emb = get_embedding("../assets/testing_photos/IMG_9122_crop_rotate.JPG")
    query_emb = get_embedding(path, model, preprocess)
    results = []
    for path, emb in embeddings.items():
        score = torch.dot(query_emb, emb).item()
        results.append((score, path))

    results.sort(reverse=True)
    return results