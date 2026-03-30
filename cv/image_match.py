## setup
import torch
import torch.nn.functional as F
import open_clip
from PIL import Image
from pathlib import Path

model_name = 'ViT-B-32'
pretrained_model = 'laion2b_s34b_b79k'

model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained_model)
model.eval()



## convert image to embedding
def get_embedding(path: Path) -> torch.Tensor:
    image = preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        emb = model.encode_image(image).squeeze(0)
    return F.normalize(emb, dim=0)


extensions = {".jpg", ".jpeg", ".png"}
search_dir = Path("../assets/tile_photos")

## preprocess all images in search dir
embeddings = {}
count = 0
for img_path in search_dir.rglob("*"):
    try:
        embeddings[img_path] = get_embedding(img_path)
        print(count, "success", img_path)
        count += 1
    except Exception as e:
        print("failed", img_path, "->", e)


## save embeddings
torch.save(embeddings, "embeddings.pt")

## load embeddings
embeddings = torch.load("embeddings.pt", weights_only=False)


## score images

query_emb = get_embedding("../assets/testing_photos/IMG_9122_crop_rotate.JPG")
results = []
for path, emb in embeddings.items():
    score = torch.dot(query_emb, emb).item()
    results.append((score, path))

results.sort(reverse=True)

import matplotlib.pyplot as plt
import matplotlib.image as mpimg

def show_results(results, top_n=5):
    fig, axes = plt.subplots(1, top_n, figsize=(20, 4))
    for ax, (score, path) in zip(axes, results[:top_n]):
        img = mpimg.imread(path)
        ax.imshow(img)
        ax.set_title(f"{score:.4f}")
        ax.axis("off")
    plt.tight_layout()
    plt.show()

show_results(results)