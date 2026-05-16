from flask import Flask, jsonify, request
from flask_cors import CORS

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pathlib import Path
ROOT = Path(__file__).parent.parent
ENGINE = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE))

from cv import projector

from tile_set import tile_set
import tile_bag
from OldMain import (initialiseBoard, get_valid_placements_all_rotations, STARTING_RIVER)

# Startup sanity check: refuse to start if data.py has an old place_meeple
# signature, so the developer sees the real problem instead of silent
# corruption (e.g. meeples rendering in the wrong position).
import inspect
from data import gameStateClass as _gs
from data import farmer, knight, lord, merchant, necrobinder
_pm_params = list(inspect.signature(_gs.place_meeple).parameters)
if _pm_params != ["self", "tile", "direction"]:
    raise RuntimeError(
        f"data.py is out of date.\n"
        f"  Found:    place_meeple{inspect.signature(_gs.place_meeple)}\n"
        f"  Expected: place_meeple(self, tile, direction)\n"
        f"Replace engine/data.py with the latest version."
    )

app = Flask(__name__)
app.json.sort_keys = False
CORS(app)


@app.errorhandler(Exception)
def _handle_unhandled(e):
    """Return JSON for any uncaught exception so clients (fake_cv, frontend)
    don't choke on Flask's HTML traceback page when an endpoint crashes."""
    import traceback as _tb
    tb_str = _tb.format_exc()
    print("[api] Unhandled exception:", file=sys.stderr)
    print(tb_str, file=sys.stderr, flush=True)
    return jsonify({
        "error": str(e) or e.__class__.__name__,
        "traceback": tb_str,
    }), 500

game_state = None
tile_bag_instance = None
empty_bag_instance = None
pending_tile = None
pending_valid = []           # list of [x, y, rotation_id]
pending_candidates = []      # ranked list of tile_id strings from CV top-N matches
pending_placement = None     # {"x", "y", "tile_id", "tile"} — set by /place, cleared by /meeple or /meeple/skip
game_over = False            # flipped True by /end after final scoring
pending_notification = None  # Swal payload set by /notify, cleared by /notify/clear

# ── Notification type definitions ────────────────────────────────────────────
# Each entry maps to a SweetAlert2 options dict.
# CV (or any caller) posts {"type": "<key>"} to /notify to trigger the popup.
# Add new entries here to define more notification types.
NOTIFICATION_TYPES = {
    # ── Game events ───────────────────────────────────────────────────────────
    "volcano": {
        "title": "Volcano!",
        "text": "Smoke pours from the marked land. Surround the tile within 8 turns or all meeples are removed!",
        "icon": "warning",
        "confirmButtonText": "Understood",
    },
    "volcano_erupted": {
        "title": "The Volcano Erupts!",
        "text": "The volcano has erupted! All meeples on surrounding tiles have been removed.",
        "icon": "error",
        "confirmButtonText": "Oh no!",
    },
    "extra_turn": {
        "title": "Extra Turn!",
        "text": "The court astrologer reads good omens. This player gets an extra turn!",
        "icon": "info",
        "confirmButtonText": "Nice!",
    },
    "unrest": {
        "title": "Unrest!",
        "text": "Whispers of revolt fill the streets. Cities score half points for the next 4 turns.",
        "icon": "warning",
        "confirmButtonText": "Noted",
    },
    # ── CV errors ─────────────────────────────────────────────────────────────
    "cv_low_confidence": {
        "title": "Tile Not Recognised",
        "text": "The camera couldn't identify the tile with enough confidence. Try repositioning it under the camera.",
        "icon": "question",
        "confirmButtonText": "Try Again",
    },
    "cv_invalid_placement": {
        "title": "Invalid Placement",
        "text": "That tile can't be placed there. Move it to a highlighted valid position.",
        "icon": "error",
        "confirmButtonText": "OK",
    },
    "cv_no_board": {
        "title": "Board Not Detected",
        "text": "The camera can't see the board. Check the camera angle and lighting.",
        "icon": "error",
        "confirmButtonText": "OK",
    },
    "cv_multiple_tiles": {
        "title": "Multiple Tiles Detected",
        "text": "More than one new tile was detected. Please place only one tile at a time.",
        "icon": "warning",
        "confirmButtonText": "Got it",
    },
}


def build_active_events(game):
    events = []

    if game.extra_turn:
        events.append({
            "name": "Extra Turn",
            "description": "The court astrologer reads good omens in the night sky. Player gets an extra turn.",
            "player_index": game.currentIndex,
        })

    for ev in game.event_pool:
        if ev.name == "volcano" and getattr(ev, "active", False):
            events.append({
                "name": "Volcano",
                "description": "Smoke pours from the marked land and the earth groans beneath the realm. Surround the marked tile within 8 turns or all meeples are removed.",
                "coords": list(ev.coords),
            })

    if getattr(game, "unrestCheck", False):
        events.append({
            "name": "Unrest",
            "description": "Whispers of revolt fill the streets and meeples live in fear. Cities score half points for the next 4 turns.",
        })

    return events


@app.route('/gamestate', methods=['GET'])
def get_gamestate():
    if game_state is None:
        return jsonify({"error": "Game not started"}), 503

    board_serialised = {}
    for (x, y), t in game_state.get_board_xy().items():
  
        meeple_info = None
        if isinstance(t.meeple_attached, tuple) and t.meeple_attached and t.meeple_attached[0]:
            _, up, down, left, right = t.meeple_attached
            if up:        side = "up"
            elif down:    side = "down"
            elif left:    side = "left"
            elif right:   side = "right"
            else:         side = "centre"
            meeple_info = {
                "side": side,
                "player_index": getattr(t, "meeple_player_index", None),
            }
        elif t.meeple_attached is True:
            # Defensive: meeple_attached should always be a tuple after
            # /meeple runs. If it's just True, an old code path overwrote
            # the direction info. Surface this as a warning rather than
            # silently rendering the meeple in the wrong (centre) position.
            print(f"[gamestate] WARNING: tile at ({x},{y}) has meeple_attached=True "
                  f"(no direction info)", file=sys.stderr)
            meeple_info = {
                "side": "unknown",
                "player_index": getattr(t, "meeple_player_index", None),
            }

        board_serialised[f"{x},{y}"] = {
            "up": t.up,
            "down": t.down,
            "left": t.left,
            "right": t.right,
            "tile_id": t.tile_id,
            "feature_continues": t.feature_continues,
            "attribute": t.attribute,
            "meeple_attached": t.meeple_attached if not isinstance(t.meeple_attached, tuple) else list(t.meeple_attached),
            "meeple": meeple_info,
        }

    players_serialised = []
    for p in game_state.players:
        players_serialised.append({
            "colour": p.return_colour(),
            "meeples": p.meeples,
            "score": p.score,
        })

    pending_placement_serialised = None
    if pending_placement is not None:
        t = pending_placement["tile"]
        valid_sides = []
        for side in ("up", "down", "left", "right"):
            if getattr(t, side) in (1, 2):
                valid_sides.append(side)
        if t.attribute == 2:
            valid_sides.append("centre")

        pending_placement_serialised = {
            "x": pending_placement["x"],
            "y": pending_placement["y"],
            "tile_id": pending_placement["tile_id"],
            "valid_sides": valid_sides,
        }

    return jsonify({
        "board": board_serialised,
        "players": players_serialised,
        "current_player": game_state.currentIndex,
        "remaining_pieces": len(tile_bag_instance.tile_bag) // 4 if tile_bag_instance else 0,
        "current_turn": game_state.current_turn,
        "pending_tile": pending_tile,
        "pending_valid": pending_valid,
        "pending_candidates": pending_candidates,
        "pending_placement": pending_placement_serialised,
        "game_over": game_over,
        "active_events": build_active_events(game_state),
        "notification": pending_notification,
    })


@app.route('/debug/event', methods=['POST'])
def debug_event():
    """Force-toggle event flags for visual testing of the Active Events panel.

    Body: {"name": "extra_turn" | "volcano" | "unrest", "enabled": true | false}
    Volcano repurposes the first Event in event_pool by renaming it and
    flipping its active flag.
    """
    if game_state is None:
        return jsonify({"error": "Game not started"}), 400

    data = request.get_json() or {}
    name = data.get("name")
    enabled = data.get("enabled", True)
    enabled = bool(enabled)

    if name == "extra_turn":
        game_state.extra_turn = enabled
    elif name == "unrest":
        game_state.unrestCheck = enabled
    elif name == "volcano":
        if not game_state.event_pool:
            return jsonify({"error": "No events in pool"}), 400
        ev = game_state.event_pool[0]
        ev.name = "volcano"
        ev.active = enabled
    else:
        return jsonify({"error": f"Unknown event name: {name}"}), 400

    return jsonify({"status": "ok", "name": name, "enabled": enabled})


@app.route('/notify', methods=['POST'])
def send_notification():
    """Trigger a SweetAlert2 popup on the frontend.

    Body: {"type": "<key>"}  — must match a key in NOTIFICATION_TYPES.
    Optional overrides: any Swal field (title, text, icon, confirmButtonText, …)
    can be included in the body to override the defaults for that type.

    Or use {"type": "custom", "title": "…", "text": "…", "icon": "…"} for a
    one-off popup not defined in NOTIFICATION_TYPES.
    """
    global pending_notification

    data = request.get_json() or {}
    ntype = data.get("type")
    if not ntype:
        return jsonify({"error": "Missing 'type' field"}), 400

    if ntype == "custom":
        payload = {k: v for k, v in data.items() if k != "type"}
        if not payload.get("title") and not payload.get("text"):
            return jsonify({"error": "Custom notification requires at least 'title' or 'text'"}), 400
    else:
        base = NOTIFICATION_TYPES.get(ntype)
        if base is None:
            return jsonify({
                "error": f"Unknown notification type: '{ntype}'. "
                         f"Known types: {list(NOTIFICATION_TYPES.keys())} (or 'custom')"
            }), 400
        payload = {**base, **{k: v for k, v in data.items() if k != "type"}}

    pending_notification = payload
    return jsonify({"status": "ok", "notification": payload})


@app.route('/notify/clear', methods=['POST'])
def clear_notification():
    """Frontend calls this after displaying the notification to dismiss it."""
    global pending_notification
    pending_notification = None
    return jsonify({"status": "ok"})


@app.route('/start', methods=['POST'])
def start_game():
    global game_state, tile_bag_instance, pending_tile, pending_valid, game_over

    if game_state is not None:
        return jsonify({"error": "Game already started"}), 400

    game_over = False

    data = request.get_json()
    if data is None or "players" not in data:
        return jsonify({"error": "Missing 'players' field"}), 400

    num_players_data = data["players"]

    class_map = {
        "farmer": farmer,
        "lord": lord,
        "knight": knight,
        "merchant": merchant,
        "necrobinder": necrobinder
    }
    default_classes = ["lord", "knight", "merchant", "farmer", "necrobinder"]

    if isinstance(num_players_data, int):
        if num_players_data < 2 or num_players_data > 5:
            return jsonify({"error": "Player count must be between 2 and 5"}), 400
        num_players_data = default_classes[:num_players_data]

    if not isinstance(num_players_data, list) or len(num_players_data) < 2 or len(num_players_data) > 5:
        return jsonify({"error": "Players must be a count (2-5) or a list of class names"}), 400

    players = []
    for name in num_players_data:
        clas = class_map.get(name.lower())
        if clas is None:
            return jsonify({"error": f"Unknown player class: '{name}'"}), 400
        players.append(clas())

    game_state = initialiseBoard(players)
    tile_bag_instance = tile_bag.tile_bag()
    empty_bag_instance = tile_bag.empty_bag()

    pending_tile = None
    pending_valid = []

    return jsonify({"status": "ok", "players": num_players_data}), 201


def _resolve_pending(tile_id):
    """Shared logic: resolve tile_id → base_num, compute valid placements, update globals.
    Returns (response_dict, error_str). On success error_str is None."""
    global pending_tile, pending_valid, pending_candidates

    if isinstance(tile_id, int):
        base_num = tile_id
    else:
        base_num = int(tile_id.replace("ID", "")) // 4

    all_valid = get_valid_placements_all_rotations(game_state, base_num)
    pending_tile = f"ID{base_num * 4}"

    if not all_valid:
        pending_valid = []
        projector.clear_proj_valid()
        return {"tile_id": pending_tile, "valid_positions": []}, None

    # Extract all valid coords for valid tile placements
    valid_coords = list(all_valid.keys())
    projector.set_proj_valid(valid_coords) # Send coords to projector to display

    # Expand to one entry per (position, rotation) so /place can validate any rotation CV detects.
    pending_valid = [[x, y, rid] for (x, y), rids in all_valid.items() for rid in rids]
    # Return unique positions only — frontend only needs to know where tiles can go, not which rotation.
    unique_positions = list({(x, y): [x, y] for x, y, _ in pending_valid}.values())
    return {"tile_id": pending_tile, "valid_positions": unique_positions}, None


@app.route('/pending', methods=['POST'])
def set_pending():
    global pending_candidates

    if game_state is None:
        return jsonify({"error": "Game not started"}), 400

    data = request.get_json()
    tile_id = data.get("tile_id")

    # Optional ranked candidate list from CV: list of tile_id strings in rank order
    pending_candidates = data.get("candidates", [])

    result, err = _resolve_pending(tile_id)
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)

@app.route('/pending/list', methods=['POST'])
def set_pending_list():
    """
    Sets the list of pending tiles to the top 4 tiles detected by the cv
    >> Allow the user to select one of these in the frontend to change the active tile
    """
    global pending_candidates

    data = request.get_json()
    tile_ids = data.get("tile_ids")

    if not tile_ids or not isinstance(tile_ids, list):
        return jsonify({"error": "Missing or invalid 'tile_ids' field"}), 400

    pending_candidates = tile_ids[:4] # top 4

    # set the first tile in the list as the pending tile
    result, err = _resolve_pending(tile_ids[0])
    if err:
        return jsonify({"error": err}), 400
    return jsonify(result)


@app.route('/pending/override', methods=['POST'])
def override_pending():
    """Website calls this when the user selects a different tile than the CV detected.
    Updates valid placements for the new tile and tells the CV to use this family
    for post-placement rotation detection."""
    import sys, os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try:
        from cv import Project_CV
    except ImportError:
        Project_CV = None

    if game_state is None:
        return jsonify({"error": "Game not started"}), 400

    data = request.get_json()
    tile_id = data.get("tile_id")
    if not tile_id:
        return jsonify({"error": "Missing tile_id"}), 400

    result, err = _resolve_pending(tile_id)
    if err:
        return jsonify({"error": err}), 400

    if Project_CV is not None:
        Project_CV.tile_id_override = tile_id

    return jsonify(result)

@app.route('/pending/change', methods=['POST'])
def change_pending():
    """
    Change the pending tile based on an id received from the frontend.
    """
    data = request.get_json()
    selected_tile = data.get("selected_tile")

    print(f"received tile: {selected_tile}")

    result, err = _resolve_pending(selected_tile)

    if err:
        return jsonify({"error": err}), 400

    return jsonify(result)


@app.route('/pending/clear', methods=['POST'])
def clear_pending():
    global pending_tile, pending_valid, pending_candidates
    pending_tile = None
    pending_valid = []
    pending_candidates = []
    return jsonify({"status": "ok"})


@app.route('/place', methods=['POST'])
def place_tile():
    global game_state, tile_bag_instance, pending_tile, pending_valid, pending_candidates, pending_placement

    if game_state is None:
        return jsonify({"error": "Game not started"}), 400

    data = request.get_json()
    x, y = data.get("x"), data.get("y")

    if x is None or y is None:
        return jsonify({"error": "Missing x or y"}), 400

    # CV may supply the exact rotation it detected post-placement; otherwise
    # fall back to the first valid rotation for this position.
    rotation_id = data.get("rotation_id")
    placed_tile_id = None
    valid_at_pos = [rid for px, py, rid in pending_valid if px == x and py == y]
    if not valid_at_pos:
        projector.set_invalid()
        return jsonify({"error": "Invalid placement position"}), 400
    if rotation_id is not None:
        if rotation_id in valid_at_pos:
            placed_tile_id = rotation_id
        else:
            # CV rotation detection returned a rotation that doesn't fit — fall back
            # to the engine-computed valid rotation for this position.
            placed_tile_id = valid_at_pos[0]
            print(f"[place] CV rotation {rotation_id} not valid at ({x},{y}) — using {placed_tile_id}")
    else:
        placed_tile_id = valid_at_pos[0]

    if placed_tile_id is None:
        return jsonify({"error": "Invalid placement"}), 400

    tile_obj = tile_set[placed_tile_id]
    game_state.place_tile(x, y, tile_obj)
    tile_bag_instance.remove_tile(placed_tile_id)
    projector.clear_proj_valid() # Clear projector valid tiles
    projector.clear_invalid()
    projector.set_valid()

    pending_tile = None
    pending_valid = []
    pending_candidates = []

    pending_placement = {
        "x": x,
        "y": y,
        "tile_id": placed_tile_id,
        "tile": tile_obj,
        "structures_managed": False,
    }

    return jsonify({
        "status": "ok",
        "placed": placed_tile_id,
        "position": [x, y],
    }), 200

@app.route('/rotate', methods=['POST'])
def rotate_tile():
    """
    called from frontend to rotate a placed tile
    body: 
    {
        x: int,
        y: int
    }
    """
    global game_state

    if game_state is None:
        return jsonify({"error": "Game not started"}), 400

    data = request.get_json()
    
    x, y = data.get("x"), data.get("y")
    if x is None or y is None:
        return jsonify({"error": "Missing x or y"}), 400

    # find the tile at (x, y)
    board = game_state.board
    print(f" board state: {game_state.board}")

    array_row, array_col = game_state.to_array_index(x, y) # convert to array indices
    tile = board[array_row][array_col]

    if tile is None:
        return jsonify({"error": f"No tile found at ({x}, {y})"}), 400

    # rotate the tile
    current_tile = tile.tile_id
    # extract number
    base_num = int(current_tile.replace("ID", ""))
    # rotate by adding 1 to the base_num
    family_base = (base_num // 4) * 4
    current_rotation = base_num % 4
    new_base_num = family_base + ((current_rotation + 1) % 4)

    new_tile_id = f"ID{new_base_num}"
    new_tile_obj = tile_set[new_tile_id]

    # update the tile on the board
    board[array_row][array_col] = new_tile_obj
    projector.clear_proj_valid() # Clear projector valid tiles
    print(f"Rotated tile at ({x},{y}) from {current_tile} to {new_tile_id}")
    # Verify the update
    verify_tile = board[array_row][array_col]
    print(f"Verification: Board now has {verify_tile.tile_id} at ({x},{y})")
    
    return jsonify({
        "status": "ok",
        "position": [x, y],
        "old_tile_id": current_tile,
        "new_tile_id": new_tile_id
    }), 200

@app.route('/meeple', methods=['POST'])
def place_meeple():
    global game_state, pending_placement

    if game_state is None:
        return jsonify({"error": "Game not started"}), 400
    if pending_placement is None:
        return jsonify({"error": "No pending placement"}), 400

    data = request.get_json()
    direction = data.get("direction")  # "up", "down", "left", "right", "centre"
    if direction not in ("up", "down", "left", "right", "centre"):
        return jsonify({"error": f"Invalid direction: {direction}"}), 400

    colour = data.get("colour")
    COLOURS = ["red", "blue", "green", "yellow", "black"]
    colour_int = None
    if colour is not None:
        if colour not in COLOURS:
            return jsonify({"error": f"Invalid colour: {colour}"}), 400
        colour_int = COLOURS.index(colour)
        if colour_int != game_state.currentIndex:
            return jsonify({
                "error": f"It is not {colour}'s turn (current player is index {game_state.currentIndex})"
            }), 400

    x    = pending_placement["x"]
    y    = pending_placement["y"]
    tile = pending_placement["tile"]

    if direction == "centre":
        if tile.attribute != 2:
            return jsonify({"error": "Centre meeple only valid on monastery tiles"}), 400
    else:
        if getattr(tile, direction) not in (1, 2):
            return jsonify({"error": f"No road or city on side '{direction}'"}), 400

    current_player = game_state.current_player()
    current_index = game_state.currentIndex
    if current_player.meeples <= 0:
        return jsonify({"error": "No meeples left for this player"}), 400


    if not pending_placement.get("structures_managed"):
        game_state.manage_structures(x, y, tile, None)
        pending_placement["structures_managed"] = True

    try:
        game_state.place_meeple(tile, direction)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    dir_to_attached = {
        "up":     (1, 1, 0, 0, 0),
        "down":   (1, 0, 1, 0, 0),
        "left":   (1, 0, 0, 1, 0),
        "right":  (1, 0, 0, 0, 1),
        "centre": (1, 0, 0, 0, 0),
    }
    tile.meeple_attached = dir_to_attached[direction]
    tile.meeple_player_index = current_index

    game_state.next_player()
    game_state.current_turn += 1
    pending_placement = None

    return jsonify({
        "status": "ok",
        "meeple_direction": direction,
        "meeple_colour": colour,
        "player_index": current_index,
        "turn": game_state.current_turn,
        "current_player": game_state.currentIndex,
    })


@app.route('/meeple/skip', methods=['POST'])
def skip_meeple():
    global game_state, pending_placement

    if game_state is None:
        return jsonify({"error": "Game not started"}), 400
    if pending_placement is None:
        return jsonify({"error": "No pending placement"}), 400

    x    = pending_placement["x"]
    y    = pending_placement["y"]
    tile = pending_placement["tile"]

    if not pending_placement.get("structures_managed"):
        game_state.manage_structures(x, y, tile, None)
        pending_placement["structures_managed"] = True

    game_state.next_player()
    game_state.current_turn += 1
    pending_placement = None

    return jsonify({
        "status": "ok",
        "turn": game_state.current_turn,
        "current_player": game_state.currentIndex,
    })


@app.route('/end', methods=['POST'])
def end_game():
    global game_over
    if game_state is None:
        return jsonify({"error": "Game not started"}), 400

    game_state.score_end_game()
    game_over = True

    return jsonify({
        "status": "ok",
        "scores": [
            {"colour": p.return_colour(), "score": p.score}
            for p in game_state.players
        ],
    })


@app.route('/reset', methods=['POST'])
def reset_game():
    global game_state, tile_bag_instance, pending_tile, pending_valid, pending_candidates, pending_placement, game_over, pending_notification
    game_state = None
    tile_bag_instance = None
    pending_tile = None
    pending_valid = []
    pending_candidates = []
    pending_placement = None
    game_over = False
    pending_notification = None
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Run api.py directly (without CV or frontend) for engine-only testing.
    # For the full system, run engine/bridge.py instead.
    print("API running on http://127.0.0.1:1234")
    app.run(host="127.0.0.1", port=1234, debug=True, use_reloader=False)