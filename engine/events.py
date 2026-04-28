import random

class Event:

    def __init__(self, coords):
        self.coords = coords
        self.name = self.choose_random_event()

    def choose_random_event(self):
        return random.choice(["extra_turn"])

    def play(self, game):
        if self.name == "extra_turn":
            self.extra_turn_event(game)

    def extra_turn_event(self, game):
        game.extra_turns = True

    def volcano_event(self):
        pass