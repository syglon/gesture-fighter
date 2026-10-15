"""Options menu and saved settings.

The menu opens from the main menu (key O or hold the index finger) and from the pause screen (key O).
It can be used with the hand (move the hand up/down to select, fist = decrease, index finger = increase,
hold an open palm to go back) or with the keyboard (arrows / WASD, Enter, Esc).
Settings are saved to settings.json next to webcam_game.py and loaded on the next start.
"""
import json
import math
from pathlib import Path

import pygame

from . import config as C
from .draw import blit_glow, gesture_icon, panel, scale_color, text
from .gestures import GESTURE_COLOR, Gesture

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"
DIFFS = ["easy", "normal", "hard"]
ROUND_TIMES = [30, 60, 90]
DEFAULTS = dict(music=8, sfx=10, fullscreen=True, difficulty="normal", shake=True, round_time=C.VS_ROUND_TIME)


def load_settings():
    """Saved settings merged over the defaults; anything missing or invalid falls back to its default."""
    s = dict(DEFAULTS)
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return s
    if not isinstance(data, dict):
        return s
    for key in ("music", "sfx"):
        if isinstance(data.get(key), int):
            s[key] = max(0, min(10, data[key]))
    for key in ("fullscreen", "shake"):
        if isinstance(data.get(key), bool):
            s[key] = data[key]
    if data.get("difficulty") in DIFFS:
        s["difficulty"] = data["difficulty"]
    if data.get("round_time") in ROUND_TIMES:
        s["round_time"] = data["round_time"]
    return s


def save_settings(settings):
    try:
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError as e:  # a read-only folder must never stop the game
        print(f"[options] Could not save settings: {e}")


# (key, label) of every row, top to bottom
ROWS = [("music", "Music volume"), ("sfx", "Sound effects volume"), ("fullscreen", "Display"),
        ("difficulty", "Boss difficulty"), ("shake", "Screen shake"), ("round_time", "Versus round time"),
        ("back", "Back")]


class OptionsMenu:
    HOLD_TIME = 1.0  # seconds of open palm to leave the menu

    def __init__(self, game):
        self.game = game
        self.open = False
        self.sel = 0
        self.prev_gesture = Gesture.NONE
        self.hold = 0.0
        self.armed = False
        self.t = 0.0

    @property
    def settings(self):
        return self.game.settings

    # ------------------------------------------------------------------ open / close
    def show(self):
        self.open = True
        self.sel = 0
        self.hold = 0.0
        self.armed = False
        self.t = 0.0
        # a gesture that is still held when the menu opens must not change a setting right away
        self.prev_gesture = self.game.controls[0].gesture if self.game.controls else Gesture.NONE
        self.game.sound.play("blip")

    def close(self):
        self.open = False
        save_settings(self.settings)
        self.game.sound.play("blip")
        # the palm used to close the menu is probably still up: the menu screens must see it released
        # first, or the main menu would start a 1-player game from the same hold
        self.game.armed = set()
        self.game.holds = {}

    # ------------------------------------------------------------------ changing values
    def change(self, row, d):
        key = ROWS[row][0]
        g, s = self.game, self.settings
        if key in ("music", "sfx"):
            s[key] = max(0, min(10, s[key] + d))
            g.apply_settings()
            if key == "sfx":
                g.sound.play("punch")  # let the player hear the new effects volume
        elif key == "fullscreen":
            g.toggle_fullscreen()  # also updates and saves the setting
        elif key == "difficulty":
            s[key] = DIFFS[(DIFFS.index(s[key]) + d) % len(DIFFS)]
            g.apply_settings()
        elif key == "shake":
            s[key] = not s[key]
            g.apply_settings()
            if s[key]:
                g.shake.add(10)  # a small demo shake
        elif key == "round_time":
            s[key] = ROUND_TIMES[(ROUND_TIMES.index(s[key]) + d) % len(ROUND_TIMES)]
        elif key == "back":
            self.close()
            return
        if key not in ("sfx",):
            g.sound.play("blip")
        save_settings(s)

    # ------------------------------------------------------------------ input
    def key(self, k):
        if k in (pygame.K_ESCAPE, pygame.K_o, pygame.K_BACKSPACE):
            self.close()
        elif k in (pygame.K_UP, pygame.K_w):
            self.sel = (self.sel - 1) % len(ROWS)
            self.game.sound.play("blip", 0.5)
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.sel = (self.sel + 1) % len(ROWS)
            self.game.sound.play("blip", 0.5)
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.change(self.sel, -1)
        elif k in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
            self.change(self.sel, +1)

    def update(self, dt, ctrl):
        """Hand control: height selects a row, fist = decrease, index finger = increase, hold palm = back."""
        self.t += dt
        g = ctrl.gesture
        if ctrl.visible and ctrl.y is not None:
            pos = ctrl.y * len(ROWS)  # with hysteresis, so a shaky hand does not jump between rows
            if abs(pos - (self.sel + 0.5)) > 0.75:
                new = max(0, min(len(ROWS) - 1, int(pos)))
                if new != self.sel:
                    self.sel = new
                    self.game.sound.play("blip", 0.4)
        entered = g is not self.prev_gesture
        self.prev_gesture = g
        if entered and g is Gesture.FIST:
            self.change(self.sel, -1)
        elif entered and g is Gesture.POINT:
            self.change(self.sel, +1)
        if not self.open:
            return
        if g is not Gesture.PALM:
            self.armed = True
            self.hold = max(0.0, self.hold - dt * 2)
        elif self.armed:
            self.hold += dt / self.HOLD_TIME
            if self.hold >= 1.0:
                self.close()

    # ------------------------------------------------------------------ drawing
    def value_text(self, key):
        s = self.settings
        if key == "fullscreen":
            return "FULLSCREEN" if self.game.fullscreen else "WINDOW"
        if key == "difficulty":
            return s[key].upper()
        if key == "shake":
            return "ON" if s[key] else "OFF"
        if key == "round_time":
            return f"{s[key]} SECONDS"
        return ""

    def draw(self, surf):
        f = self.game.fonts
        W, H = C.SCREEN_W, C.SCREEN_H
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 175))
        surf.blit(ov, (0, 0))
        r = pygame.Rect(0, 0, 780, 600)
        r.center = (W // 2, H // 2)
        panel(surf, r, color=(16, 12, 30), alpha=240, border=C.C_SHIELD, radius=14, width=3)
        text(surf, f.big, "OPTIONS", (r.centerx, r.y + 46), C.C_SHIELD)

        row_h, y0 = 56, r.y + 96
        for i, (key, label) in enumerate(ROWS):
            rr = pygame.Rect(r.x + 30, y0 + i * row_h, r.w - 60, row_h - 8)
            sel = i == self.sel
            if sel:
                pulse = 0.5 + 0.5 * math.sin(self.t * 6)
                blit_glow(surf, rr.center, 220, scale_color(C.C_SHIELD, 0.12 + 0.08 * pulse))
            panel(surf, rr, color=(40, 32, 70) if sel else (26, 20, 44), alpha=230,
                  border=C.C_SHIELD if sel else (60, 56, 90), radius=8)
            if key == "back":
                text(surf, f.mid, "BACK", rr.center, C.WHITE if sel else (200, 200, 220))
                continue
            text(surf, f.small, label, (rr.x + 18, rr.centery), C.WHITE, "midleft")
            vx = rr.right - 18
            if key in ("music", "sfx"):
                v = self.settings[key]
                text(surf, f.small, f"{v * 10}%", (vx, rr.centery), C.WHITE, "midright")
                for k in range(10):
                    seg = pygame.Rect(vx - 330 + k * 24, rr.centery - 10, 20, 20)
                    col = C.C_SHIELD if k < v else (55, 50, 80)
                    pygame.draw.rect(surf, col, seg, border_radius=4)
            else:
                val = self.value_text(key)
                col = C.C_SPECIAL if sel else (230, 230, 245)
                text(surf, f.small, f"◀  {val}  ▶" if sel else val, (vx, rr.centery), col, "midright")

        # hints: hand gestures and keyboard
        hy = r.bottom - 58
        items = [(None, "hand up/down: select"), (Gesture.FIST, "decrease"), (Gesture.POINT, "increase"),
                 (Gesture.PALM, "hold: back")]
        x = r.x + 40
        for gest, words in items:
            if gest is not None:
                gesture_icon(surf, gest, (x + 12, hy + 2), 24, GESTURE_COLOR[gest])
                x += 30
            img_rect = text(surf, f.tiny, words, (x, hy), (200, 200, 220), "midleft", shadow=False)
            x = img_rect.right + 26
        text(surf, f.tiny, "Keyboard: ↑ ↓ select    ← → change    Enter: change    Esc / O: back",
             (r.centerx, hy + 30), (170, 170, 195), shadow=False)
        if self.hold > 0:
            pygame.draw.rect(surf, C.C_SHIELD, (r.x + 40, r.bottom - 14, int((r.w - 80) * self.hold), 5))
