<<<<<<< HEAD
#import ....
from data import tile, gameClass, player

#Datatypes

    #Tile
    #board_state[Tile] - something like that
=======
from data import tile, player, gameStateClass
from tile_set import tile_set
>>>>>>> 308f0c50c0bc56ce846ff4bd15b4543e0201d863

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
<<<<<<< HEAD
    initialiseBoard() #sets up internal board tracking, TODO: Add player count as argument
    checkValidBoardState() #makes sure players placed rivers right and the game is okay to start
=======
    game = initialiseBoard(NUM_PLAYERS) #sets up internal board tracking
>>>>>>> 308f0c50c0bc56ce846ff4bd15b4543e0201d863

    print(game.board)

    meeple = 0
    
    
    # #play turns until peices run out
    #while game.remaining_pieces > 0:
    for new_tile in TEST_GAME: #Loop only for testing the TEST_GAME list
        playTurn(game, current_turn, new_tile, meeple)
        current_turn += 1
    
    

#initialises internal board system
<<<<<<< HEAD
def initialiseBoard(playerCount):
    global game

    #TODO: Initialize players
    playerList = []
    for i in range(0, playerCount):
        #create player objects and add to game.players
        playerList.append(player(i))
        

    #TODO: Initialize starting board with river tiles
    game = gameClass(playerList)
    pass


# Given a board state, check that all connections are legal
def checkValidBoardState(board_state):
    pass
=======
def initialiseBoard(num_players):
    players = [player(i) for i in range(num_players)]

    game = gameStateClass(players)

    # Commented out as i think each player will take turns placing tiles, uncomment if not the case
    # Temp code for now
    #for tile_id, row, col in STARTING_RIVER:
        #game.place_tile(row, col, tile_set[tile_id])
    
    
    return game
>>>>>>> 308f0c50c0bc56ce846ff4bd15b4543e0201d863


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
