"""Oyun nesneleri: mermiler, lazerler, özel ışın, oyuncu (Fighter) ve Boss."""
import math
import random
from collections import deque

import pygame

from . import config as C
from .draw import blit_glow, gesture_icon, lerp, scale_color
from .gestures import GESTURE_COLOR, Gesture


def circle_rect_hit(cx, cy, r, rect):
    nx = max(rect.left, min(cx, rect.right))
    ny = max(rect.top, min(cy, rect.bottom))
    return (cx - nx) ** 2 + (cy - ny) ** 2 <= r * r


# ====================================================================== projectiles
class Projectile:
    def __init__(self, x, y, vx, vy, radius, damage, owner, kind, color, homing=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.radius = radius
        self.damage = damage
        self.owner = owner          # "player" | "boss"
        self.kind = kind            # punch | fire | reflect | orb | missile | wall
        self.color = color
        self.homing = homing
        self.shooter = None     # mermiyi atan oyuncu (istatistik / versus)
        self.target = None      # güdümlü füzenin hedefi
        self.alive = True
        self.age = 0.0
        self.trail = deque(maxlen=9)

    def update(self, dt, game):
        self.age += dt
        if self.homing and self.age > 0.25:
            if self.target is None or self.target.hp <= 0:
                self.target = game.pick_target()
            if self.target is not None:
                desired = max(-260.0, min(260.0, (self.target.y - self.y) * 2.2))
                self.vy += (desired - self.vy) * min(1.0, self.homing * dt)
        self.trail.append((self.x, self.y))
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.kind == "fire" and random.random() < 0.8:
            game.particles.emit(self.x, self.y + random.uniform(-8, 8), -self.vx * 0.1 + random.uniform(-40, 40),
                                random.uniform(-60, 20), random.choice([(255, 160, 40), (255, 90, 20), (255, 220, 120)]),
                                life=random.uniform(0.2, 0.4), size=random.uniform(2, 5))
        elif self.kind == "missile" and random.random() < 0.7:
            game.particles.emit(self.x - math.copysign(14, self.vx), self.y, -self.vx * 0.3, random.uniform(-30, 30),
                                (255, 120, 60), life=0.25, size=3, glow=True)
        if self.x < -60 or self.x > C.SCREEN_W + 60 or self.y < ARENA_LIMIT_TOP:
            self.alive = False
        elif self.y > C.FLOOR_Y - self.radius * 0.5:
            self.alive = False  # zemine çarptı
            game.particles.burst(self.x, C.FLOOR_Y, self.color, n=10, speed=(60, 220), life=(0.15, 0.4),
                                 angle=-math.pi / 2, spread=2.2)

    def draw(self, surf):
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            f = (i + 1) / (n + 1)
            blit_glow(surf, (tx, ty), self.radius * (0.6 + f), scale_color(self.color, 0.35 * f))
        x, y = int(self.x), int(self.y)
        r = self.radius
        if self.kind == "missile":
            ang = math.atan2(self.vy, self.vx)
            pts = [(x + math.cos(ang) * r * 1.4, y + math.sin(ang) * r * 1.4),
                   (x + math.cos(ang + 2.5) * r, y + math.sin(ang + 2.5) * r),
                   (x + math.cos(ang - 2.5) * r, y + math.sin(ang - 2.5) * r)]
            blit_glow(surf, (x, y), r * 2.4, (150, 40, 30))
            pygame.draw.polygon(surf, (255, 80, 60), pts)
            pygame.draw.polygon(surf, (255, 220, 200), pts, 2)
            # vurulabilir olduğunu gösteren nişangah
            pygame.draw.circle(surf, (255, 255, 255), (x, y), int(r * 1.7), 1)
            return
        flick = 1.0 + (0.15 * math.sin(self.age * 40) if self.kind == "fire" else 0.0)
        blit_glow(surf, (x, y), r * 2.6 * flick, self.color)
        pygame.draw.circle(surf, self.color, (x, y), int(r * flick))
        pygame.draw.circle(surf, (255, 255, 255), (x, y), max(2, int(r * 0.5)))
        if self.kind in ("punch", "reflect"):
            d = 1 if self.vx >= 0 else -1
            rect = pygame.Rect(0, 0, r * 3, r * 3)
            rect.center = (x - d * r * 0.6, y)
            a0 = -math.pi / 2.2 if d > 0 else math.pi - math.pi / 2.2
            pygame.draw.arc(surf, (255, 255, 255), rect, a0, a0 + math.pi / 1.1, 3)


ARENA_LIMIT_TOP = C.ARENA_TOP - 80


class Laser:
    """Uyarı süresi boyunca yanıp söner, sonra yatay bir ışın olarak ateşlenir."""

    def __init__(self, y, warn, duration, damage, half_h=32, x_end=None, color=(255, 60, 120)):
        self.y = y
        self.warn = warn
        self.duration = duration
        self.damage = damage
        self.half_h = half_h
        self.x_end = x_end if x_end is not None else C.BOSS_X - 80
        self.color = color
        self.t = 0.0
        self.alive = True
        self.hit = set()         # vurduğu oyuncular (id)
        self.blocked_by = set()  # kalkanla karşılayan oyuncular (id)
        self.started = False

    @property
    def firing(self):
        return self.warn <= self.t < self.warn + self.duration

    def update(self, dt):
        self.t += dt
        if self.t >= self.warn + self.duration:
            self.alive = False

    def draw(self, surf):
        y = int(self.y)
        if self.t < self.warn:
            k = self.t / self.warn
            blink = (math.sin(self.t * (12 + 30 * k)) > 0)
            col = self.color if blink else scale_color(self.color, 0.4)
            band = pygame.Surface((self.x_end, self.half_h * 2), pygame.SRCALPHA)
            band.fill((*self.color, int(25 + 45 * k)))
            surf.blit(band, (0, y - self.half_h))
            for x in range(0, int(self.x_end), 28):
                pygame.draw.line(surf, col, (x, y), (x + 14, y), 2)
            pygame.draw.line(surf, scale_color(self.color, 0.6), (0, y - self.half_h), (self.x_end, y - self.half_h), 1)
            pygame.draw.line(surf, scale_color(self.color, 0.6), (0, y + self.half_h), (self.x_end, y + self.half_h), 1)
            return
        ft = self.t - self.warn
        inten = min(1.0, ft / 0.06) * min(1.0, (self.duration - ft) / 0.12)
        hh = self.half_h * (0.7 + 0.3 * inten) + math.sin(self.t * 60) * 3
        layer = pygame.Surface((int(self.x_end), int(hh * 2.6) + 2))
        lh = layer.get_height()
        for frac, col in ((1.3, scale_color(self.color, 0.45 * inten)), (1.0, scale_color(self.color, inten)),
                          (0.45, scale_color((255, 255, 255), inten))):
            h = int(hh * frac)
            pygame.draw.rect(layer, col, (0, lh // 2 - h, self.x_end, h * 2))
        surf.blit(layer, (0, y - lh // 2), special_flags=pygame.BLEND_ADD)
        blit_glow(surf, (self.x_end, y), hh * 3, scale_color(self.color, inten))


class SpecialBeam:
    def __init__(self, owner, duration=C.SPECIAL_DURATION, dps=C.SPECIAL_DPS):
        self.owner = owner
        self.duration = duration
        self.dps = dps
        self.t = 0.0
        self.alive = True
        self.half_h = 46
        self.dmg_accum = 0.0
        self.color = C.C_SPECIAL

    @property
    def y(self):
        return self.owner.hand_pos[1]

    @property
    def x0(self):
        return self.owner.hand_pos[0]

    @property
    def intensity(self):
        return min(1.0, self.t / 0.15) * min(1.0, max(0.0, self.duration - self.t) / 0.3)

    def update(self, dt):
        self.t += dt
        if self.t >= self.duration:
            self.alive = False

    def draw(self, surf):
        inten = self.intensity
        x0 = int(self.x0)
        x1 = C.SCREEN_W if self.owner.facing > 0 else 0
        w = abs(x1 - x0)
        hh = self.half_h * (0.6 + 0.4 * inten)
        layer = pygame.Surface((w, int(hh * 3) + 2))
        lh = layer.get_height()
        cols = ((1.5, scale_color((255, 120, 20), 0.5 * inten)),
                (1.0, scale_color(self.color, inten)),
                (0.5, scale_color((255, 255, 230), inten)))
        for frac, col in cols:
            pts_top, pts_bot = [], []
            for x in range(0, w + 20, 20):
                wob = math.sin(x * 0.05 - self.t * 30) * 5 * frac
                h = hh * frac + wob
                pts_top.append((x, lh / 2 - h))
                pts_bot.append((x, lh / 2 + h))
            pygame.draw.polygon(layer, col, pts_top + pts_bot[::-1])
        left = x0 if self.owner.facing > 0 else x1
        surf.blit(layer, (left, int(self.y - lh / 2)), special_flags=pygame.BLEND_ADD)
        blit_glow(surf, (x0, self.y), hh * 2.6, scale_color(self.color, inten))


# ====================================================================== fighter
class Fighter:
    """Oyuncu karakteri. `facing` sayesinde iki kişilik modda sağ tarafta da kullanılabilir."""

    def __init__(self, x=C.PLAYER_X, facing=1, color=(90, 220, 255), name="P1"):
        self.x = x
        self.facing = facing
        self.color = color
        self.name = name
        self.y = self.target_y = (C.PLAYER_Y_MIN + C.PLAYER_Y_MAX) / 2
        self.max_hp = C.PLAYER_MAX_HP
        self.hp = self.ghost_hp = float(self.max_hp)
        self.energy = float(C.PLAYER_MAX_ENERGY)
        self.special = 0.0
        self.gesture = Gesture.NONE
        self.shield_on = False
        self.shield_t = 0.0
        self.guard_break = 0.0
        self.energy_delay = 0.0
        self.cooldown = 0.0
        self.hold_timer = 0.0
        self.pending = None
        self.iframes = 0.0
        self.hurt_flash = 0.0
        self.attack_anim = 0.0
        self.beam = None
        self.t = 0.0
        self.combo = 0
        self.combo_timer = 0.0

    @property
    def hand_pos(self):
        reach = 40 + 22 * self.attack_anim
        return self.x + self.facing * reach, self.y - 14 + math.sin(self.t * 3) * 2

    @property
    def shield_center(self):
        return self.x + self.facing * 12, self.y - 4

    @property
    def hitbox(self):
        return pygame.Rect(int(self.x - 24), int(self.y - 62), 48, 120)

    @property
    def in_parry_window(self):
        return self.shield_on and self.shield_t <= C.PARRY_WINDOW

    def update_timers(self, dt):
        self.t += dt
        self.cooldown = max(0.0, self.cooldown - dt)
        self.iframes = max(0.0, self.iframes - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt * 3)
        self.attack_anim = max(0.0, self.attack_anim - dt * 6)
        self.guard_break = max(0.0, self.guard_break - dt)
        if self.ghost_hp > self.hp:
            self.ghost_hp = max(self.hp, self.ghost_hp - dt * 40)
        self.combo_timer -= dt
        if self.combo_timer <= 0:
            self.combo = 0

    def draw(self, surf, fonts):
        x = int(self.x)
        y = self.y + math.sin(self.t * 3) * 3
        # zemindeki gölge
        h_above = C.FLOOR_Y - (y + 58)
        sw = max(30, 70 - h_above * 0.08)
        shadow = pygame.Surface((int(sw * 2), 16), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 110), shadow.get_rect())
        surf.blit(shadow, (x - sw, C.FLOOR_Y - 6))

        if self.iframes > 0 and int(self.iframes * 14) % 2 == 0:
            return  # hasar sonrası yanıp sönme

        body = (230, 236, 255)
        if self.hurt_flash > 0:
            body = (255, int(236 * (1 - self.hurt_flash)), int(255 * (1 - self.hurt_flash)))
        f = self.facing
        dark = (20, 20, 35)
        head = (x + f * 4, int(y - 44))
        neck = (x, int(y - 28))
        hip = (x - f * 2, int(y + 18))
        hand = (int(self.hand_pos[0]), int(self.hand_pos[1]))
        back_hand = (x - f * 22, int(y + 2))
        legs = [(x - 16, int(y + 58)), (x + 16, int(y + 58))]

        blit_glow(surf, (x, y), 90, scale_color(self.color, 0.25))
        # atkı
        sway = math.sin(self.t * 6) * 6
        pygame.draw.polygon(surf, self.color, [(neck[0] - 2, neck[1] - 4), (neck[0] - f * 34, neck[1] + 4 + sway),
                                               (neck[0] - f * 30, neck[1] + 14 + sway), (neck[0] + 2, neck[1] + 6)])
        for w, col in ((12, dark), (8, body)):
            pygame.draw.line(surf, col, neck, hip, w)
            for leg in legs:
                pygame.draw.line(surf, col, hip, leg, w)
            pygame.draw.line(surf, col, neck, back_hand, w - 2)
            pygame.draw.line(surf, col, neck, hand, w - 2)
        pygame.draw.circle(surf, dark, head, 19)
        pygame.draw.circle(surf, body, head, 16)
        # vizör
        pygame.draw.rect(surf, self.color, (head[0] + (2 if f > 0 else -14), head[1] - 5, 12, 6), border_radius=3)

        gcol = GESTURE_COLOR[self.gesture]
        blit_glow(surf, hand, 36 + 10 * self.attack_anim, scale_color(gcol, 0.8))
        if self.gesture is Gesture.NONE:
            pygame.draw.circle(surf, dark, hand, 10)
            pygame.draw.circle(surf, body, hand, 8)
        else:
            gesture_icon(surf, self.gesture, hand, 30, gcol)

        if self.shield_on:
            self._draw_shield(surf)
        if self.guard_break > 0:
            for i in range(3):
                a = self.t * 5 + i * math.tau / 3
                p = (head[0] + math.cos(a) * 26, head[1] - 24 + math.sin(a) * 7)
                blit_glow(surf, p, 10, (255, 230, 80))
                pygame.draw.circle(surf, (255, 240, 140), (int(p[0]), int(p[1])), 3)

    def _draw_shield(self, surf):
        cx, cy = self.shield_center
        r = C.SHIELD_RADIUS + math.sin(self.t * 20) * 2
        parry = self.in_parry_window
        col = C.C_PARRY if parry else C.C_SHIELD
        low = self.energy / C.PLAYER_MAX_ENERGY
        s = pygame.Surface((int(r * 2 + 8), int(r * 2 + 8)), pygame.SRCALPHA)
        c = (s.get_width() // 2, s.get_height() // 2)
        pygame.draw.circle(s, (*col, 40 if not parry else 80), c, int(r))
        pygame.draw.circle(s, (*col, 200), c, int(r), 4 if not parry else 7)
        # altıgen desen hissi veren ön yay
        rect = pygame.Rect(0, 0, int(r * 2 - 10), int(r * 2 - 10))
        rect.center = c
        a0 = -math.pi / 2.5 if self.facing > 0 else math.pi - math.pi / 2.5
        pygame.draw.arc(s, (255, 255, 255, 180), rect, a0, a0 + math.pi / 1.25, 3)
        if low < 0.3 and int(self.t * 10) % 2 == 0:
            s.set_alpha(120)
        surf.blit(s, (int(cx - c[0]), int(cy - c[1])))


# ====================================================================== boss
PHASE_COLORS = {1: (130, 100, 255), 2: (255, 150, 40), 3: (255, 50, 70)}
PHASE_ATTACKS = {
    1: [("orb", 3), ("spread", 3), ("laser", 1)],
    2: [("burst", 3), ("spread", 2), ("laser", 2), ("missile", 2)],
    3: [("burst", 2), ("spread", 2), ("double_laser", 2), ("missile", 2), ("wall", 3)],
}
PHASE_INTERVAL = {1: 1.75, 2: 1.3, 3: 1.0}
PHASE_MOVE = {1: (100, 0.8, 0.0), 2: (135, 1.1, 0.25), 3: (150, 1.5, 0.4)}  # genlik, hız, oyuncuyu takip
ATTACK_COLORS = {"orb": (190, 110, 255), "burst": (190, 110, 255), "spread": (255, 150, 40),
                 "missile": (255, 80, 60), "wall": (255, 60, 200), "laser": (255, 60, 120),
                 "double_laser": (255, 60, 120)}


class Boss:
    def __init__(self, difficulty="normal"):
        self.diff = dict(C.DIFFICULTY[difficulty])
        self.max_hp = C.BOSS_MAX_HP
        self.hp = self.ghost_hp = float(self.max_hp)
        self.home_x = C.BOSS_X
        self.x = C.SCREEN_W + 220
        self.mid_y = (C.ARENA_TOP + C.ARENA_BOTTOM) / 2
        self.y = self.mid_y
        self.radius = C.BOSS_RADIUS
        self.t = 0.0
        self.phase = 1
        self.state = "intro"   # intro | idle | windup | transition | dying | gloat | dead
        self.state_t = 0.0
        self.attack_cd = 1.6
        self.current = None
        self.last_attack = None
        self.queue = []
        self.flash = 0.0
        self.hit_shake = 0.0
        self.ghost_delay = 0.0
        self.target = None  # şu an nişan alınan oyuncu

    # ------------------------------------------------------------------
    @property
    def color(self):
        return PHASE_COLORS[self.phase]

    @property
    def vulnerable(self):
        return self.state in ("idle", "windup")

    @property
    def emitter(self):
        return self.x - self.radius * 0.75, self.y

    def set_state(self, s):
        self.state = s
        self.state_t = 0.0

    def _target(self, game):
        if self.target is None or self.target.hp <= 0:
            self.target = game.pick_target()
        return self.target

    def take_damage(self, dmg):
        self.hp = max(0.0, self.hp - dmg)
        self.flash = 0.12
        self.hit_shake = min(10.0, self.hit_shake + 3 + dmg * 0.3)
        self.ghost_delay = 0.5

    # ------------------------------------------------------------------
    def update(self, dt, game):
        if self.state == "dead":
            return
        self.t += dt
        self.state_t += dt
        self.flash = max(0.0, self.flash - dt)
        self.hit_shake = max(0.0, self.hit_shake - dt * 30)
        self.ghost_delay -= dt
        if self.ghost_delay <= 0 and self.ghost_hp > self.hp:
            self.ghost_hp = max(self.hp, self.ghost_hp - dt * (60 + (self.ghost_hp - self.hp) * 3))

        # giriş animasyonu
        if self.state == "intro":
            self.x += (self.home_x - self.x) * min(1.0, dt * 2.2)
        else:
            self.x += (self.home_x - self.x) * min(1.0, dt * 4)

        # dikey hareket
        amp, spd, follow = PHASE_MOVE[self.phase]
        if self.state in ("transition", "dying", "intro"):
            target = self.mid_y
        else:
            target = self.mid_y + amp * math.sin(self.t * spd)
            tgt = self._target(game)
            if tgt is not None:
                target = lerp(target, tgt.y, follow)
        if self.state == "windup":
            target = self.y  # saldırı hazırlarken sabit dur
        self.y += (target - self.y) * min(1.0, dt * 2.5)
        lo, hi = C.ARENA_TOP + self.radius + 20, C.ARENA_BOTTOM - self.radius - 30
        self.y = max(lo, min(hi, self.y))

        # sıraya alınmış alt saldırılar (burst vb.)
        if self.state in ("idle", "windup"):
            for q in self.queue:
                q[0] -= dt
            due = [q for q in self.queue if q[0] <= 0]
            self.queue = [q for q in self.queue if q[0] > 0]
            for _, fn in due:
                fn()

        if self.state == "idle":
            self.attack_cd -= dt
            if self.attack_cd <= 0:
                self.current = self._choose()
                self.target = game.pick_target()
                self.set_state("windup")
                game.sound.play("blip", 0.5)
        elif self.state == "windup":
            wind = 0.5 if self.phase == 1 else 0.38 if self.phase == 2 else 0.28
            if self.state_t >= wind:
                self._execute(self.current, game)
                self.last_attack = self.current
                self.set_state("idle")
                self.attack_cd = PHASE_INTERVAL[self.phase] * self.diff["interval"] * random.uniform(0.85, 1.15)
        elif self.state == "transition":
            if self.state_t >= 2.2:
                self.set_state("idle")
                self.attack_cd = 0.8

        # faz geçişi
        if self.state in ("idle", "windup") and self.hp > 0:
            frac = self.hp / self.max_hp
            new_phase = 1 if frac > 2 / 3 else 2 if frac > 1 / 3 else 3
            if new_phase > self.phase:
                self.phase = new_phase
                self.queue.clear()
                self.set_state("transition")
                game.on_boss_phase(new_phase)

    def _choose(self):
        options = [(a, w) for a, w in PHASE_ATTACKS[self.phase] if a != self.last_attack]
        total = sum(w for _, w in options)
        r = random.uniform(0, total)
        for a, w in options:
            r -= w
            if r <= 0:
                return a
        return options[-1][0]

    # ------------------------------------------------------------------ attacks
    def _shoot(self, game, angle_offset_deg=0.0, speed=430, dmg=8, radius=15, kind="orb", color=None, homing=0.0):
        ex, ey = self.emitter
        p = self._target(game)
        if p is None:
            return
        ang = math.atan2(p.y - ey, p.x - ex) + math.radians(angle_offset_deg)
        speed *= self.diff["speed"]
        game.spawn(Projectile(ex, ey, math.cos(ang) * speed, math.sin(ang) * speed, radius,
                              dmg * self.diff["damage"], "boss", kind, color or ATTACK_COLORS["orb"], homing))

    def _laser(self, game, y, warn):
        y = max(C.ARENA_TOP + 30, min(C.ARENA_BOTTOM - 30, y))
        game.add_laser(Laser(y, warn, 0.45, 15 * self.diff["damage"], x_end=self.emitter[0]))
        game.sound.play("laser_warn")

    def _execute(self, name, game):
        p = self._target(game)
        if p is None:
            return
        if name == "orb":
            self._shoot(game)
            game.sound.play("boss_shot")
        elif name == "burst":
            n = 3 if self.phase == 2 else 4
            for i in range(n):
                self.queue.append([i * 0.14, lambda: (self._shoot(game, speed=480), game.sound.play("boss_shot"))])
        elif name == "spread":
            n = {1: 3, 2: 5, 3: 7}[self.phase]
            step = 12 if n < 7 else 10
            for i in range(n):
                self._shoot(game, (i - (n - 1) / 2) * step, speed=380, dmg=6, radius=13,
                            color=ATTACK_COLORS["spread"])
            game.sound.play("boss_shot")
        elif name == "laser":
            self._laser(game, p.y, 0.95 if self.phase == 1 else 0.8)
        elif name == "double_laser":
            self._laser(game, p.y, 0.85)
            self.queue.append([0.7, lambda: self._target(game) and self._laser(game, self._target(game).y, 0.8)])
        elif name == "missile":
            n = 2 if self.phase == 2 else 3
            ex, ey = self.emitter
            for i in range(n):
                vy = (-1 if i % 2 == 0 else 1) * random.uniform(180, 280)
                m = Projectile(ex, ey + vy * 0.1, -260 * self.diff["speed"], vy, 13,
                               12 * self.diff["damage"], "boss", "missile", ATTACK_COLORS["missile"], homing=2.0)
                m.target = p if i % 2 == 0 else game.pick_target()
                game.spawn(m)
            game.sound.play("boss_shot")
        elif name == "wall":
            gap = random.uniform(C.PLAYER_Y_MIN, C.PLAYER_Y_MAX)
            ex = self.emitter[0]
            y = C.ARENA_TOP + 18
            while y < C.ARENA_BOTTOM - 10:
                if abs(y - gap) > 90:
                    game.spawn(Projectile(ex, y, -260 * self.diff["speed"], 0, 14, 10 * self.diff["damage"],
                                          "boss", "wall", ATTACK_COLORS["wall"]))
                y += 40
            game.sound.play("laser_fire", 0.5)

    # ------------------------------------------------------------------ draw
    def draw(self, surf, game):
        col = self.color
        sx = random.uniform(-self.hit_shake, self.hit_shake)
        sy = random.uniform(-self.hit_shake, self.hit_shake)
        if self.state == "dying":
            sx += random.uniform(-8, 8)
            sy += random.uniform(-8, 8)
        x, y = int(self.x + sx), int(self.y + sy + math.sin(self.t * 2) * 4)
        R = self.radius

        blit_glow(surf, (x, y), R * 2.4, scale_color(col, 0.45))
        if self.state == "transition":
            k = (self.state_t * 2) % 1.0
            pygame.draw.circle(surf, col, (x, y), int(R + 30 + k * 160), max(1, int(8 * (1 - k))))

        # dönen dikenler
        n = 10
        spike = 26 + 10 * (self.phase - 1)
        rot = self.t * (0.6 + 0.5 * self.phase)
        for i in range(n):
            a = rot + i * math.tau / n
            base1 = (x + math.cos(a - 0.17) * (R + 4), y + math.sin(a - 0.17) * (R + 4))
            base2 = (x + math.cos(a + 0.17) * (R + 4), y + math.sin(a + 0.17) * (R + 4))
            tip = (x + math.cos(a) * (R + spike), y + math.sin(a) * (R + spike))
            pygame.draw.polygon(surf, scale_color(col, 0.6), [base1, tip, base2])
            pygame.draw.polygon(surf, col, [base1, tip, base2], 2)

        pygame.draw.circle(surf, (34, 30, 52), (x, y), R)
        pygame.draw.circle(surf, (80, 72, 115), (x, y), R, 7)
        ring = pygame.Rect(0, 0, int(R * 1.6), int(R * 1.6))
        ring.center = (x, y)
        for i in range(3):
            a = -self.t * 1.5 + i * math.tau / 3
            pygame.draw.arc(surf, col, ring, a, a + 1.4, 5)

        # göz
        eye_r = int(R * 0.5)
        windup = self.state == "windup"
        sclera = (235, 235, 245) if not windup else (255, 255, 255)
        pygame.draw.circle(surf, sclera, (x, y), eye_r)
        p = self.target if self.target is not None and self.target.hp > 0 else None
        ang = math.atan2((p.y if p else y) - y, (p.x if p else 0) - x)
        ix, iy = x + math.cos(ang) * eye_r * 0.38, y + math.sin(ang) * eye_r * 0.38
        icol = ATTACK_COLORS.get(self.current, col) if windup else col
        if windup:
            blit_glow(surf, (ix, iy), eye_r * (1.5 + self.state_t * 4), icol)
        pygame.draw.circle(surf, icol, (int(ix), int(iy)), int(eye_r * 0.55))
        if self.phase == 3:
            pygame.draw.ellipse(surf, (10, 0, 0), (int(ix - eye_r * 0.1), int(iy - eye_r * 0.4),
                                                   int(eye_r * 0.2), int(eye_r * 0.8)))
        else:
            pygame.draw.circle(surf, (10, 5, 20), (int(ix), int(iy)), int(eye_r * 0.24))
        pygame.draw.circle(surf, (255, 255, 255), (int(ix - eye_r * 0.15), int(iy - eye_r * 0.18)),
                           max(2, eye_r // 9))

        if windup:
            ex, ey = self.emitter
            blit_glow(surf, (ex + sx, ey + sy), 20 + self.state_t * 80, ATTACK_COLORS.get(self.current, col))
        if self.flash > 0:
            blit_glow(surf, (x, y), R * 1.6, (int(255 * self.flash / 0.12),) * 3)
