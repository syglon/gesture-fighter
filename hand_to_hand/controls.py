"""Girişler: el = joystick + butonlar, klavye ve ikisinin birleşimi.

El kontrolü:
  * Elin kameradaki yatay konumu merkezden sağa/sola -> yürü
  * Eli yukarı kaldır -> zıpla, aşağı indir -> çömel
  * ✊ yumruk yapınca -> yumruk (jab)
  * ✊ yumruğu kameraya doğru / hızla savurunca -> güçlü yumruk
  * ☝ işaret parmağı -> tekme
  * 🖐 açık el (tut) -> blok
  * ✌ iki parmak -> HANDOUKEN (süper bar doluysa SHIN HANDOUKEN)
"""
import time
from collections import deque

import pygame

from gesture_fighter.gestures import Gesture

from . import config as C
from .fighter import Intent

BUTTON_OF = {Gesture.FIST: "punch", Gesture.POINT: "kick", Gesture.PEACE: "special"}


class GestureJoystick:
    def __init__(self, tracker, slot=0, center_x=0.5):
        self.tracker = tracker
        self.slot = slot
        self.center_x = center_x
        self.prev_gesture = Gesture.NONE
        self.was_up = False
        self.history = deque()
        self.last_fid = -1
        self.thrust_cd = 0.0
        # gösterim için
        self.visible = False
        self.zone = (0, 0)     # (yatay, dikey) -1/0/1
        self.gesture = Gesture.NONE
        self.hand = None
        self.thrust_flash = 0.0

    def read(self, dt):
        self.thrust_cd = max(0.0, self.thrust_cd - dt)
        self.thrust_flash = max(0.0, self.thrust_flash - dt)
        _, hands, fid = self.tracker.snapshot()
        h = hands.get(self.slot)
        self.hand = h
        if h is None:
            self.visible = False
            self.prev_gesture = Gesture.NONE
            self.gesture = Gesture.NONE
            self.zone = (0, 0)
            self.was_up = False
            self.history.clear()
            return Intent()
        self.visible = True
        x, y = h.center
        now = time.monotonic()
        if fid != self.last_fid:
            self.last_fid = fid
            self.history.append((now, x, y, h.size))
        while self.history and now - self.history[0][0] > C.THRUST_WINDOW:
            self.history.popleft()

        dx = x - self.center_x
        move = 0 if abs(dx) < C.DEAD_X else (1 if dx > 0 else -1)
        up = y < C.JUMP_Y
        down = y > C.CROUCH_Y
        jump = up and not self.was_up
        self.was_up = up
        self.zone = (move, -1 if up else 1 if down else 0)

        g = h.gesture
        attack = None
        if g is not self.prev_gesture and g in BUTTON_OF:
            attack = BUTTON_OF[g]
        if g is Gesture.FIST and self.thrust_cd <= 0 and self._thrust():
            attack = "heavy"
            self.thrust_cd = C.THRUST_COOLDOWN
            self.thrust_flash = 0.4
            self.history.clear()
        self.prev_gesture = g
        self.gesture = g
        return Intent(move=move, crouch=down, jump=jump, block=g is Gesture.PALM, attack=attack)

    def _thrust(self):
        if len(self.history) < 2:
            return False
        t0, x0, y0, s0 = self.history[0]
        t1, x1, y1, s1 = self.history[-1]
        if t1 - t0 < 0.05:
            return False
        speed = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / (t1 - t0)
        min_size = min(hh[3] for hh in self.history)
        growth = s1 / max(1e-6, min_size)
        return speed > C.THRUST_SPEED or growth > C.THRUST_GROWTH


KEYS_P1 = dict(left=[pygame.K_a], right=[pygame.K_d], up=[pygame.K_w], down=[pygame.K_s],
               punch=[pygame.K_j], heavy=[pygame.K_u], kick=[pygame.K_k], special=[pygame.K_i],
               block=[pygame.K_l])
KEYS_P2 = dict(left=[pygame.K_LEFT], right=[pygame.K_RIGHT], up=[pygame.K_UP], down=[pygame.K_DOWN],
               punch=[pygame.K_KP1, pygame.K_COMMA], heavy=[pygame.K_KP4, pygame.K_m],
               kick=[pygame.K_KP2, pygame.K_PERIOD], special=[pygame.K_KP5, pygame.K_n],
               block=[pygame.K_KP3, pygame.K_SLASH])


class KeyboardFight:
    def __init__(self, keys):
        self.keys = keys
        self.prev = {}

    def read(self, pressed):
        def down(name):
            return any(pressed[k] for k in self.keys[name])

        state = {n: down(n) for n in self.keys}
        edge = {n: state[n] and not self.prev.get(n, False) for n in state}
        self.prev = state
        attack = None
        for b in ("special", "heavy", "kick", "punch"):
            if edge[b]:
                attack = b
                break
        move = (1 if state["right"] else 0) - (1 if state["left"] else 0)
        return Intent(move=move, crouch=state["down"], jump=edge["up"], block=state["block"], attack=attack)


class PlayerInput:
    """El (varsa) + klavye. Klavyede basılan her şey el girişine eklenir."""

    def __init__(self, joystick=None, keys=KEYS_P1):
        self.joystick = joystick
        self.keyboard = KeyboardFight(keys)

    def read(self, dt, pressed, me=None, opp=None, game=None):
        kb = self.keyboard.read(pressed)
        if self.joystick is None:
            return kb
        hd = self.joystick.read(dt)
        return Intent(move=kb.move or hd.move, crouch=kb.crouch or hd.crouch, jump=kb.jump or hd.jump,
                      block=kb.block or hd.block, attack=kb.attack or hd.attack)


class Dummy:
    """Antrenman kuklası: hiçbir şey yapmaz (isteğe bağlı blok)."""

    def __init__(self):
        self.block = False

    def read(self, dt, pressed, me=None, opp=None, game=None):
        return Intent(block=self.block)
