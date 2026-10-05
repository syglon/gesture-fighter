#!/usr/bin/env python3
"""Gesture Fighter — ME461

Kamera el hareketlerinizi algılar, siz de boss'a saldırırsınız:
    ✊ Yumruk        -> PUNCH   (hızlı, hasarı az)
    🖐 Açık el       -> SHIELD  (engeller; tam zamanında açarsan PARRY ile mermiyi geri yollar)
    ☝ İşaret parmağı -> FIRE    (ateş topu, enerji harcar)
    ✌ İki parmak     -> SPECIAL (özel bar doluyken dev ışın)
Elinizi yukarı/aşağı hareket ettirerek karakteri hareket ettirirsiniz.

Çalıştırma:
    .venv/bin/python webcam_game.py
    .venv/bin/python webcam_game.py --camera 1 --difficulty hard --fullscreen
    .venv/bin/python webcam_game.py --keyboard      # kamerasız test
"""
import argparse
import sys

from gesture_fighter.game import main


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Gesture Fighter — camera controlled boss fight (ME461)")
    ap.add_argument("--camera", type=int, default=0, help="kamera indeksi (varsayılan 0)")
    ap.add_argument("--keyboard", action="store_true", help="kamerayı kullanma, sadece klavye")
    ap.add_argument("--difficulty", choices=["easy", "normal", "hard"], default="normal")
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--mute", action="store_true", help="sesleri kapat")
    ap.add_argument("--no-mirror", action="store_true", help="kamera görüntüsünü aynalama")
    ap.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)  # otomatik test için
    return ap.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main(parse_args()))
