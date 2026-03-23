import cv2 as cv
import numpy as np

# Open Camera for recording
cap = cv.VideoCapture(0)

# Error if no camera connected
if not cap.isOpened():
    print("Error, camera not opened")
    exit()

# While camera recording
while cap.isOpened():
    # Get a frames else exits if an error occurs
    ret, frame = cap.read()
    if not ret:
        print("Camera turned off, exiting")
        break

    # Image processing
    # Greyscale image
    grey_img = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

    # Blur image to remove noise
    blur = cv.GaussianBlur(grey_img, (5, 5), 0)
    
    # Find edges in image
    edges = cv.Canny(blur, 100, 250)

    # Find shapes in image
    contours, tiers = cv.findContours(edges, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)

    # Get largest contours
    large_contours = sorted(contours, key = cv.contourArea, reverse = True)
    final_contours = []
    #print(large_contours)
    # Find shapes in image
    for c in large_contours:
        # Get sides number of each shape, check to make sure real and a square
        sides = cv.approxPolyDP(c, 0.032*cv.arcLength(c, True), True)
        #print(sides)

        if len(sides) == 4:
            # Rectangle or Square
            (x, y, w, h) = cv.boundingRect(sides)
            ar = w / float(h)
            if ar >= 0.9 and ar <= 1.1:
                # Aspect ratio correct - real shape
                final_contours.append(sides)


    # Show all contours
    img_contours = cv.drawContours(frame.copy(), large_contours, -1, (0, 0, 255), 2)

    # Show shapes on image
    img_final = cv.drawContours(frame.copy(), final_contours, -1, (0, 0, 255), 2)

    # Display image
    cv.imshow("Camera", img_final)
    
    # Exit if pressed - exit button
    c = cv.waitKey(10)
    if c == ord('q'):
        break
