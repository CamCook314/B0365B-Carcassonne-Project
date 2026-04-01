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

	# For tile printing in testing
	def __repr__(self):
		return f"Tile(u={self.up} d={self.down} l={self.left} r={self.right})"


class player:

	# Constructor for each player object. colour is an integer that represents the player's colour.
	# Integers for the colour are as follows:
	# red = 0, blue = 1, green = 2, yellow = 3, black = 4
	# meeples is an integer that represents how many meeples the player has left to place.

	def __init__(self, colour):
		self.colour = colour
		self.meeples = 7
		self.score = 0

# This was the 2d array way of doing the class
class gameClass:

	# board is a 2d array of tile objects
	# players is a list of player objects
	def __init__(self, players, turn):
		self.board = [[None] * 15 for _ in range(15)]
		self.players = players
		self.currentIndex = 0


	def currentPlayer(self):
		return self.players[self.currentIndex]

	def nextPlayer(self):
		self.currentIndex = (self.currentIndex + 1) % len(self.players)
	
# This was the mapping way of doing the class
class gameStateClass:
	def __init__(self, players):
		self.board = {}
		self.players = players
		self.currentIndex = 0
		self.remaining_pieces = 72
		self.current_turn = 1

	def place_tile(self, row, col, tile):
		self.board[(row, col)] = tile
		self.remaining_pieces -= 1

	def nextPlayer(self):
		self.currentIndex = (self.currentIndex + 1) % len(self.players)
	
	def currentPlayer(self):
		return self.players[self.currentIndex]
	
	def __repr__(self):
		board_str = "\n".join(
			f"  {coords}: {tile}" for coords, tile in self.board.items()
		)
		return f"board={self.board}"
