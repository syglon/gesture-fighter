"""Sound effects and arcade music are synthesized with numpy at start-up — no audio files are needed."""
import numpy as np
import pygame


class SoundBank:
    MUSIC_VOLUME = 0.35
    MUSIC_VOLUMES = {"menu": 0.3, "battle": 0.35}

    def __init__(self, enabled=True):
        self.sounds = {}
        self.music = {}
        self.enabled = False
        self.current_music = None
        self.music_ch = None
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(24)
            pygame.mixer.set_reserved(1)          # channel 0 is reserved for music
            self.music_ch = pygame.mixer.Channel(0)
            self._build()
            self._build_music()
            self.enabled = True
        except Exception as e:
            print(f"[sound] Sound disabled: {e}")

    # ------------------------------------------------------------------ music
    def play_music(self, name):
        """Plays a music track in a loop; does nothing if that track is already playing."""
        if not self.enabled or self.music_ch is None:
            return
        if name == self.current_music and self.music_ch.get_busy():
            return
        track = self.music.get(name)
        if track is None:
            return
        self.current_music = name
        self.music_ch.play(track, loops=-1, fade_ms=700)
        self.music_ch.set_volume(self.MUSIC_VOLUMES.get(name, self.MUSIC_VOLUME))

    def stop_music(self):
        if self.music_ch is not None:
            self.music_ch.fadeout(300)
        self.current_music = None

    def pause_music(self, paused):
        if self.music_ch is None:
            return
        if paused:
            self.music_ch.pause()
        else:
            self.music_ch.unpause()

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

        # mirror: a bright rising crystal sound + bell
        d = 0.7
        sig = sum(self._sweep(f0, f0 * 2, d, curve=0.6) / (i + 1) for i, f0 in enumerate((660, 990, 1320)))
        self._make("mirror_cast", (sig + 0.4 * self._sweep(2640, 2640, d)) * self._env(d, 0.01, 4), 0.4)
        # mirror reflection: a high metallic "ping"
        d = 0.35
        sig = sum(self._sweep(f0, f0 * 1.02, d) / (i + 1) for i, f0 in enumerate((1760, 2794, 3951)))
        self._make("mirror_hit", (sig + 0.3 * self._sweep(600, 2400, d, "square")) * self._env(d, 0.002, 12), 0.4)

        # special ready: a rising three-note chime
        self._make("ready", self._melody([784, 1175, 1568], 0.07), 0.3)
        # dissolving on death: a shimmering rising whoosh
        d = 0.8
        self._make("dissolve", (0.5 * self._noise(d, 2) + 0.4 * self._sweep(300, 1800, d, curve=0.6))
                   * self._env(d, 0.02, 4), 0.3)

        self._make("win", self._melody([523, 659, 784, 1047, 784, 1047], 0.14), 0.4)
        self._make("lose", self._melody([440, 392, 349, 262], 0.28, wave="saw"), 0.35)

    # ------------------------------------------------------------------ chiptune synthesis
    @staticmethod
    def _midi(n):
        return 440.0 * 2 ** ((n - 69) / 12)

    def _tone(self, freq, dur, wave="pulse", duty=0.5, decay=6.0, vibrato=0.0):
        n = max(1, int(self.rate * dur))
        t = np.arange(n) / self.rate
        f = freq * (1 + vibrato * np.sin(2 * np.pi * 5.5 * t))
        ph = (np.cumsum(f) / self.rate) % 1.0
        if wave == "pulse":
            sig = np.where(ph < duty, 1.0, -1.0)
        elif wave == "tri":
            sig = 4 * np.abs(ph - 0.5) - 1
        else:
            sig = np.sin(2 * np.pi * ph)
        env = np.exp(-t * decay)
        a = min(n, int(self.rate * 0.004))
        env[:a] *= np.linspace(0, 1, a)
        r = min(n, int(self.rate * 0.006))
        env[-r:] *= np.linspace(1, 0, r)
        return sig * env

    def _drum(self, kind):
        if kind == "kick":
            d = 0.16
            return self._sweep(150, 42, d, curve=0.4) * self._env(d, 0.001, 18)
        if kind == "snare":
            d = 0.14
            return (0.8 * self._noise(d, 2) + 0.4 * self._sweep(190, 160, d)) * self._env(d, 0.001, 24)
        d = 0.05  # hi-hat: high-pitched noise
        n = self._noise(d)
        hp = n - np.convolve(n, np.ones(6) / 6, mode="same")
        return hp * self._env(d, 0.001, 70)

    def _render(self, bpm, bars, chords, lead=True, drums=True, arp_wave="pulse"):
        """chords: one (root midi note, is_minor) per bar. Layers the parts on a 16th-note grid."""
        step = 60.0 / bpm / 4
        total = int(self.rate * step * 16 * bars)
        buf = np.zeros(total)

        def add(at_step, sig, vol):
            i = int(at_step * step * self.rate)
            if i >= total:
                return
            seg = sig[: total - i]
            buf[i:i + len(seg)] += seg * vol

        kick, snare, hat = self._drum("kick"), self._drum("snare"), self._drum("hat")
        for b in range(bars):
            root, minor = chords[b % len(chords)]
            third = 3 if minor else 4
            tones = [root, root + third, root + 7, root + 12]
            base = b * 16
            # bass: root / octave in eighth notes
            for k in range(8):
                note = root - 12 + (12 if k % 2 else 0)
                add(base + 2 * k, self._tone(self._midi(note), step * 1.8, "pulse", 0.5, 9), 0.20)
            # arpeggio: sixteenth notes, two octaves up
            for k in range(16):
                note = tones[[0, 1, 2, 3, 2, 1, 2, 3][k % 8]] + 24
                add(base + k, self._tone(self._midi(note), step * 0.9, arp_wave, 0.25, 16), 0.07)
            if lead:
                # melody: a motif built from chord tones, varied in the second half
                motif = [2, 1, 0, 1, 2, 3, 2] if b < bars // 2 else [3, 2, 1, 2, 0, 1, 3]
                starts = [0, 3, 6, 8, 10, 12, 14]
                for j, (st, idx) in enumerate(zip(starts, motif)):
                    ln = (starts[j + 1] if j + 1 < len(starts) else 16) - st
                    note = tones[idx] + 12
                    add(base + st, self._tone(self._midi(note), step * ln * 0.95, "pulse", 0.5, 2.5, 0.006), 0.10)
            if drums:
                for k in (0, 8) + ((10,) if b % 2 else ()):
                    add(base + k, kick, 0.55)
                for k in (4, 12):
                    add(base + k, snare, 0.30)
                for k in range(0, 16, 2):
                    add(base + k, hat, 0.10 if k % 4 else 0.06)
        return buf

    def _render_menu(self):
        """Upbeat platformer-style menu theme (original melody): 144 BPM in C major, a bouncy staccato
        NES-style lead, an "oom-pah" bass (root on beats 1 and 3, chord stabs on 2 and 4) and light drums."""
        bpm, bars = 144, 8
        step = 60.0 / bpm / 4
        total = int(self.rate * step * 16 * bars)
        buf = np.zeros(total)

        def add(at_step, sig, vol):
            i = int(at_step * step * self.rate)
            seg = sig[: max(0, total - i)]
            buf[i:i + len(seg)] += seg * vol

        major, minor = [0, 4, 7], [0, 3, 7]
        # (root midi note, chord shape) per bar: C - Am - F - G - C - F - G - C
        chords = [(48, major), (45, minor), (41, major), (43, major),
                  (48, major), (41, major), (43, major), (48, major)]
        # (bar, step, midi note, length in 16th steps)
        melody = [(0, 0, 72, 2), (0, 2, 76, 2), (0, 4, 79, 2), (0, 6, 76, 2), (0, 8, 79, 3), (0, 12, 84, 4),
                  (1, 0, 81, 2), (1, 2, 79, 2), (1, 4, 76, 2), (1, 6, 72, 2), (1, 8, 76, 2), (1, 12, 69, 4),
                  (2, 0, 77, 2), (2, 2, 81, 2), (2, 4, 77, 2), (2, 6, 72, 2), (2, 8, 74, 2), (2, 10, 77, 2),
                  (2, 12, 81, 4),
                  (3, 0, 79, 3), (3, 3, 77, 1), (3, 4, 76, 2), (3, 6, 74, 2), (3, 8, 71, 4), (3, 12, 67, 4),
                  (4, 0, 72, 2), (4, 2, 76, 2), (4, 4, 79, 2), (4, 6, 84, 2), (4, 8, 83, 2), (4, 10, 79, 2),
                  (4, 12, 76, 4),
                  (5, 0, 77, 2), (5, 2, 76, 2), (5, 4, 74, 2), (5, 6, 72, 2), (5, 8, 69, 2), (5, 10, 72, 2),
                  (5, 12, 77, 4),
                  (6, 0, 79, 2), (6, 2, 81, 2), (6, 4, 83, 2), (6, 6, 86, 2), (6, 8, 83, 2), (6, 10, 79, 2),
                  (6, 12, 74, 4),
                  (7, 0, 84, 4), (7, 4, 79, 2), (7, 6, 76, 2), (7, 8, 72, 8)]
        kick, snare, hat = self._drum("kick"), self._drum("snare"), self._drum("hat")
        for b, (root, shape) in enumerate(chords):
            base = b * 16
            # oom-pah: bass root / fifth on beats 1 and 3, short chord stabs on beats 2 and 4
            add(base, self._tone(self._midi(root - 12), step * 3, "tri", decay=6), 0.30)
            add(base + 8, self._tone(self._midi(root - 5), step * 3, "tri", decay=6), 0.28)
            for k in (4, 12):
                for iv in shape:
                    add(base + k, self._tone(self._midi(root + 12 + iv), step * 1.5, "pulse", 0.25, 14), 0.035)
            add(base, kick, 0.30)
            add(base + 8, kick, 0.22)
            for k in (4, 12):
                add(base + k, snare, 0.14)
            for k in range(2, 16, 4):  # off-beat hi-hats
                add(base + k, hat, 0.05)
        for b, st, note, ln in melody:  # staccato lead: notes are cut short for a bouncy feel
            add(b * 16 + st, self._tone(self._midi(note), step * ln * 0.7, "pulse", 0.25, 5), 0.10)
            add(b * 16 + st, self._tone(self._midi(note + 12), step * ln * 0.5, "tri", decay=9), 0.025)
        return buf

    def _build_music(self):
        am, f, c, g, e = (45, True), (41, False), (48, False), (43, False), (40, False)
        battle = self._render(150, 8, [am, f, c, g, am, f, g, e])
        menu = self._render_menu()
        for name, sig in (("battle", battle), ("menu", menu)):
            peak = np.max(np.abs(sig)) or 1.0
            data = (sig / peak * 0.8 * 32767).astype(np.int16)
            if self.channels == 2:
                data = np.ascontiguousarray(np.column_stack([data, data]))
            self.music[name] = pygame.sndarray.make_sound(data)

    def _melody(self, notes, step, wave="square"):
        parts = []
        for f in notes:
            parts.append(self._sweep(f, f, step, wave) * self._env(step, 0.005, 6))
        return np.concatenate(parts)
