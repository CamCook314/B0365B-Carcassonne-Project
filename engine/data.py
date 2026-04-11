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

	def returnColour(self):
		colours = ["red", "blue", "green", "yellow", "black"]
		return colours[self.colour]



class gameStateClass:
	def __init__(self, players):
		# board is a 2d array of tile objects
		self.board = [[None] * 15 for _ in range(15)]
		# players is a list of player objects
		self.players = players
		self.currentIndex = 0
		self.remaining_pieces = 72
		self.current_turn = 1
		self.structures = []

	def place_tile(self, row, col, tile):
		if not self.check_valid_placement(row, col, tile):
			raise ValueError(f"Invalid tile placement at ({row}, {col})")
		self.board[row][col] = tile
		self.remaining_pieces -= 1

	def manage_structures(self, row, col, tile):
		matching_structures = []

		for structure in self.structures:
			connections = structure.check_structure_compatability(row, col, tile, self.board)
    
			if connections is not None:
				matching_structures.append(structure)
		
		if len(matching_structures) == 0:
			if tile.up == 1 or tile.right == 1 or tile.down == 1 or tile.left == 1:
				new_struct = structures(tile, row, col, 1)
			elif tile.up == 2 or tile.right == 2 or tile.down == 2 or tile.left == 2:
				new_struct = structures(tile, row, col, 2)
			elif tile.attribute == 2: #Monastary
				new_struct = structures(tile, row, col, 3)
		
			self.structures.append(new_struct)
		elif len(matching_structures) == 1:
			matching_structures[0].extend_structure(row, col, tile, self.board)

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
		# Position must be within bounds
		if row < 0 or row >= len(self.board) or col < 0 or col >= len(self.board[0]):
			return False

		# Position must be empty
		if self.board[row][col] is not None:
			return False

		# values mean (neighbor_row, neighbor_col), opposite_side, my_edge
		neighbors = {
			"up":    ((row - 1, col), "down",  tile.up),
			"down":  ((row + 1, col), "up",    tile.down),
			"left":  ((row, col - 1), "right", tile.left),
			"right": ((row, col + 1), "left",  tile.right),
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
	
	def __repr__(self):
		return f"board={self.board}"
	

#Types will be road, city, monastary in order 1, 2, 3
# Monastary will be check differently
class structures:
	def __init__(self, first_tile,row, col, structure):
		self.type = structure
		self.tiles_used = [(first_tile, row, col)]
		self.edges = []
		self.players = []
		self.completed = False

		#brute force initialisation
		if self.type == 1:
			if first_tile.up == 1:
				self.edges.append((first_tile, "up"))
			if first_tile.down == 1:
				self.edges.append((first_tile, "down"))
			if first_tile.left == 1:
				self.edges.append((first_tile, "left"))
			if first_tile.right == 1:
				self.edges.append((first_tile, "right"))
		elif self.type == 2:
			if first_tile.up == 2:
				self.edges.append((first_tile, "up"))
			if first_tile.down == 2:
				self.edges.append((first_tile, "down"))
			if first_tile.left == 2:
				self.edges.append((first_tile, "left"))
			if first_tile.right == 2:
				self.edges.append((first_tile, "right"))

	
	def extend_structure(self, row, col, tile, board):
		# Check monastary differently
		if self.type == 3:
			return
		self.tiles_used.append((tile, row, col)) # for scoring
		
		neighbors = {
			"up":    ((row - 1, col), "down",  tile.up),
			"down":  ((row + 1, col), "up",    tile.down),
			"left":  ((row, col - 1), "right", tile.left),
			"right": ((row, col + 1), "left",  tile.right),
		}

		for direction, ((nr, nc), opposite_side, my_edge) in neighbors.items():
			if nr < 0 or nr >= len(board) or nc < 0 or nc >= len(board[0]):
				continue
			neighbor = board[nr][nc]
			
			if neighbor is not None:
				if getattr(neighbor, opposite_side) == my_edge:
					if (neighbor, opposite_side) in self.edges:
						self.edges.remove((neighbor, opposite_side)) #remove non open edges
			else:
				if my_edge == self.type:
					self.edges.append((tile, direction)) #add open edges

	def add_player(self, player):
		self.players.append(player)

	#check if new tile belongs in this structure
	def check_structure_compatability(self,  row, col, tile, board):
		connections = []

		neighbors = {
			"up":    ((row - 1, col), "down",  tile.up),
			"down":  ((row + 1, col), "up",    tile.down),
			"left":  ((row, col - 1), "right", tile.left),
			"right": ((row, col + 1), "left",  tile.right),
		}

		for (nr, nc), opposite_side, my_edge in neighbors.values():
			if nr < 0 or nr >= len(board) or nc < 0 or nc >= len(board[0]):
				continue
			neighbor = board[nr][nc]

			if neighbor is None:
				continue

			if my_edge == self.type and getattr(neighbor, opposite_side) == self.type:
				if (neighbor, opposite_side) in self.edges:
					connections.append((neighbor, opposite_side))

		return connections

	def score_structure(self):
		if self.type == 3: #Monastary scoring
			self.players[0].score += 9
			return

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

	def check_completed(self, board):
		if self.type == 3: # Checks all surrounding tiles for monastary
			row = self.tiles_used[0][1]
			col = self.tiles_used[0][2]
			all_neighbors = [
				(row - 1, col - 1), (row - 1, col), (row - 1, col + 1),
				(row,   col - 1), (row,   col), (row,   col + 1),
				(row + 1, col - 1), (row + 1, col), (row + 1, col + 1)]
			for nr, nc in all_neighbors:
				if board[nr][nc] is None:
					return False
			return True

			
		if len(self.edges) == 0:
			return True
		return False

	def __repr__(self):
		return f"structure ={self.type}, size= {len(self.tiles_used)}"
		
	




def printBoard(game):
    width = 7
    for row in game.board:
        line = ""
        for t in row:
            if t is None:
                line += ".".center(width)
            else:
                line += str(t).center(width)
        print(line)




#Tests
p1 = player(0)
p2 = player(1)

game = gameStateClass([p1, p2])

t1 = tile(1, 1, 0, 0, 0, 0)  # road vertical

game.place_tile(3, 3, t1)
game.manage_structures(3, 3, t1)

print("Placed first tile")
printBoard(game)

t2 = tile(1, 1, 0, 0, 0, 0)  # road vertical

game.place_tile(2, 3, t2)

game.manage_structures(2, 3, t2)

print("After extending road upward")
printBoard(game)

print(game.structures)