"""
bridge.py - Single entry point for the Carcassonne AR system.

Run with:
    python engine/bridge.py

Starts three components:
  1. Flask API server  (engine/api.py)
  2. CV main loop      (cv/Project_CV.py)
  3. Vite dev server   (frontend/)

Then polls CV globals every 100 ms and makes the appropriate API calls:
  - tile_checked  → POST /pending  (with tile_id + ranked candidates)
  - cv_to_engine  → POST /place    (with x, y, rotation_id)
"""

import sys
import shutil
import time
import threading
import subprocess
import requests
from pathlib import Path

# Make project root and engine dir importable
ROOT = Path(__file__).parent.parent
ENGINE = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE))

from cv import Project_CV
from cv import projector
import api as engine_api

API_BASE = "http://127.0.0.1:1234"

# Camera processing resolution — must match PROC_W/PROC_H in Project_CV.py
_CV_PROC_W = 1920
_CV_PROC_H = 1080

_last_proj_tile_size: float | None = None   # tracks last calibrated value to avoid redundant calls
_last_proj_angle: float | None = None       # tracks last calibrated angle


def _sync_projector_calibration():
    """Derive projector tile size, origin, and rotation from CV's measured grid and push to projector."""
    global _last_proj_tile_size, _last_proj_angle
    tile_size = Project_CV.grid_tile_size
    origin    = Project_CV.grid_origin
    angle     = Project_CV.grid_angle
    if tile_size is None or origin is None or angle is None:
        return
    if projector.proj_w is None or projector.proj_h is None:
        return
    if tile_size == _last_proj_tile_size and angle == _last_proj_angle:
        return  # already up to date
    scale_x = projector.proj_w / _CV_PROC_W
    scale_y = projector.proj_h / _CV_PROC_H
    proj_origin      = (round(origin[0] * scale_x), round(origin[1] * scale_y))
    proj_tile_size   = round(tile_size * scale_x)   # X spacing
    proj_tile_size_y = round(tile_size * scale_y)   # Y spacing (projector is 16:10, camera is 16:9)
    projector.set_proj_calibration(origin=proj_origin, tile_size=proj_tile_size,
                                   tile_size_y=proj_tile_size_y, angle=angle)
    _last_proj_tile_size = tile_size
    _last_proj_angle     = angle
    print(f"[bridge] Projector calibration updated — origin={proj_origin}"
          f"  tile_size={proj_tile_size}px (x)  {proj_tile_size_y}px (y)  angle={angle:.2f}°")


# ── API helpers ───────────────────────────────────────────────────────────────

def _update_remaining_families():
    """Read the tile bag directly and push remaining family base IDs to CV."""
    if engine_api.tile_bag_instance is None:
        return
    Project_CV.remaining_families = {
        (int(k.replace("ID", "")) // 4) * 4
        for k in engine_api.tile_bag_instance.tile_bag.keys()
    }


LIVE_ID_CROPS_DIR = ROOT / "cv" / "live_id_crops"
GAME_REFS_DIR     = ROOT / "cv" / "game_refs"

_last_placed_id: str | None = None


def _save_id_crop_as_game_ref(confirmed_id: str):
    """Copy the last identification crop to cv/live_id_crops/<confirmed_id>.jpg.

    Stored separately from game_refs so they don't corrupt rotation training
    (the image content may be at a different orientation than the filename implies).
    train.py uses both directories for family classification; train_rotation.py
    only uses game_refs where rotation labels are verified.
    """
    src = Project_CV.last_id_crop_path
    if not src or not Path(src).exists():
        return
    LIVE_ID_CROPS_DIR.mkdir(exist_ok=True)
    dst = LIVE_ID_CROPS_DIR / f"{confirmed_id}.jpg"
    shutil.copy2(src, dst)
    print(f"[bridge] Saved id crop → live_id_crops/{confirmed_id}.jpg")


def _save_placed_crop_as_game_ref(confirmed_id: str | None):
    """Copy the placed-slot crop to cv/game_refs/<confirmed_id>.jpg for rotation training.

    Unlike live_id_crops, placed-slot crops go through crop_placed_slot() with the
    same board_angle deskew used during rotation inference, so rotation labels are
    verified and safe for train_rotation.py.
    """
    if confirmed_id is None:
        return
    src = Project_CV.last_placed_crop_path
    if not src or not Path(src).exists():
        return
    GAME_REFS_DIR.mkdir(exist_ok=True)
    dst = GAME_REFS_DIR / f"{confirmed_id}.jpg"
    shutil.copy2(src, dst)
    print(f"[bridge] Saved placed crop → game_refs/{confirmed_id}.jpg")


def _post(path: str, body: dict) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=body, timeout=5)
        return r.json()
    except Exception as e:
        print(f"[bridge] POST {path} failed: {e}")
        return None


def _debug_proj_alignment(vp_tuples: list):
    """Print camera-PROC pixel vs projector pixel for each valid grid position.

    Helps tune PROJ_OFFSET_X / PROJ_OFFSET_Y in cv/config.json when the
    projected outlines are visually offset from the physical tile positions.
    """
    gox = Project_CV.grid_origin
    ts  = Project_CV.grid_tile_size
    if gox is None or ts is None:
        return
    pox, poy = projector.proj_origin
    pts_x    = projector.proj_tile_size
    pts_y    = projector.proj_tile_size_y
    ox, oy   = gox
    print(f"[proj-align] cam_origin=({ox},{oy})  cam_tile={ts}px  "
          f"proj_origin=({pox},{poy})  proj_tile=({pts_x}x,{pts_y}y)px  "
          f"offset=({projector.PROJ_OFFSET_X},{projector.PROJ_OFFSET_Y})")
    for gx, gy in vp_tuples:
        cam_x = round(ox + gx * ts)
        cam_y = round(oy - gy * ts)
        prj_x = round(pox + gx * pts_x)
        prj_y = round(poy - gy * pts_y)
        print(f"  grid({gx:+d},{gy:+d}):  cam=({cam_x},{cam_y})  proj=({prj_x},{prj_y})")


def _handle_tile_checked():
    tile_id    = Project_CV.tile_id
    candidates = Project_CV.tile_candidates   # list of (score, tile_id) tuples

    # Send top 4 alternatives (different family from the pending tile).
    # Exclude the same family — it's already shown as the main tile preview.
    pending_family = int(tile_id.replace("ID", "")) // 4
    candidate_ids = [
        rid for _, rid in candidates
        if int(rid.replace("ID", "")) // 4 != pending_family
    ][:20]

    print(f"[bridge] tile_checked - tile={tile_id}  candidates={candidate_ids[:3]}...")
    resp = _post("/pending", {"tile_id": tile_id, "candidates": candidate_ids})
    if resp and "error" not in resp:
        vp = resp.get("valid_positions", [])
        vp_tuples = [(int(p[0]), int(p[1])) for p in vp]
        Project_CV.valid_placements = set(vp_tuples)
        # Don't project for the origin tile — grid not yet placed, anywhere is valid
        if Project_CV.grid_origin is not None:
            projector.set_proj_valid(vp_tuples)
        print(f"[bridge] /pending OK - {len(vp)} valid positions")
        _debug_proj_alignment(vp_tuples)
    else:
        Project_CV.valid_placements = None
        projector.clear_proj_valid()
        print(f"[bridge] /pending error: {resp}")

    Project_CV.tile_checked = False


def _handle_cv_to_engine():
    global _last_placed_id
    tile_id    = Project_CV.tile_id
    grid_coord = Project_CV.grid_coord
    gx, gy     = grid_coord

    print(f"[bridge] cv_to_engine - tile={tile_id}  coord=({gx},{gy})")
    resp = _post("/place", {"x": gx, "y": gy, "rotation_id": tile_id})

    if resp and resp.get("status") == "ok":
        confirmed_id = resp.get("placed")
        _last_placed_id = confirmed_id
        print(f"[bridge] /place OK - placed {confirmed_id} at {resp.get('position')}")
        # Clear projection BEFORE signalling CV to proceed.
        # Wait for the projector thread to confirm it has rendered a blank frame
        # so the camera sees no projection before rotation matching or meeple baseline.
        Project_CV.valid_placements = None
        projector.clear_proj_valid()
        projector.proj_blank_rendered.wait(timeout=0.5)
        Project_CV.game_response = (True, 1)
        _update_remaining_families()
        _save_id_crop_as_game_ref(confirmed_id)

        # Compute which sides of the placed tile are valid for meeple placement
        # and pass to CV so ambiguous detections can snap to the nearest valid side.
        if engine_api.pending_placement is not None:
            tile = engine_api.pending_placement["tile"]
            Project_CV.valid_meeple_sides = [
                s for s in ("up", "down", "left", "right", "centre")
                if Project_CV.is_valid_meeple_side(tile, s)
            ]
            print(f"[bridge] valid meeple sides: {Project_CV.valid_meeple_sides}")
        else:
            Project_CV.valid_meeple_sides = None
    else:
        print(f"[bridge] /place error: {resp}")
        Project_CV.game_response = (True, 0)

    Project_CV.cv_to_engine = False


def _handle_meeple_placed():
    colour    = Project_CV.meeple_colour
    direction = Project_CV.meeple_direction
    print(f"[bridge] meeple_placed - colour={colour}  direction={direction}")
    resp = _post("/meeple", {"colour": colour, "direction": direction})
    if resp and resp.get("status") == "ok":
        print(f"[bridge] /meeple OK - turn={resp.get('turn')}  player={resp.get('current_player')}")
    else:
        print(f"[bridge] /meeple error: {resp}")
        # Fall back to skip so the game state stays consistent (e.g. colour mismatch)
        print("[bridge] /meeple failed — falling back to /meeple/skip")
        skip_resp = _post("/meeple/skip", {})
        if skip_resp and skip_resp.get("status") == "ok":
            print(f"[bridge] /meeple/skip fallback OK - turn={skip_resp.get('turn')}")
        else:
            print(f"[bridge] /meeple/skip fallback error: {skip_resp}")
    _save_placed_crop_as_game_ref(_last_placed_id)
    Project_CV.meeple_placed        = False
    Project_CV.meeple_colour        = None
    Project_CV.meeple_direction     = None
    Project_CV.valid_meeple_sides   = None


def _handle_meeple_skip():
    print("[bridge] meeple_skip - calling /meeple/skip")
    resp = _post("/meeple/skip", {})
    if resp and resp.get("status") == "ok":
        print(f"[bridge] /meeple/skip OK - turn={resp.get('turn')}  player={resp.get('current_player')}")
    else:
        print(f"[bridge] /meeple/skip error: {resp}")
    _save_placed_crop_as_game_ref(_last_placed_id)
    Project_CV.meeple_skip          = False
    Project_CV.valid_meeple_sides   = None


# ── Thread targets ─────────────────────────────────────────────────────────────

def _run_api():
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    engine_api.app.run(host="127.0.0.1", port=1234, debug=False, use_reloader=False)


def _run_cv():
    Project_CV.cv_main_loop()


def _run_frontend():
    frontend_dir = ROOT / "frontend"
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    return subprocess.Popen(
        [npm, "run", "dev"],
        cwd=str(frontend_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def _run_projector():
    projector.projector_main()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("[bridge] Starting Vite dev server...")
    vite_proc = _run_frontend()
    print("Website up on port 5173")

    print("[bridge] Starting Flask API...")
    threading.Thread(target=_run_api, daemon=True).start()

    # Give Flask a moment to bind before CV starts making requests
    time.sleep(1.5)

    print("[bridge] Starting projector loop...")
    threading.Thread(target=_run_projector, daemon=True).start()

    # Give time for projector to start up
    time.sleep(0.5)

    print("[bridge] Starting CV loop...")
    threading.Thread(target=_run_cv, daemon=True).start()

    print("[bridge] All components running. Waiting for /start...\n")

    try:
        # Wait for the frontend to POST /start before entering the game loop
        while engine_api.game_state is None:
            _sync_projector_calibration()
            time.sleep(0.1)

        game = engine_api.game_state
        print(f"[bridge] Game started - {len(game.players)} players.\n")
        _update_remaining_families()

        while len(engine_api.tile_bag_instance.tile_bag) > 0:
            # Read current player from the engine each turn so that game events
            # like extra_turn (which keep currentIndex the same) are respected.
            p = game.players[engine_api.game_state.currentIndex]

            tiles_left = len(engine_api.tile_bag_instance.tile_bag) // 4
            print(f"[bridge] {p.return_colour()}'s turn - {tiles_left} tiles left")

            Project_CV.expected_meeple_colour = p.return_colour().lower()

            turn_done        = False
            tile_just_placed = False  # True after /place accepted, until meeple resolved

            while not turn_done:
                try:
                    _sync_projector_calibration()

                    if Project_CV.tile_checked:
                        _handle_tile_checked()

                    # Tile just confirmed as placed — clear projection NOW so the rotation
                    # crop (taken ~2s later at MEEPLE_BASELINE_SETTLE) sees a clean image.
                    if Project_CV.proj_clear_requested:
                        Project_CV.valid_placements = None
                        projector.clear_proj_valid()
                        projector.proj_blank_rendered.wait(timeout=0.5)
                        Project_CV.proj_clear_requested = False
                        print("[bridge] Projection cleared early for rotation crop.")

                    if Project_CV.cv_to_engine:
                        _handle_cv_to_engine()
                        # If the engine accepted the placement, pending_placement is now set.
                        # Track this so we can detect when the website resolves the meeple.
                        tile_just_placed = engine_api.pending_placement is not None

                    # Website button pressed: pending_placement cleared without CV flags being set
                    if tile_just_placed and engine_api.pending_placement is None:
                        print("[bridge] Meeple/skip handled via website — unblocking CV.")
                        _save_placed_crop_as_game_ref(_last_placed_id)
                        Project_CV.meeple_placed        = False   # clear in case safety also fired
                        Project_CV.meeple_skip          = False
                        Project_CV.meeple_handled       = True
                        Project_CV.valid_meeple_sides   = None
                        turn_done        = True
                        tile_just_placed = False

                    elif Project_CV.meeple_placed:
                        _handle_meeple_placed()
                        turn_done        = True
                        tile_just_placed = False

                    elif Project_CV.meeple_skip:
                        _handle_meeple_skip()
                        turn_done        = True
                        tile_just_placed = False

                except Exception as e:
                    print(f"[bridge] Poll error: {e}")

                time.sleep(0.1)

        print("[bridge] Tile bag empty - game over")

        # Trigger end-game scoring on the engine and report final scores
        resp = _post("/end", {})
        if resp and resp.get("status") == "ok":
            print(f"[bridge] /end OK - final scores: {resp.get('scores')}")
        else:
            print(f"[bridge] /end error: {resp}")

    except KeyboardInterrupt:
        print("\n[bridge] Shutting down...")
    finally:
        # Kill Vite - it's a real subprocess, not a daemon thread, so it survives Ctrl+C
        if vite_proc.poll() is None:
            vite_proc.terminate()
            vite_proc.wait()
            print("[bridge] Vite stopped.")

        # Close down projector display as Ctrl+C doesn't remove projector connection
        projector.projector_exit()

        # Restore terminal - os.system uses cmd.exe on Windows so stty won't work.
        # subprocess.run finds the Git Bash stty binary via PATH instead.
        try:
            subprocess.run(["stty", "sane"], check=False)
        except FileNotFoundError:
            pass  # stty not available (pure cmd.exe) - open a new terminal


if __name__ == "__main__":
    main()
