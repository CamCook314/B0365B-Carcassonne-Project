"""
CV test interface — run this instead of main.py while the engine is not yet complete.

The engine team will eventually replace the validate() call below with real game
logic.  The protocol this file implements is the contract they need to honour:

  Inputs  (read from Project_CV globals):
    Project_CV.cv_to_engine  — True when CV has a placement ready
    Project_CV.tile_id       — str, e.g. "ID38"
    Project_CV.grid_coord    — (gx, gy) tuple in CV coordinate space

  Output  (written to Project_CV globals):
    Project_CV.game_response = (True, 1)   valid placement
    Project_CV.game_response = (True, 0)   invalid placement

Usage
-----
  1. Optionally fill PRESET_RESPONSES with a sequence of 1s and 0s so the
     first N placements are answered automatically.
  2. Run:  python engine/cv_test_interface.py
  3. At any point type 'y' <Enter> or 'n' <Enter> in the terminal to queue
     the next response.  You can type several in advance — they drain one
     per placement.  If the queue is empty when a tile is placed the
     program just waits until you type.
"""

import sys
import os
import time
import threading
import queue

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cv import Project_CV

# ── Pre-set sequence ──────────────────────────────────────────────────────────
# Fill with 1 (valid) or 0 (invalid) to pre-queue responses before any tile
# is placed.  Leave as [] for fully interactive mode.
# Example: [1, 1, 0, 1, 1] → accept, accept, reject, accept, accept
PRESET_RESPONSES = []

# ── Internal response queue ───────────────────────────────────────────────────
_q: queue.Queue = queue.Queue()


def _keyboard_reader() -> None:
    """Background thread — reads y/n from stdin and pushes to the queue."""
    while True:
        try:
            line = input().strip().lower()
            if line == 'y':
                _q.put(1)
                print("  → queued: VALID")
            elif line == 'n':
                _q.put(0)
                print("  → queued: INVALID")
            elif line:
                print("  (y = valid,  n = invalid)")
        except EOFError:
            break


def validate() -> bool:
    """
    Return True to accept the placement, False to reject it.
    Blocks until a response is available in the queue.
    tile_id and grid_coord are printed by the caller before this is invoked.
    """
    if _q.empty():
        print("  Waiting for response — type 'y' (valid) or 'n' (invalid) ...")
    result = _q.get()          # Blocks here until the keyboard thread pushes something
    return result == 1


def _cv_thread() -> None:
    Project_CV.cv_main_loop()


def run() -> None:
    # Pre-populate queue from PRESET_RESPONSES
    for r in PRESET_RESPONSES:
        _q.put(r)
    if PRESET_RESPONSES:
        print(f"Pre-loaded {len(PRESET_RESPONSES)} response(s): {PRESET_RESPONSES}")

    # Start keyboard reader as a daemon so it dies when the main thread exits
    threading.Thread(target=_keyboard_reader, daemon=True).start()

    # Start CV loop as a daemon thread
    threading.Thread(target=_cv_thread, daemon=True).start()

    print("CV test interface running.")
    print("Type 'y' or 'n' at any time — responses are queued and consumed one")
    print("per placement.  Pre-type several in advance if you want.\n")

    while True:
        if Project_CV.cv_to_engine:
            tile_id    = Project_CV.tile_id
            grid_coord = Project_CV.grid_coord

            print(f"\n[CV → Engine]  tile={tile_id}  coord={grid_coord}")

            valid  = validate()
            result = 1 if valid else 0

            print(f"[Engine → CV]  {'VALID' if valid else 'INVALID'}")
            Project_CV.game_response = (True, result)

        if Project_CV.meeple_placed:
            print(f"[Meeple]  direction={Project_CV.meeple_direction}  (acknowledged)")
            Project_CV.meeple_placed    = False
            Project_CV.meeple_direction = None

        if Project_CV.meeple_skip:
            print("[Meeple]  skipped  (acknowledged)")
            Project_CV.meeple_skip = False

        time.sleep(0.1)    # 100 ms poll keeps this thread responsive without burning CPU


if __name__ == "__main__":
    run()
