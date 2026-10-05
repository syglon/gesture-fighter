"""Çizim yardımcıları: parıltı (glow), yazılar, barlar, el hareketi ikonları, arka plan."""
import random

import numpy as np
import pygame

from . import config as C
from .gestures import Gesture

# ---------------------------------------------------------------- glow
_glow_cache = {}


def glow(radius, color):
    radius = max(2, int(radius))
    color = tuple(int(c) for c in color)
    key = (radius, color)
    surf = _glow_cache.get(key)
    if surf is None:
        if len(_glow_cache) > 600:
            _glow_cache.clear()
        size = radius * 2
        yy, xx = np.mgrid[0:size, 0:size]
        d = np.sqrt((xx - radius + 0.5) ** 2 + (yy - radius + 0.5) ** 2) / radius
        f = np.clip(1.0 - d, 0.0, 1.0) ** 2
        arr = np.empty((size, size, 3), dtype=np.uint8)
        for i in range(3):
            arr[..., i] = (f * color[i]).astype(np.uint8)
        surf = pygame.surfarray.make_surface(arr.swapaxes(0, 1))
        _glow_cache[key] = surf
    return surf


def blit_glow(target, pos, radius, color):
    r = max(2, int(radius))
    target.blit(glow(r, color), (int(pos[0]) - r, int(pos[1]) - r), special_flags=pygame.BLEND_ADD)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale_color(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


# ---------------------------------------------------------------- text
class Fonts:
    def __init__(self):
        path = pygame.font.match_font("dejavusans,liberationsans,arial,freesans", bold=True)
        self._path = path
        self._cache = {}
        self.huge = self.get(110)
        self.big = self.get(60)
        self.mid = self.get(34)
        self.small = self.get(22)
        self.tiny = self.get(16)

    def get(self, size):
        f = self._cache.get(size)
        if f is None:
            f = pygame.font.Font(self._path, size)
            self._cache[size] = f
        return f


_text_cache = {}


def render_text(font, text, color):
    key = (id(font), text, color)
    s = _text_cache.get(key)
    if s is None:
        if len(_text_cache) > 800:
            _text_cache.clear()
        s = font.render(text, True, color)
        _text_cache[key] = s
    return s


def text(surf, font, s, pos, color=C.WHITE, anchor="center", shadow=True, alpha=255):
    img = render_text(font, s, tuple(color))
    rect = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    if shadow:
        sh = render_text(font, s, (0, 0, 0))
        if alpha < 255:
            sh = sh.copy()
            sh.set_alpha(alpha)
        off = max(2, font.get_height() // 18)
        surf.blit(sh, rect.move(off, off))
    surf.blit(img, rect)
    return rect


# ---------------------------------------------------------------- UI
def panel(surf, rect, color=C.C_UI_BG, alpha=190, border=None, radius=10, width=2):
    rect = pygame.Rect(rect)
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
    surf.blit(s, rect.topleft)
    if border is not None:
        pygame.draw.rect(surf, border, rect, width, border_radius=radius)


def bar(surf, rect, frac, color, ghost=None, back=(25, 25, 40), border=(230, 230, 245), reverse=False):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surf, back, rect, border_radius=5)
    inner = rect.inflate(-6, -6)

    def part(f, col):
        f = max(0.0, min(1.0, f))
        w = int(inner.w * f)
        if w <= 0:
            return
        r = pygame.Rect(inner.x, inner.y, w, inner.h)
        if reverse:
            r.right = inner.right
        pygame.draw.rect(surf, col, r, border_radius=3)

    if ghost is not None and ghost > frac:
        part(ghost, (255, 255, 255))
    part(frac, color)
    # parlaklık şeridi
    if frac > 0:
        hl = pygame.Rect(inner.x, inner.y, int(inner.w * max(0.0, min(1.0, frac))), max(2, inner.h // 3))
        if reverse:
            hl.right = inner.right
        pygame.draw.rect(surf, scale_color(color, 1.35), hl, border_radius=3)
    pygame.draw.rect(surf, border, rect, 2, border_radius=5)


# ---------------------------------------------------------------- gesture icon
_FINGER_PATTERN = {
    Gesture.FIST: (0, 0, 0, 0),
    Gesture.PALM: (1, 1, 1, 1),
    Gesture.POINT: (1, 0, 0, 0),
    Gesture.PEACE: (1, 1, 0, 0),
}
_FINGER_LEN = (0.42, 0.48, 0.44, 0.34)


def gesture_icon(surf, g, center, size, color, outline=(15, 15, 25)):
    """Basit vektörel el ikonu çizer (emoji fontuna gerek kalmasın diye)."""
    cx, cy = center
    s = size
    if g not in _FINGER_PATTERN:
        text(surf, pygame.font.Font(None, int(s)), "?", center, color)
        return
    pattern = _FINGER_PATTERN[g]
    palm = pygame.Rect(0, 0, int(s * 0.62), int(s * 0.46))
    palm.midtop = (cx, int(cy - s * 0.02))
    fw = max(3, int(s * 0.13))
    gap = (palm.w - 4 * fw) / 5
    rects = []
    for i in range(4):
        x = palm.x + gap + i * (fw + gap)
        if pattern[i]:
            h = int(s * _FINGER_LEN[i])
            r = pygame.Rect(int(x), palm.y - h + fw // 2, fw, h + fw)
        else:
            r = pygame.Rect(int(x), palm.y - int(s * 0.07), fw, int(s * 0.2))
        rects.append(r)
    # başparmak
    if g is Gesture.PALM:
        thumb = pygame.Rect(0, 0, int(s * 0.32), fw)
        thumb.midright = (palm.x + fw // 2, palm.centery - int(s * 0.02))
    else:
        thumb = pygame.Rect(0, 0, int(s * 0.36), fw)
        thumb.midleft = (palm.x + int(fw * 0.3), palm.y + int(s * 0.16))
    shapes = rects + [palm, thumb]
    o = max(2, int(s * 0.04))
    for r in shapes:
        pygame.draw.rect(surf, outline, r.inflate(o * 2, o * 2), border_radius=fw)
    for r in [palm] + rects:
        pygame.draw.rect(surf, color, r, border_radius=fw // 2 + 1)
    pygame.draw.rect(surf, scale_color(color, 0.8), thumb, border_radius=fw // 2 + 1)


# ---------------------------------------------------------------- background
def build_background():
    W, H = C.SCREEN_W, C.SCREEN_H
    bg = pygame.Surface((W, H))
    top, mid, bot = (8, 6, 22), (34, 14, 52), (12, 8, 26)
    for y in range(H):
        t = y / H
        col = lerp_color(top, mid, t / 0.85) if t < 0.85 else lerp_color(mid, bot, (t - 0.85) / 0.15)
        pygame.draw.line(bg, col, (0, y), (W, y))
    rng = random.Random(461)
    for _ in range(170):
        x, y = rng.randrange(W), rng.randrange(int(C.FLOOR_Y * 0.95))
        b = rng.randint(60, 200)
        r = 1 if rng.random() < 0.85 else 2
        pygame.draw.circle(bg, (b, b, min(255, b + 30)), (x, y), r)
    # uzak şehir/dağ silueti
    pts = [(0, C.FLOOR_Y)]
    x = 0
    while x <= W:
        pts.append((x, C.FLOOR_Y - rng.randint(30, 120)))
        x += rng.randint(30, 80)
    pts.append((W, C.FLOOR_Y))
    pygame.draw.polygon(bg, (24, 12, 40), pts)
    # zemin ızgarası (perspektif)
    floor = pygame.Rect(0, C.FLOOR_Y, W, H - C.FLOOR_Y)
    pygame.draw.rect(bg, (16, 8, 30), floor)
    hz = (W // 2, C.FLOOR_Y - 140)
    for i in range(-20, 21):
        x_bottom = W // 2 + i * 120
        pygame.draw.line(bg, (90, 40, 140), (lerp(hz[0], x_bottom, (C.FLOOR_Y - hz[1]) / (H - hz[1])), C.FLOOR_Y),
                         (x_bottom, H), 1)
    for k in range(1, 6):
        y = C.FLOOR_Y + int((H - C.FLOOR_Y) * (k / 6) ** 1.6)
        pygame.draw.line(bg, (90, 40, 140), (0, y), (W, y), 1)
    pygame.draw.line(bg, (200, 90, 255), (0, C.FLOOR_Y), (W, C.FLOOR_Y), 2)
    # ufuk parıltısı
    blit_glow(bg, (W // 2, C.FLOOR_Y), 520, (60, 20, 80))
    return bg
