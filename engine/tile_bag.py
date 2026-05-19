import tile_set
import data
from collections import defaultdict


def create_ID(tile_id):
    return "ID" + str(tile_id)

def find_int(tile_id):
    if isinstance(tile_id, str):
        temp = tile_id.split("ID")
        num_id = int(temp[1])
    else:
        num_id = tile_id
    return num_id

def find_tile_bounds(tile_id):
    tile_num = find_int(tile_id)
    lower = (tile_num // 4) * 4
    upper = lower + 3
    return (lower, upper)

class tile_bag:
    # Constructor for the tile bag, which contains all tiles
    # and several functions to remove, find how many of a specific tile
    # and a testing function to reset the tile bag if needed
    def __init__(self):
        self.tile_bag = tile_set.tile_set.copy()

    ## Function to be able to see what tiles the bag contains totally
    def __str__(self):
        string = ""
        for i in self.tile_bag:
            string += (str(i) + ": " + str(self.tile_bag[i]) + "\n")
        return string
    
    ## Function to reset bag for testing
    def reset_bag(self):
        self.tile_bag = tile_set.tile_set.copy()

    ## Function to remove a tile from the tile bag
    def remove_tile(self, tile_id):
        # Making sure the tile id is usable and correct instance for dict key check
        if isinstance(tile_id, str):
            t_id = tile_id
        else:
            t_id = create_ID(tile_id)

        # As tiles are rotations each tiles has 4 entries
        # need to remove all entries so this function finds the tile bounds
        lower, upper = find_tile_bounds(t_id)

        # Checking the bounds so no error produces from key indexing
        if lower < 0:
            print("Error, tile Id outside range")
            return 1
        elif upper > 335:
            print("Error, tile Id outside range")
            return 1
        
        # Got valid bounds remove the tile from the bag removing all 4 rotations
        for i in range(lower, upper + 1):
            removed = self.tile_bag.pop(create_ID(i), None)
            if removed == None:
                print("Error, trying to remove already removed tile")
                continue  # keep removing remaining rotations — don't leave bag in partial state

    # Function to find a tile given an ID
    def find_tile_id(self, tile_id):
        # Making sure the tile id is usable and correct instance for dict key check
        if isinstance(tile_id, str):
            t_id = tile_id
        else:
            t_id = create_ID(tile_id)
        
        # Get tile details from tile bag
        tile = self.tile_bag.get(t_id, None)

        # Check tile exists
        if tile == None:
            print("Error, trying to find already removed tile")
            return None
        else:
            return tile
    
    def tile_predict(self, side_up, side_down, side_left, side_right):
        # Lists to store tile matches
        matching = []
        match_ind_tiles = []

        # Calculate how many tiles are in the tile bag
        num_tiles = ((len(self.tile_bag) + 1) / 4)
        for i in self.tile_bag:
            # Get tile class information
            tile = self.find_tile_id(i)
            # Prevent None value errors
            if tile == None:
                continue
            # Check tile matches specified attributes
            if tile.up == side_up:
                if tile.down == side_down:
                    if tile.left == side_left:
                        if tile.right == side_right:
                            # Found matching tile to conditions
                            matching.append((i, tile, find_int(i) // 4))

        # Now remove tiles that are just the same rotated piece
        if len(matching) == 0:
            # No matching tiles in bag no probability chance
            return 0
        match_ind_tiles.append(matching[0])
        # Now for each entry check it isn't already stored in the
        # individual tile set list
        for i in matching:
            check = True
            for j in match_ind_tiles:
                if i[2] == j[2]:
                    # Repeat
                    check = False
            if check:
                # No repeats
                match_ind_tiles.append(i)
        # Calculate probability
        chance = (len(match_ind_tiles) / num_tiles) * 100
        # Round for nice viewing
        return (round(chance, 2), len(match_ind_tiles))
    
class empty_bag():

    def __init__(self):
        self.bag = {}
    
    ## Function to be able to see what tiles the bag contains totally
    def __str__(self):
        string = ""
        for i in self.bag:
            string += (str(i) + ": " + str(self.bag[i]) + "\n")
        return string
    
    def add_tile(self, tile_id, tile_coords):
        self.bag[tile_coords] = tile_id

    def check_tiles(self, current_id, predict_id, direction):
        current_tile = tile_set.tile_set.get(current_id)
        predict_tile = tile_set.tile_set.get(predict_id)
        check = False
        if direction == "UP":
            if (current_tile.up == predict_tile.down):
                check = True
        elif direction == "DOWN":
            if (current_tile.down == predict_tile.up):
                check = True
        elif direction == "LEFT":
            if (current_tile.left == predict_tile.right):
                check = True
        elif direction == "RIGHT":
            if (current_tile.right == predict_tile.left):
                check = True
        return check

    def predict_move(self, tile_id):
        bounds = find_tile_bounds(tile_id)
        tiles = []
        for i in range(bounds[0], bounds[1] + 1):
            tiles.append(create_ID(i))
        moves = defaultdict(set)
        for tile in tiles:
            predict_tile = tile_set.tile_set.get(tile)
            for key, value in self.bag.items():
                current_coords = key
                if (self.bag.get((current_coords[0], current_coords[1] + 1))) == None:
                    # UP and empty space
                    if (self.check_tiles(value, tile, "UP") == True):
                        # Tile can be placed above current tile
                        check_up = True
                        predict_coords = (key[0], key[1] + 1)
                        # Checking if a tile is present on the left of predicted tile
                        if (self.bag.get((predict_coords[0] - 1, predict_coords[1]))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0] - 1, predict_coords[1]))
                            if (self.check_tiles(check_tile, tile, "RIGHT") != True):
                                # Tile does not match
                                check_up = False

                        # Checking if a tile is present on the right of predicted tile
                        if (self.bag.get((predict_coords[0] + 1, predict_coords[1]))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0] + 1, predict_coords[1]))
                            if (self.check_tiles(check_tile, tile, "LEFT") != True):
                                # Tile does not match
                                check_up = False
                        
                        # Checking if a tile is present above the predicted tile
                        if (self.bag.get((predict_coords[0], predict_coords[1] + 1))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0], predict_coords[1] + 1))
                            if (self.check_tiles(check_tile, tile, "DOWN") != True):
                                # Tile does not match
                                check_up = False

                        # Check if current tile and surrounding prediction tiles all match
                        if check_up == True:
                            moves[predict_coords].add(tile)

                if (self.bag.get((current_coords[0], current_coords[1] - 1))) == None:
                    # DOWN and empty
                    if (self.check_tiles(value, tile, "DOWN") == True):
                        ## Tile can be placed below current tile
                        check_down = True
                        predict_coords = (key[0], key[1] - 1)
                        # Checking if a tile is present on the left of predicted tile
                        if (self.bag.get((predict_coords[0] - 1, predict_coords[1]))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0] - 1, predict_coords[1]))
                            if (self.check_tiles(check_tile, tile, "RIGHT") != True):
                                # Tile does not match
                                check_down = False
                        # Checking if a tile is present on the right of predicted tile
                        if (self.bag.get((predict_coords[0] + 1, predict_coords[1]))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0] + 1, predict_coords[1]))
                            if (self.check_tiles(check_tile, tile, "LEFT") != True):
                                # Tile does not match
                                check_down = False
                        # Checking if a tile is present below the predicted tile
                        if (self.bag.get((predict_coords[0], predict_coords[1] - 1))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0], predict_coords[1] + 1))
                            if (self.check_tiles(check_tile, tile, "UP") != True):
                                # Tile does not match
                                check_down = False
                        # Check if current tile and surrounding prediction tiles all match
                        if check_down == True:
                            moves[predict_coords].add(tile)

                if (self.bag.get((current_coords[0] - 1, current_coords[1]))) == None:
                    # LEFT and empty
                    if (self.check_tiles(value, tile, "LEFT") == True):
                        ## Tile can be placed to the left of current tile
                        check_left = True
                        predict_coords = (key[0] - 1, key[1])
                        # Checking if a tile is present on the left of predicted tile
                        if (self.bag.get((predict_coords[0] - 1, predict_coords[1]))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0] - 1, predict_coords[1]))
                            if (self.check_tiles(check_tile, tile, "RIGHT") != True):
                                # Tile does not match
                                check_left = False
                        # Checking if a tile is present above the predicted tile
                        if (self.bag.get((predict_coords[0], predict_coords[1] + 1))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0], predict_coords[1] + 1))
                            if (self.check_tiles(check_tile, tile, "DOWN") != True):
                                # Tile does not match
                                check_left = False
                        # Checking if a tile is present below the predicted tile
                        if (self.bag.get((predict_coords[0], predict_coords[1] - 1))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0], predict_coords[1] - 1))
                            if (self.check_tiles(check_tile, tile, "UP") != True):
                                # Tile does not match
                                check_left = False
                        # Check if current tile and surrounding prediction tiles all match
                        if check_left == True:
                            moves[predict_coords].add(tile)
                if (self.bag.get((current_coords[0] + 1, current_coords[1]))) == None:
                    # RIGHT
                    if (self.check_tiles(value, tile, "RIGHT") == True):
                        ## Tile can be placed to the right of current tile
                        check_right = True
                        predict_coords = (key[0] + 1, key[1])
                        # Checking if a tile is present on the right of predicted tile
                        if (self.bag.get((predict_coords[0] + 1, predict_coords[1]))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0] + 1, predict_coords[1]))
                            if (self.check_tiles(check_tile, tile, "LEFT") != True):
                                # Tile does not match
                                check_right = False
                        # Checking if a tile is present above the predicted tile
                        if (self.bag.get((predict_coords[0], predict_coords[1] + 1))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0], predict_coords[1] + 1))
                            if (self.check_tiles(check_tile, tile, "DOWN") != True):
                                # Tile does not match
                                check_right = False
                        # Checking if a tile is present below the predicted tile
                        if (self.bag.get((predict_coords[0], predict_coords[1] - 1))) != None:
                            # Tile exists
                            check_tile = self.bag.get((predict_coords[0], predict_coords[1] - 1))
                            if (self.check_tiles(check_tile, tile, "UP") != True):
                                # Tile does not match
                                check_right = False
                        # Check if current tile and surrounding prediction tiles all match
                        if check_right == True:
                            moves[predict_coords].add(tile)
        return moves


