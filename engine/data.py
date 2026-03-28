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

class game:

	# board is a 2d array of tile objects
	# players is a list of player objects
	def __init__(self, board, players):
        self.players = players