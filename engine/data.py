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
	# integers for the colour are as follows:
	# red = 0, blue = 1, green = 2, yellow = 3, black = 4
	# meeples is an integer that represents how many meeples the player has left to place.

	def __init__(self, colour):
		self.colour = colour
		self.meeples = 7
		self.score = 0

	def return_colour(self):
		colours = ["red", "blue", "green", "yellow", "black"]
		return colours[self.colour]



class gameStateClass:
	def __init__(self, players):
		# board is a 2d array of tile
		self.board = [[None] * 15 for _ in range(15)]
		# offsets to convert logical coordinates to array indexes
		self.row_offset = 0
		self.col_offset = 0
		# players is a list of player objects
		self.players = players
		self.currentIndex = 0
		self.remaining_pieces = 72
		self.current_turn = 1

	# converts x,y logical coordinates to array indexes using offsets.
	# x increases going right, y increases going up (standard math axes).
	# internally the 2d array has rows increasing downward, so y is negated.
	# when the board expands upward or leftward to support negative coordinates,
	# rows/cols are prepended and the offsets increase.
	
	# for example, if a tile is placed at x=-1 and the board expands left by 10,
	# col_offset becomes 10, so x=-1 maps to array_col = -1 + 10 = 9.
	# this way the game logic can use any coordinate (including negatives)
	# while the underlying array always uses positive indexes.
	def to_array_index(self, x, y):
		array_row = -y + self.row_offset
		array_col = x + self.col_offset
		return array_row, array_col

	# expands the board when a tile placement would fall outside the current
  	# array bounds. works on array indexes after converting from x,y coordinates.
	def expand_board(self, x, y):
		array_row, array_col = self.to_array_index(x, y)
		rows = len(self.board)
		cols = len(self.board[0])

		# expand upward
		if array_row < 0:
			new_rows = [([None] * cols) for _ in range(10)]
			self.board = new_rows + self.board
			self.row_offset += 10

		# expand downward
		if array_row >= rows:
			new_rows = [([None] * cols) for _ in range(10)]
			self.board = self.board + new_rows

		# expand left
		if array_col < 0:
			for r in self.board:
				r[:0] = [None] * 10
			self.col_offset += 10

		# expand right
		if array_col >= cols:
			for r in self.board:
				r.extend([None] * 10)

	# x = column (increase goes right), y = row (increase goes up)
	def place_tile(self, x, y, tile):
		self.expand_board(x, y)
		if not self.check_valid_placement(x, y, tile):
			raise ValueError(f"Invalid tile placement at ({x}, {y})")
		array_row, array_col = self.to_array_index(x, y)
		self.board[array_row][array_col] = tile
		self.remaining_pieces -= 1

	def next_player(self):
		self.currentIndex = (self.currentIndex + 1) % len(self.players)

	def current_player(self):
		return self.players[self.currentIndex]

	#Place meeple on tile and where on tile if it has multiple places
	def place_meeple(self, tile, up, down, left, right):
		if tile.meeple_attached[0] == 1:
			raise ValueError("Meeple already placed on this tile")

		player = self.current_player()
		if player.meeples <= 0:
			raise ValueError("No meeples left")

		tile.meeple_attached = (1, up, down, left, right)
		player.meeples -= 1



	def check_valid_placement(self, x, y, tile):
		array_row, array_col = self.to_array_index(x, y)

		# Position must be within bounds
		if array_row < 0 or array_row >= len(self.board) or array_col < 0 or array_col >= len(self.board[0]):
			return False

		# Position must be empty
		if self.board[array_row][array_col] is not None:
			return False

		# values mean (neighbor_row, neighbor_col), opposite_side, my_edge
		neighbors = {
			"up":    ((array_row - 1, array_col), "down",  tile.up),
			"down":  ((array_row + 1, array_col), "up",    tile.down),
			"left":  ((array_row, array_col - 1), "right", tile.left),
			"right": ((array_row, array_col + 1), "left",  tile.right),
		}

		has_neighbor = False
		for (nr, nc), opposite_side, my_edge in neighbors.values():
			if nr < 0 or nr >= len(self.board) or nc < 0 or nc >= len(self.board[0]):
				continue
			neighbor = self.board[nr][nc]
			if neighbor is not None:
				has_neighbor = True
				if getattr(neighbor, opposite_side) != my_edge:
					return False

		# Must be adjacent to at least one existing tile (unless board is empty)
		board_empty = all(self.board[r][c] is None for r in range(len(self.board)) for c in range(len(self.board[0])))
		if not board_empty and not has_neighbor:
			return False

		return True

	# returns a dictionary of placed tiles as (x, y) graphical coordinates
	def get_board_xy(self):
		board_xy = {}
		for array_row in range(len(self.board)):
			for array_col in range(len(self.board[array_row])):
				if self.board[array_row][array_col] is not None:
					x = array_col - self.col_offset
					y = -(array_row - self.row_offset)
					board_xy[(x, y)] = self.board[array_row][array_col]
		return board_xy

	def __repr__(self):
		return f"board={self.board}"
	

#Types will be road, city, monastary
class structures:
	def __init__(self, first_tile, structure):
		self.type = structure
		self.tiles_used = [first_tile]
		self.edges = []
		self.players = []
		self.completed = False

		#brute force initialisation
		if self.type == "road":
			if first_tile.up == 1:
				self.edges.append((first_tile, "up"))
			if first_tile.down == 1:
				self.edges.append((first_tile, "down"))
			if first_tile.left == 1:
				self.edges.append((first_tile, "left"))
			if first_tile.right == 1:
				self.edges.append((first_tile, "right"))
		elif self.type == "city":
			if first_tile.up == 2:
				self.edges.append((first_tile, "up"))
			if first_tile.down == 2:
				self.edges.append((first_tile, "down"))
			if first_tile.left == 2:
				self.edges.append((first_tile, "left"))
			if first_tile.right == 2:
				self.edges.append((first_tile, "right"))

	
	def extend_structure(self, row, col, tile, board):
		self.tiles_used.append(tile) # for scoring
		
		neighbors = {
			"up":    ((row - 1, col), "down",  tile.up),
			"down":  ((row + 1, col), "up",    tile.down),
			"left":  ((row, col - 1), "right", tile.left),
			"right": ((row, col + 1), "left",  tile.right),
		}
		for direction, (pos, opposite_side, my_edge) in neighbors.items():
			neighbor = board.get(pos)
			if (neighbor, opposite_side) in self.edges:
					self.edges.remove((neighbor, opposite_side))
			elif my_edge == self.type and neighbor is None:
				self.edges.append((tile, direction))
		pass

	def add_player(self, player):
		self.players.append(player)

	def score_structure(self):
		temp_score = 0
		for tile in self.tiles_used:
			if self.type == 1:
				temp_score += 1
				continue
			elif self.type == 2:
				if tile.attribute == 1:
					temp_score += 4
				else:
					temp_score += 2

		for player in self.players:
			player.score += temp_score
		pass

	def check_completed(self):
		if len(self.edges) == 0:
			return True
		return False

	def __repr__(self):
		pass
		
	


