import cv2
from cvzone.HandTrackingModule import HandDetector
import mouse
import numpy as np
import threading
import time
import pyautogui  # for screen size

# Detect screen resolution dynamically
screen_w, screen_h = pyautogui.size()

# Initialize camera
hands = HandDetector(detectionCon=0.8, maxHands=1)
cap = cv2.VideoCapture(0)
cam_w, cam_h = 640, 480
cap.set(3, cam_w)
cap.set(4, cam_h)

# Fix OpenCV window size once (before loop)
cv2.namedWindow("Camera Feed", cv2.WINDOW_AUTOSIZE)
cv2.resizeWindow("Camera Feed", cam_w, cam_h)

# Frame and click delay setup
frameR = 100
l_delay = 0
r_delay = 0
double_delay = 0

# Delay reset functions
def l_clk_delay():
    global l_delay, l_clk_thread
    time.sleep(1)
    l_delay = 0
    l_clk_thread = threading.Thread(target=l_clk_delay)

def r_clk_delay():
    global r_delay, r_clk_thread
    time.sleep(1)
    r_delay = 0
    r_clk_thread = threading.Thread(target=r_clk_delay)

def double_clk_delay():
    global double_delay, double_clk_thread
    time.sleep(2)
    double_delay = 0
    double_clk_thread = threading.Thread(target=double_clk_delay)

l_clk_thread = threading.Thread(target=l_clk_delay)
r_clk_thread = threading.Thread(target=r_clk_delay)
double_clk_thread = threading.Thread(target=double_clk_delay)

prev_x, prev_y = 0, 0
smoothening = 5

while True:
    success, frame = cap.read()
    frame = cv2.flip(frame, 1)
    detector, frame = hands.findHands(frame, flipType=False)

    cv2.rectangle(frame, (frameR, frameR), (cam_w - frameR, cam_h - frameR), (255, 0, 255), 2)

    if detector:
        lmlist = detector[0]['lmList']
        ind_x, ind_y = lmlist[8][0], lmlist[8][1]
        mid_x, mid_y = lmlist[12][0], lmlist[12][1]
        cv2.circle(frame, (ind_x, ind_y), 5, (0, 255, 0), 2)

        fingers = hands.fingersUp(detector[0])

        # mouse movement
        if fingers[1] == 1 and fingers[2] == 0 and fingers[0] == 1:
            curr_x = int(np.interp(ind_x, (frameR, cam_w - frameR), (0, screen_w)))
            curr_y = int(np.interp(ind_y, (frameR, cam_h - frameR), (0, screen_h)))

            final_x = prev_x + (curr_x - prev_x) / smoothening
            final_y = prev_y + (curr_y - prev_y) / smoothening

            mouse.move(int(final_x), int(final_y))
            prev_x, prev_y = final_x, final_y

        # Mouse Button Clicks
        if fingers[1] == 1 and fingers[2] == 1 and fingers[0] == 1:
            if abs(ind_x - mid_x) < 25:
                if fingers[4] == 0 and l_delay == 0:
                    mouse.click(button="left")
                    l_delay = 1
                    l_clk_thread.start()

                if fingers[4] == 1 and r_delay == 0:
                    mouse.click(button="right")
                    r_delay = 1
                    r_clk_thread.start()

        # Mouse Scrolling
        if fingers[1] == 1 and fingers[2] == 1 and fingers[0] == 0 and fingers[4] == 0:
            if abs(ind_x - mid_x) < 25:
                mouse.wheel(delta=-1)
        if fingers[1] == 1 and fingers[2] == 1 and fingers[0] == 0 and fingers[4] == 1:
            if abs(ind_x - mid_x) < 25:
                mouse.wheel(delta=1)

        # Double Mouse Click
        if fingers[1] == 1 and fingers[2] == 0 and fingers[0] == 0 and fingers[4] == 0:
            mouse.double_click(button="left")

        # Screenshot feature
        if fingers == [0, 0, 0, 0, 0]:
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            pyautogui.screenshot(f"screenshot_{timestamp}.png")
            cv2.putText(frame, "Screenshot Taken", (200, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
            time.sleep(1)

    cv2.imshow("Camera Feed", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
