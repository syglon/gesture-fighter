"""Partiküller, uçan yazılar ve ekran sarsıntısı."""
import math
import random

import pygame

from .draw import blit_glow, text


class Particles:
    def __init__(self):
        # [x, y, vx, vy, life, max_life, size, color, gravity, drag, glow]
        self.items = []

    def burst(self, x, y, color, n=20, speed=(80, 380), life=(0.3, 0.8), size=(2, 6),
              gravity=0.0, angle=None, spread=math.tau, drag=2.5, glow=True):
        for _ in range(n):
            a = random.uniform(0, math.tau) if angle is None else angle + random.uniform(-spread / 2, spread / 2)
            v = random.uniform(*speed)
            lf = random.uniform(*life)
            self.items.append([x, y, math.cos(a) * v, math.sin(a) * v, lf, lf,
                               random.uniform(*size), color, gravity, drag, glow])

    def emit(self, x, y, vx, vy, color, life=0.4, size=4, gravity=0.0, drag=1.0, glow=True):
        self.items.append([x, y, vx, vy, life, life, size, color, gravity, drag, glow])

    def update(self, dt):
        alive = []
        for p in self.items:
            p[4] -= dt
            if p[4] <= 0:
                continue
            k = max(0.0, 1.0 - p[9] * dt)
            p[2] *= k
            p[3] = p[3] * k + p[8] * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            alive.append(p)
        self.items = alive[-1500:]

    def draw(self, surf):
        for x, y, _, _, life, max_life, size, color, _, _, g in self.items:
            f = life / max_life
            r = size * (0.4 + 0.6 * f)
            if g:
                blit_glow(surf, (x, y), r * 3, tuple(int(c * f) for c in color))
            pygame.draw.circle(surf, color, (int(x), int(y)), max(1, int(r)))

    def clear(self):
        self.items.clear()


class FloatingText:
    def __init__(self, x, y, s, color, font, life=0.9, vy=-70, pop=True):
        self.x, self.y, self.s, self.color, self.font = x, y, s, color, font
        self.life = self.max_life = life
        self.vy = vy
        self.pop = pop

    def update(self, dt):
        self.life -= dt
        self.y += self.vy * dt
        self.vy *= max(0.0, 1 - 2 * dt)
        return self.life > 0

    def draw(self, surf):
        f = self.life / self.max_life
        alpha = int(255 * min(1.0, f * 2.5))
        text(surf, self.font, self.s, (self.x, self.y), self.color, alpha=alpha)


class Shake:
    def __init__(self):
        self.amount = 0.0

    def add(self, amount):
        self.amount = min(30.0, max(self.amount, amount))

    def update(self, dt):
        self.amount = max(0.0, self.amount - dt * 40 - self.amount * 4 * dt)

    def offset(self):
        if self.amount <= 0.3:
            return 0, 0
        a = self.amount
        return int(random.uniform(-a, a)), int(random.uniform(-a, a))
