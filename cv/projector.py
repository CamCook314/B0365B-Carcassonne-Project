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
PROJ_SCALE    = 1.0
if os.path.exists(_CFG_PATH):
    with open(_CFG_PATH) as _f:
        _pcfg = json.load(_f)
    PROJ_OFFSET_X = _pcfg.get("PROJ_OFFSET_X", 0)
    PROJ_OFFSET_Y = _pcfg.get("PROJ_OFFSET_Y", 0)
    PROJ_SCALE    = _pcfg.get("PROJ_SCALE", 1.0)
if PROJ_OFFSET_X or PROJ_OFFSET_Y:
    print(f"[projector] Manual offset from config: dx={PROJ_OFFSET_X}  dy={PROJ_OFFSET_Y}")
if PROJ_SCALE != 1.0:
    print(f"[projector] Tile scale from config: {PROJ_SCALE}")

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
PROJECTOR_INDEX = 3

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

def set_proj_calibration(origin=None, tile_size=None, tile_size_y=None, angle_deg=None,
                         apply_scale=True):
    global proj_origin, proj_tile_size, proj_tile_size_y
    global proj_angle_deg, proj_a, proj_b, proj_a_y, proj_b_y
    scale = PROJ_SCALE if apply_scale else 1.0
    if origin is not None:
        proj_origin      = (origin[0] + PROJ_OFFSET_X, origin[1] + PROJ_OFFSET_Y)
    if tile_size is not None:
        proj_tile_size   = tile_size * scale
    if tile_size_y is not None:
        proj_tile_size_y = tile_size_y * scale
    if angle_deg is not None:
        proj_angle_deg   = angle_deg
    θ      = math.radians(proj_angle_deg)
    cos_θ  = math.cos(θ)
    sin_θ  = math.sin(θ)
    proj_a   = proj_tile_size   * cos_θ
    proj_b   = proj_tile_size   * sin_θ
    proj_a_y = proj_tile_size_y * cos_θ
    proj_b_y = proj_tile_size_y * sin_θ


def set_proj_steps(a, b, a_y, b_y):
    """Override the step vectors directly — used by affine auto-calibration in bridge."""
    global proj_a, proj_b, proj_a_y, proj_b_y
    proj_a   = a
    proj_b   = b
    proj_a_y = a_y
    proj_b_y = b_y


# ── Homography calibration ────────────────────────────────────────────────────
# Maps camera proc-frame pixels (1920×1080) → projector pixels exactly,
# removing perspective and scale error from the linear formula.
# Set once at startup from 4 green calibration dots; None until then.
_homography:       "np.ndarray | None" = None
_cam_origin:       "tuple | None"      = None   # grid origin in cam proc pixels
_cam_a:            "float | None"      = None   # grid_tracker.a (tile_size * cos θ)
_cam_b:            "float | None"      = None   # grid_tracker.b (tile_size * sin θ)
_cam_c:            "float | None"      = None   # grid_tracker.c (y-step x-component)
_cam_d:            "float | None"      = None   # grid_tracker.d (y-step y-component)

# Projector positions of the 4 calibration dots — populated in projector_main()
# once resolution is known so startup() can draw them.
calib_dot_proj_pts: list = []


def set_homography(H):
    """Store the camera→projector homography matrix."""
    global _homography
    _homography = np.asarray(H, dtype=np.float64).reshape(3, 3)
    print("[projector] Homography set — using exact cam→proj mapping.")


def set_cam_grid(origin, a, b, c=None, d=None):
    """Store the camera-space grid parameters used by tile_grid_points with H.

    Called by bridge every poll cycle so _cam_origin stays current as the grid
    refits after each tile placement (tile_size rarely changes, but origin does).
    c and d are the y-step components from the 6-param affine model; when None
    the isotropic defaults (c=b, d=-a) are used as fallback.
    """
    global _cam_origin, _cam_a, _cam_b, _cam_c, _cam_d
    _cam_origin = origin
    _cam_a      = float(a)
    _cam_b      = float(b)
    if c is not None:
        _cam_c = float(c)
    if d is not None:
        _cam_d = float(d)


def cam_to_proj(cam_x: float, cam_y: float) -> tuple:
    """Map a camera proc-frame pixel to a projector pixel via the homography."""
    pt = _homography @ np.array([cam_x, cam_y, 1.0], dtype=np.float64)
    return (int(round(pt[0] / pt[2])), int(round(pt[1] / pt[2])))


def proj_tile_size_from_H(cam_origin, cam_a, cam_b):
    """Compute projector tile size (px) by mapping a unit cam step through H.

    Returns an int or None if H is not yet set.
    """
    if _homography is None or cam_origin is None:
        return None
    p0 = cam_to_proj(float(cam_origin[0]), float(cam_origin[1]))
    p1 = cam_to_proj(cam_origin[0] + cam_a, cam_origin[1] + cam_b)
    return max(1, int(round(math.hypot(p1[0] - p0[0], p1[1] - p0[1]))))


def compute_homography(cam_pts, proj_pts):
    """Compute H mapping camera proc-frame pixels to projector pixels.

    Orders both point sets TL→TR→BR→BL by y then x so the pairing is
    deterministic regardless of detection order.

    NOTE: with exactly 4 points findHomography always reports 0 reprojection
    error regardless of pairing.  A centroid sanity check catches gross
    ordering mistakes (the centroid of 4 symmetric dots is the display centre,
    so H(cam_centroid) should be close to proj_centroid).
    """
    def _tl_tr_br_bl(pts):
        arr   = np.array(pts, dtype=np.float32)
        by_y  = arr[np.argsort(arr[:, 1])]
        top   = by_y[:2][np.argsort(by_y[:2, 0])]   # TL, TR
        bot   = by_y[2:][np.argsort(by_y[2:, 0])]   # BL, BR
        return np.array([top[0], top[1], bot[1], bot[0]], dtype=np.float32)  # TL TR BR BL

    cam_ordered  = _tl_tr_br_bl(cam_pts)
    proj_ordered = _tl_tr_br_bl(proj_pts)

    print("[projector] Calibration correspondences:")
    for lbl, cp, pp in zip(["TL", "TR", "BR", "BL"], cam_ordered, proj_ordered):
        print(f"  {lbl}  cam=({cp[0]:.0f},{cp[1]:.0f})  proj=({pp[0]:.0f},{pp[1]:.0f})")

    H, _ = cv.findHomography(cam_ordered, proj_ordered)
    if H is None:
        print("[projector] compute_homography: findHomography failed.")
        return None

    # Sanity check: the centroid of the 4 symmetric dots equals the display
    # centre in both spaces.  H(cam_centroid) should be near proj_centroid.
    cam_c  = np.mean(np.array(cam_pts,  dtype=np.float64), axis=0)
    proj_c = np.mean(np.array(proj_pts, dtype=np.float64), axis=0)
    pt     = H @ np.array([cam_c[0], cam_c[1], 1.0])
    mapped = pt[:2] / pt[2]
    dist   = float(np.hypot(mapped[0] - proj_c[0], mapped[1] - proj_c[1]))
    print(f"[projector] Centroid check: cam ({cam_c[0]:.0f},{cam_c[1]:.0f}) "
          f"→ proj ({mapped[0]:.0f},{mapped[1]:.0f}), "
          f"expected ({proj_c[0]:.0f},{proj_c[1]:.0f}), error={dist:.0f}px")
    if dist > 100:
        print("[projector] WARNING: centroid error >100px — dot correspondences "
              "may be wrong.  Check that camera and projector orientations match.")
    return H


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
    _add = True
    with img_lock:
        # Check if key is in event keys
        if img in img_keys:
            # Check there isn't an event already at the same coords
            for key in img_keys:
                values = img_dict[key]
                if coord in values:
                    _add = False
        # Add event if nothing is at the coords
        if _add:
            if isinstance(coord, tuple):
                img_dict[img].add(coord)
            else:
                img_dict[img].update(coord)
    if _add:
        print(f"[PROJECTOR] >>> add_img: {img} at {coord}")

# Function that removes an event from the dictionary
def del_img(img, coord):
    with img_lock:
        if img in img_keys:
            if img != "UNREST":
                if img in img_dict:
                    img_dict[img].discard(coord)
            else:
                img_dict.pop(img, None)
    print(f"[PROJECTOR] >>> del_img: {img} at {coord}")

## START UP FUNCTION
def startup(canvas, centre_x, centre_y):
    if _homography is None and calib_dot_proj_pts and not Project_CV.calib_complete:
        # Calibration phase: show 4 green dots so the camera can detect them.
        # Hide the placement cross so the player knows not to place a tile yet.
        for pt in calib_dot_proj_pts:
            cv.circle(canvas, pt, 25, (0, 255, 0), -1)
        # Use white text so it doesn't show up in CV's green HSV filter
        cv.putText(canvas, "Calibrating projector...",
                   (centre_x - 220, centre_y), cv.FONT_HERSHEY_SIMPLEX,
                   1, (255, 255, 255), 2, cv.LINE_AA)
        cv.putText(canvas, "Press C in CV window to skip",
                   (centre_x - 210, centre_y + 50), cv.FONT_HERSHEY_SIMPLEX,
                   0.7, (200, 200, 200), 2, cv.LINE_AA)
    else:
        # H established (or calibration skipped) — show the normal placement cross.
        colour = (0, 255, 255)
        canvas = cv.drawMarker(canvas, (centre_x, centre_y), colour, cv.MARKER_CROSS, 30, 2)
    return canvas

# Function that calculates a given coords tile centre point, and start and end pixel coords.
# Primary path: camera 6-param model → homography → exact projector pixel.
# Fallback (no H / no cam grid): rotation-aware linear formula in projector-pixel space.
def tile_grid_points(grid_origin, _grid_tile_size, tile_coord, img_size, _tile_size_y=None):
    gx, gy = tile_coord
    if _homography is not None and _cam_origin is not None and _cam_a is not None:
        # Use the same affine model the camera tracks, then project through H.
        # c/d default to isotropic until the 6-param fit accumulates vertical data.
        c = _cam_c if _cam_c is not None else _cam_b
        d = _cam_d if _cam_d is not None else -_cam_a
        cam_x = _cam_origin[0] + gx * _cam_a + gy * c
        cam_y = _cam_origin[1] + gx * _cam_b + gy * d
        tile_origin_x, tile_origin_y = cam_to_proj(cam_x, cam_y)
        tile_origin_x += PROJ_OFFSET_X
        tile_origin_y += PROJ_OFFSET_Y
    else:
        tile_origin_x = round(grid_origin[0] + gx * proj_a   + gy * proj_b)
        tile_origin_y = round(grid_origin[1] + gx * proj_b_y - gy * proj_a_y)
    tile_origin = (tile_origin_x, tile_origin_y)
    tile_start  = (tile_origin_x - (img_size // 2), tile_origin_y + (img_size // 2))
    tile_end    = (tile_origin_x + (img_size // 2), tile_origin_y - (img_size // 2))
    return (tile_start, tile_end, tile_origin)

# Function that sets the invalid move border flag
def set_invalid():
    global invalid_border
    with invalid_lock:
        invalid_border = True
    print("[PROJECTOR] >>> Invalid border ON")

# Function that clears the invalid move border flag
def clear_invalid():
    global invalid_border
    with invalid_lock:
        invalid_border = False
    print("[PROJECTOR] >>> Invalid border OFF")

# Function that draws the invalid move border
def set_invalid_border(canvas, width, height):
    colour = (0, 165, 255)  # Orange — filtered by blob_pipeline's proj_orange mask
    thickness = 10
    cv.rectangle(canvas, (0, 0), (width - 1, height - 1), colour, thickness)
    return canvas

# Function that sets the valid move border flag
def set_valid():
    global valid_border
    with valid_b_lock:
        valid_border = True
    print("[PROJECTOR] >>> Valid border ON")

# Function that clears the valid move border flag
def clear_valid():
    global valid_border
    with valid_b_lock:
        valid_border = False
    print("[PROJECTOR] >>> Valid border OFF")

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
    print("[PROJECTOR] >>> Event border ON")

# Function that clears the event border flag
def clear_event():
    global event_border
    with event_lock:
        event_border = False
    print("[PROJECTOR] >>> Event border OFF")

# Function the draws the event border
def set_event_border(canvas, width, height):
    colour = (255, 0, 0)  # Blue — filtered by blob_pipeline's proj_blue mask
    thickness = 10
    cv.rectangle(canvas, (0, 0), (width - 1, height - 1), colour, thickness)
    return canvas

# Function that sets the valid placement flag and coords
def set_proj_valid(coords):
    global valid_flag
    global valid_tiles
    with valid_lock:
        valid_flag = True
        valid_tiles = coords
    print(f"[PROJECTOR] >>> Valid placements ON: {len(coords)} positions {sorted(coords)}")
    # Always show the full-screen border whenever valid placements are active
    # so the player can see from across the table that it's time to place a tile.
    if coords:
        set_valid()

# Function that clears the valid tile flags and reset tile coords
def clear_proj_valid():
    global valid_flag
    global valid_tiles
    with valid_lock:
        valid_flag = False
        valid_tiles = None
    clear_valid()  # remove full-screen border whenever placements are cleared
    proj_blank_rendered.clear()  # projector hasn't rendered the blank frame yet
    print("[PROJECTOR] >>> Valid placements cleared")

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
    global proj_w, proj_h, calib_dot_proj_pts
    proj_w, proj_h = projector.width, projector.height
    print(f"[projector] Using display [{PROJECTOR_INDEX}]: {proj_w}x{proj_h}")

    # Calibration dot positions at the four 25%/75% corners — spread evenly so
    # the homography is well-conditioned and the dots are clearly separated.
    calib_dot_proj_pts = [
        (round(proj_w * 0.25), round(proj_h * 0.25)),  # top-left
        (round(proj_w * 0.75), round(proj_h * 0.25)),  # top-right
        (round(proj_w * 0.75), round(proj_h * 0.75)),  # bottom-right
        (round(proj_w * 0.25), round(proj_h * 0.75)),  # bottom-left
    ]
    print(f"[projector] Calibration dot positions: {calib_dot_proj_pts}")

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
        showing_valid = False   # safe default; set inside the else branch below
        # Create an empty black frame
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
            # Always draw a border — colour indicates current game state.
            # Priority: event (blue) > invalid (orange) > default (magenta).
            with event_lock:
                _border_event = event_border
            with invalid_lock:
                _border_invalid = invalid_border
            if _border_event:
                canvas = set_event_border(canvas, proj_w, proj_h)
            elif _border_invalid:
                canvas = set_invalid_border(canvas, proj_w, proj_h)
            else:
                canvas = set_valid_border(canvas, proj_w, proj_h)
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