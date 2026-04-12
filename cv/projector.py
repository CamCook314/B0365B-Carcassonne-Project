import cv2 as cv
import numpy as np
import screeninfo
from pathlib import Path
import random


def create_ID(tile_id):
    return "ID" + str(tile_id)

base_pth = Path(__file__).resolve().parent.parent
asset_pth = base_pth / "assets" / "tile_photos"
print(asset_pth)
monitors = screeninfo.get_monitors()
if len(monitors) == 1:
    print("Projector not connected in extended mode")
    exit()

ran_num = random.randint(0, 335)

ran_id = create_ID(ran_num)
id_str = ran_id + ".jpg"
print(id_str)

img_path = asset_pth / id_str

# Change to [1] for projector
projector = monitors[1]
test_img = cv.imread(img_path, cv.IMREAD_COLOR)

cv.namedWindow("Projector", cv.WINDOW_NORMAL)

cv.setWindowProperty("Projector", cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)

#cv.resizeWindow("Projector", projector.height, projector.width)

cv.moveWindow("Projector", projector.x, projector.y)

cv.imshow("Projector", test_img)
cv.waitKey(0)
cv.destroyAllWindows()