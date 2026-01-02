import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time
from collections import deque

pyautogui.FAILSAFE = True

# Camera & screen
cam = cv2.VideoCapture(0)
cam_w, cam_h = 640, 480
cam.set(3, cam_w)
cam.set(4, cam_h)
screen_w, screen_h = pyautogui.size()

# Nose control area (visual box)
track_w, track_h = 300, 200
track_x_start = (cam_w - track_w) // 2
track_y_start = (cam_h - track_h) // 2

cursor_history = deque(maxlen=5)

# Blink detection (left eye)
STATIC_BASELINE_FRAMES = 30
baseline_buffer_left = deque(maxlen=STATIC_BASELINE_FRAMES)
adaptive_factor = 0.75
min_ear_threshold = 0.15

blink_cooldown = 1.0
last_click_time = 0

CONSEC_FRAMES_TO_BLINK = 3
left_eye_blink_counter = 0

DEBUG = True

mp_face = mp.solutions.face_mesh
face_mesh = mp_face.FaceMesh(refine_landmarks=False)

LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]

def calculate_EAR(eye_landmarks):
    A = np.linalg.norm(np.array([eye_landmarks[1].x, eye_landmarks[1].y]) -
                       np.array([eye_landmarks[5].x, eye_landmarks[5].y]))
    B = np.linalg.norm(np.array([eye_landmarks[2].x, eye_landmarks[2].y]) -
                       np.array([eye_landmarks[4].x, eye_landmarks[4].y]))
    C = np.linalg.norm(np.array([eye_landmarks[0].x, eye_landmarks[0].y]) -
                       np.array([eye_landmarks[3].x, eye_landmarks[3].y]))
    if C == 0:
        return 0.0
    return (A + B) / (2.0 * C)

def adaptive_threshold(buffer):
    if len(buffer) == 0:
        return 0.2
    baseline = np.mean(buffer)
    return max(min_ear_threshold, adaptive_factor * baseline)

warmup_done = False
warmup_frames = 0

while True:
    ret, frame = cam.read()
    if not ret:
        break
    frame = cv2.flip(frame, 1)
    frame_h, frame_w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)

    # Draw the visual box
    cv2.rectangle(frame, (track_x_start, track_y_start),
                  (track_x_start + track_w, track_y_start + track_h),
                  (0, 255, 255), 2)

    if results.multi_face_landmarks:
        landmarks = results.multi_face_landmarks[0].landmark

        # Nose position
        nose = landmarks[1]
        nose_x = int(nose.x * frame_w)
        nose_y = int(nose.y * frame_h)

        # Only update cursor if nose is inside the control box
        if (track_x_start <= nose_x <= track_x_start + track_w) and \
           (track_y_start <= nose_y <= track_y_start + track_h):
            # Map nose within box → entire screen
            screen_x = int(np.interp(nose_x,
                                     [track_x_start, track_x_start + track_w],
                                     [0, screen_w]))
            screen_y = int(np.interp(nose_y,
                                     [track_y_start, track_y_start + track_h],
                                     [0, screen_h]))

            # Clamp values just in case
            screen_x = int(np.clip(screen_x, 0, screen_w - 1))
            screen_y = int(np.clip(screen_y, 0, screen_h - 1))

            # Smooth cursor movement
            cursor_history.append((screen_x, screen_y))
            avg_x = int(np.mean([c[0] for c in cursor_history]))
            avg_y = int(np.mean([c[1] for c in cursor_history]))
            pyautogui.moveTo(avg_x, avg_y)

        # Draw nose point
        cv2.circle(frame, (nose_x, nose_y), 5, (0, 255, 0), -1)

        # Blink detection (left eye) — unaffected by box boundaries
        left_eye_landmarks = [landmarks[i] for i in LEFT_EYE_IDX]
        left_ear = calculate_EAR(left_eye_landmarks)

        current_time = time.time()

        if not warmup_done:
            baseline_buffer_left.append(left_ear)
            warmup_frames += 1
            cv2.putText(frame, f"Calibrating {warmup_frames}/{STATIC_BASELINE_FRAMES}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 165, 0), 2)
            if warmup_frames >= STATIC_BASELINE_FRAMES:
                warmup_done = True
                if DEBUG:
                    print("Calibration done. Left baseline:", np.mean(baseline_buffer_left))
        else:
            left_thr = adaptive_threshold(baseline_buffer_left)

            if left_ear < left_thr:
                left_eye_blink_counter += 1
            else:
                left_eye_blink_counter = 0

            if left_eye_blink_counter >= CONSEC_FRAMES_TO_BLINK and (current_time - last_click_time) > blink_cooldown:
                pyautogui.click(button='left')
                last_click_time = current_time
                left_eye_blink_counter = 0
                if DEBUG:
                    print("Left eye blink — click:", time.strftime("%H:%M:%S"))
                    cv2.putText(frame, "Blink CLICK", (10, 120),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            if DEBUG:
                cv2.putText(frame, f"EAR: {left_ear:.3f} Thr: {left_thr:.3f}", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 0), 2)
                cv2.putText(frame, f"Cnt: {left_eye_blink_counter}", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 2)

    else:
        cv2.putText(frame, "No face detected", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.imshow("Eye Controlled Mouse", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cam.release()
cv2.destroyAllWindows()
