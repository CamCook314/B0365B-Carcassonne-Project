import cv2 as cv
import numpy as np
import screeninfo
from pathlib import Path
import random
import time
import Project_CV
from collections import defaultdict
import threading

# Display FLAG
projector_display = threading.Event()

# INVALID MOVE FLAGS
invalid_border = False # Flag to tell projector to project a cross on given coord
invalid_lock = threading.Lock()

# VALID MOVE FLAGS
valid_border = False # Flag to tell projector to project a cross on given coord
valid_b_lock = threading.Lock()

# EVENT TRIGGER FLAGS
event_border = False # Flag to tell projector to project a cross on given coord
event_lock = threading.Lock()

# VALID MOVE TILE LOCATION FLAGS
valid_flag = False   # Flag to tell projector to project valid tiles
valid_tiles = None  # Variable to store set of valid tile coordinates
valid_lock = threading.Lock()

## TILE SIZE
TILE_SIZE = 65

## EVENT IMAGE SIZE
EVENT_SIZE = round(0.6 * TILE_SIZE)

## IMAGE DICTIONARY LOCK
img_lock = threading.Lock()

## IMAGE DICTIONARY
img_dict = defaultdict(set)

## IMAGE KEYS
img_keys = ["EVENT", "VOLCANO", "BAD_TILE", "GOOD_TILE", "UNREST"]
for key in img_keys:
    img_dict[key]

def add_img(img, coord):
    add_img = True
    with img_lock:
        if img in img_keys:   
            for key in img_keys:
                values = img_dict[key]
                if coord in values:
                    add_img = False
        if add_img:
            if isinstance(coord, tuple):
                img_dict[img].add(coord)
            else:
                img_dict[img].update(coord)

        
def del_img(img, coord):
    with img_lock:
        if img in img_keys:
            if img != "UNREST":
                if img in img_dict:
                    img_dict[img].discard(coord)
            else:
                img_dict.pop(img, None)

## START UP
def startup(canvas, centre_x, centre_y):
    # No tile has been placed yet draw bounding box
    colour = (0, 255, 255) # YELLOW - CAN BE CHANGED
    canvas = cv.drawMarker(canvas, (centre_x, centre_y), colour, cv.MARKER_CROSS, 30, 2)
    text = "Place tile on cross to start"
    org =(centre_x - 215, centre_y - 30)
    font = cv.FONT_HERSHEY_SIMPLEX
    scale = 1
    lineType = cv.LINE_AA
    canvas = cv.putText(canvas, text, org, font, scale, colour, 2, lineType)
    return canvas

def tile_grid_points(grid_origin, grid_tile_size, tile_coord, img_size):
    origin = grid_origin
    # grid_tile_size is static pixel value not (#,#)
    tile_x = round(grid_tile_size * tile_coord[0] * 1.1) # X coord
    tile_y = round(grid_tile_size * tile_coord[1]) # Y coord
    tile_origin = (origin[0] + tile_x, origin[1] - tile_y)
    tile_start = (tile_origin[0] - (img_size // 2), tile_origin[1] + (img_size // 2))
    tile_end = (tile_origin[0] + (img_size // 2), tile_origin[1] - (img_size // 2))
    return (tile_start, tile_end, tile_origin)

## SET INVALID MOVE
def set_invalid():
    global invalid_border
    with invalid_lock:
        invalid_border = True

## CLEAR INVALID MOVE
def clear_invalid():
    global invalid_border
    with invalid_lock:
        invalid_border = False

## INVALID MOVE
def set_invalid_border(canvas, width, height):
    colour = (0, 0, 255) # RED
    thickness = 10
    cv.rectangle(canvas, (0, 0), (width - 1, height - 1), colour, thickness)
    return canvas

## SET INVALID MOVE
def set_valid():
    global valid_border
    with valid_lock:
        valid_border = True

## CLEAR INVALID MOVE
def clear_valid():
    global valid_border
    with valid_lock:
        valid_border = False

## INVALID MOVE
def set_valid_border(canvas, width, height):
    colour = (0, 255, 0) # GREEN
    thickness = 10
    cv.rectangle(canvas, (0, 0), (width - 1, height - 1), colour, thickness)
    return canvas

## SET INVALID MOVE
def set_event():
    global event_border
    with event_lock:
        event_border = True

## CLEAR INVALID MOVE
def clear_event():
    global event_border
    with event_lock:
        event_border = False

## INVALID MOVE
def set_event_border(canvas, width, height):
    colour = (255, 255, 0) # CYAN
    thickness = 10
    cv.rectangle(canvas, (0, 0), (width - 1, height - 1), colour, thickness)
    return canvas

def set_proj_valid(coords):
    global valid_flag
    global valid_tiles
    with valid_lock:
        valid_flag = True
        valid_tiles = coords

def clear_proj_valid():
    global valid_flag
    global valid_tiles
    with valid_lock:
        valid_flag = False
        valid_tiles = None

def project_valids(canvas, grid_origin, grid_tile_size, tile_coords):
    colour = (0, 255, 0)
    thickness = -1
    cross_colour = (0, 100, 0)
    cross_thickness = 2
    for coord in tile_coords:
        tile_data = tile_grid_points(grid_origin, grid_tile_size, coord, EVENT_SIZE)
        cv.rectangle(canvas, tile_data[0], tile_data[1], colour, thickness)
        cv.drawMarker(canvas, tile_data[2], cross_colour, cv.MARKER_CROSS, 20, cross_thickness)
    return canvas


# EVENT TYPES
## EVENT TILE
def event_tile(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, EVENT_SIZE)
    back_colour = (255, 255, 0)
    text_colour = (0, 0, 255)
    back_thickness = -1    
    cv.rectangle(canvas, tile_data[0], tile_data[1], back_colour, back_thickness)
    text = "?"
    org = tile_data[2]
    font = cv.FONT_HERSHEY_SIMPLEX
    org = (org[0] - 9, org[1] + 11)
    scale = 1
    lineType = cv.LINE_AA
    canvas = cv.putText(canvas, text, org, font, scale, text_colour, 2, lineType)
    return canvas

## BAD TILE (ALL TILES COMBINED FOR PROTOTYPE)
def event_bad_tile(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, TILE_SIZE)
    colour = (123, 255, 177) # PALE GREEN
    thickness = -1
    cv.rectangle(canvas, tile_data[0], tile_data[1], colour, thickness)
    return canvas

## GOOD TILE (ALL TILES COMBINED FOR PROTOTYPE)
def event_good_tile(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, TILE_SIZE)
    colour = (0, 215, 255) # GOLD
    thickness = -1
    cv.rectangle(canvas, tile_data[0], tile_data[1], colour, thickness)
    return canvas

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

## VOLCANO
def event_volcano(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, TILE_SIZE)
    colour = (0, 70, 255) # ORANGE
    thickness = -1
    cv.rectangle(canvas, tile_data[0], tile_data[1], colour, thickness)
    return canvas

## CITY UNREST
def event_unrest(canvas, grid_origin, grid_tile_size, tile_coords):
    colour = (128, 128, 255) # LIGHT RED
    thickness = -1
    for coord in tile_coords:
        tile_data = tile_grid_points(grid_origin, grid_tile_size, coord, TILE_SIZE)
        cv.rectangle(canvas, tile_data[0], tile_data[1], colour, thickness)
    return canvas

def projector_exit():
    projector_display.clear()

## MAIN LOOP FUNCTION THAT CAN BE CALLED TO CREATE A THREAD
def projector_main():
    projector_display.set()
    # Get screens info, projector in extend mode is classed as extra screen
    monitors = screeninfo.get_monitors()
    # Check to make sure monitor is connected
    while len(monitors) == 1:
        print("Projector not connected in extended mode")
        time.sleep(1)

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
    while projector_display.is_set():
        # Create an empty black rame
        canvas = np.zeros((proj_h, proj_w, 3), dtype=np.uint8)

        if Project_CV.grid_origin == None:
            canvas = startup(canvas, centre_w, centre_h)
        else:
            with img_lock:
                snapshot = {k: set(v) for k, v in img_dict.items()}
            for key, values in snapshot.items():
                if key == "UNREST":
                        canvas = event_unrest(canvas, Project_CV.grid_origin, 
                                            round(Project_CV.grid_tile_size), values)
                for value in values:
                    if key == "REVERSE":
                        canvas = event_reverse_move(canvas, Project_CV.grid_origin,
                                                    round(Project_CV.grid_tile_size), value)
                    elif key == "MORE_SCORE":
                        canvas = event_more_score(canvas, Project_CV.grid_origin,
                                                    round(Project_CV.grid_tile_size), value)
                    elif key == "EVENT":
                        canvas = event_tile(canvas, Project_CV.grid_origin, 
                                            round(Project_CV.grid_tile_size), value)
                    elif key == "VOLCANO":
                        canvas = event_volcano(canvas, Project_CV.grid_origin, 
                                            round(Project_CV.grid_tile_size), value)
                    elif key == "BAD_TILE":
                        canvas = event_bad_tile(canvas, Project_CV.grid_origin, 
                                            round(Project_CV.grid_tile_size), value)
                    elif key == "GOOD_TILE":
                        canvas = event_good_tile(canvas, Project_CV.grid_origin, 
                                            round(Project_CV.grid_tile_size), value)
            with valid_b_lock:
                if valid_border:
                    canvas = set_valid_border(canvas, proj_w, proj_h)

            with invalid_lock:
                if invalid_border:
                    canvas = set_invalid_border(canvas, proj_w, proj_h)
            
            with event_lock:
                if event_border:
                    canvas = set_event_border(canvas, proj_w, proj_h)
            
            with valid_lock:
                if valid_flag:
                    canvas = project_valids(canvas, Project_CV.grid_origin, 
                                            Project_CV.grid_tile_size, valid_tiles)
            
        # Show image
        cv.imshow("Projector", canvas)
        # Wait for any key and then exit
        # Exit if pressed - exit button
        c = cv.waitKey(1)
        #Qif c == ord('q'):
        #    break
        time.sleep(0.1)

    cv.destroyAllWindows()