"""Kamera + MediaPipe HandLandmarker'ı ayrı bir thread'de çalıştırır.

Oyun döngüsü 60 FPS'te akarken el algılama ~20-30 FPS'te arka planda çalışır;
oyun her karede sadece en son sonucu okur (snapshot), böylece oyun takılmaz.

Slot mantığı:
  * split=False (tek oyuncu): kameradaki en büyük (en yakın) el -> slot 0
  * split=True  (iki oyuncu): görüntünün sol yarısındaki el -> slot 0, sağ yarısı -> slot 1
"""
import os
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

# mediapipe, tensorflow'u sadece doküman üretimi için opsiyonel olarak import ediyor.
# Sistemde numpy 2 ile uyumsuz eski bir tensorflow kuruluysa bu import çöküyor;
# tensorflow'u gizleyince mediapipe kendi yedek yoluna (ModuleNotFoundError) düşüyor.
if "tensorflow" not in sys.modules:
    sys.modules["tensorflow"] = None

import cv2  # noqa: E402

from . import config as C  # noqa: E402
from .gestures import Gesture, GestureFilter, classify, finger_states  # noqa: E402

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"

# El bu kadar algılama karesi boyunca görülmezse "kayıp" sayılır
LOST_AFTER = 4


@dataclass
class HandInfo:
    gesture: Gesture       # filtrelenmiş (kararlı) hareket
    raw: Gesture           # bu karedeki ham sınıflandırma
    points: list           # 21 adet normalize (x, y) — çizim için
    center: tuple          # avuç merkezi, normalize (x, y)
    size: float            # elin görüntüdeki boyutu (yakınlık ölçüsü)
    fingers: tuple         # (işaret, orta, yüzük, serçe) açık mı


def ensure_model():
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_000_000:
        return MODEL_PATH
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"[tracker] El modeli indiriliyor: {MODEL_URL}")
    tmp = MODEL_PATH.with_suffix(".part")
    urllib.request.urlretrieve(MODEL_URL, tmp)
    tmp.replace(MODEL_PATH)
    return MODEL_PATH


class HandTracker:
    def __init__(self, camera_index=0, split=False, mirror=True, max_hands=2):
        self.camera_index = camera_index
        self.split = split
        self.mirror = mirror
        self.max_hands = max_hands

        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._cap = None
        self._landmarker = None

        self._frame = None
        self._frame_id = 0
        self._hands = {}
        # Her zaman 2 slot ayrılır; split ayarı oyun sırasında set_split() ile değişebilir
        self._filters = [GestureFilter() for _ in range(2)]
        self._last_seen = [None] * 2
        self._lost = [LOST_AFTER] * 2
        self.fps = 0.0
        self.error = None

    # ------------------------------------------------------------------
    def start(self):
        """Kamerayı ve modeli açar. (başarılı_mı, mesaj) döndürür."""
        try:
            from mediapipe.tasks.python import BaseOptions, vision
        except Exception as e:  # pragma: no cover
            return False, f"mediapipe yüklenemedi: {e}"
        try:
            model = ensure_model()
        except Exception as e:
            return False, f"El modeli indirilemedi: {e}"

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            return False, f"Kamera {self.camera_index} açılamadı"
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, C.CAMERA_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, C.CAMERA_H)
        ok, _ = cap.read()
        if not ok:
            cap.release()
            return False, f"Kamera {self.camera_index} görüntü vermiyor"

        opts = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=self.max_hands,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(opts)
        self._cap = cap
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="HandTracker", daemon=True)
        self._thread.start()
        return True, "Kamera hazır"

    @property
    def slots(self):
        return 2 if self.split else 1

    def set_split(self, split):
        """Tek oyuncu (en büyük el) / iki oyuncu (sol-sağ yarı) modları arasında geçiş."""
        with self._lock:
            self.split = split
            for f in self._filters:
                f.reset()
            self._last_seen = [None] * 2
            self._lost = [LOST_AFTER] * 2
            self._hands = {}

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._cap is not None:
            self._cap.release()
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass

    def snapshot(self):
        """(önizleme_rgb, {slot: HandInfo}, frame_id) döndürür."""
        with self._lock:
            return self._frame, dict(self._hands), self._frame_id

    # ------------------------------------------------------------------
    def _loop(self):
        import mediapipe as mp

        t0 = time.monotonic()
        last_ts = -1
        fps_t, fps_n = time.monotonic(), 0
        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            if self.mirror:
                frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            ts = int((time.monotonic() - t0) * 1000)
            if ts <= last_ts:
                ts = last_ts + 1
            last_ts = ts
            try:
                result = self._landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
            except Exception as e:  # pragma: no cover
                self.error = str(e)
                continue

            detected = [self._parse(lms, w / h) for lms in result.hand_landmarks]
            hands = self._assign(detected)
            preview = cv2.resize(rgb, (C.PREVIEW_W, C.PREVIEW_H), interpolation=cv2.INTER_AREA)

            fps_n += 1
            now = time.monotonic()
            if now - fps_t >= 0.5:
                self.fps = fps_n / (now - fps_t)
                fps_t, fps_n = now, 0

            with self._lock:
                self._frame = preview
                self._hands = hands
                self._frame_id += 1

    @staticmethod
    def _parse(lms, aspect):
        # Mesafe/açı hesabı için eksenleri aynı ölçeğe getir (x ve z, genişliğe göre normalize)
        pts3 = [(p.x * aspect, p.y, p.z * aspect) for p in lms]
        pts2 = [(p.x, p.y) for p in lms]
        raw = classify(pts3)
        fingers = tuple(finger_states(pts3))
        cx = (pts2[0][0] + pts2[5][0] + pts2[9][0] + pts2[17][0]) / 4
        cy = (pts2[0][1] + pts2[5][1] + pts2[9][1] + pts2[17][1]) / 4
        size = ((pts3[0][0] - pts3[9][0]) ** 2 + (pts3[0][1] - pts3[9][1]) ** 2) ** 0.5
        return raw, pts2, (cx, cy), size, fingers

    def _assign(self, detected):
        per_slot = [None] * self.slots
        if self.split:
            for d in detected:
                slot = 0 if d[2][0] < 0.5 else 1
                if per_slot[slot] is None or d[3] > per_slot[slot][3]:
                    per_slot[slot] = d
        elif detected:
            per_slot[0] = max(detected, key=lambda d: d[3])

        hands = {}
        for slot in range(self.slots):
            d = per_slot[slot]
            filt = self._filters[slot]
            if d is not None:
                raw, pts, center, size, fingers = d
                stable = filt.update(raw)
                info = HandInfo(stable, raw, pts, center, size, fingers)
                self._last_seen[slot] = info
                self._lost[slot] = 0
                hands[slot] = info
            else:
                self._lost[slot] += 1
                if self._lost[slot] < LOST_AFTER and self._last_seen[slot] is not None:
                    # Kısa kayıplarda son bilinen eli koru (titremeyi önler)
                    hands[slot] = self._last_seen[slot]
                else:
                    filt.reset()
                    self._last_seen[slot] = None
        return hands
