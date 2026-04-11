"""
find_cameras.py — List all available camera devices, force 1080p, and save a test frame.

Usage:
    python cv/find_cameras.py
"""

import cv2

for i in range(3):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) if i > 0 else cv2.VideoCapture(i)
    if not cap.isOpened():
        print(f"Camera {i}: not available")
        continue

    # Try to request 1080p
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    ret, frame = cap.read()
    if ret:
        h, w = frame.shape[:2]
        path = f"camera_{i}_frame.jpg"
        cv2.imwrite(path, frame)
        print(f"Camera {i}: actual frame {w}x{h} — saved {path}")
    else:
        print(f"Camera {i}: opened but could not read frame")

    cap.release()
