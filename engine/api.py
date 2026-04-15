from flask import Flask, jsonify, request
from flask_cors import CORS
from tile_set import tile_set
import tile_bag
from main import initialiseBoard, get_valid_placements, STARTING_RIVER
 
app = Flask(__name__)
app.json.sort_keys = False
CORS(app)
 
game_state = None
tile_bag_instance = None

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
    })
 
 
@app.route('/start', methods=['POST'])
def start_game():
    global game_state, tile_bag_instance
 
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
 
    for tile_id, _, _ in STARTING_RIVER:
        tile_bag_instance.remove_tile(tile_id)
 
if __name__ == "__main__":
    print("API running on http://127.0.0.1:1234")
    app.run(host="127.0.0.1", port=1234, debug=True)

