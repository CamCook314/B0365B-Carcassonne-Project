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
import os
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
import api as engine_api

API_BASE = "http://127.0.0.1:1234"


# ── API helpers ───────────────────────────────────────────────────────────────

def _update_remaining_families():
    """Read the tile bag directly and push remaining family base IDs to CV."""
    if engine_api.tile_bag_instance is None:
        return
    Project_CV.remaining_families = {
        (int(k.replace("ID", "")) // 4) * 4
        for k in engine_api.tile_bag_instance.tile_bag.keys()
    }


def _post(path: str, body: dict) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=body, timeout=5)
        return r.json()
    except Exception as e:
        print(f"[bridge] POST {path} failed: {e}")
        return None


def _handle_tile_checked():
    tile_id    = Project_CV.tile_id
    candidates = Project_CV.tile_candidates   # list of (score, tile_id) tuples

    # Send top 4 alternatives (different family from the pending tile).
    # Exclude the same family — it's already shown as the main tile preview.
    pending_family = int(tile_id.replace("ID", "")) // 4
    candidate_ids = [
        rid for _, rid in candidates
        if int(rid.replace("ID", "")) // 4 != pending_family
    ][:10]

    print(f"[bridge] tile_checked - tile={tile_id}  candidates={candidate_ids[:3]}...")
    resp = _post("/pending", {"tile_id": tile_id, "candidates": candidate_ids})
    if resp and "error" not in resp:
        print(f"[bridge] /pending OK - {len(resp.get('valid_positions', []))} valid positions")
    else:
        print(f"[bridge] /pending error: {resp}")

    Project_CV.tile_checked = False


def _handle_cv_to_engine():
    tile_id    = Project_CV.tile_id
    grid_coord = Project_CV.grid_coord
    gx, gy     = grid_coord

    print(f"[bridge] cv_to_engine - tile={tile_id}  coord=({gx},{gy})")
    resp = _post("/place", {"x": gx, "y": gy, "rotation_id": tile_id})

    if resp and resp.get("status") == "ok":
        print(f"[bridge] /place OK - placed {resp.get('placed')} at {resp.get('position')}")
        Project_CV.game_response = (True, 1)
        _update_remaining_families()
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
    Project_CV.meeple_placed    = False
    Project_CV.meeple_colour    = None
    Project_CV.meeple_direction = None


def _handle_meeple_skip():
    print("[bridge] meeple_skip - calling /meeple/skip")
    resp = _post("/meeple/skip", {})
    if resp and resp.get("status") == "ok":
        print(f"[bridge] /meeple/skip OK - turn={resp.get('turn')}  player={resp.get('current_player')}")
    else:
        print(f"[bridge] /meeple/skip error: {resp}")
    Project_CV.meeple_skip = False


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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("[bridge] Starting Vite dev server...")
    vite_proc = _run_frontend()
    print("Website up on port 5173")

    print("[bridge] Starting Flask API...")
    threading.Thread(target=_run_api, daemon=True).start()

    # Give Flask a moment to bind before CV starts making requests
    time.sleep(1.5)

    print("[bridge] Starting CV loop...")
    threading.Thread(target=_run_cv, daemon=True).start()

    print("[bridge] All components running. Waiting for /start...\n")

    try:
        # Wait for the frontend to POST /start before entering the game loop
        while engine_api.game_state is None:
            time.sleep(0.1)

        game = engine_api.game_state
        print(f"[bridge] Game started - {len(game.players)} players.\n")
        _update_remaining_families()

        while len(engine_api.tile_bag_instance.tile_bag) > 0:
            for p in game.players: # looping through each player in the game (use p to dictate which player's turn)

                # breaks if there are no pieces left, the game should end
                if len(engine_api.tile_bag_instance.tile_bag) == 0:
                    break

                tiles_left = len(engine_api.tile_bag_instance.tile_bag) // 4
                print(f"[bridge] {p.return_colour()}'s turn - {tiles_left} tiles left")

                Project_CV.expected_meeple_colour = p.return_colour().lower()

                turn_done        = False
                tile_just_placed = False  # True after /place accepted, until meeple resolved

                while not turn_done:
                    try:
                        if Project_CV.tile_checked:
                            _handle_tile_checked()

                        if Project_CV.cv_to_engine:
                            _handle_cv_to_engine()
                            # If the engine accepted the placement, pending_placement is now set.
                            # Track this so we can detect when the website resolves the meeple.
                            tile_just_placed = engine_api.pending_placement is not None

                        # Website button pressed: pending_placement cleared without CV flags being set
                        if tile_just_placed and engine_api.pending_placement is None:
                            print("[bridge] Meeple/skip handled via website — unblocking CV.")
                            Project_CV.meeple_placed  = False   # clear in case safety also fired
                            Project_CV.meeple_skip    = False
                            Project_CV.meeple_handled = True
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

        # Restore terminal - os.system uses cmd.exe on Windows so stty won't work.
        # subprocess.run finds the Git Bash stty binary via PATH instead.
        try:
            subprocess.run(["stty", "sane"], check=False)
        except FileNotFoundError:
            pass  # stty not available (pure cmd.exe) - open a new terminal


if __name__ == "__main__":
    main()
