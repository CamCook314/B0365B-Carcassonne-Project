from tile_set import tile_set
from tile import tile
from events import Event
# Variable declarations
import random
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from cv import projector

class player:

	# Constructor for each player object. colour is an integer that represents the player's colour.
	# integers for the colour are as follows:
	# red = 0, blue = 1, green = 2, yellow = 3, black = 4
	# meeples is an integer that represents how many meeples the player has left to place.

	def __init__(self, colour):
		self.colour = colour
		self.meeples = 7
		self.score = 0

	def ability(self,structure, game):
		pass

	def return_colour(self):
		colours = ["red", "blue", "green", "yellow", "black"]
		return colours[self.colour]


class farmer(player): #gets an extra point when scoring roads
	def __init__(self):
		super().__init__(3)

	def ability(self, structure, game):
		if structure.type == 1:
			self.score += 1

class knight(player): #gets an extra 2 points when scoring cities
	def __init__(self):
		super().__init__(1)
	
	def ability(self, structure, game):
		if structure.type == 2:
			self.score += 2
		pass

class lord(player): # steals point from random player with > 1 score when scoring cities
	def __init__(self):
		super().__init__(0)

	def ability(self, structure, game):
		max_play = game.players[0]

		if structure.type == 2:
			for play in game.players:
				if play.score > max_play:
					max_play = play
			self.score += 1
			max_play.score -= 1
				


		pass

class merchant(player): #starts with 3 points
	def __init__(self):
		super().__init__(2)
		self.score = 3

	def ability(self, structure, game):
		pass

class necrobinder(player): #immune to negative tile effects
	def __init__(self):
		super().__init__(4)

	def ability(self, structure, game):
		for tile in structure.tiles_used:
			tile.bad_tile = False

		
		pass




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
		self.structures = []
		self.river_struct = [] # will contain coordinates for river tiles for various uses
		self.tile_dict_turn = {} #tracks tiles placed in last 3 turns


		# The below are event states. Read by api.build_active_events() to populate the
		# Active Events panel on the website. Add new event flags here.

		# List of Event objects, each pinned to a random (x, y). Triggered in
		# place_tile() when a tile is placed on those coords.
		self.event_pool = []
		# Set True by Event.extra_turn_event
		self.extra_turn = False
		# unrestCheck: set True by Event.unrest_event; read by score_structure() to
		#   halve city scores until the unrest timer expires.
		self.unrestCheck = False

		
			

	# converts x,y logical coordinates to array indexes using offsets.
	# x increases going right, y increases going up (standard math axes).
	# internally the 2d array has rows increasing downward, so y is negated.
	# when the board expands upward or leftward to support negative coordinates,
	# rows/cols are prepended and the offsets increase.
	
	# for example, if a tile is placed at x=-1 and the board expands left by 10,
	# col_offset becomes 10, so x=-1 maps to array_col = -1 + 10 = 9.
	# this way the game logic can use any coordinate (including negatives)
	# while the underlying array always uses positive indexes.

	# Helper function to convert logical x,y coordinates to the 2d list indexes
	def to_array_index(self, x, y):
		array_row = -y + self.row_offset
		array_col = x + self.col_offset
		return array_row, array_col
	

	def event_init(self):
		for i in range(4):  # 4 event coords
			max_x = 0
			min_x = 0
			max_y = 0
			min_y = 0
			for (j,k) in self.river_struct:
				if j > 0:
					if j > max_x:
						max_x = j
				elif j < 0:
					if j < min_x:
						min_x = j
				if k > 0:
					if k > max_y:
						max_y = k
				elif k < 0:
					if k < min_y:
						min_y = k
			while True:
				randx = random.randint(min_x - 5, max_x + 5) #max 5 tiles away from any river tile
				randy = random.randint(min_y - 5, max_y + 5)

				if (randx, randy) not in [e.coords for e in self.event_pool] and (randx, randy) not in self.river_struct: #unique coords
					self.event_pool.append(Event((randx, randy)))
					print(Event((randx, randy)))
					projector.add_img("EVENT", (randx, randy))
					break
	
	#for 3 turns after its placed, every turn the tile has a 5% chance to either turn good or bad, effects are permanent
	def good_tile_bad_tile(self, tile,x, y): #runs every turn
		self.tile_dict_turn[tile] = 0

		overstayed = []
		for til in self.tile_dict_turn:
			roll = random.random()
			if roll < 0.02: # 5% chance
				til.bad_tile = True
				projector.add_img("BAD_TILE", (x, y))
			elif roll > 0.98:
				til.good_tile = True
				projector.add_img("GOOD_TILE", (x, y))

			self.tile_dict_turn[til] += 1
			if self.tile_dict_turn[til] >= 3: #only 3 turns to change
				overstayed.append(til)

		for til in overstayed:
			del self.tile_dict_turn[til]

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
			for structure in self.structures:
				structure.tiles_used = [(t, r + 10, c) for t, r, c in structure.tiles_used]


		# expand downward
		if array_row >= rows:
			new_rows = [([None] * cols) for _ in range(10)]
			self.board = self.board + new_rows

		# expand left
		if array_col < 0:
			for r in self.board:
				r[:0] = [None] * 10
			self.col_offset += 10
			for structure in self.structures:
				structure.tiles_used = [(t, r, c + 10) for t, r, c in structure.tiles_used]

		# expand right
		if array_col >= cols:
			for r in self.board:
				r.extend([None] * 10)

	def extra_turn_event(self): # assuming they take it now
		self.extra_turn = True
		

	# x = column (increase goes right), y = row (increase goes up)
	def place_tile(self, x, y, tile):
		self.expand_board(x, y)
		if not self.check_valid_placement(x, y, tile):
			raise ValueError(f"Invalid tile placement at ({x}, {y})")
		array_row, array_col = self.to_array_index(x, y)
		self.board[array_row][array_col] = tile
		self.remaining_pieces -= 1

		if tile.up == 3 or tile.down == 3 or tile.right == 3 or tile.left == 3:
			self.river_struct.append((x,y))

		if len(self.river_struct) == 12:
			self.event_init()

		tile.player_placed = self.current_player()
		for event in self.event_pool:
			if event.coords == (x, y):
				projector.del_img("EVENT", (x, y))
				event.play(self)

		self.good_tile_bad_tile(tile, x, y)
		



	def remove_tile(self, x, y, tile):
		array_row, array_col = self.to_array_index(x, y)
		self.board[array_row][array_col] = None
		self.remaining_pieces += 1

		#tilebag.add(tile) add tile back into tilebag depending on what it can do


	#player is None if no meeple added
	def manage_structures(self, row, col, tile, player=None):
		"""
		Manages structures for the game, creating new ones, extending them, merging, and scoring
		once complete

		Args: 
			row (int): row of added tile
			col (int): col of added tile
			tile (tile object): tile to be added
		
		"""


		new_row, new_col = self.to_array_index(row, col)
		connections = []	
		for type in [1,2]: # to check for tiles with 2 structure types
			matching_edges = []
			for dir, vdir in [("up", tile.up), ("down", tile.down), ("left", tile.left), ("right", tile.right)]:
				if vdir == type:
					matching_edges.append(dir) #gets all edges of the tile
			if not matching_edges:
				continue

			if tile.feature_continues == 1: # if the feature continues treat all edges as 1 structure else treat them all as seperate
				edgegroup = [matching_edges]
			else:
				edgegroup = [[d] for d in matching_edges]
			for group in edgegroup: #only 1 if feature continues, multiple if seperated
				matching_structures = []
				for structure in self.structures:
					if structure.type != type:
						continue
					connections = structure.check_structure_compatability(new_row, new_col, tile, self.board)
					group_connections = [c for c in connections if c in group]
					if group_connections:
						matching_structures.append((structure, group_connections))
				if len(matching_structures) == 0: # no structure found, create new one
					if type == 1 and (tile.up == 1 or tile.right == 1 or tile.down == 1 or tile.left == 1): # for roads
						temp_struct = structures(tile, new_row, new_col, 1)
						if tile.feature_continues == 0:
							temp_struct.edges = []
							temp_struct.edges.append((tile, group[0]))
						
						self.structures.append(temp_struct)
					elif type == 2 and (tile.up == 2 or tile.right == 2 or tile.down == 2 or tile.left == 2): #for cities
						temp_struct = structures(tile, new_row, new_col, 2)
						if tile.feature_continues == 0:
							temp_struct.edges = []
							temp_struct.edges.append((tile, group[0]))
						self.structures.append(temp_struct)
				elif len(matching_structures) == 1: # 1 matching structure, need to extend
					struct, _ = matching_structures[0]
					struct.extend_structure(new_row, new_col, tile, self.board, group)
				elif len(matching_structures) >= 2: #2 or more matches, so need to merge into 1 structure
					all_tiles = []
					all_edges = []
					all_players = []
					for struct, _ in matching_structures:
						all_tiles += struct.tiles_used
						all_players += struct.players
						all_edges += struct.edges
						self.structures.remove(struct)
					new_struct = structures(all_tiles[0][0], all_tiles[0][1], all_tiles[0][2], matching_structures[0][0].type)
					new_struct.players = all_players
					new_struct.tiles_used = all_tiles
					
					new_struct.edges = all_edges
					new_struct.extend_structure(new_row, new_col, tile, self.board, group)

					self.structures.append(new_struct)
		if tile.attribute == 2: #Monastary
			#Monastary detected
			temp_struct = structures(tile, new_row, new_col, 3)
			self.structures.append(temp_struct)
		for structure in self.structures: # score all completed structures
			if structure.check_completed(self.board):
				structure.score_structure(self.unrestCheck, self)
				self.structures.remove(structure)


	def next_player(self):
		
		if self.extra_turn:
			self.extra_turn = False
			return
		for ev in self.event_pool: #check events every turn
			if ev.name == "volcano" and ev.active == True:
				ev.volcano_check(self)
		self.currentIndex = (self.currentIndex + 1) % len(self.players)
		self.current_turn += 1

	def current_player(self):
		return self.players[self.currentIndex]

	# Place a meeple on the just-placed tile, on the given direction
	# ("up", "down", "left", "right", "centre"). Uses the current player.
	# The colour is implicit (each player has a fixed colour from index).
	def place_meeple(self, tile, direction):
		player = self.current_player()

		if player.meeples <= 0:
			raise ValueError("No meeples left")

		# Monastery meeple goes in the centre 
		if direction == "centre":
			if tile.attribute != 2:
				raise ValueError("Centre meeple only valid on monastery tiles")
			for structure in self.structures:
				if structure.type != 3:
					continue
				for entry in structure.tiles_used:
					t = entry[0] if isinstance(entry, tuple) else entry
					if t is tile:
						if structure.players:
							raise ValueError("Structure already has meeple, please remove meeple")
						structure.add_player(player)
						player.meeples -= 1
						return
			raise ValueError("Could not find monastery structure for this tile")

		# Edge meeple
		edge_value = getattr(tile, direction)
		if edge_value not in (1, 2):
			raise ValueError(f"No road or city on side '{direction}'")

		for structure in self.structures:
			if structure.type != edge_value:
				continue
			for entry in structure.tiles_used:
				t = entry[0] if isinstance(entry, tuple) else entry
				if t is tile:
					if structure.players:
							raise ValueError("Structure already has meeple, please remove meeple")
					structure.add_player(player)
					player.meeples -= 1
					return

		raise ValueError(f"No {('road' if edge_value == 1 else 'city')} structure found containing this tile")


	def check_valid_placement(self, x, y, tile):
		array_row, array_col = self.to_array_index(x, y)

		# Check if position is within current board boundaries
		# If in bounds, position must be empty. Out of bounds is always empty (board will expand).
		if array_row >= 0 and array_row < len(self.board):
			if array_col >= 0 and array_col < len(self.board[0]):
				
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

		# strictly only allow 1 continuous river during starting phase
		tile_has_river = (tile.up == 3 or tile.down == 3
		                  or tile.left == 3 or tile.right == 3)
		if tile_has_river:
			river_connects = False
			for (nr, nc), opposite_side, my_edge in neighbors.values():
				if my_edge != 3:
					continue
				if nr < 0 or nr >= len(self.board) or nc < 0 or nc >= len(self.board[0]):
					continue
				neighbor = self.board[nr][nc]
				if neighbor is None:
					continue
				if getattr(neighbor, opposite_side) == 3:
					river_connects = True
					break

			if not river_connects:
				any_river_on_board = False
				for row in self.board:
					for placed in row:
						if placed is None:
							continue
						if (placed.up == 3 or placed.down == 3
						        or placed.left == 3 or placed.right == 3):
							any_river_on_board = True
							break
					if any_river_on_board:
						break
				if any_river_on_board:
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

	def score_end_game(self): # score all structures at end, these will be all uncompleted structures, so half points
		for struct in self.structures:
			temp_score = 0
			if struct.type == 1:
				temp_score += len(struct.tiles_used)
				for players in struct.players:
					players.score += temp_score
			elif struct.type == 2:
				for tiles in struct.tiles_used:
					if tiles[0].attribute == 1:
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
					if self.board[nr][nc] is not None:
						temp_score += 1
				for players in struct.players: # should only be one player tho
					players.score += temp_score


	def get_valid_placements(self, tile_obj):
		valid = []
		for (x, y), t in self.get_board_xy().items():
			# check all 4 neighbors of each placed tile
			neighbors = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
			for neighbor_x, neighbor_y in neighbors:
				if game.check_valid_placement(neighbor_x, neighbor_y, tile_obj):
					valid.append((neighbor_x, neighbor_y))
		# also check (0,0) if board is empty
		if not self.get_board_xy() and self.check_valid_placement(0, 0, tile_obj):
			valid.append((0, 0))
		return list(set(valid))
	

	def get_valid_placements_all_rotations(self, base_tile_num):
		base = base_tile_num * 4
		all_valid = {}
		
		for r in range(4):
			rid = f"ID{base + r}"
			if rid not in tile_set:
				continue
			tile_obj = tile_set[rid]
			valid = self.get_valid_placements(tile_obj)
			for x, y in valid:
				if (x, y) not in all_valid:
					all_valid[(x, y)] = rid
		
		return all_valid
	def __repr__(self):
		return f"board={self.board}"
	

#Types will be road, city, monastary in order 1, 2, 3
# Monastary will be check differently
class structures:
	"""
	class of structure object, these will be in progress structures 
	and all tiles involved will be tracked for scoring
	"""

	def __init__(self, first_tile, row, col, structure):
		"""
		Initialise structure

		Takes the first tile added, its location and the type of the structure
		
		"""
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
	
	def extend_structure(self, row, col, tile, board, group = None):
		"""
		This method, given a new tile, checks what structure it is to be added to and adds it
		If no structure is found then a new one is made
		if 2 or more structures are found, they are merged into one

		takes the new tile, its locations and the current board state
		
		"""

		# Check monastary differently
		print("extending")
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
			if group is not None and direction not in group:
				continue
			if nr < 0 or nr >= len(board) or nc < 0 or nc >= len(board[0]) or my_edge != self.type:
				continue
			neighbor = board[nr][nc]
			
			if neighbor is not None and getattr(neighbor, opposite_side) == self.type:
            # this edge is now closed — remove the neighbour's open edge too
				if (neighbor, opposite_side) in self.edges:
					self.edges.remove((neighbor, opposite_side))
			else:
				self.edges.append((tile, direction)) #add open edges

	def add_player(self, player):
		"""
		Adds player to be associated with the structure for scoring

		Takes the player object
		"""
		self.players.append(player)

	#check if new tile belongs in this structure
	def check_structure_compatability(self,  row, col, tile, board):
		"""
		Similar to extend structure but this method only checks if a tile is compatible with
		the structure

		Takes the tile, its location and the current board state
		"""

		connections = []

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
			if neighbor is None or my_edge != self.type or getattr(neighbor, opposite_side) != self.type:
				continue
			for tile1, row1, col1 in self.tiles_used:
				if tile1 is neighbor and row1 == nr and col1 == nc:
					if (neighbor, opposite_side) in self.edges:
						connections.append(direction)
						break
		return connections

	def score_structure(self, unrest, game):
		"""
		This method scores a structure once it is deemed completed
		"""

		if self.type == 3: #Monastary scoring
			if len(self.players) == 0:
				return
			self.players[0].score += 9
			return

		temp_score = 0
		for tile, row, col in self.tiles_used:
			modifier = 1 # for good or bad tiles
			if tile.good_tile == True:
				modifier = 2
				print("tile went good")
			elif tile.bad_tile == True:
				modifier = 0.5
				print("tile went bad")

			if self.type == 1:
				temp_score += 1 * modifier
				continue
			elif self.type == 2:
				if tile.attribute == 1 and unrest == True:
					temp_score += 2 * modifier
				else:
					temp_score += 1
				if tile.attribute == 1 and unrest == False:
					temp_score += 4 * modifier
				else:
					temp_score += 2 * modifier

		for player in self.players:
			player.score += temp_score
			player.ability(self, game)
		pass

	def check_completed(self, board):
		"""
		This method checks if a structure is 
		completed by checking the open edges
		"""

		if self.type == 3: # Checks all surrounding tiles for monastary
			row = self.tiles_used[0][1]
			col = self.tiles_used[0][2]
			all_neighbors = [
				(row - 1, col - 1), (row - 1, col), (row - 1, col + 1),
				(row,   col - 1), (row,   col), (row,   col + 1),
				(row + 1, col - 1), (row + 1, col), (row + 1, col + 1)]
			for nr, nc in all_neighbors:
				if nr < 0 or nr >= len(board) or nc < 0 or nc >= len(board[0]) or board[nr][nc] is None:
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



if __name__ == "__main__":
	#Tests
	p1 = player("red")
	p2 = player("blue")

	game = gameStateClass([p1, p2])

	"""t1 = tile(1, 1, 1, 0, 0, 0)  # road vertical

	game.place_tile(3, 3, t1)
	game.manage_structures(3, 3, t1)
	game.place_meeple(t1, "up")

	printBoard(game)
	print(game.structures)

	t2 = tile(0, 1, 0, 1, 1, 0) # road going up and right
	t3 = tile( 1, 1, 1, 0, 0, 0) # another split road

	game.place_tile(3, 4, t2)
	game.manage_structures(3, 4, t2)

	printBoard(game)
	print(game.structures)

	game.place_tile(4,4, t3)
	game.manage_structures(4, 4, t3)
	game.place_meeple(t3, "up")

	printBoard(game)
	print(game.structures)
	print(p1.score)

	t4 = tile( 1, 1, 1, 0, 0, 0)
	
	game.place_tile(4,5, t4)
	
	game.manage_structures(4, 5, t4)
	

	printBoard(game)
	print(game.structures)
	print(p1.score)
	print(p2.score)


	"""
	t1 = tile(1, 1, 0, 0, 1, 0)
	t3 = tile(1, 0, 0, 0, 0, 0) # tile up end
	t4 = tile(0,1,0,0,0,0) #tile down end

	t5 = tile(0,0,0,0,0,2) #monastary tile
	
	game.place_tile(3, 3, t1)
	game.manage_structures(3, 3, t1)
	game.place_meeple(t1, "up")

	print("Placed first tile")
	printBoard(game)

	game.place_tile(4, 3, t1)
	game.manage_structures(4, 3, t1)

	print("Placed second tile")
	printBoard(game)
	print(game.structures)

	game.place_tile(4, 2, t1)
	game.manage_structures(4, 2, t1)
	

	print("Placed third tile")
	printBoard(game)
	print(game.structures)

	game.place_tile(4, 1, t1)
	game.manage_structures(4, 1, t1)

	print("Placed fourth tile")
	printBoard(game)
	print(game.structures)

	game.place_tile(3, 1, t3)
	game.manage_structures(3, 1, t3)

	print("Placed fifth tile")
	printBoard(game)
	print(game.structures)
	#error here, tile added to wrong structure

	game.place_tile(3, 4, t4)
	game.manage_structures(3, 4, t4)

	

	print("after finishing structure and adding monastry")
	printBoard(game)

	print(game.structures)


	t2 = tile(1, 1, 0, 0, 1, 0)  # road vertical
	game.place_tile(3, 2, t2)

	game.manage_structures(3, 2, t2)

	print("After extending road upward")
	printBoard(game)

	print(game.structures)

	print("Player 1 score is " + str(p1.score))
	print("Player 2 score is " + str(p2.score))
