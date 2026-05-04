import Project_CV
import projector
import threading
import time

def run_projector():
    projector.projector_main()

# TEMP VARIABLES
#Project_CV.grid_origin = (980, 600)
#Project_CV.grid_tile_size = 100

t = threading.Thread(target=run_projector, daemon=True)
t.start()

time.sleep(1)

while True:
    text = input("""S to start, Q is exit, REVERSE # # for reverse, MORE_SCORE # # for more score,
                    INAVLID set for invalid move, INVALID clear to clear invalid move: """)
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
    elif words[0] == "INVALID":
        if words[1] != "clear":
            print(f"Adding an INVALID move event")
            projector.set_invalid()
        else:
            print(f"Clearing INVALID move mark event")
            projector.clear_invalid()
    elif words[0] == "EVENT":
        projector.add_img("EVENT", (int(words[1]), int(words[2])))
    elif words[0] == "VOLCANO":
        projector.add_img("VOLCANO", (int(words[1]), int(words[2])))
    elif words[0] == "CLEAR":
        projector.del_img(words[1], (int(words[2]), int(words[3])))
    elif words[0] == "VALID":
        if words[1] != "clear":
            print(f"Adding valid tile locations")
            print(words[1])
            projector.set_proj_valid(eval(words[1]))
        else:
            print(f"Clearing valid tile locations")
            projector.clear_proj_valid()

    time.sleep(0.1)
    
    