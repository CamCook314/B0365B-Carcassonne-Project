from data import tile, player, gameStateClass
from tile_set import tile_set
from flask import Flask, jsonify, request
import threading

#im using camelCase for functions and snake_case for variables

game_state = None

# Flask API stuff
app = Flask(__name__)
app.json.sort_keys = False

#returns the game state the website requests to /gamestate at port 1234
@app.route('/gamestate', methods=['GET'])
def get_gamestate():
    if game_state is None:
        return jsonify({"error": "Game not started"}), 503

    board_serialised = {}
    for row in range(len(game_state.board)):
        for col in range(len(game_state.board[row])):
            t = game_state.board[row][col]
            if t is not None:
                board_serialised[f"{row},{col}"] = {
                    "up": t.up,
                    "down": t.down,
                    "left": t.left,
                    "right": t.right,
                    "feature_continues": t.feature_continues,
                    "attribute": t.attribute,
                    "meeple_attached": t.meeple_attached,
                }

    players_serialised = []
    for p in game_state.players:
        players_serialised.append({
            "colour": p.returnColour(),
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


# starts the game when a POST request is sent to /start
@app.route('/start', methods=['POST'])
def start_game():
    global game_state

    if game_state is not None:
        return jsonify({"error": "Game already started"}), 400

    data = request.get_json()
    if data is None or "players" not in data:
        return jsonify({"error": "Missing 'players' field"}), 400

    num_players = data["players"]
    if not isinstance(num_players, int) or num_players < 2 or num_players > 5:
        return jsonify({"error": "Players must be between 2 and 5"}), 400

    game_state = initialiseBoard(num_players)




    # TESTING: Place river tiles on the board at start
    for tile_id, row, col in STARTING_RIVER:
        try:
            game_state.place_tile(row, col, tile_set[tile_id])
        except ValueError:
            print(f"Skipping invalid river tile {tile_id} at ({row}, {col})")

    # TESTING: Place test tiles on the board at start
    for tile_id, row, col in TEST_GAME:
        try:
            game_state.place_tile(row, col, tile_set[tile_id])
        except ValueError:
            print(f"Skipping invalid test tile {tile_id} at ({row}, {col})")

    return jsonify({"message": f"Game started with {num_players} players"}), 201


def start_api():
    app.run(host="127.0.0.1", port=1234, threaded=True)

NUM_PLAYERS = 3

# Hard-coded river for testing
STARTING_RIVER = [
    ("ID0",  7, 5),
    ("ID9",  7, 6),
    ("ID32", 7, 7),
    ("ID8",  8, 7),
    ("ID1",  9, 7),
]

#Hard coded game for testing - tiles will be played in order, mix of valid and invalid tiles
TEST_GAME = [
    ("ID0",  7, 5),
    ("ID9",  7, 6),
    ("ID32", 7, 7),
    ("ID122",  10, 7), #valid tile
    ]

TOTAL_PIECES = 82
remaining_pieces = 82

current_turn = 1


#Function that is first called upon game start. launches the API and waits for a POST to /start
def gameStart():
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    print("API running on http://127.0.0.1:1234, waiting for POST /start to begin game")
    api_thread.join()
"""
    Old gameStart code - will be reworked to use API-driven flow
    global game_state
    game = initialiseBoard(NUM_PLAYERS) #sets up internal board tracking
    game_state = game
    print(game.board)
    meeple = 0
    play turns until peices run out
    #while game.remaining_pieces > 0:
    for new_tile in TEST_GAME: #Loop only for testing the TEST_GAME list
        playTurn(game, current_turn, new_tile, meeple)
        current_turn += 1
"""  
    

#initialises internal board system

def initialiseBoard(num_players):
    players = [player(i) for i in range(num_players)]

    game = gameStateClass(players)

    # Commented out as i think each player will take turns placing tiles, uncomment if not the case
    # Temp code for now
    #for tile_id, row, col in STARTING_RIVER:
        #game.place_tile(row, col, tile_set[tile_id])
    
    
    return game


#Runs every turn
def playTurn(game, current_turn, tile, meeple):

    checkMeeplePlaced() # check if meeple placed on valid tile played
    checkDoneStructures() # Checks if the new tile completed a structure
    pass


#Check if a meeple was placed on new tile, if it is right colour and whether its on a road or city for double tiles
def checkMeeplePlaced() :
    pass

#scans board state and checks and scores all completed structures not scored previously
def checkDoneStructures():
    updateScores() #update scores for all affected players if there is a done structure
    pass


#updates scores for every player, given player id and score add
def updateScores():
    pass


# Test Game
if __name__ == "__main__":
    gameStart()
