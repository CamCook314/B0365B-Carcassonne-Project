#import ....
from data import tile, player, gameStateClass
from tile_set import tile_set

#Datatypes

    #Tile
    #board_state[Tile] - something like that

#im using camelCase for functions and snake_case for variables

NUM_PLAYERS = 3

TOTAL_PIECES = 72
remaining_pieces = 72

current_turn = 1

#player data dictionary, includes colour, number of held meeples, current score


#Function that is first called upon game start
def gameStart():
    game = initialiseBoard(NUM_PLAYERS) #sets up internal board tracking

    # checkValidBoardState() #makes sure players placed rivers right and the game is okay to start

    # #play turns until peices run out
    # while game.remaining_pieces > 0:
    #     playTurn(current_turn)
        
        
    

#initialises internal board system
def initialiseBoard():
    players = [player(i) for i in range(NUM_PLAYERS)]

    game = gameStateClass(players)

    # starting river logic maybe function

    for tile, row, col in STARTING_RIVER:
        game.place_tile(row, col, tile)
    
    return game


# Given a board state, check that all connections are legal
def checkValidBoardState(board_state):
    pass


#Runs every turn
def playTurn(current_turn):
    checkValidBoardState() # after tile placed
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