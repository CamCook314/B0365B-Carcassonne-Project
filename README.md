Carcassonne AR
An augmented reality companion to [Carcassonne](https://www.zmangames.com/game/carcassonne/) for score tracking and guidance as well as dynamic events.

Physical Setup
Requires a camera and projector with some mounting method capable of viewing a full table.
Mount the camera directly overhead (or at a steep downward angle) pointing at the board surface, 80 cm above the table.
Position the projector so its image covers the full board area from above or at a low angle.
The board must sit within the overlapping field of view of both devices.
Connect the projector as an extended display. Note its display index (0-based) you will need it in `cv/config.json`.

Installation

You need to have Python 3.14 and [NodeJS](https://nodejs.org/en/download/) with a package manager such as [npm](https://www.npmjs.com/) installed
Then run:
``` bash
## install python requirements
pip install -r requirements.txt
```
``` bash
## install js requirements
cd /frontend/
npm install
```


 Usage
### Projector calibration (first run only)

On first launch the projector shows four green dots at the screen corners instead of the placement cross. The CV window shows a live green-filter view counting stable detections. Once all four dots are detected for 15 consecutive frames the homography is computed and saved to `cv/config.json` — calibration will be skipped on every subsequent run.

For dependencies
Pip install -r requirement.txt

Then run from `python engine/bridge.py`
This will start the 3 components:
 1. Flask API server (/engine/api.py)
 2. CV main loop     (/cv/Project_CV.py)
 3. Vite dev server  (/frontend/)
 A web browser will then launch at address `localhost:5173`.
 

Debug Testing frontend loop

1. Vite Dev server (/frontend/)
2. Flask API server (/engine/api.py)
3. Fake Cv testing file (/engine/fake_cv.py)
 Dependencies

**Python:**
[opencv-python](https://pypi.org/project/opencv-python/)
[numpy](https://pypi.org/project/numpy/)
[open_clip-torch](https://pypi.org/project/open-clip-torch/)
[Pillow](https://pypi.org/project/Pillow/)
[screeninfo](https://pypi.org/project/screeninfo/)
[flask](https://pypi.org/project/Flask/)
[flask-cors](https://pypi.org/project/Flask-Cors/)
[requests](https://pypi.org/project/requests/)
[dinov2](https://github.com/facebookresearch/dinov2)
[transformers](https://pypi.org/project/transformers/)

**JavaScript:**
[@eslint/js@9.39.4](https://www.npmjs.com/package/@eslint/js)
[@types/react-dom@19.2.3](https://www.npmjs.com/package/@types/react-dom)
[@types/react@19.2.14](https://www.npmjs.com/package/@types/react)
[@vitejs/plugin-react@6.0.1](https://www.npmjs.com/package/@vitejs/plugin-react)
[bootstrap@5.3.8](https://www.npmjs.com/package/bootstrap)
[eslint-plugin-react-hooks@7.0.1](https://www.npmjs.com/package/eslint-plugin-react-hooks)
[eslint-plugin-react-refresh@0.5.2](https://www.npmjs.com/package/eslint-plugin-react-refresh)
[eslint@9.39.4](https://www.npmjs.com/package/eslint)
[globals@17.4.0](https://www.npmjs.com/package/globals)
[react-dom@19.2.4](https://www.npmjs.com/package/react-dom)
[react-zoom-pan-pinch@4.0.3](https://www.npmjs.com/package/react-zoom-pan-pinch)
[react@19.2.4](https://www.npmjs.com/package/react)
[sweetalert2@11.26.24](https://www.npmjs.com/package/sweetalert2)
[vite@8.0.3](https://www.npmjs.com/package/vite)


```
Pre-trained Models 
Classifier_head.pt
- **Path:** `cv/classifier_head.pt`
- **Type:** MLP head on top of DINOv2-base (ViT-B/14, frozen backbone)
- **Purpose:** Identifies which of the 84 tile families is in frame
- **Architecture:** Linear(768→256) → GELU → Dropout(0.5) → Linear(256→84)
- **Training script:** `cv/train.py`
- **Regenerate:** `python cv/train.py --epochs 30 --augments 30`
- **Live crops:** Additional training images captured during gameplay are accumulated in `cv/live_id_crops/` and included automatically on the next training run
- **License:** Training images created by the team. DINOv2 weights from
  Meta AI (Apache-2.0); accessed via the `transformers` library.

rotation_model.pth
- **Path:** `cv/rotation_model.pth`
- **Type:** ResNet 18 rotation classifier (4 class: 0, 90, 180, 270 degrees)
- **Architecture:** ResNet-18, 224×224 input,
- **Base weights:** ImageNet pretrained ResNet-18 fine tuned on our own data
- **Training data:** Custom dataset of Carcassonne tile photos collected
  by the team, drawn from three sources studio photos
  (`assets/tile_photos/edit`), game reference images (`cv/game_refs`),
  and live capture crops).
- **Training:** 85/15 stratified train/val split, AdamW, cross-entropy,
  with augmentation (colour jitter, random crop, blur, quarter-turn
  rotation) to compensate for limited data. Best checkpoint saved by
  validation accuracy. Training script: `cv/train_rotation.py`.
- **Framework:** PyTorch / torchvision
- **License:** Training images created by the team. Base ResNet-18 weights
  from torchvision (BSD-3-Clause).
```
Course Info
University of Queensland
DECO3801 - Design Computing Studio 3 - Build
Semester 1, 2026

