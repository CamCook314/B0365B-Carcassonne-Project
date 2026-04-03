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

	#Meeple_attatched is set to 0 unless a meeple is detected, then 1,
	# The next 4 are up, down, left, right for which structure it is on, when it applies

	def __init__(self, up, down, left, right, feature_continues, attribute):
		self.up = up
		self.down = down
		self.left = left
		self.right = right
		self.feature_continues = feature_continues
		self.attribute = attribute
		self.meeple_attached = (0, 0, 0, 0, 0)

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
		if not self.check_valid_placement(row, col, tile):
			raise ValueError(f"Invalid tile placement at ({row}, {col})")
		self.board[(row, col)] = tile
		self.remaining_pieces -= 1

	def nextPlayer(self):
		self.currentIndex = (self.currentIndex + 1) % len(self.players)
	
	def currentPlayer(self):
		return self.players[self.currentIndex]
	
	#Place meeple on tile and where on tile if it has multiple places
	def place_meeple(self, tile, up, down, left, right):
		if tile.meeple_attached[0] == 1:
			raise ValueError("Meeple already placed on this tile")

		player = self.currentPlayer()
		if player.meeples <= 0:
			raise ValueError("No meeples left")

		tile.meeple_attached = (1, up, down, left, right)
		player.meeples -= 1

	
	
	def check_valid_placement(self, row, col, tile):
		# Position must be empty
		if (row, col) in self.board:
			return False

		# values mean pos, opposite_side, my_edge
		neighbors = {
			"up":    ((row - 1, col), "down",  tile.up),
			"down":  ((row + 1, col), "up",    tile.down),
			"left":  ((row, col - 1), "right", tile.left),
			"right": ((row, col + 1), "left",  tile.right),
		}

		has_neighbor = False
		for pos, opposite_side, my_edge in neighbors.values():
			neighbor = self.board.get(pos)
			if neighbor is not None:
				has_neighbor = True
				if getattr(neighbor, opposite_side) != my_edge:
					return False

		# Must be adjacent to at least one existing tile
		if self.board and not has_neighbor:
			return False

		return True
	
	def __repr__(self):
		return f"board={self.board}"
	

#Types will be road, city, monastary
class structures:
	def __init__(self, first_tile):
		self.type = None
		self.tiles_used = [first_tile]
		self.edges = set()
		self.players = []
		self.completed = False
	
	def extend_structure(self, tile):
		self.tiles_used.append(tile)
		self.edges.add(tile, "up") #Example
		pass

	def add_player(self, player):
		self.players.append(player)

	def score_structure(self):
		pass

	def check_completed(self):
		if len(self.edges) == 0:
			return True
		return False

	def __repr__(self):
		pass
		
	

