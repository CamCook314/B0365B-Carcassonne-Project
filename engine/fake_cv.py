"""
fake_cv.py – Interactive CV simulator

Simulates the camera system by letting you type tiles and coordinates
in the terminal. The frontend shows valid placements in real time.

Flow:
  1. You enter a tile number which relates to 4 tile ID's
  2. The API stores it as a pending tile, frontend highlights valid spots
  3. You enter coordinates (e.g. 3,-1) and this is cv detecting placement
  4. The tile is placed, turn advances

Usage in order:
  Terminal 1:  cd frontend/ ; npm run dev
  Terminal 2:  cd engine; python api.py
  Terminal 3:  cd engine; python fake_cv.py
"""

import requests

BASE_URL = "http://127.0.0.1:1234"


def _safe_json(res):
    """Return res.json() if possible, otherwise a dict with the raw text.
    The API now returns JSON for errors too, but if Flask debug mode is on
    or the server crashes hard, the body may be HTML. This makes sure
    callers always get a dict."""
    try:
        return res.json()
    except Exception:
        body = res.text or ""
        # Pull a short summary out of HTML if present
        snippet = body.strip().split("\n")[0][:200]
        return {"error": f"non-JSON response (status {res.status_code})", "raw": snippet}


def api_get(path, **kwargs):
    res = requests.get(f"{BASE_URL}{path}", **kwargs)
    return res.ok, _safe_json(res)


def api_post(path, **kwargs):
    res = requests.post(f"{BASE_URL}{path}", **kwargs)
    return res.ok, _safe_json(res)


def run():
    # Reset and start
    api_post("/reset")

    num = input("Number of players (2-5): ").strip()
    try:
        num = int(num)
    except ValueError:
        num = 3

    ok, data = api_post("/start", json={"players": num})
    if not ok:
        print(f"Failed to start: {data}")
        return

    print(f"\nGame started with {num} players")
    print("The river has been placed.\n")

    while True:
        # Get current state for context
        ok, state = api_get("/gamestate")
        if not ok:
            print("Lost connection to API")
            break

        current_player = state["current_player"]
        turn = state["current_turn"]
        colours = ["red", "blue", "green", "yellow", "black"]
        colour = colours[current_player] if current_player < len(colours) else f"P{current_player+1}"

        print(f"\n--- Turn {turn} | {colour}'s turn ---")
        print(f"Tiles on board: {len(state['board'])} | Remaining: {state['remaining_pieces']}")

        # Enter tiles 
        while True:
            tile_input = input("\nEnter base tile numbers (or 'quit'): ").strip()

            if tile_input.lower() == "quit":
                print("Ending session.")
                api_post("/pending/clear")
                return

            try:
                tile_nums = [int(x.strip()) for x in tile_input.split(",")]
            except ValueError:
                print("  Enter a number (base tile ID)")
                continue

            # Tell the API which tile was detected 
            # ok, data = api_post("/pending", json={"tile_id": tile_num})

            # Send list of most similar tiles to API
            ok, data = api_post("/pending/list", json={"tile_ids": tile_nums})
            tile_num = tile_nums[0]
            if not ok:
                print(f"  Error: {data.get('error', 'Unknown error')}")
                continue

            valid = data.get("valid_positions", [])
            if not valid:
                print(f"  No valid placements for {tile_num}. Try another tile.")
                api_post("/pending/clear")
                continue

            print(f"  Valid placements for {tile_num}:")
            for i, pos in enumerate(valid):
                print(f"    {i+1}. ({pos[0]}, {pos[1]})")

            break

        # Enter coodinates to palce tile
        while True:
            coord = input(f"\nPlace {tile_num} at x,y (or 'cancel'): ").strip()

            if coord.lower() == "cancel":
                api_post("/pending/clear")
                print("  Cancelled.")
                break
      
            # Parse as x,y
            try:
                parts = coord.replace(" ", "").split(",")
                x, y = int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                print("  Invalid format. Use 'x,y'")
                continue

            # Place the tile
            ok, result = api_post("/place", json={"tile_id": tile_num, "x": x, "y": y})
            if ok:
                print(f"  Placed {tile_num} at ({x}, {y})")
                # Now handle the meeple step
                _handle_meeple_step()
                break
            else:
                print(f"  Error: {result.get('error', 'Unknown')}")
                continue


def _handle_meeple_step():
    """After a tile is placed, prompt the user to place a meeple or skip."""
    # Fetch the current pending_placement to see which sides are valid
    ok, state = api_get("/gamestate")
    if not ok:
        print("  Could not fetch gamestate after placement.")
        return

    pending = state.get("pending_placement")
    if not pending:
        # No pending placement — turn already advanced or no meeple step needed
        return

    valid_sides = pending.get("valid_sides", [])

    while True:
        if not valid_sides:
            print("  No valid meeple positions on this tile — skipping.")
            api_post("/meeple/skip")
            return

        print(f"\n  Place a meeple? Valid sides: {valid_sides}")
        print(f"    Options: {', '.join(valid_sides)}, or 'skip'")
        choice = input("  Meeple direction: ").strip().lower()

        if choice in ("skip", "s", ""):
            ok, result = api_post("/meeple/skip")
            if ok:
                print(f"  Skipped. Turn {result.get('turn')}, next player P{result.get('current_player', 0) + 1}")
            else:
                print(f"  Error skipping: {result.get('error', 'Unknown')}")
            return

        if choice not in valid_sides:
            print(f"  Invalid choice. Must be one of {valid_sides} or 'skip'.")
            continue

        ok, result = api_post("/meeple", json={"direction": choice})
        if ok:
            print(f"  Meeple placed on '{choice}'. Turn {result.get('turn')}, next player P{result.get('current_player', 0) + 1}")
            return
        else:
            print(f"  Error placing meeple: {result.get('error', 'Unknown')}")
            if "traceback" in result:
                print("  --- server traceback ---")
                print(result["traceback"])
                print("  ------------------------")
            # let the user try again
            continue


if __name__ == "__main__":
    run()