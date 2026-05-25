import serial
import cv2
import mediapipe as mp
import time
import math

# ================= CONFIG =================
SERIAL_PORT = '/dev/cu.usbmodem101' #Change this according to system
BAUD_RATE = 115200
debug = False
cam_source = 0

# ================= SERIAL =================
if not debug:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)

# ================= LIMITS =================
x_min, x_max = 0, 180
y_min, y_max = 0, 180
z_min, z_max = 10, 180
wp_min, wp_max = 0, 180
wr_min, wr_max = 0, 180

claw_open = 60
claw_close = 0

fist_threshold = 7

# Initial
servo = [90, 90, 90, 90, 90, claw_open]
prev = servo.copy()

# ================= MEDIAPIPE =================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
cap = cv2.VideoCapture(cam_source)

# ================= HELPERS =================
def clamp(v, mn, mx):
    return max(min(v, mx), mn)

def map_range(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def dist(a, b):
    return ((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)**0.5

# ================= FIST =================
def is_fist(hand, palm):
    WRIST = hand.landmark[0]
    s = 0
    for i in [8,12,16,20]:
        s += dist(WRIST, hand.landmark[i])
    return (s / palm) < fist_threshold

# ================= MAIN MAPPING =================
def get_servo(hand):
    angles = [90]*6

    WRIST = hand.landmark[0]
    INDEX = hand.landmark[5]
    MIDDLE = hand.landmark[9]

    palm = dist(WRIST, INDEX)

    # ===== CLAW =====
    angles[5] = claw_close if is_fist(hand, palm) else claw_open

    # ===== BASE =====
    dx = WRIST.x - INDEX.x
    base = clamp(dx * 300, -90, 90)
    angles[0] = int(map_range(base, -90, 90, x_max, x_min))

    # ===== SHOULDER =====
    y = clamp(WRIST.y, 0.3, 0.9)
    angles[1] = int(map_range(y, 0.3, 0.9, y_max, y_min))

    # ===== ELBOW =====
    palm = clamp(palm, 0.1, 0.3)
    angles[2] = int(map_range(palm, 0.1, 0.3, z_max, z_min))

    # ===== WRIST PITCH =====
    dy = WRIST.y - MIDDLE.y
    pitch = clamp(dy * 300, -90, 90)
    angles[3] = int(map_range(pitch, -90, 90, wp_min, wp_max))

    # ===== WRIST ROLL =====
    dx2 = hand.landmark[17].x - hand.landmark[5].x
    roll = clamp(dx2 * 300, -90, 90)
    angles[4] = int(map_range(roll, -90, 90, wr_min, wr_max))

    return angles

# ================= LOOP =================
with mp_hands.Hands(min_detection_confidence=0.5,
                    min_tracking_confidence=0.5) as hands:

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = hands.process(rgb)

        if res.multi_hand_landmarks:
            hand = res.multi_hand_landmarks[0]
            new = get_servo(hand)

            # smoothing
            for i in range(6):
                servo[i] = int(0.7*prev[i] + 0.3*new[i])

            if servo != prev:
                print("Servo:", servo)

                if not debug:
                    data = ",".join(map(str, servo)) + "\n"
                    ser.write(data.encode())

                prev = servo.copy()

            mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

        cv2.putText(frame, str(servo), (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

        cv2.imshow("6DOF Control", frame)

        if cv2.waitKey(5) & 0xFF == 27:
            break

cap.release()
cv2.destroyAllWindows()