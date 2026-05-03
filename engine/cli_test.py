"""
cli_test.py — Drive a scripted 3-player game against the running API.

Run the live system first (engine/bridge.py or engine/api.py), then:
    python engine/cli_test.py

A 1-second pause separates each tile and meeple action so the live UI has
time to render between steps.

Game shape (mimics the start of a real Carcassonne game with the River
expansion fully placed before regular play):

  Turns 1-9   River expansion. 9 tiles laid as an S-curve from the top-left
              source-cap east → south → east → south to a second source-cap.
              Players rotate (red, blue, green) but no meeples are placed —
              river tiles have no roads or cities to claim.

  Turns 10-13 GREEN's 4-tile completed city along y=1 (above the river start).
              Green meeples on turn 12; turn 13 caps the right end and the
              city completes mid-game → +8 to green via score_structure().

  Turns 14-15 BLUE's 2-tile completed road at (5,-2)-(5,-3). Blue claims it
              on turn 14, green caps it on turn 15 → +2 to blue mid-game.

  Turns 16-17 RED's 2-tile completed road at (3,0)-(4,0). Red claims it on
              turn 16, blue caps it on turn 17 → +2 to red mid-game.

  Turns 18-19 Filler: a stand-alone monastery and a stray road dead-end.

  Turns 20-21 BLUE's incomplete 2-tile city at (-1,0)-(-1,1). Blue claims it
              on turn 20; green extends with a cap-down on turn 21. The city
              still has one open edge → stays in self.structures until /end,
              then score_end_game() awards 2 partial points (1 per tile).

  Turns 22-30 More tile placements to fill the board: three additional
              monasteries (no claims), a road tile, a road cap that joins
              with another road tile, etc. None of these add player score —
              they're just to make the board feel populated like a real game.

Final: GREEN 8 (completed city), BLUE 4 (completed road + incomplete city),
       RED 2 (completed road). Green wins.
"""

import sys
import time
import requests

API = "http://127.0.0.1:1234"
DELAY = 1.0   # seconds between actions


# Each turn: (player_colour, tile_family_for_pending, x, y, meeple_direction, rotation_id)
# meeple_direction=None  → /meeple/skip
# rotation_id=None       → let the API pick the first valid rotation at (x,y)
TURNS = [
    # ── River expansion (turns 1-9, no meeples) ──────────────────────────────
    ("red",   "ID0",   0,  0, None,    None),     # source cap (right)
    ("blue",  "ID9",   1,  0, None,    None),     # straight L+R
    ("green", "ID32",  2,  0, None,    None),     # corner L→down
    ("red",   "ID8",   2, -1, None,    None),     # straight U+D
    ("blue",  "ID40",  2, -2, None,    None),     # corner U→right
    ("green", "ID13",  3, -2, None,    None),     # straight L+R
    ("red",   "ID42",  4, -2, None,    "ID42"),   # corner L→down (default would pick ID41=U+L)
    ("blue",  "ID10",  4, -3, None,    "ID10"),   # straight U+D (force fresh tile object)
    ("green", "ID1",   4, -4, None,    None),     # bottom source cap (up)

    # ── Green's 4-tile completed city (turns 10-13) ──────────────────────────
    ("red",   "ID92",  0,  1, None,    None),     # cap-left, skip
    ("blue",  "ID233", 1,  1, None,    None),     # mid #1, skip
    ("green", "ID232", 2,  1, "right", "ID235"),  # mid #2 (forced) — green claims city
    ("red",   "ID94",  3,  1, None,    None),     # cap-right → city completes → +8 green

    # ── Blue's 2-tile completed road (turns 14-15) ───────────────────────────
    ("blue",  "ID122", 5, -2, "down",  None),     # blue claims road dead-end
    ("green", "ID122", 5, -3, None,    "ID123"),  # green caps it → +2 blue

    # ── Red's 2-tile completed road (turns 16-17) ────────────────────────────
    ("red",   "ID122", 3,  0, "right", "ID122"),  # red claims road dead-end
    ("blue",  "ID122", 4,  0, None,    "ID120"),  # blue caps it → +2 red

    # ── Filler (turns 18-19) ────────────────────────────────────────────────
    ("green", "ID88",  4,  1, None,    None),     # monastery, no meeple (engine bug)
    ("red",   "ID132", 5,  1, None,    "ID133"),  # stray road-down dead-end

    # ── Blue's incomplete 2-tile city (turns 20-21) ─────────────────────────
    ("blue",  "ID232", -1, 0, "up",    "ID232"),  # blue claims a fresh city
    ("green", "ID92", -1,  1, None,    "ID95"),   # extend with cap-down (closes one edge)

    # ── Board-filling turns (22-30) ──────────────────────────────────────────
    ("red",   "ID88",  1,  2, None,    "ID89"),   # monastery
    ("blue",  "ID88",  2,  2, None,    "ID90"),   # monastery
    ("green", "ID88",  3,  2, None,    "ID91"),   # monastery
    ("red",   "ID68", -1,  2, None,    None),     # road L+R tile (no claim)
    ("blue",  "ID132", 0,  2, None,    "ID132"),  # road cap-left (joins ID68)
    ("green", "ID132", 2, -3, None,    "ID134"),  # road right tile
    ("red",   "ID64",  3, -3, None,    None),     # ID67 picked: connects via road into ID134
    ("blue",  "ID132", 5, -1, None,    "ID135"),  # stray road-up dead-end
    ("green", "ID0",   1, -1, None,    "ID2"),    # river-left only (decorative)
]


def post(path, body=None):
    r = requests.post(f"{API}{path}", json=body or {}, timeout=5)
    return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text


def get(path):
    r = requests.get(f"{API}{path}", timeout=5)
    return r.status_code, r.json()


def show_scores(label):
    code, state = get("/gamestate")
    if code != 200:
        print(f"  [/gamestate {code}] {state}")
        return
    line = ", ".join(f"{p['colour']}={p['score']} ({p['meeples']} meeples)" for p in state["players"])
    print(f"  {label}: {line}  | game_over={state['game_over']}")


def main():
    print("=== Reset + start 3-player game ===")
    post("/reset")
    code, resp = post("/start", {"players": 3})
    if code != 201:
        print(f"  /start failed: {resp}")
        sys.exit(1)
    print(f"  {resp}")
    show_scores("initial")

    for i, (colour, tile_family, x, y, direction, rotation_id) in enumerate(TURNS, start=1):
        print(f"\n=== Turn {i}: {colour} → tile {tile_family} at ({x},{y}), "
              f"{'meeple ' + direction if direction else 'skip'}"
              f"{', forced ' + rotation_id if rotation_id else ''} ===")

        time.sleep(DELAY)
        code, resp = post("/pending", {"tile_id": tile_family})
        if code != 200:
            print(f"  /pending failed: {resp}")
            sys.exit(1)
        print(f"  /pending → tile_id={resp['tile_id']}, {len(resp['valid_positions'])} valid positions")

        time.sleep(DELAY)
        place_body = {"x": x, "y": y}
        if rotation_id is not None:
            place_body["rotation_id"] = rotation_id
        code, resp = post("/place", place_body)
        if code != 200:
            print(f"  /place failed: {resp}")
            sys.exit(1)
        print(f"  /place  → placed {resp['placed']} at {resp['position']}")

        time.sleep(DELAY)
        if direction is None:
            code, resp = post("/meeple/skip")
            print(f"  /skip   → turn={resp.get('turn')} next_player={resp.get('current_player')}")
        else:
            code, resp = post("/meeple", {"colour": colour, "direction": direction})
            if code != 200:
                print(f"  /meeple failed: {resp}")
                sys.exit(1)
            print(f"  /meeple → {colour} {direction}, turn={resp['turn']} next_player={resp['current_player']}")

        show_scores("after")

    print("\n=== Triggering /end ===")
    time.sleep(DELAY)
    code, resp = post("/end")
    print(f"  /end → {resp}")

    show_scores("final")

    code, state = get("/gamestate")
    if code == 200 and state["game_over"]:
        ranked = sorted(state["players"], key=lambda p: p["score"], reverse=True)
        winner = ranked[0]
        print(f"\n  Winner: {winner['colour']} with {winner['score']} points")
        print("  Ranking:", " > ".join(f"{p['colour']}({p['score']})" for p in ranked))


if __name__ == "__main__":
    main()
