#import ....
import sys
import os
from data import tile, player, gameStateClass
from tile_set import tile_set
# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cv import Project_CV
import threading
import time
import tile_bag

#im using camelCase for functions and snake_case for variables

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
    ]

TOTAL_PIECES = 82
remaining_pieces = 82

current_turn = 1

#player data dictionary, includes colour, number of held meeples, current score


#Function that is first called upon game start
def gameStart():
    initialiseBoard() #sets up internal board tracking, TODO: Add player count as argument
    t = threading.Thread(target=Project_CV.cv_main_loop, daemon=True)
    t.start()
    tileBag = tile_bag.tile_bag()
    #checkValidBoardState() #makes sure players placed rivers right and the game is okay to start
    game = initialiseBoard(NUM_PLAYERS) #sets up internal board tracking

    print(game.board)

    meeple = 0
    
    
    # #play turns until peices run out
    #while game.remaining_pieces > 0:
    for new_tile in TEST_GAME: #Loop only for testing the TEST_GAME list
        playTurn(game, current_turn, new_tile, meeple)
        current_turn += 1

    # #play turns until peices run out
    # while game.remaining_pieces > 0:
    #     playTurn(current_turn)

    # Test code to test threads replicated in another file so can be commented out for now
    # so as to not break the main file testing in engine
    """
    print("Starting")
    while True:
        if Project_CV.cv_to_engine:
            # This is the CV communicating to the game engine

            # Variables are:
            # Project_CV.grid_coord which is a tuple (x, y)
            # TESTING
            print(Project_CV.tile_id) # Check game engine can access variables
            # Project_CV.tile_id which is a number at the moment can be changed

            # At the end have
            Project_CV.game_response = (True, 1) # 1 is a temp value as nothing has been implemented for it yet
        
        time.sleep(0.1)
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
