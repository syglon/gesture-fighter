"""Gün batımında bir şehir sokağı: paralaks katmanlar, neon tabelalar ve tezahürat yapan kalabalık."""
import math
import random

import pygame

from gesture_fighter.draw import blit_glow, lerp_color

from . import config as C

W, H = C.W, C.H


def _layer_width(factor):
    return int(W + (C.STAGE_W - W) * factor)


class Stage:
    def __init__(self, fonts):
        self.fonts = fonts
        rng = random.Random(461)
        self.sky = self._sky()
        self.far = self._buildings(_layer_width(0.25), rng, (38, 26, 58), (255, 200, 120), 180, 360, 0.15, False)
        self.mid = self._buildings(_layer_width(0.55), rng, (24, 16, 38), (255, 230, 150), 120, 280, 0.25, True)
        self.ground = self._ground()
        self.crowd = [(rng.uniform(0, _layer_width(0.8)), rng.uniform(0, math.tau), rng.choice(
            [(60, 40, 80), (80, 50, 70), (50, 50, 90), (90, 60, 60)]), rng.uniform(0.8, 1.15))
            for _ in range(70)]
        self.excite = 0.0

    def _sky(self):
        s = pygame.Surface((W, H))
        stops = [(0.0, (22, 14, 48)), (0.35, (88, 34, 92)), (0.62, (230, 100, 80)), (0.8, (255, 170, 90)),
                 (1.0, (255, 200, 120))]
        for y in range(H):
            t = y / H
            for i in range(len(stops) - 1):
                if stops[i][0] <= t <= stops[i + 1][0]:
                    k = (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0])
                    col = lerp_color(stops[i][1], stops[i + 1][1], k)
                    break
            pygame.draw.line(s, col, (0, y), (W, y))
        blit_glow(s, (W * 0.62, 470), 260, (120, 60, 20))
        pygame.draw.circle(s, (255, 220, 150), (int(W * 0.62), 470), 70)
        return s

    def _buildings(self, width, rng, color, window, hmin, hmax, lit, signs):
        s = pygame.Surface((width, H), pygame.SRCALPHA)
        x = -20
        sign_texts = ["ME461", "DOJO", "METU", "RAMEN", "ARCADE", "KO!"]
        while x < width:
            bw = rng.randint(70, 160)
            bh = rng.randint(hmin, hmax)
            top = C.FLOOR_Y - 30 - bh
            pygame.draw.rect(s, color, (x, top, bw, bh + 40))
            if rng.random() < 0.3:
                pygame.draw.rect(s, color, (x + bw // 3, top - 30, 8, 30))
            for wy in range(top + 12, C.FLOOR_Y - 50, 22):
                for wx in range(x + 10, x + bw - 14, 18):
                    if rng.random() < lit:
                        pygame.draw.rect(s, window, (wx, wy, 8, 11))
            if signs and rng.random() < 0.45:
                txt = rng.choice(sign_texts)
                neon = rng.choice([(255, 60, 160), (60, 230, 255), (255, 220, 60), (120, 255, 120)])
                img = self.fonts.small.render(txt, True, neon)
                sx, sy = x + bw // 2 - img.get_width() // 2, top + 20
                glow = pygame.Surface((img.get_width() + 30, img.get_height() + 24), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*neon, 50), glow.get_rect(), border_radius=10)
                s.blit(glow, (sx - 15, sy - 12))
                pygame.draw.rect(s, (20, 10, 30), (sx - 8, sy - 4, img.get_width() + 16, img.get_height() + 8),
                                 border_radius=4)
                pygame.draw.rect(s, neon, (sx - 8, sy - 4, img.get_width() + 16, img.get_height() + 8), 2,
                                 border_radius=4)
                s.blit(img, (sx, sy))
            x += bw + rng.randint(-10, 20)
        return s

    def _ground(self):
        s = pygame.Surface((C.STAGE_W, H - C.FLOOR_Y + 40))
        s.fill((48, 40, 52))
        pygame.draw.rect(s, (70, 58, 70), (0, 0, C.STAGE_W, 40))
        pygame.draw.line(s, (120, 100, 110), (0, 40), (C.STAGE_W, 40), 3)
        for x in range(0, C.STAGE_W, 120):
            pygame.draw.line(s, (60, 50, 62), (x, 0), (x, 40), 2)
        for x in range(0, C.STAGE_W, 160):
            pygame.draw.rect(s, (200, 190, 160), (x + 40, 80, 70, 8))
        return s

    def update(self, dt):
        self.excite = max(0.0, self.excite - dt * 0.6)

    def cheer(self, amount=0.5):
        self.excite = min(1.0, self.excite + amount)

    def draw(self, surf, cam_x, t):
        surf.blit(self.sky, (0, 0))
        surf.blit(self.far, (-cam_x * 0.25, 0))
        surf.blit(self.mid, (-cam_x * 0.55, 0))
        # kalabalık
        ox = -cam_x * 0.8
        base = C.FLOOR_Y - 40
        for x, ph, col, sc in self.crowd:
            sx = x + ox
            if sx < -30 or sx > W + 30:
                continue
            jump = abs(math.sin(t * (3 + 6 * self.excite) + ph)) * (3 + 14 * self.excite)
            hy = base - 36 * sc - jump
            pygame.draw.rect(surf, col, (sx - 11 * sc, hy + 10 * sc, 22 * sc, 40 * sc), border_radius=6)
            pygame.draw.circle(surf, lerp_color(col, (0, 0, 0), 0.2), (int(sx), int(hy)), int(10 * sc))
            if self.excite > 0.3 and math.sin(ph * 7) > 0:
                arm = hy + 8 - 16 * self.excite
                pygame.draw.line(surf, col, (sx - 9 * sc, hy + 14 * sc), (sx - 14 * sc, arm), 4)
                pygame.draw.line(surf, col, (sx + 9 * sc, hy + 14 * sc), (sx + 14 * sc, arm), 4)
        # bariyer
        pygame.draw.rect(surf, (30, 22, 36), (0, base - 6, W, 34))
        pygame.draw.line(surf, (255, 180, 80), (0, base - 6), (W, base - 6), 2)
        surf.blit(self.ground, (-cam_x, C.FLOOR_Y - 40))
