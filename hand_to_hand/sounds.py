"""Gesture Fighter'ın ses bankası + dövüş oyununa özel ek sesler."""
from gesture_fighter.sound import SoundBank


class FightSounds(SoundBank):
    def _build(self):
        super()._build()
        d = 0.16
        self._make("whoosh", self._noise(d, 12) * self._env(d, 0.03, 14), 0.25)
        d = 0.25
        self._make("heavy", (self._sweep(140, 40, d) + 0.8 * self._noise(d, 8)) * self._env(d, decay=14), 0.65)
        d = 0.2
        self._make("kick", (self._sweep(220, 60, d) + 0.7 * self._noise(d, 5)) * self._env(d, decay=16), 0.55)
        d = 0.18
        self._make("land", self._noise(d, 30) * self._env(d, decay=20), 0.3)
        d = 0.5
        self._make("handouken", (0.6 * self._sweep(300, 1200, d, "saw") + 0.6 * self._noise(d, 4))
                   * self._env(d, 0.02, 5), 0.4)
