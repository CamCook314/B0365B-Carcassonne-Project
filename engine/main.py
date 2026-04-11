#import ....
import sys
import os
from data import tile, player, gameStateClass
from tile_set import tile_set
from flask import Flask, jsonify, request
# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from cv import Project_CV
except ImportError:
    Project_CV = None
import threading
import time
import tile_bag


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
    for (x, y), t in game_state.get_board_xy().items():
        board_serialised[f"{x},{y}"] = {
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
    for tile_id, x, y in STARTING_RIVER:
        try:
            game_state.place_tile(x, y, tile_set[tile_id])
        except ValueError:
            print(f"Skipping invalid river tile {tile_id} at ({x}, {y})")

    # TESTING: Place test tiles on the board at start
    for tile_id, x, y in TEST_GAME:
        try:
            game_state.place_tile(x, y, tile_set[tile_id])
        except ValueError:
            print(f"Skipping invalid test tile {tile_id} at ({x}, {y})")

    return jsonify({"message": f"Game started with {num_players} players"}), 201


def start_api():
    app.run(host="127.0.0.1", port=1234, threaded=True)

NUM_PLAYERS = 3

# Hard-coded river for testing (x, y) where x increases right, y increases up
STARTING_RIVER = [
    ("ID0",  0, 0),
    ("ID9",  1, 0),
    ("ID32", 2, 0),
    ("ID8",  2, -1),
    ("ID1",  2, -2),
]

#Hard coded game for testing - tiles will be played in order, mix of valid and invalid tiles
TEST_GAME = [
    ("ID0",  0, 0),    # invalid - already placed by river
    ("ID9",  1, 0),    # invalid - already placed by river
    ("ID32", 2, 0),    # invalid - already placed by river
    ("ID122",  2, -3), #valid tile
    ]

TOTAL_PIECES = 82
remaining_pieces = 82

current_turn = 1

# func to pretty print board - testing only
def printBoard(game):
    width = 7
    for row in game.board:
        line = ""
        for t in row:
            if t is None:
                line += ".".center(width)
            else:
                line += t.tile_id.center(width)
        print(line)

#Function that is first called upon game start. launches the API and waits for a POST to /start
def gameStart():
    # api_thread = threading.Thread(target=start_api, daemon=True)
    # api_thread.start()
    # print("API running on http://127.0.0.1:1234, waiting for POST /start to begin game")

    # t = threading.Thread(target=Project_CV.cv_main_loop, daemon=True)
    # t.start()
    # tileBag = tile_bag.tile_bag()

    # api_thread.join()




    # Old gameStart code / Testing without API interference
    global game_state
    tileBag = tile_bag.tile_bag()

    # Remove river tiles from bag since they're pre-placed for testing
    for tile_id, _, _ in STARTING_RIVER:
        tileBag.remove_tile(tile_id)

    game = initialiseBoard(NUM_PLAYERS)
    game_state = game
    print(f"Game started with {NUM_PLAYERS} players")
    printBoard(game)

    # play turns until pieces run out
    while game.remaining_pieces > 0:
        playTurn(game, tileBag)

    scoreEndGame(game)

    # LEGACY CODE BELOW

    # #play turns until peices run out
    # while game.remaining_pieces > 0:
    #     playTurn(current_turn)

    # Test code to test threads replicated in another file so can be commented out for now
    # so as to not break the main file testing in engine
    # print("Starting")
    # while True:
    #     if Project_CV.cv_to_engine:
    #         # This is the CV communicating to the game engine

    #         # Variables are:
    #         # Project_CV.grid_coord which is a tuple (x, y)
    #         # TESTING
    #         print(Project_CV.tile_id) # Check game engine can access variables
    #         # Project_CV.tile_id which is a number at the moment can be changed

    #         # At the end have
    #         Project_CV.game_response = (True, 1) # 1 is a temp value as nothing has been implemented for it yet

    #     time.sleep(0.1)

    

#initialises internal board system

def initialiseBoard(num_players):
    players = [player(i) for i in range(num_players)]

    game = gameStateClass(players)

    # Temp code for testing river
    for tile_id, x, y in STARTING_RIVER:
        game.place_tile(x, y, tile_set[tile_id])
    
    
    return game


def get_valid_placements(game, tile_obj):
    valid = []
    for (x, y), t in game.get_board_xy().items():
        # check all 4 neighbors of each placed tile
        neighbors = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        for neighbor_x, neighbor_y in neighbors:
            if game.check_valid_placement(neighbor_x, neighbor_y, tile_obj):
                valid.append((neighbor_x, neighbor_y))
    # also check (0,0) if board is empty
    if not game.get_board_xy() and game.check_valid_placement(0, 0, tile_obj):
        valid.append((0, 0))
    return list(set(valid))


#Runs every turn
def playTurn(game, tileBag):
    current = game.current_player()
    print(f"\n Turn {game.current_turn}, {current.return_colour()}'s turn")
    print(f"Meeples: {current.meeples}, Score: {current.score}, Pieces left: {game.remaining_pieces}")

    # Getting Tile from Player, might turn into fetch request to project CV?
    while True:
        tile_input = input("Enter tile ID or 'board' to see board: ").strip()

        if tile_input.lower() == "board":
            printBoard(game)
            continue

        if tile_input not in tile_set:
            print(f"Unknown tile '{tile_input}'. Try again.")
            continue

        tile_obj = tile_set[tile_input]
        found = tileBag.find_tile_id(tile_input)
        if found is None:
            print(f"Tile {tile_input} already used. Try again.")
            continue

        break


    # Valid placements
    valid = get_valid_placements(game, tile_obj)
    if not valid:
        print(f"No valid placements for {tile_input}, skipping turn")
        tileBag.remove_tile(tile_input)
        game.next_player()
        game.current_turn += 1
        return

    print(f"Valid placements for {tile_input}")
    for i, (x, y) in enumerate(valid):
        print(f"x = {x}, y = {y}")


    # collect x and y from user
    while True:
        try:
            x, y = map(int, input("Enter x,y: ").split(","))
            if (x, y) not in valid:
                print("Not valid, try again.")
                continue
            break
        except:
            print("Invalid, try again.")


    # placing tile
    game.place_tile(x, y, tile_obj)
    tileBag.remove_tile(tile_input)
    print(f"Placed {tile_input} at ({x}, {y})")

    checkMeeplePlaced(game, current, tile_obj, x, y)
    #game.manage_structures(x, y, tile_obj)
    checkDoneStructures(game)

    # Advanced to next turn
    game.next_player()
    game.current_turn += 1
    printBoard(game)



#Check if a meeple was placed on new tile, if it is right colour and whether its on a road or city for double tiles
def checkMeeplePlaced(game, current, tile_obj, x, y) :
    pass

#scans board state and checks and scores all completed structures not scored previously
def checkDoneStructures(game):
    updateScores() #update scores for all affected players if there is a done structure
    pass


#updates scores for every player, given player id and score add
def updateScores():
    pass

def scoreEndGame(game):
    pass


# Test Game
if __name__ == "__main__":
    gameStart()
