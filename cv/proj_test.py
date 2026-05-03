import Project_CV
import projector
import threading
import time
import cv2 as cv

def run_projector():
    projector.projector_main()

# TEMP VARIABLES
# Project_CV.grid_origin = (980, 600)
# Project_CV.grid_tile_size = 100

t = threading.Thread(target=run_projector, daemon=True)
t.start()

time.sleep(1)

while True:
    text = input("""S to start, Q is exit, REVERSE # # for reverse, MORE_SCORE # # for more score,
                    INAVLID # # for invalid move, INVALID clear to clear invalid move: """)
    words = text.split()
    if words[0] == "S":
        Project_CV.grid_origin = (980, 600)
        Project_CV.grid_tile_size = 100
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
    elif words[0] == "INVALID":
        if words[1] != "clear":
            print(f"Adding an INVALID move mark at ({words[1]},{words[2]})")
            projector.set_invalid((int(words[1]),int(words[2])))
        else:
            print(f"Clearing INVALID move mark")
            projector.clear_invalid()
    
    