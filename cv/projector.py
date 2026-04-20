import cv2 as cv
import numpy as np
import screeninfo
from pathlib import Path
import random
import time

# Used for testing and as a backup to convert nums to strings
def create_ID(tile_id):
    return "ID" + str(tile_id)

# Get file path of parent folder
base_pth = Path(__file__).resolve().parent.parent
# Convert parent folder path to directory of tile photos
asset_pth = base_pth / "assets" / "tile_photos"
# Get screens info, projector in extend mode is classed as extra screen
monitors = screeninfo.get_monitors()
# Check to make sure monitor is connected
if len(monitors) > 1:
    print("Projector not connected in extended mode")
    exit()

# Get project screen settings
projector = monitors[0]

# Define projector resolution
proj_w, proj_h = projector.width, projector.height

# Set up projector window
cv.namedWindow("Projector", cv.WINDOW_NORMAL)
# Make project window fullscreen
cv.setWindowProperty("Projector", cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)
# Make it so displayed image starts at (0,0) to be displayed properly
cv.moveWindow("Projector", projector.x, projector.y)


# While camera recording
while True:
    # Create an empty black rame
    canvas = np.zeros((proj_h, proj_w, 3), dtype=np.uint8)
    # Get a random number to display a random tile
    ran_num = random.randint(0, 335)

    # Convert random number to string and get file path to img
    ran_id = create_ID(ran_num)
    id_str = ran_id + ".jpg"
    print(id_str)
    img_path = asset_pth / id_str

    # Read in test img
    test_img = cv.imread(img_path, cv.IMREAD_COLOR)

    resized_img = cv.resize(test_img, (50, 50))

    # Get random coords
    fh, fw = canvas.shape[:2]
    h, w = resized_img.shape[:2]
    ran_x = random.randint(0, proj_w - w)
    ran_y = random.randint(0, proj_h - h)

    canvas[ran_y:ran_y+h, ran_x:ran_x+w] = resized_img

    # Show image
    cv.imshow("Projector", canvas)
    # Wait for any key and then exit
    # Exit if pressed - exit button
    c = cv.waitKey(10)
    if c == ord('q'):
        break

    time.sleep(1)