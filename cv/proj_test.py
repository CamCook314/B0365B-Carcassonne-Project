import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cv import Project_CV
from cv import projector
import threading
import time
from textwrap import dedent

def run_projector():
    projector.projector_main()

# TEMP VARIABLES
#Project_CV.grid_origin = (980, 600)
#Project_CV.grid_tile_size = 100

t = threading.Thread(target=run_projector, daemon=True)
t.start()

time.sleep(1)

while True:
    text = input(("""
    S to start, Q is exit
    REVERSE/MORE_SCORE/EVENT/VOLCANO/GOOD_TILE/BAD_TILE # # to set event at (#,#) coord
    BORDER VALID/INVALID/EVENT SET or BORDER VALID/INVALID/EVENT CLEAR for borders
    UNREST {(#,#),(#,#)} to create unrest event and CLEAR UNREST to clear it
    CLEAR REVERSE/MORE_SCORE/EVENT/VOLCANO/GOOD_TILE/BAD_TILE # # to clear event at coord
    VALID [(#,#),(#,#)] to create valid tile placement event and CLEAR VALID to clear it
"""))
    words = text.split(" ")
    if words[0] == "S":
        Project_CV.grid_origin = (980, 600)
        Project_CV.grid_tile_size = 70
    elif words[0] == "Q":
        projector.projector_exit()
        time.sleep(0.5)
        exit()
    elif words[0] == "REVERSE":
        print(f"Adding a Reverse event at ({words[1]},{words[2]})")
        projector.add_img("REVERSE", (int(words[1]), int(words[2])))
    elif words[0] == "MORE_SCORE":
        print(f"Adding a More Score event at ({words[1]},{words[2]})")
        projector.add_img("MORE_SCORE", (int(words[1]), int(words[2])))
    elif words[0] == "BORDER":
        if words[1] == "INVALID":
            if words[2] != "CLEAR":
                print(f"Adding an INVALID move event")
                projector.set_invalid()
            else:
                print(f"Clearing INVALID move mark event")
                projector.clear_invalid()
        elif words[1] == "VALID":
            if words[2] != "CLEAR":
                print(f"Adding an VALID move event")
                projector.set_valid()
            else:
                print(f"Clearing VALID move mark event")
                projector.clear_valid()
        elif words[1] == "EVENT":
            if words[2] != "CLEAR":
                print(f"Adding an EVENT tile event")
                projector.set_event()
            else:
                print(f"Clearing EVENT tile event")
                projector.clear_event()
    elif words[0] == "EVENT":
        projector.add_img("EVENT", (int(words[1]), int(words[2])))
    elif words[0] == "VOLCANO":
        projector.add_img("VOLCANO", (int(words[1]), int(words[2])))
    elif words[0] == "GOOD_TILE":
        projector.add_img("GOOD_TILE", (int(words[1]), int(words[2])))
    elif words[0] == "BAD_TILE":
        projector.add_img("BAD_TILE", (int(words[1]), int(words[2])))
    elif words[0] == "UNREST":
        projector.add_img("UNREST", eval(words[1]))
    elif words[0] == "CLEAR":
        if words[1] != "UNREST":
            projector.del_img(words[1], (int(words[2]), int(words[3])))
        else:
            projector.del_img(words[1], (0,0))
    elif words[0] == "VALID":
        if words[1] != "CLEAR":
            print(f"Adding valid tile locations")
            print(words[1])
            projector.set_proj_valid(eval(words[1]))
        else:
            print(f"Clearing valid tile locations")
            projector.clear_proj_valid()

    time.sleep(0.1)
    
    