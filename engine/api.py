from flask import Flask, jsonify, request
from flask_cors import CORS
from tile_set import tile_set
import tile_bag
from main import (initialiseBoard, get_valid_placements_all_rotations, STARTING_RIVER)

app = Flask(__name__)
app.json.sort_keys = False
CORS(app)

game_state = None
tile_bag_instance = None
pending_tile = None
pending_valid = []    # list of [x, y, rotation_id]


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

    pending_tile = None
    pending_valid = []

    return jsonify({"status": "ok", "players": num_players}), 201


@app.route('/pending', methods=['POST'])
def set_pending():
    global pending_tile, pending_valid

    if game_state is None:
        return jsonify({"error": "Game not started"}), 400

    data = request.get_json()
    tile_id = data.get("tile_id")

    # Convert to base tile number
    if isinstance(tile_id, int):
        base_num = tile_id
    else:
        base_num = int(tile_id.replace("ID", "")) // 4

    # Engine checks all 4 rotations and returns valid placements
    all_valid = get_valid_placements_all_rotations(game_state, base_num)

    if not all_valid:
        return jsonify({"error": "No valid placements for this tile"}), 400

    pending_tile = f"ID{base_num * 4}"
    pending_valid = [[x, y, rid] for (x, y), rid in all_valid.items()]

    return jsonify({
        "tile_id": pending_tile,
        "valid_positions": pending_valid,
    })


@app.route('/pending/clear', methods=['POST'])
def clear_pending():
    global pending_tile, pending_valid
    pending_tile = None
    pending_valid = []
    return jsonify({"status": "ok"})


@app.route('/place', methods=['POST'])
def place_tile():
    global game_state, tile_bag_instance, pending_tile, pending_valid

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

    # Engine places tile, bag removes all 4 rotations
    game_state.place_tile(x, y, tile_set[placed_tile_id])
    tile_bag_instance.remove_tile(placed_tile_id)

    pending_tile = None
    pending_valid = []

    game_state.next_player()
    game_state.current_turn += 1

    return jsonify({
        "status": "ok",
        "placed": placed_tile_id,
        "position": [x, y],
        "turn": game_state.current_turn,
        "current_player": game_state.currentIndex,
    }), 200


@app.route('/reset', methods=['POST'])
def reset_game():
    global game_state, tile_bag_instance, pending_tile, pending_valid
    game_state = None
    tile_bag_instance = None
    pending_tile = None
    pending_valid = []
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("API running on http://127.0.0.1:1234")
    app.run(host="127.0.0.1", port=1234, debug=True)