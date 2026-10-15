#!/usr/bin/env python3
"""Gesture Fighter — ME461 (team Bad Bots)

The camera detects your hand gestures and you fight with them:
    ✊ Fist            -> PUNCH   (fast, low damage)
    🖐 Open palm       -> SHIELD  (blocks; raised just in time it PARRIES the shot back)
    ☝ Index finger    -> FIRE    (fireball, costs energy)
    ✌ Two fingers     -> SPECIAL (huge beam when the special bar is full)
    🤟 Index + little  -> MIRROR  (versus only: a mirror that reflects the opponent's shots)
Move your hand up and down to move your fighter.

Running:
    .venv/bin/python webcam_game.py
    .venv/bin/python webcam_game.py --camera 1 --difficulty hard --windowed
    .venv/bin/python webcam_game.py --keyboard      # test without a camera
    .venv/bin/python webcam_game.py --versus        # two-player match (the camera image is split in half)
"""
import argparse
import sys

from gesture_fighter.game import main


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Gesture Fighter — a fighting game controlled by hand gestures (ME461)")
    ap.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    ap.add_argument("--keyboard", action="store_true", help="do not use the camera, keyboard only")
    ap.add_argument("--difficulty", choices=["easy", "normal", "hard"], default="normal", help="boss difficulty")
    ap.add_argument("--versus", action="store_true", help="start a 2-player versus match directly")
    ap.add_argument("--windowed", action="store_true", help="start in a window instead of fullscreen (F toggles it)")
    ap.add_argument("--mute", action="store_true", help="no sound or music")
    ap.add_argument("--no-mirror", action="store_true", help="do not mirror the camera image")
    ap.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)  # for automated tests
    return ap.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main(parse_args()))
