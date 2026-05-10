#import ....
import sys
import os
from data import tile, player, gameStateClass
from tile_set import tile_set
# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from cv import Project_CV
except ImportError:
    Project_CV = None
import threading
import time
import tile_bag


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
    # Old gameStart code / Testing without API interference
    global game_state
    tileBag = tile_bag.tile_bag()

    # Remove river tiles from bag since they're pre-placed for testing
    # for tile_id, _, _ in STARTING_RIVER:
    #     tileBag.remove_tile(tile_id)

    game = initialiseBoard(NUM_PLAYERS)
    game_state = game
    print(f"Game started with {NUM_PLAYERS} players")
    printBoard(game)

    # play turns until pieces run out
    while game.remaining_pieces > 0:
        playTurn(game, tileBag)

    #scoreEndGame(game)

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

def initialiseBoard(players):
    #players = [player(i) for i in range(num_players)]

    game = gameStateClass(players)

    # # Temp code for testing river
    # for tile_id, x, y in STARTING_RIVER:
    #     game.place_tile(x, y, tile_set[tile_id])
    
    
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

def get_valid_placements_all_rotations(game, base_tile_num):
    base = base_tile_num * 4
    all_valid = {}
    
    for r in range(4):
        rid = f"ID{base + r}"
        if rid not in tile_set:
            continue
        tile_obj = tile_set[rid]
        valid = get_valid_placements(game, tile_obj)
        for x, y in valid:
            if (x, y) not in all_valid:
                all_valid[(x, y)] = []
            all_valid[(x, y)].append(rid)

    return all_valid

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

    game.manage_structures(x, y, tile_obj)

    #assuming tile obj already has meeple_attached populated or not populated
    """
    wait here until meeple detected or next tile detected

    if meeple detected 
        tile_obj.meeple_attached = meeple_coords; - from cv
        game.place_meeple(tile_obj)
    else just advance to next turn
    
    """


    # Advanced to next turn
    game.next_player()
    game.current_turn += 1
    printBoard(game)


"""
def scoreEndGame(game):
    for struct in game.structures:
        temp_score = 0
        if struct.type == 1:
            temp_score += len(struct.tiles_used)
            for players in struct.players:
                players.score += temp_score
        elif struct.type == 2:
            for tiles in struct.tiles_used:
                if tiles.attribute == 1:
                    temp_score += 2
                else:
                    temp_score += 1
            for players in struct.players:
                players.score += temp_score
        elif struct.type == 3:
            row = struct.tiles_used[0][1]
            col = struct.tiles_used[0][2]
            all_neighbors = [
				(row - 1, col - 1), (row - 1, col), (row - 1, col + 1),
				(row,   col - 1), (row,   col), (row,   col + 1),
				(row + 1, col - 1), (row + 1, col), (row + 1, col + 1)]
            for nr, nc in all_neighbors:
                if game.board[nr][nc] is not None:
                    temp_score += 1
            for players in struct.players: # should only be one player tho
                players.score += temp_score
"""


# Test Game
if __name__ == "__main__":
    gameStart()
