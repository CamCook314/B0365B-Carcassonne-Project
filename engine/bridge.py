"""
bridge.py — Single entry point for the Carcassonne AR system.

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

    # Send ranked tile IDs only (frontend doesn't need raw scores)
    candidate_ids = [rid for _, rid in candidates]

    print(f"[bridge] tile_checked — tile={tile_id}  candidates={candidate_ids[:3]}...")
    resp = _post("/pending", {"tile_id": tile_id, "candidates": candidate_ids})
    if resp and "error" not in resp:
        print(f"[bridge] /pending OK — {len(resp.get('valid_positions', []))} valid positions")
    else:
        print(f"[bridge] /pending error: {resp}")

    Project_CV.tile_checked = False


def _handle_cv_to_engine():
    tile_id    = Project_CV.tile_id
    grid_coord = Project_CV.grid_coord
    gx, gy     = grid_coord

    print(f"[bridge] cv_to_engine — tile={tile_id}  coord=({gx},{gy})")
    resp = _post("/place", {"x": gx, "y": gy, "rotation_id": tile_id})

    if resp and resp.get("status") == "ok":
        print(f"[bridge] /place OK — placed {resp.get('placed')} at {resp.get('position')}")
        Project_CV.game_response = (True, 1)
    else:
        print(f"[bridge] /place error: {resp}")
        Project_CV.game_response = (True, 0)

    Project_CV.cv_to_engine = False


def _handle_meeple_placed():
    colour    = Project_CV.meeple_colour
    direction = Project_CV.meeple_direction
    print(f"[bridge] meeple_placed — colour={colour}  direction={direction}")
    resp = _post("/meeple", {"colour": colour, "direction": direction})
    if resp and resp.get("status") == "ok":
        print(f"[bridge] /meeple OK — turn={resp.get('turn')}  player={resp.get('current_player')}")
    else:
        print(f"[bridge] /meeple error: {resp}")
    Project_CV.meeple_placed    = False
    Project_CV.meeple_colour    = None
    Project_CV.meeple_direction = None


def _handle_meeple_skip():
    print("[bridge] meeple_skip — calling /meeple/skip")
    resp = _post("/meeple/skip", {})
    if resp and resp.get("status") == "ok":
        print(f"[bridge] /meeple/skip OK — turn={resp.get('turn')}  player={resp.get('current_player')}")
    else:
        print(f"[bridge] /meeple/skip error: {resp}")
    Project_CV.meeple_skip = False


# ── Thread targets ─────────────────────────────────────────────────────────────

def _run_api():
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

    print("[bridge] Starting Flask API...")
    threading.Thread(target=_run_api, daemon=True).start()

    # Give Flask a moment to bind before CV starts making requests
    time.sleep(1.5)

    print("[bridge] Starting CV loop...")
    threading.Thread(target=_run_cv, daemon=True).start()

    print("[bridge] All components running. Polling CV globals...\n")

    try:
        while True:
            try:
                if Project_CV.tile_checked:
                    _handle_tile_checked()

                if Project_CV.cv_to_engine:
                    _handle_cv_to_engine()

                if Project_CV.meeple_placed:
                    _handle_meeple_placed()

                if Project_CV.meeple_skip:
                    _handle_meeple_skip()

            except Exception as e:
                print(f"[bridge] Poll error: {e}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[bridge] Shutting down...")
    finally:
        # Kill Vite — it's a real subprocess, not a daemon thread, so it survives Ctrl+C
        if vite_proc.poll() is None:
            vite_proc.terminate()
            vite_proc.wait()
            print("[bridge] Vite stopped.")

        # Restore terminal — os.system uses cmd.exe on Windows so stty won't work.
        # subprocess.run finds the Git Bash stty binary via PATH instead.
        try:
            subprocess.run(["stty", "sane"], check=False)
        except FileNotFoundError:
            pass  # stty not available (pure cmd.exe) — open a new terminal


if __name__ == "__main__":
    main()
