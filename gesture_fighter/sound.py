"""Ses efektleri numpy ile anında sentezlenir — harici ses dosyası gerekmez."""
import numpy as np
import pygame


class SoundBank:
    def __init__(self, enabled=True):
        self.sounds = {}
        self.enabled = False
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(24)
            self._build()
            self.enabled = True
        except Exception as e:
            print(f"[sound] Ses kapalı: {e}")

    def play(self, name, volume=1.0):
        if not self.enabled:
            return
        s = self.sounds.get(name)
        if s is not None:
            ch = s.play()
            if ch is not None:
                ch.set_volume(volume)

    # ------------------------------------------------------------------
    def _t(self, dur):
        return np.arange(int(self.rate * dur)) / self.rate

    def _sweep(self, f0, f1, dur, wave="sine", curve=1.0):
        t = self._t(dur)
        x = (t / dur) ** curve
        f = f0 + (f1 - f0) * x
        phase = 2 * np.pi * np.cumsum(f) / self.rate
        if wave == "square":
            return np.sign(np.sin(phase)) * 0.6
        if wave == "saw":
            return 2 * ((phase / (2 * np.pi)) % 1.0) - 1
        return np.sin(phase)

    def _noise(self, dur, smooth=1):
        n = np.random.uniform(-1, 1, int(self.rate * dur))
        if smooth > 1:
            n = np.convolve(n, np.ones(smooth) / smooth, mode="same") * np.sqrt(smooth)
        return n

    def _env(self, dur, attack=0.005, decay=10.0):
        t = self._t(dur)
        env = np.exp(-t * decay)
        a = int(self.rate * attack)
        if a > 0:
            env[:a] *= np.linspace(0, 1, a)
        fade = min(len(env), int(self.rate * 0.01))
        env[-fade:] *= np.linspace(1, 0, fade)
        return env

    def _make(self, name, sig, vol=0.5):
        sig = np.asarray(sig, dtype=np.float64)
        peak = np.max(np.abs(sig)) or 1.0
        data = (sig / peak * vol * 32767).astype(np.int16)
        if self.channels == 2:
            data = np.ascontiguousarray(np.column_stack([data, data]))
        self.sounds[name] = pygame.sndarray.make_sound(data)

    def _build(self):
        d = 0.18
        self._make("punch", (self._sweep(180, 50, d) + 0.6 * self._noise(d, 6)) * self._env(d, decay=22), 0.55)

        d = 0.4
        self._make("fire", (0.7 * self._noise(d, 3) + 0.5 * self._sweep(250, 900, d, "saw"))
                   * self._env(d, 0.02, 7), 0.4)

        d = 0.35
        self._make("shield", (self._sweep(500, 760, d) + 0.5 * self._sweep(750, 1140, d)) * self._env(d, 0.01, 9), 0.3)

        d = 0.25
        sig = sum(self._sweep(f, f * 0.98, d) / (i + 1) for i, f in enumerate((1250, 1870, 2730)))
        self._make("block", (sig + 0.3 * self._noise(d)) * self._env(d, decay=18), 0.4)

        d = 0.6
        sig = self._sweep(1400, 2200, d) + 0.6 * self._sweep(2100, 3300, d)
        self._make("parry", sig * self._env(d, decay=6), 0.45)

        d = 1.6
        sig = (0.8 * self._sweep(55, 110, d, "saw") + 0.5 * self._noise(d, 8)
               + 0.4 * self._sweep(220, 880, d, curve=2))
        self._make("special", sig * self._env(d, 0.05, 1.6), 0.6)

        d = 0.16
        self._make("boss_shot", self._sweep(900, 220, d, "square") * self._env(d, decay=14), 0.22)

        d = 0.09
        self._make("laser_warn", self._sweep(880, 880, d, "square") * self._env(d, decay=8), 0.18)

        d = 0.6
        self._make("laser_fire", (self._sweep(110, 90, d, "saw") + 0.5 * self._noise(d, 2))
                   * self._env(d, 0.01, 3), 0.4)

        d = 0.3
        self._make("hurt", (self._sweep(260, 70, d, "square") + 0.5 * self._noise(d, 4)) * self._env(d, decay=9), 0.45)

        d = 0.12
        self._make("boss_hit", (self._sweep(320, 140, d) + 0.4 * self._noise(d, 4)) * self._env(d, decay=25), 0.4)

        d = 1.1
        self._make("explosion", (self._noise(d, 20) + 0.5 * self._sweep(80, 30, d)) * self._env(d, 0.005, 4), 0.6)

        d = 0.08
        self._make("blip", self._sweep(660, 990, d) * self._env(d, decay=20), 0.25)

        d = 0.25
        self._make("beep", self._sweep(660, 660, d, "square") * self._env(d, decay=8), 0.25)
        d = 0.6
        self._make("go", self._sweep(990, 990, d, "square") * self._env(d, decay=4), 0.3)

        d = 0.25
        self._make("fizzle", self._noise(d, 10) * self._env(d, decay=14), 0.2)

        d = 1.2
        self._make("roar", (self._sweep(70, 45, d, "saw") + 0.7 * self._noise(d, 30)) * self._env(d, 0.08, 2.5), 0.6)

        self._make("win", self._melody([523, 659, 784, 1047, 784, 1047], 0.14), 0.4)
        self._make("lose", self._melody([440, 392, 349, 262], 0.28, wave="saw"), 0.35)

    def _melody(self, notes, step, wave="square"):
        parts = []
        for f in notes:
            parts.append(self._sweep(f, f, step, wave) * self._env(step, 0.005, 6))
        return np.concatenate(parts)
