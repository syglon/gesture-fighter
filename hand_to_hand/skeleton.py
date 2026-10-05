"""Prosedürel iskelet animasyonu.

Her poz; kalça konumu, gövde eğimi ve el/ayak HEDEF noktalarıyla tanımlanır.
Dirsek ve dizler 2 kemikli ters kinematik (IK) ile hesaplanır. Böylece pozlar
kolayca yazılır, aralarında yumuşak geçiş (interpolasyon) yapılır ve ayaklar yere basar.

Koordinatlar "bakış çerçevesinde": x = dövüşçünün baktığı yön, y = yukarı, (0,0) = ayakların ortası.
"""
import math

import pygame

from gesture_fighter.draw import blit_glow, lerp_color, scale_color

TORSO, NECK, HEAD_R = 60, 6, 15
UA, FA = 30, 30   # üst kol, ön kol
TH, SH = 42, 42   # uyluk, baldır


def P(base=None, **kw):
    d = dict(POSES[base]) if base else {}
    d.update(kw)
    return d


POSES = {}
POSES["idle"] = dict(hx=0, hy=74, lean=10, head=-4, fh=(22, 16), bh=(12, 10), ff=(26, 0), bf=(-32, 0))
POSES["crouch"] = dict(hx=-2, hy=44, lean=22, head=-10, fh=(22, 12), bh=(12, 6), ff=(30, 0), bf=(-30, 0))
POSES["jump"] = dict(hx=0, hy=74, lean=6, head=-4, fh=(20, 18), bh=(10, 14), ff=(22, 36), bf=(-12, 30))
POSES["block"] = dict(hx=-6, hy=72, lean=-4, head=-10, fh=(16, 30), bh=(22, 22), ff=(24, 0), bf=(-34, 0))
POSES["c_block"] = P("crouch", lean=12, fh=(16, 26), bh=(20, 18))
# saldırılar (w = hazırlık / windup)
POSES["jab_w"] = P("idle", fh=(12, 14))
POSES["jab"] = dict(hx=6, hy=72, lean=14, head=-6, fh=(60, 4), bh=(8, 10), ff=(30, 0), bf=(-32, 0))
POSES["heavy_w"] = dict(hx=-6, hy=72, lean=0, head=-6, fh=(-6, 4), bh=(20, 16), ff=(28, 0), bf=(-36, 0))
POSES["heavy"] = dict(hx=20, hy=70, lean=26, head=-14, fh=(64, 4), bh=(-12, -8), ff=(46, 0), bf=(-40, 0))
POSES["kick_w"] = dict(hx=-4, hy=78, lean=-6, head=0, fh=(18, 18), bh=(8, 10), ff=(30, 46), bf=(-14, 0))
POSES["kick"] = dict(hx=-6, hy=80, lean=-22, head=10, fh=(14, 20), bh=(-14, 6), ff=(100, 94), bf=(-12, 0))
POSES["c_jab_w"] = P("crouch", fh=(12, 8))
POSES["c_jab"] = P("crouch", hx=4, lean=26, fh=(58, 0))
POSES["sweep_w"] = P("crouch", hy=40, lean=30, fh=(20, -20), bh=(10, -10), ff=(40, 4))
POSES["sweep"] = dict(hx=-10, hy=30, lean=42, head=-30, fh=(22, -42), bh=(6, -30), ff=(106, 6), bf=(-26, 0))
POSES["upper_w"] = P("crouch", fh=(6, -4), lean=26)
POSES["upper"] = dict(hx=6, hy=86, lean=-4, head=4, fh=(22, 64), bh=(-6, 4), ff=(14, 4), bf=(-24, 0))
POSES["j_punch"] = P("jump", lean=18, fh=(56, -24), bh=(6, 10))
POSES["j_heavy_w"] = P("jump", lean=-6, fh=(-8, 30))
POSES["j_kick"] = P("jump", lean=-12, ff=(72, -12), bf=(-14, 34), fh=(14, 22), bh=(-12, 16))
POSES["fire_w"] = dict(hx=-8, hy=68, lean=-4, head=-6, fh=(-20, -44), bh=(-26, -40), ff=(34, 0), bf=(-40, 0))
POSES["fire"] = dict(hx=12, hy=68, lean=18, head=-8, fh=(64, -6), bh=(58, 2), ff=(42, 0), bf=(-44, 0))
# tepkiler
POSES["hit"] = dict(hx=-12, hy=72, lean=-22, head=-22, fh=(0, -16), bh=(-14, -10), ff=(30, 0), bf=(-26, 0))
POSES["c_hit"] = P("crouch", lean=-4, head=-24, fh=(2, -10), bh=(-8, -8))
POSES["air_hit"] = dict(hx=0, hy=70, lean=-55, head=-20, fh=(-10, 30), bh=(-24, 20), ff=(40, 40), bf=(24, 20))
POSES["down"] = dict(hx=0, hy=16, lean=-84, head=0, fh=(-14, -6), bh=(-4, -12), ff=(62, 2), bf=(52, 10))
POSES["win"] = dict(hx=0, hy=76, lean=2, head=8, fh=(10, 62), bh=(14, -22), ff=(22, 0), bf=(-26, 0))
POSES["intro"] = dict(hx=0, hy=76, lean=38, head=14, fh=(10, -34), bh=(4, -34), ff=(16, 0), bf=(-16, 0))


def lerp_pose(a, b, t):
    out = {}
    for k, va in a.items():
        vb = b[k]
        if isinstance(va, tuple):
            out[k] = (va[0] + (vb[0] - va[0]) * t, va[1] + (vb[1] - va[1]) * t)
        else:
            out[k] = va + (vb - va) * t
    return out


def _ik(root, target, l1, l2, prefer):
    dx, dy = target[0] - root[0], target[1] - root[1]
    d = math.hypot(dx, dy)
    if d < 1e-6:
        dx, d = 1e-6, 1e-6
    ux, uy = dx / d, dy / d
    reach = l1 + l2 - 0.01
    if d >= reach:  # hedef uzakta: uzuv dümdüz uzanır
        return (root[0] + ux * l1, root[1] + uy * l1), (root[0] + ux * reach, root[1] + uy * reach)
    d = max(d, abs(l1 - l2) + 0.01)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    px, py = root[0] + ux * a, root[1] + uy * a
    c1 = (px - uy * h, py + ux * h)
    c2 = (px + uy * h, py - ux * h)
    if prefer == "forward":      # dizler öne
        joint = c1 if c1[0] >= c2[0] else c2
    else:                        # dirsekler aşağı
        joint = c1 if c1[1] <= c2[1] else c2
    return joint, (root[0] + ux * d, root[1] + uy * d)


def solve(p):
    hip = (p["hx"], p["hy"])
    a = math.radians(p["lean"])
    tdir = (math.sin(a), math.cos(a))
    neck = (hip[0] + tdir[0] * TORSO, hip[1] + tdir[1] * TORSO)
    ha = a + math.radians(p["head"])
    head = (neck[0] + math.sin(ha) * (NECK + HEAD_R), neck[1] + math.cos(ha) * (NECK + HEAD_R))
    sh = (hip[0] + tdir[0] * (TORSO - 8), hip[1] + tdir[1] * (TORSO - 8))
    shf, shb = (sh[0] + 3, sh[1]), (sh[0] - 5, sh[1] + 1)
    ef, hf = _ik(shf, (shf[0] + p["fh"][0], shf[1] + p["fh"][1]), UA, FA, "down")
    eb, hb = _ik(shb, (shb[0] + p["bh"][0], shb[1] + p["bh"][1]), UA, FA, "down")
    hipf, hipb = (hip[0] + 3, hip[1]), (hip[0] - 4, hip[1])
    kf, ff = _ik(hipf, p["ff"], TH, SH, "forward")
    kb, bf = _ik(hipb, p["bf"], TH, SH, "forward")
    return dict(hip=hip, neck=neck, head=head, tdir=tdir, ha=ha, shf=shf, shb=shb, ef=ef, hf=hf, eb=eb, hb=hb,
                hipf=hipf, hipb=hipb, kf=kf, ff=ff, kb=kb, bf=bf)


OUTLINE = (16, 12, 22)


def render(surf, j, ox, oy, facing, col, t, flash=0.0, aura=None, scale=1.0):
    """j: solve() çıktısı; (ox, oy): ekranda ayakların ortası."""

    sc = scale

    def S(p):
        return (ox + facing * p[0] * sc, oy - p[1] * sc)

    def c(rgb, k=1.0):
        rgb = scale_color(rgb, k)
        return lerp_color(rgb, (255, 255, 255), flash) if flash > 0 else rgb

    def limb(a, b, w, color):
        A, B = S(a), S(b)
        w = max(2, int(w * sc))
        pygame.draw.line(surf, OUTLINE, A, B, w + 5)
        for P_ in (A, B):
            pygame.draw.circle(surf, OUTLINE, (int(P_[0]), int(P_[1])), (w + 5) // 2)
        pygame.draw.line(surf, color, A, B, w)
        for P_ in (A, B):
            pygame.draw.circle(surf, color, (int(P_[0]), int(P_[1])), w // 2)

    def foot(knee, ankle, color):
        sx, sy = ankle[0] - knee[0], ankle[1] - knee[1]
        n = math.hypot(sx, sy) or 1
        fx, fy = -sy / n, sx / n  # baldırı 90° döndür -> parmaklar öne
        if fx < 0:
            fx, fy = -fx, -fy
        tip = (ankle[0] + fx * 14, ankle[1] + fy * 14)
        limb(ankle, tip, 8, color)

    def fist(p, color):
        Pp = S(p)
        pygame.draw.circle(surf, OUTLINE, (int(Pp[0]), int(Pp[1])), int(10 * sc))
        pygame.draw.circle(surf, color, (int(Pp[0]), int(Pp[1])), int(8 * sc))
        pygame.draw.circle(surf, scale_color(color, 1.3), (int(Pp[0] - 2 * sc), int(Pp[1] - 3 * sc)), int(3 * sc))

    if aura is not None:
        blit_glow(surf, S((j["hip"][0], j["hip"][1] + 30)), 130 * sc, aura)

    gi, skin, glove = col["gi"], col["skin"], col["glove"]
    # --- arka kol ve bacak (koyu)
    limb(j["shb"], j["eb"], 13, c(gi, 0.72))
    limb(j["eb"], j["hb"], 10, c(skin, 0.75))
    fist(j["hb"], c(glove, 0.7))
    limb(j["hipb"], j["kb"], 17, c(gi, 0.72))
    limb(j["kb"], j["bf"], 15, c(gi, 0.72))
    foot(j["kb"], j["bf"], c(skin, 0.72))

    # --- gövde
    hip, neck, td = j["hip"], j["neck"], j["tdir"]
    n = (td[1], -td[0])
    top = (neck[0] - td[0] * 4, neck[1] - td[1] * 4)
    poly = [(hip[0] + n[0] * 14, hip[1] + n[1] * 14), (top[0] + n[0] * 18, top[1] + n[1] * 18),
            (top[0] - n[0] * 16, top[1] - n[1] * 16), (hip[0] - n[0] * 13, hip[1] - n[1] * 13)]
    sp = [S(p) for p in poly]
    pygame.draw.polygon(surf, c(gi), sp)
    pygame.draw.polygon(surf, OUTLINE, sp, int(3 * sc))
    # yaka (V)
    chest = (hip[0] + td[0] * 24 + n[0] * 4, hip[1] + td[1] * 24 + n[1] * 4)
    pygame.draw.line(surf, c(gi, 0.7), S((top[0] + n[0] * 10, top[1] + n[1] * 10)), S(chest), int(3 * sc))
    pygame.draw.line(surf, c(gi, 0.7), S((top[0] - n[0] * 6, top[1] - n[1] * 6)), S(chest), int(3 * sc))
    pygame.draw.polygon(surf, c(skin), [S((top[0] + n[0] * 9, top[1] + n[1] * 9)), S(chest),
                                         S((top[0] - n[0] * 5, top[1] - n[1] * 5))])
    # kemer
    b0 = (hip[0] + td[0] * 6, hip[1] + td[1] * 6)
    limb((b0[0] + n[0] * 14, b0[1] + n[1] * 14), (b0[0] - n[0] * 13, b0[1] - n[1] * 13), 6, c(col["belt"]))
    knot = (b0[0] + n[0] * 12, b0[1] + n[1] * 12)
    sway = math.sin(t * 9) * 4
    for k in (0, 1):
        end = (knot[0] + 4 + k * 5 + sway * 0.5, knot[1] - 20 + k * 3)
        pygame.draw.line(surf, c(col["belt"]), S(knot), S(end), int(4 * sc))

    # --- ön bacak
    limb(j["hipf"], j["kf"], 17, c(gi))
    limb(j["kf"], j["ff"], 15, c(gi))
    foot(j["kf"], j["ff"], c(skin))

    # --- kafa
    ha = j["ha"]
    up = (math.sin(ha), math.cos(ha))
    fw = (math.cos(ha), -math.sin(ha))
    hc = j["head"]
    pygame.draw.line(surf, OUTLINE, S(neck), S(hc), int(13 * sc))
    pygame.draw.line(surf, c(skin), S(neck), S(hc), int(8 * sc))
    Hs = S(hc)
    pygame.draw.circle(surf, OUTLINE, (int(Hs[0]), int(Hs[1])), int((HEAD_R + 3) * sc))
    pygame.draw.circle(surf, c(skin), (int(Hs[0]), int(Hs[1])), int(HEAD_R * sc))
    hair_c = S((hc[0] - fw[0] * 4 + up[0] * 4, hc[1] - fw[1] * 4 + up[1] * 4))
    pygame.draw.circle(surf, c(col["hair"]), (int(hair_c[0]), int(hair_c[1])), int((HEAD_R - 2) * sc))
    face_c = S((hc[0] + fw[0] * 3 - up[0] * 2, hc[1] + fw[1] * 3 - up[1] * 2))
    pygame.draw.circle(surf, c(skin), (int(face_c[0]), int(face_c[1])), int((HEAD_R - 4) * sc))
    eye = (hc[0] + fw[0] * 9 + up[0] * 1, hc[1] + fw[1] * 9 + up[1] * 1)
    eye2 = (eye[0] - fw[0] * 4, eye[1] - fw[1] * 4)
    pygame.draw.line(surf, OUTLINE, S(eye), S(eye2), int(3 * sc))
    # alın bandı ve uçuşan uçları
    bf_ = (hc[0] + fw[0] * 14 + up[0] * 6, hc[1] + fw[1] * 14 + up[1] * 6)
    bb_ = (hc[0] - fw[0] * 14 + up[0] * 6, hc[1] - fw[1] * 14 + up[1] * 6)
    pygame.draw.line(surf, c(col["band"]), S(bf_), S(bb_), int(5 * sc))
    for k in (0, 1):
        pts = [S(bb_)]
        for i in range(1, 5):
            wave = math.sin(t * 12 + i * 0.9 + k) * 2.5 * i / 2
            pts.append(S((bb_[0] - i * 8, bb_[1] - i * (1.5 + k * 2) + wave)))
        pygame.draw.lines(surf, c(col["band"]), False, pts, int(4 * sc))

    # --- ön kol
    limb(j["shf"], j["ef"], 13, c(gi))
    limb(j["ef"], j["hf"], 10, c(skin))
    fist(j["hf"], c(glove))
