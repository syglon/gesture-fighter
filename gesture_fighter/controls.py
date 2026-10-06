"""Oyuncu girişi soyutlaması: kamera eli, klavye veya ikisi birden.

İki kişilik moda geçişte her oyuncuya ayrı bir controller verilir
(ör. HandController(tracker, slot=0) ve HandController(tracker, slot=1)).
"""
from dataclasses import dataclass

import pygame

from . import config as C
from .gestures import Gesture


@dataclass
class ControlState:
    gesture: Gesture = Gesture.NONE
    y: float | None = None       # 0 (üst) .. 1 (alt), None = konumu değiştirme
    visible: bool = False        # kamera eli görüyor mu


def _remap(v, lo, hi):
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


class HandController:
    def __init__(self, tracker, slot=0):
        self.tracker = tracker
        self.slot = slot

    def read(self, dt, keys):
        _, hands, _ = self.tracker.snapshot()
        h = hands.get(self.slot)
        if h is None:
            return ControlState()
        return ControlState(h.gesture, _remap(h.center[1], C.HAND_Y_MIN, C.HAND_Y_MAX), True)


KEYMAP_P1 = {
    "gestures": {
        Gesture.FIST: (pygame.K_1, pygame.K_j),
        Gesture.PALM: (pygame.K_2, pygame.K_k),
        Gesture.POINT: (pygame.K_3, pygame.K_l),
        Gesture.PEACE: (pygame.K_4, pygame.K_SEMICOLON),
    },
    "up": (pygame.K_w, pygame.K_UP),
    "down": (pygame.K_s, pygame.K_DOWN),
}


# İki kişilik modda klavye (kamerasız test için): P1 soldaki oyuncu, P2 sağdaki
KEYMAP_VS_P1 = {
    "gestures": {Gesture.FIST: (pygame.K_1,), Gesture.PALM: (pygame.K_2,),
                 Gesture.POINT: (pygame.K_3,), Gesture.PEACE: (pygame.K_4,)},
    "up": (pygame.K_w,),
    "down": (pygame.K_s,),
}
KEYMAP_VS_P2 = {
    "gestures": {Gesture.FIST: (pygame.K_7, pygame.K_KP1), Gesture.PALM: (pygame.K_8, pygame.K_KP2),
                 Gesture.POINT: (pygame.K_9, pygame.K_KP3), Gesture.PEACE: (pygame.K_0, pygame.K_KP4)},
    "up": (pygame.K_UP,),
    "down": (pygame.K_DOWN,),
}


class KeyboardController:
    """Kamera olmadan test/yedek: tuşa basılı tutmak = hareketi tutmak."""

    SPEED = 1.5  # normalize birim / sn

    def __init__(self, keymap=KEYMAP_P1):
        self.keymap = keymap
        self.y = 0.5
        self.active = False

    def read(self, dt, keys):
        gesture = Gesture.NONE
        for g, codes in self.keymap["gestures"].items():
            if any(keys[k] for k in codes):
                gesture = g
                break
        moved = False
        if any(keys[k] for k in self.keymap["up"]):
            self.y -= self.SPEED * dt
            moved = True
        if any(keys[k] for k in self.keymap["down"]):
            self.y += self.SPEED * dt
            moved = True
        self.y = max(0.0, min(1.0, self.y))
        self.active = moved or gesture is not Gesture.NONE
        return ControlState(gesture, self.y if moved else None, False)


class CombinedController:
    """Kamera eli varsa onu kullanır; klavyeye basılırsa klavye öncelikli olur."""

    def __init__(self, hand=None, keyboard=None):
        self.hand = hand
        self.keyboard = keyboard or KeyboardController()

    def read(self, dt, keys):
        kb = self.keyboard.read(dt, keys)
        hs = self.hand.read(dt, keys) if self.hand else ControlState()
        gesture = kb.gesture if kb.gesture is not Gesture.NONE else hs.gesture
        if kb.y is not None:
            y = kb.y
        else:
            y = hs.y
            if y is not None:
                self.keyboard.y = y  # klavyeye geçildiğinde zıplama olmasın
        return ControlState(gesture, y, hs.visible)
