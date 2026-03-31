# Variable declarations

class tile:

	# Constructor for each tile object. up, down left and right
	# are integers that represent what kind of connector type the
	# side is. Integers are as follows:

	# 0 = no connector (field)
	# 1 = road
	# 2 = city
	# 3 = river

	# feature_continues, whether features continue from side to side
	# 0 = no
	# 1 = yes

	# the attribute integer represents any other special
	# characteristics. Integers are as follows:

	# 0 = none
	# 1 = shield (for city tiles)
	# 2 = monastery (for field tiles)

	def __init__(self, up, down, left, right, feature_continues, attribute):
        self.up = up
        self.down = down
        self.left = left
        self.right = right
		self.feature_continues = feature_continues
        self.attribute = attribute


class player:

	# Constructor for each player object. colour is an integer that represents the player's colour.
	# Integers for the colour are as follows:
	# red = 0, blue = 1, green = 2, yellow = 3, black = 4
	# meeples is an integer that represents how many meeples the player has left to place.

	def __init__(self, colour):
		self.colour = colour
		self.meeples = 7
		self.score = 0

class gameClass:

	# board is a 2d array of tile objects
	# players is a list of player objects
	def __init__(self, players, turn):
		self.board = [[None] * 15 for _ in range(15)]
        self.players = players
        self.currentIndex = 0


    def currentPlayer(self):
        return self.players[self.currentIndex]

    def nextPlayer:
		self.currentIndex = (self.currentIndex + 1) % len(self.players)