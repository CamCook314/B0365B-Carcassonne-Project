import cv2 as cv
import numpy as np
import screeninfo
import time
import json
import math
import os
from . import Project_CV
from collections import defaultdict
import threading

# Manual projector alignment offsets in projector pixels.
# Set PROJ_OFFSET_X / PROJ_OFFSET_Y in cv/config.json to nudge the projected
# grid until the outlines land on the correct physical positions.
_CFG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
PROJ_OFFSET_X = 0
PROJ_OFFSET_Y = 0
if os.path.exists(_CFG_PATH):
    with open(_CFG_PATH) as _f:
        _pcfg = json.load(_f)
    PROJ_OFFSET_X = _pcfg.get("PROJ_OFFSET_X", 0)
    PROJ_OFFSET_Y = _pcfg.get("PROJ_OFFSET_Y", 0)
if PROJ_OFFSET_X or PROJ_OFFSET_Y:
    print(f"[projector] Manual offset from config: dx={PROJ_OFFSET_X}  dy={PROJ_OFFSET_Y}")

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

# Signalled by the projector loop after it renders a frame with no valid tiles.
# Bridge waits on this before unblocking CV for rotation matching / meeple baseline.
proj_blank_rendered = threading.Event()
proj_blank_rendered.set()  # starts "clear" — no projection showing at startup

## PROJECTOR DISPLAY INDEX
# 0 = primary monitor, 1 = first extended display, 2 = second, etc.
# Run once to see all detected monitors printed at startup, then set this.
PROJECTOR_INDEX = 1

## TILE SIZE
TILE_SIZE = 65

## VALID-PLACEMENT MARKER — hollow outline drawn slightly LARGER than the tile.
## Drawing the outline outside the tile boundary means magenta projector light
## falls on the table around the slot, not on the tile surface when placed.
## The magenta filter in blob_pipeline removes the thin line from blob detection
## so it doesn't form a false contour, but tile pixels are unaffected.
VALID_MARKER_SCALE     = 1.15  # outline rect is 115% of the tile size
VALID_MARKER_THICKNESS = 4

## EVENT MARKER SIZE — filled marker for non-placement event indicators only.
## Placement markers no longer use a fixed pixel size (see VALID_MARKER_SCALE).
MARKER_SIZE = round(0.6 * TILE_SIZE)
EVENT_SIZE  = round(0.6 * TILE_SIZE)

## PROJECTOR COORDINATE SYSTEM
# proj_origin: projector pixel (x, y) of grid position (0, 0) — set to screen
#              centre at startup to match the startup cross, updated by CV once
#              the grid is established via set_proj_calibration().
# proj_tile_size: projector pixels per tile — derived from camera tile size × scale.
# proj_a / proj_b: rotation-aware step vectors for the grid (like grid_tracker.a/b but
#   scaled to projector pixels). Moving right by 1 grid unit shifts by (+proj_a, +proj_b_y)
#   and moving up by 1 grid unit shifts by (+proj_b, -proj_a_y).
proj_origin      = None         # set in projector_main() once resolution is known
proj_tile_size   = TILE_SIZE    # projector pixels per tile — X axis
proj_tile_size_y = TILE_SIZE    # projector pixels per tile — Y axis (may differ due to aspect ratio)
proj_angle_deg   = 0.0          # current board rotation angle in degrees
proj_a           = float(TILE_SIZE)   # x-step for +1 grid-x  (tile_size_x * cos θ)
proj_b           = 0.0                # x-step for +1 grid-y  (tile_size_x * sin θ)
proj_a_y         = float(TILE_SIZE)   # y-step for +1 grid-y  (tile_size_y * cos θ)
proj_b_y         = 0.0                # y-step for +1 grid-x  (tile_size_y * sin θ)

# Projector resolution — set in projector_main(); read by CV to compute scale factor.
proj_w = None
proj_h = None

def set_proj_calibration(origin=None, tile_size=None, tile_size_y=None, angle_deg=None):
    global proj_origin, proj_tile_size, proj_tile_size_y
    global proj_angle_deg, proj_a, proj_b, proj_a_y, proj_b_y
    if origin is not None:
        proj_origin      = (origin[0] + PROJ_OFFSET_X, origin[1] + PROJ_OFFSET_Y)
    if tile_size is not None:
        proj_tile_size   = tile_size
    if tile_size_y is not None:
        proj_tile_size_y = tile_size_y
    if angle_deg is not None:
        proj_angle_deg   = angle_deg
    θ      = math.radians(proj_angle_deg)
    cos_θ  = math.cos(θ)
    sin_θ  = math.sin(θ)
    proj_a   = proj_tile_size   * cos_θ
    proj_b   = proj_tile_size   * sin_θ
    proj_a_y = proj_tile_size_y * cos_θ
    proj_b_y = proj_tile_size_y * sin_θ

## IMAGE DICTIONARY LOCK
img_lock = threading.Lock()

## IMAGE DICTIONARY
img_dict = defaultdict(set)

## IMAGE KEYS
img_keys = ["EVENT", "VOLCANO", "BAD_TILE", "GOOD_TILE", "UNREST"]
for key in img_keys:
    img_dict[key]

# Function that adds an event to the dictionary
def add_img(img, coord):
    add_img = True
    with img_lock:
        # Check if key is in event keys
        if img in img_keys:   
            # Check there isn't an event already at the same coords
            for key in img_keys:
                values = img_dict[key]
                if coord in values:
                    add_img = False
        # Add event if nothing is at the coords
        if add_img:
            if isinstance(coord, tuple):
                # Add a single coord
                img_dict[img].add(coord)
            else:
                # Adds a set of coords
                img_dict[img].update(coord)

# Function that removes an event from the dictionary     
def del_img(img, coord):
    # Taking the lock
    with img_lock:
        # Check if is an event key
        if img in img_keys:
            # Is not a set of coordinates
            if img != "UNREST":
                # Remove coord value
                if img in img_dict:
                    img_dict[img].discard(coord)
            else:
                # Remove whole entry
                img_dict.pop(img, None)

## START UP FUNCTION
def startup(canvas, centre_x, centre_y):
    # No tile has been placed yet draw bounding box
    colour = (0, 255, 255) # YELLOW - CAN BE CHANGED
    canvas = cv.drawMarker(canvas, (centre_x, centre_y), colour, cv.MARKER_CROSS, 30, 2)
    text = "Place tile on cross to start"
    org =(centre_x - 215, centre_y - 30) # Calculate start point based on testing for text
    font = cv.FONT_HERSHEY_SIMPLEX
    scale = 1
    lineType = cv.LINE_AA
    #canvas = cv.putText(canvas, text, org, font, scale, colour, 2, lineType)
    return canvas

# Function that calculates a given coords tile centre point, and start and end pixel coords.
# Uses module-level proj_a/proj_b/proj_a_y/proj_b_y step vectors so board rotation is
# accounted for automatically. grid_tile_size and tile_size_y are kept for API compat.
def tile_grid_points(grid_origin, _grid_tile_size, tile_coord, img_size, _tile_size_y=None):
    gx, gy = tile_coord
    # Rotation-aware step: matches grid_tracker.grid_to_px but in projector-pixel space.
    tile_origin_x = round(grid_origin[0] + gx * proj_a   + gy * proj_b)
    tile_origin_y = round(grid_origin[1] + gx * proj_b_y - gy * proj_a_y)
    tile_origin = (tile_origin_x, tile_origin_y)
    tile_start = (tile_origin_x - (img_size // 2), tile_origin_y + (img_size // 2))
    tile_end   = (tile_origin_x + (img_size // 2), tile_origin_y - (img_size // 2))
    return (tile_start, tile_end, tile_origin)

# Function that sets the invalid move border flag
def set_invalid():
    global invalid_border
    with invalid_lock:
        invalid_border = True

# Function that clears the invalid move border flag
def clear_invalid():
    global invalid_border
    with invalid_lock:
        invalid_border = False

# Function that draws the invalid move border
def set_invalid_border(canvas, width, height):
    colour = (255, 0, 255) # Magenta — filtered by blob_pipeline's proj_magenta mask
    thickness = 10
    cv.rectangle(canvas, (0, 0), (width - 1, height - 1), colour, thickness)
    return canvas

# Function that seets the valid move border flag
def set_valid():
    global valid_border
    with valid_b_lock:
        valid_border = True

# Function that clears the valid move border flag
def clear_valid():
    global valid_border
    with valid_b_lock:
        valid_border = False

# Function that draws the valid move border
def set_valid_border(canvas, width, height):
    colour = (255, 0, 255) # Magenta — filtered by blob_pipeline's proj_magenta mask
    thickness = 10
    cv.rectangle(canvas, (0, 0), (width - 1, height - 1), colour, thickness)
    return canvas

# Function that sets the event border flag
def set_event():
    global event_border
    with event_lock:
        event_border = True

# Function that clears the event border flag
def clear_event():
    global event_border
    with event_lock:
        event_border = False

# Function the draws the event border
def set_event_border(canvas, width, height):
    colour = (255, 0, 255) # Magenta — filtered by blob_pipeline's proj_magenta mask
    thickness = 10
    cv.rectangle(canvas, (0, 0), (width - 1, height - 1), colour, thickness)
    return canvas

# Function that sets the valid placement flag and 
def set_proj_valid(coords):
    global valid_flag
    global valid_tiles
    with valid_lock:
        valid_flag = True
        valid_tiles = coords

# Function that clears the valid tile flags and reset tile coords
def clear_proj_valid():
    global valid_flag
    global valid_tiles
    with valid_lock:
        valid_flag = False
        valid_tiles = None
    proj_blank_rendered.clear()  # projector hasn't rendered the blank frame yet

# Function to display all valid tile placement locations for a tile.
# Draws a hollow magenta outline slightly larger than the tile so the projector
# light hits the table around the slot, not the tile surface itself.
def project_valids(canvas, grid_origin, grid_tile_size, tile_coords):
    colour     = (255, 0, 255)  # Magenta
    outline_sz = max(1, round(grid_tile_size * VALID_MARKER_SCALE))
    for coord in tile_coords:
        tile_data = tile_grid_points(grid_origin, grid_tile_size, coord, outline_sz, proj_tile_size_y)
        cv.rectangle(canvas, tile_data[0], tile_data[1], colour, VALID_MARKER_THICKNESS)
    return canvas


# EVENT TYPES
## EVENT TILE
def event_tile(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, EVENT_SIZE, proj_tile_size_y)
    colour = (0, 165, 255) # ORANGE
    cv.rectangle(canvas, tile_data[0], tile_data[1], colour, -1)
    text = "?"
    org = (tile_data[2][0] - 9, tile_data[2][1] + 11)
    canvas = cv.putText(canvas, text, org, cv.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv.LINE_AA)
    return canvas

## BAD TILE (ALL TILES COMBINED FOR PROTOTYPE)
def event_bad_tile(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, MARKER_SIZE, proj_tile_size_y)
    cv.rectangle(canvas, tile_data[0], tile_data[1], (0, 165, 255), -1) # ORANGE
    return canvas

## GOOD TILE (ALL TILES COMBINED FOR PROTOTYPE)
def event_good_tile(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, MARKER_SIZE, proj_tile_size_y)
    cv.rectangle(canvas, tile_data[0], tile_data[1], (0, 165, 255), -1) # ORANGE
    return canvas

## REVERSE MOVE ORDER
def event_reverse_move(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, EVENT_SIZE, proj_tile_size_y)
    cv.rectangle(canvas, tile_data[0], tile_data[1], (0, 165, 255), -1) # ORANGE
    return canvas

## MORE SCORE
def event_more_score(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, EVENT_SIZE, proj_tile_size_y)
    cv.rectangle(canvas, tile_data[0], tile_data[1], (0, 165, 255), -1) # ORANGE
    return canvas

## VOLCANO
def event_volcano(canvas, grid_origin, grid_tile_size, tile_coord):
    tile_data = tile_grid_points(grid_origin, grid_tile_size, tile_coord, MARKER_SIZE, proj_tile_size_y)
    cv.rectangle(canvas, tile_data[0], tile_data[1], (0, 165, 255), -1) # ORANGE
    return canvas

## CITY UNREST
def event_unrest(canvas, grid_origin, grid_tile_size, tile_coords):
    for coord in tile_coords:
        tile_data = tile_grid_points(grid_origin, grid_tile_size, coord, MARKER_SIZE, proj_tile_size_y)
        cv.rectangle(canvas, tile_data[0], tile_data[1], (0, 165, 255), -1) # ORANGE
    return canvas

# Function to tell projector thread to stop displaying and to start exiting
def projector_exit():
    projector_display.clear()

## MAIN LOOP FUNCTION THAT CAN BE CALLED TO CREATE A THREAD
def projector_main():
    projector_display.set()
    # Get screens info, projector in extend mode is classed as extra screen
    monitors = screeninfo.get_monitors()
    # Check to make sure monitor is connected
    while len(monitors) <= PROJECTOR_INDEX:
        print(f"[projector] Waiting for display index {PROJECTOR_INDEX} "
              f"(only {len(monitors)} monitor(s) detected)...")
        time.sleep(1)
        monitors = screeninfo.get_monitors()

    print("[projector] Detected monitors:")
    for i, m in enumerate(monitors):
        marker = " ← selected" if i == PROJECTOR_INDEX else ""
        print(f"  [{i}] {m.width}x{m.height}  offset=({m.x},{m.y})  name={m.name}{marker}")

    # Get project screen settings
    projector = monitors[PROJECTOR_INDEX]
    # Define projector resolution and expose at module level for CV calibration
    global proj_w, proj_h
    proj_w, proj_h = projector.width, projector.height
    print(f"[projector] Using display [{PROJECTOR_INDEX}]: {proj_w}x{proj_h}")

    # Centre point of the display — also the default projector grid origin
    centre_w = proj_w // 2
    centre_h = proj_h // 2
    global proj_origin
    if proj_origin is None:
        proj_origin = (centre_w, centre_h)

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
        # Startup section
        if Project_CV.grid_origin == None:
            # Display startup display
            canvas = startup(canvas, centre_w, centre_h)
        else:
            with img_lock:
                # Grab a snapshot of the current event dictionary
                snapshot = {k: set(v) for k, v in img_dict.items()}
            for key, values in snapshot.items():
                # For each key check the event and then place the event in the coords stored in value
                # This event is only displayed with a set of coords not indiviudally
                if key == "UNREST":
                        canvas = event_unrest(canvas, proj_origin, proj_tile_size, values)
                for value in values:
                    if key == "REVERSE":
                        canvas = event_reverse_move(canvas, proj_origin, proj_tile_size, value)
                    elif key == "MORE_SCORE":
                        canvas = event_more_score(canvas, proj_origin, proj_tile_size, value)
                    elif key == "EVENT":
                        canvas = event_tile(canvas, proj_origin, proj_tile_size, value)
                    elif key == "VOLCANO":
                        canvas = event_volcano(canvas, proj_origin, proj_tile_size, value)
                    elif key == "BAD_TILE":
                        canvas = event_bad_tile(canvas, proj_origin, proj_tile_size, value)
                    elif key == "GOOD_TILE":
                        canvas = event_good_tile(canvas, proj_origin, proj_tile_size, value)
            # Check for displaying the valid tile placement border
            with valid_b_lock:
                if valid_border:
                    canvas = set_valid_border(canvas, proj_w, proj_h)
            # Check for displaying the invalid tile placement border
            with invalid_lock:
                if invalid_border:
                    canvas = set_invalid_border(canvas, proj_w, proj_h)
            # Check for displaying the event has occured border
            with event_lock:
                if event_border:
                    canvas = set_event_border(canvas, proj_w, proj_h)
            # Check for displaying all posible valid moves for the given tile
            with valid_lock:
                showing_valid = valid_flag
                if showing_valid:
                    canvas = project_valids(canvas, proj_origin, proj_tile_size, valid_tiles)

        # Show image — must happen before signalling proj_blank_rendered so bridge
        # doesn't proceed until the blank frame has actually been sent to the display.
        cv.imshow("Projector", canvas)
        cv.waitKey(1)
        # Signal AFTER waitKey so the frame is in the display pipeline before CV proceeds.
        if Project_CV.grid_origin is not None and not showing_valid:
            proj_blank_rendered.set()
        #Qif c == ord('q'):
        #    break
        time.sleep(0.1)

    # Close all display windows and then exit
    cv.destroyAllWindows()