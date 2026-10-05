#!/usr/bin/env python3
"""HAND TO HAND — Street Fighter tarzı, el hareketleriyle oynanan dövüş oyunu (ME461)

Elin kameradaki konumu joystick gibi çalışır:
    sağa/sola -> yürü, yukarı -> zıpla, aşağı -> çömel
Hareketler butonlar gibi çalışır:
    ✊ yumruk -> jab   ·   ✊ + kameraya doğru savurma -> güçlü yumruk
    ☝ işaret parmağı -> tekme   ·   🖐 açık el -> blok   ·   ✌ iki parmak -> HANDOUKEN

Çalıştırma:
    .venv/bin/python street_game.py
    .venv/bin/python street_game.py --difficulty hard --fullscreen
    .venv/bin/python street_game.py --keyboard
"""
import argparse
import sys

from hand_to_hand.game import main


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="HAND TO HAND — gesture street fighter (ME461)")
    ap.add_argument("--camera", type=int, default=0, help="kamera indeksi (varsayılan 0)")
    ap.add_argument("--keyboard", action="store_true", help="kamerayı kullanma, sadece klavye")
    ap.add_argument("--difficulty", choices=["easy", "normal", "hard"], default="normal", help="CPU zorluğu")
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--mute", action="store_true")
    ap.add_argument("--no-mirror", action="store_true", help="kamera görüntüsünü aynalama")
    ap.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)
    return ap.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main(parse_args()))
