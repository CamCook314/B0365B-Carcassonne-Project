import cv2 as cv
import numpy as np
import screeninfo
from pathlib import Path
import random
import time
import Project_CV
from collections import defaultdict

# INVALID MOVE FLAGS
invalid_tile = False # Flag to tell projector to project a cross on given coord
invalid_coord = None # Will be a (x, y) grid coord of invalid move

## TILE SIZE
TILE_SIZE = 85

## EVENT IMAGE SIZE
EVENT_SIZE = round(0.5 * TILE_SIZE)

## IMAGE DICTIONARY
img_dict = defaultdict(set)

## IMAGE KEYS
img_keys = ["REVERSE", "MORE_SCORE"]
for key in img_keys:
    img_dict[key]

def add_img(img, coord):
    if img in img_keys:
        img_dict[img].add(coord)

def del_img(img, coord):
    if img in img_keys:
        img_dict[img].discard(coord)

## START UP
def startup(canvas, centre_x, centre_y):
    # No tile has been placed yet draw bounding box
    start_point = (centre_x - 350, centre_y + 350)
    end_point = (centre_x + 350, centre_y - 350)
    colour = (0, 255, 255) # YELLOW - CAN BE CHANGED
    canvas = cv.rectangle(canvas, start_point, end_point, colour, 2)
    text = "Place tile within bounding box"
    org =(centre_x - 240, centre_y)
    font = cv.FONT_HERSHEY_SIMPLEX
    scale = 1
    lineType = cv.LINE_AA
    canvas = cv.putText(canvas, text, org, font, scale, colour, 2, lineType)
    return canvas

def tile_grid_points(grid_origin, grid_tile_size, tile_coord, img_size):
    origin = grid_origin
    # grid_tile_size is static pixel value not (#,#)
    tile_x = grid_tile_size * tile_coord[0] # X coord
    tile_y = grid_tile_size * tile_coord[1] # Y coord
    tile_origin = (origin[0] + tile_x, origin[1] + tile_y)
    tile_start = (tile_origin[0] - (img_size // 2), tile_origin[1] + (img_size // 2))
    tile_end = (tile_origin[0] + (img_size // 2), tile_origin[1] - (img_size // 2))
    return (tile_start, tile_end, tile_origin)

## INVALID MOVE
def invalid_move(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord)
    colour = (0, 0, 255) # RED
    thickness = 2
    cv.drawMarker(canvas, tile_data[2], colour, cv.MARKER_TILTED_CROSS, EVENT_SIZE, thickness)
    return canvas

# EVENT TYPES
## REVERSE MOVE ORDER
def event_reverse_move(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, EVENT_SIZE)
    colour = (255, 0, 0) # BLUE
    thickness = -1
    cv.rectangle(canvas, tile_data[0], tile_data[1], colour, thickness)
    return canvas

## MORE SCORE
def event_more_score(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, EVENT_SIZE)
    colour = (0, 255, 0) # GREEN
    thickness = -1
    cv.rectangle(canvas, tile_data[0], tile_data[1], colour, thickness)
    return canvas


## MAIN LOOP FUNCTION THAT CAN BE CALLED TO CREATE A THREAD
def projector_main():
    # Get screens info, projector in extend mode is classed as extra screen
    monitors = screeninfo.get_monitors()
    # Check to make sure monitor is connected
    if len(monitors) == 1:
        print("Projector not connected in extended mode")
        exit()

    # Get project screen settings
    projector = monitors[1]
    # Define projector resolution
    proj_w, proj_h = projector.width, projector.height

    centre_w = proj_w // 2
    centre_h = proj_h // 2

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

        if Project_CV.grid_origin == None:
            canvas = startup(canvas, centre_w, centre_h)
        else:
            for key, values in img_dict.items():
                for value in values:
                    if key == "REVERSE":
                        canvas = event_reverse_move(canvas, Project_CV.grid_origin,
                                                    round(Project_CV.grid_tile_size), value)
                    elif key == "MORE_SCORE":
                        canvas = event_more_score(canvas, Project_CV.grid_origin,
                                                    round(Project_CV.grid_tile_size), value)
            if invalid_move:
                canvas = invalid_move(canvas, Project_CV.grid_origin, 
                                      round(Project_CV.grid_tile_size), invalid_coord)
        # Show image
        cv.imshow("Projector", canvas)
        # Wait for any key and then exit
        # Exit if pressed - exit button
        c = cv.waitKey(10)
        if c == ord('q'):
            break
        time.sleep(0.1)

projector_main()