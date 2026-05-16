import random
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from cv import projector

# Note: To add a new event:
'''
1. Add its name to the list in choose_random_event() so the spawner can pick it.
2. Add an `elif self.name == "<name>": self.<name>_event(game)` branch in play().
3. Define <name>_event(self, game) — set any flags on `game` your effect needs
(add new fields to gameStateClass.__init__ in data.py if needed).
4. If it has a duration, define check_<name>(self, game) and call it from
gameStateClass.next_player() each turn.
5. Have it in the UI by editing build_active_events() in api.py, append
a {"name", "description", "player_index"?} dict when your flag is active.
'''
class Event:

    def __init__(self, coords):
        self.coords = coords
        self.name = self.choose_random_event()
        self.active = False
        self.turn = 0

    def choose_random_event(self):
        return random.choice(["extra turn", "volcano", "unrest"]) #random event pool

    def play(self, game):
        if self.name == "extra turn":
            self.extra_turn_event(game)
        elif self.name == "volcano":
            self.volcano_event(game)
        elif self.name == "unrest":
            self.unrest_event(game)

    def extra_turn_event(self, game):
        self.name = "extra turn"
        game.extra_turn = True

    def volcano_event(self, game): #gives 8 turns for players to have to fully surround the event tile other wise all meeples deleted
        self.name = "volcano"
        self.turn = game.current_turn
        self.active = True
        projector.add_img("VOLCANO", (self.coords[0], self.coords[1]))


    def volcano_check(self, game): # runs every turn
        if game.current_turn < self.turn + 8: #change this for more or less turns
            return

        arr_r, arr_c = game.to_array_index(self.coords[0], self.coords[1])
        fully_surrounded = True
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = arr_r + dr, arr_c + dc
                if nr < 0 or nr >= len(game.board):
                    fully_surrounded = False
                    break
                if nc < 0 or nc >= len(game.board[0]):
                    fully_surrounded = False
                    break
                if game.board[nr][nc] is None:
                    fully_surrounded = False
                    break
            if not fully_surrounded:
                break

        if not fully_surrounded:
            for i in game.structures: #destroy if finds empty neighbour
                i.players = [] #empty players list
            for j in game.players:
                j.meeples = 7 #reset everybodys meeple counts

        self.active = False
        projector.del_img("VOLCANO", (self.coords[0], self.coords[1]))

    def unrest_event(self, game): #all cities score half points for next 4 turns
        self.name = "unrest"
        self.turn = game.current_turn
        self.active = True
        game.unrestCheck = True
        projector.add_img("UNREST", (self.coords[0], self.coords[1]))


    def unrest_check(self, game):
        if game.current_turn >= self.turn + 4: # change this to chance turns
            game.unrestCheck = False
            self.active = False
            projector.del_img("UNREST", (self.coords[0], self.coords[1]))

    def __repr__(self):
        return f"Event {self.name} placed at {self.coords}"