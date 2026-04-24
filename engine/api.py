from flask import Flask, jsonify, request
from flask_cors import CORS

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tile_set import tile_set
import tile_bag
from OldMain import (initialiseBoard, get_valid_placements_all_rotations, STARTING_RIVER)

app = Flask(__name__)
app.json.sort_keys = False
CORS(app)

game_state = None
tile_bag_instance = None
empty_bag_instance = None
pending_tile = None
pending_valid = []           # list of [x, y, rotation_id]
pending_candidates = []      # ranked list of tile_id strings from CV top-N matches
pending_placement = None     # {"x", "y", "tile_id", "tile"} — set by /place, cleared by /meeple or /meeple/skip


@app.route('/gamestate', methods=['GET'])
def get_gamestate():
    if game_state is None:
        return jsonify({"error": "Game not started"}), 503

    board_serialised = {}
    for (x, y), t in game_state.get_board_xy().items():
        board_serialised[f"{x},{y}"] = {
            "up": t.up,
            "down": t.down,
            "left": t.left,
            "right": t.right,
            "tile_id": t.tile_id,
            "feature_continues": t.feature_continues,
            "attribute": t.attribute,
            "meeple_attached": t.meeple_attached,
        }

    players_serialised = []
    for p in game_state.players:
        players_serialised.append({
            "colour": p.return_colour(),
            "meeples": p.meeples,
            "score": p.score,
        })

    return jsonify({
        "board": board_serialised,
        "players": players_serialised,
        "current_player": game_state.currentIndex,
        "remaining_pieces": game_state.remaining_pieces,
        "current_turn": game_state.current_turn,
        "pending_tile": pending_tile,
        "pending_valid": pending_valid,
        "pending_candidates": pending_candidates,
    })


@app.route('/start', methods=['POST'])
def start_game():
    global game_state, tile_bag_instance, pending_tile, pending_valid

    if game_state is not None:
        return jsonify({"error": "Game already started"}), 400

    data = request.get_json()
    if data is None or "players" not in data:
        return jsonify({"error": "Missing 'players' field"}), 400

    num_players = data["players"]
    if not isinstance(num_players, int) or num_players < 2 or num_players > 5:
        return jsonify({"error": "Players must be between 2 and 5"}), 400

    game_state = initialiseBoard(num_players)
    tile_bag_instance = tile_bag.tile_bag()
    empty_bag_instance = tile_bag.empty_bag()

    pending_tile = None
    pending_valid = []

    return jsonify({"status": "ok", "players": num_players}), 201


def _resolve_pending(tile_id):
    """Shared logic: resolve tile_id → base_num, compute valid placements, update globals.
    Returns (response_dict, error_str). On success error_str is None."""
    global pending_tile, pending_valid, pending_candidates

    if isinstance(tile_id, int):
        base_num = tile_id
    else:
        base_num = int(tile_id.replace("ID", "")) // 4

    all_valid = get_valid_placements_all_rotations(game_state, base_num)
    if not all_valid:
        return None, "No valid placements for this tile"

    pending_tile = f"ID{base_num * 4}"
    pending_valid = [[x, y, rid] for (x, y), rid in all_valid.items()]
    return {"tile_id": pending_tile, "valid_positions": pending_valid}, None


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
    if rotation_id is not None:
        valid_at_pos = [rid for px, py, rid in pending_valid if px == x and py == y]
        if not valid_at_pos:
            return jsonify({"error": "Invalid placement position"}), 400
        placed_tile_id = rotation_id
    else:
        for px, py, rid in pending_valid:
            if px == x and py == y:
                placed_tile_id = rid
                break

    if placed_tile_id is None:
        return jsonify({"error": "Invalid placement"}), 400

    tile_obj = tile_set[placed_tile_id]
    game_state.place_tile(x, y, tile_obj)
    tile_bag_instance.remove_tile(placed_tile_id)

    pending_tile = None
    pending_valid = []
    pending_candidates = []
    # Store placement so /meeple or /meeple/skip can finish the turn
    pending_placement = {"x": x, "y": y, "tile_id": placed_tile_id, "tile": tile_obj}

    return jsonify({
        "status": "ok",
        "placed": placed_tile_id,
        "position": [x, y],
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
    colour    = data.get("colour")     # "red", "blue", "green", "yellow", "black"
    if direction not in ("up", "down", "left", "right", "centre"):
        return jsonify({"error": f"Invalid direction: {direction}"}), 400

    x    = pending_placement["x"]
    y    = pending_placement["y"]
    tile = pending_placement["tile"]

    dir_to_attached = {
        "up":     (1, 1, 0, 0, 0),
        "down":   (1, 0, 1, 0, 0),
        "left":   (1, 0, 0, 1, 0),
        "right":  (1, 0, 0, 0, 1),
        "centre": (1, 0, 0, 0, 0),
    }
    tile.meeple_attached = dir_to_attached[direction]

    # Monastery: manage_structures handles player attachment at creation time
    if direction == "centre" and tile.attribute == 2:
        game_state.manage_structures(x, y, tile, game_state.current_player())
    else:
        game_state.manage_structures(x, y, tile, None)
        game_state.place_meeple(tile)

    game_state.next_player()
    game_state.current_turn += 1
    pending_placement = None

    return jsonify({
        "status": "ok",
        "meeple_colour": colour,
        "meeple_direction": direction,
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

    game_state.manage_structures(x, y, tile, None)
    game_state.next_player()
    game_state.current_turn += 1
    pending_placement = None

    return jsonify({
        "status": "ok",
        "turn": game_state.current_turn,
        "current_player": game_state.currentIndex,
    })


@app.route('/reset', methods=['POST'])
def reset_game():
    global game_state, tile_bag_instance, pending_tile, pending_valid, pending_candidates, pending_placement
    game_state = None
    tile_bag_instance = None
    pending_tile = None
    pending_valid = []
    pending_candidates = []
    pending_placement = None
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Run api.py directly (without CV or frontend) for engine-only testing.
    # For the full system, run engine/bridge.py instead.
    print("API running on http://127.0.0.1:1234")
    app.run(host="127.0.0.1", port=1234, debug=True, use_reloader=False)