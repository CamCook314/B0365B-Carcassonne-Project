import random

class Event:

    def __init__(self, coords):
        self.coords = coords
        self.name = self.choose_random_event()
        self.active = False
        self.turn = 0

    def choose_random_event(self):
        return random.choice(["extra_turn"])

    def play(self, game):
        if self.name == "extra_turn":
            self.extra_turn_event(game)

    def extra_turn_event(self, game):
        game.extra_turn = True

    def volcano_event(self, game): #gives 5 turns for players to have to fully surround the event tile other wise all meeples deleted
        self.turn = game.current_turn
        self.active = True

    def check_volcano(self, game): # runs every turn
        all_neighbors = [
					(self.coords[0] - 1, self.coords[1] - 1), (self.coords[0] - 1, self.coords[1]), (self.coords[0]- 1, self.coords[1] + 1),
					(self.coords[0],   self.coords[1] - 1), (self.coords[0],   self.coords[1]), (self.coords[0],   self.coords[1] + 1),
					(self.coords[0] + 1, self.coords[1] - 1), (self.coords[0] + 1, self.coords[1]), (self.coords[0] + 1, self.coords[1] + 1)]
        if game.turnNum >= self.start_turn + 5:
            for nr, nc in all_neighbors:
                if game.board[nr][nc] is None:
                    for i in game.structures: #destroy if finds empty neighbour
                        i.players = [] #empty players list
                    for j in game.players:
                        j.meeples = 7 #reset everybodys meeple counts
                    self.active = False

    def __repr__(self):
        return f"Event {self.name} placed at {self.coords}"