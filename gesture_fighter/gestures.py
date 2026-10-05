"""El iskeletinden (21 MediaPipe noktası) hareket sınıflandırma.

Her parmak için iki ölçüt kullanılır:
  * bilek→uç mesafesi / bilek→PIP mesafesi oranı (açık parmakta > 1)
  * PIP eklemindeki bükülme açısı (açık parmakta küçük)
Bu iki ölçüt elin dönmesinden ve kameraya uzaklığından büyük ölçüde bağımsızdır.
"""
import math
from collections import Counter, deque
from enum import Enum

from . import config as C


class Gesture(Enum):
    NONE = 0
    FIST = 1   # ✊ Punch
    PALM = 2   # 🖐 Shield
    POINT = 3  # ☝ Fire
    PEACE = 4  # ✌ Special


GESTURE_ACTION = {
    Gesture.NONE: "-",
    Gesture.FIST: "PUNCH",
    Gesture.PALM: "SHIELD",
    Gesture.POINT: "FIRE",
    Gesture.PEACE: "SPECIAL",
}

GESTURE_HAND = {
    Gesture.NONE: "?",
    Gesture.FIST: "Fist",
    Gesture.PALM: "Open palm",
    Gesture.POINT: "Index finger",
    Gesture.PEACE: "Two fingers",
}

GESTURE_COLOR = {
    Gesture.NONE: (150, 150, 170),
    Gesture.FIST: C.C_PUNCH,
    Gesture.PALM: C.C_SHIELD,
    Gesture.POINT: C.C_FIRE,
    Gesture.PEACE: C.C_SPECIAL,
}

# MediaPipe el topolojisi (çizim için)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]

WRIST = 0
# (MCP, PIP, TIP) — işaret, orta, yüzük, serçe
FINGERS = [(5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)]

EXTEND_RATIO = 1.10
EXTEND_MAX_BEND = 70.0  # derece


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _dist(a, b):
    return _norm(_sub(a, b))


def _angle(u, v):
    nu, nv = _norm(u), _norm(v)
    if nu < 1e-9 or nv < 1e-9:
        return 0.0
    c = (u[0] * v[0] + u[1] * v[1] + u[2] * v[2]) / (nu * nv)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def finger_states(pts):
    """pts: 21 adet (x, y, z), eksenleri aynı ölçekte. 4 parmak için açık/kapalı listesi döner."""
    wrist = pts[WRIST]
    states = []
    for mcp, pip, tip in FINGERS:
        ratio = _dist(wrist, pts[tip]) / max(_dist(wrist, pts[pip]), 1e-6)
        bend = _angle(_sub(pts[pip], pts[mcp]), _sub(pts[tip], pts[pip]))
        states.append(ratio > EXTEND_RATIO and bend < EXTEND_MAX_BEND)
    return states


def classify(pts):
    """21 noktadan Gesture döndürür. Başparmak bilerek yok sayılır (en gürültülü parmak)."""
    index, middle, ring, pinky = finger_states(pts)
    n = index + middle + ring + pinky
    if n == 0:
        return Gesture.FIST
    if n == 4 or (n == 3 and pinky):
        return Gesture.PALM
    if index and not middle and not ring and not pinky:
        return Gesture.POINT
    if index and middle and not ring and not pinky:
        return Gesture.PEACE
    return Gesture.NONE


class GestureFilter:
    """Titremeyi önlemek için çoğunluk oylaması yapan küçük filtre."""

    def __init__(self, window=C.GESTURE_WINDOW, required=C.GESTURE_REQUIRED):
        self.history = deque(maxlen=window)
        self.required = required
        self.stable = Gesture.NONE

    def update(self, gesture):
        self.history.append(gesture)
        best, count = Counter(self.history).most_common(1)[0]
        if count >= self.required:
            self.stable = best
        return self.stable

    def reset(self):
        self.history.clear()
        self.stable = Gesture.NONE
