#!/usr/bin/env python3
"""Gesture Fighter — ME461

Kamera el hareketlerinizi algılar, siz de boss'a saldırırsınız:
    ✊ Yumruk        -> PUNCH   (hızlı, hasarı az)
    🖐 Açık el       -> SHIELD  (engeller; tam zamanında açarsan PARRY ile mermiyi geri yollar)
    ☝ İşaret parmağı -> FIRE    (ateş topu, enerji harcar)
    ✌ İki parmak     -> SPECIAL (özel bar doluyken dev ışın)
    🤟 İşaret + serçe -> MIRROR  (sadece versus: rakibin mermilerini yansıtan ayna)
Elinizi yukarı/aşağı hareket ettirerek karakteri hareket ettirirsiniz.

Çalıştırma:
    .venv/bin/python webcam_game.py
    .venv/bin/python webcam_game.py --camera 1 --difficulty hard --fullscreen
    .venv/bin/python webcam_game.py --keyboard      # kamerasız test
    .venv/bin/python webcam_game.py --versus        # iki kişilik kapışma (kamera ikiye bölünür)
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
    ap.add_argument("--fullscreen", action="store_true", help="start in fullscreen")
    ap.add_argument("--mute", action="store_true", help="no sound or music")
    ap.add_argument("--no-mirror", action="store_true", help="do not mirror the camera image")
    ap.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)  # otomatik test için
    return ap.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main(parse_args()))
