import tile_set
import data


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
            return
        elif upper > 335:
            print("Error, tile Id outside range")
            return
        
        # Got valid bounds remove the tile from the bag removing all 4 rotations
        for i in range(lower, upper + 1):
            removed = self.tile_bag.pop(create_ID(i), None)
            if removed == None:
                # Handle for error, shouldn't reach here unless
                # AI model breaks
                print("Error, trying to remove already removed tile")
                return

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
        return round(chance, 2)