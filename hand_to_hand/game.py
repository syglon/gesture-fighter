"""HAND TO HAND — ana oyun: menü, raundlar, vuruş çözümleme, mermiler ve arayüz."""
import dataclasses
import math
import random

import pygame

from gesture_fighter.draw import Fonts, blit_glow, gesture_icon, lerp_color, panel, scale_color, text
from gesture_fighter.fx import Particles, Shake
from gesture_fighter.gestures import GESTURE_COLOR, HAND_CONNECTIONS, Gesture

from . import config as C
from .ai import CPU
from .controls import KEYS_P1, KEYS_P2, Dummy, GestureJoystick, PlayerInput
from .fighter import Fighter, Intent
from .sounds import FightSounds
from .stage import Stage

W, H = C.W, C.H
DIFFS = ["easy", "normal", "hard"]
MODES = [  # (mod, menü gesture'ı, başlık, tuş)
    ("1p", Gesture.POINT, "1 PLAYER", "vs CPU", pygame.K_1),
    ("2p", Gesture.PEACE, "2 PLAYERS", "split camera", pygame.K_2),
    ("training", Gesture.PALM, "TRAINING", "practice moves", pygame.K_3),
]


class Projectile:
    def __init__(self, owner, move):
        self.owner = owner
        self.move = move
        self.kind = move.projectile
        sup = self.kind == "super"
        self.x = owner.x + owner.facing * 70 * C.SCALE
        self.y = owner.y + 108 * C.SCALE
        self.vx = owner.facing * (650 if sup else 560)
        self.r = (44 if sup else 26) * C.SCALE
        self.hits = 5 if sup else 1
        self.hit_cd = 0.0
        self.t = 0.0
        self.alive = True

    @property
    def color(self):
        return (255, 205, 70) if self.kind == "super" else (90, 170, 255)

    def rect(self):
        r = self.r * 0.85
        return pygame.Rect(int(self.x - r), int(C.FLOOR_Y - self.y - r), int(r * 2), int(r * 2))

    def update(self, dt, game):
        self.t += dt
        self.hit_cd -= dt
        self.x += self.vx * dt
        if self.x < -100 or self.x > C.STAGE_W + 100 or abs(self.x - game.cam_x - W / 2) > W * 0.75:
            self.alive = False
        for _ in range(2):
            a = random.uniform(0, math.tau)
            game.particles.emit(self.x + math.cos(a) * self.r * 0.6, C.FLOOR_Y - self.y + math.sin(a) * self.r * 0.6,
                                -self.vx * 0.25 + random.uniform(-40, 40), random.uniform(-40, 40),
                                self.color if random.random() < 0.7 else (255, 255, 255),
                                life=random.uniform(0.15, 0.35), size=random.uniform(2, 5))

    def draw(self, surf, cam_x):
        x, y = self.x - cam_x, C.FLOOR_Y - self.y
        col = self.color
        blit_glow(surf, (x, y), self.r * 2.6, scale_color(col, 0.8))
        pygame.draw.circle(surf, col, (int(x), int(y)), int(self.r * 0.75))
        for i in range(3):
            a = self.t * 14 + i * math.tau / 3
            rr = self.r * 0.75
            rect = pygame.Rect(0, 0, int(rr * 2), int(rr * 1.4))
            rect.center = (int(x), int(y))
            pygame.draw.arc(surf, (255, 255, 255), rect, a, a + 1.6, 3)
        pygame.draw.circle(surf, (255, 255, 255), (int(x), int(y)), int(self.r * 0.38))


class Game:
    def __init__(self, args):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        flags = pygame.SCALED | (pygame.FULLSCREEN if args.fullscreen else 0)
        self.screen = pygame.display.set_mode((W, H), flags)
        pygame.display.set_caption("HAND TO HAND — ME461")
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()
        self.sound = FightSounds(enabled=not args.mute)
        self.difficulty = args.difficulty
        self.max_frames = args.frames
        self.frame = 0

        self.tracker = None
        self.camera_msg = "Keyboard mode (--keyboard)"
        if not args.keyboard:
            from gesture_fighter.hand_tracker import HandTracker
            tr = HandTracker(args.camera, split=False, mirror=not args.no_mirror)
            ok, msg = tr.start()
            self.camera_msg = msg
            if ok:
                self.tracker = tr
            else:
                print(f"[game] {msg} — klavye moduna geçiliyor.")
        self.menu_js = GestureJoystick(self.tracker, 0, 0.5) if self.tracker else None

        self.stage = Stage(self.fonts)
        self.world = pygame.Surface((W, H))
        self.particles = Particles()
        self.shake = Shake()
        self.texts = []
        self.rings = []
        self._preview = (None, -1, None)
        self.debug = False
        self.paused = False
        self.running = True
        self.mode = "1p"
        self.t = 0.0
        self.setup_match("1p")
        self.go_title()

    # ================================================================== setup
    def set_state(self, s):
        self.state = s
        self.state_t = 0.0
        self.holds = {}
        self.hold_armed = False

    def go_title(self):
        self.paused = False
        if self.tracker:
            self.tracker.set_split(False)
        self.setup_match("1p")
        for f in self.fighters:
            f.set_state("idle")
        self.set_state("title")

    def setup_match(self, mode):
        self.mode = mode
        cx = C.STAGE_W / 2
        self.fighters = [Fighter(C.P1, cx - 260, 1), Fighter(C.P2, cx + 260, -1)]
        tr = self.tracker
        if tr:
            tr.set_split(mode == "2p")
        if mode == "2p":
            self.inputs = [PlayerInput(GestureJoystick(tr, 0, 0.25) if tr else None, KEYS_P1),
                           PlayerInput(GestureJoystick(tr, 1, 0.75) if tr else None, KEYS_P2)]
        elif mode == "training":
            self.inputs = [PlayerInput(GestureJoystick(tr, 0, 0.5) if tr else None, KEYS_P1), Dummy()]
        else:
            self.inputs = [PlayerInput(GestureJoystick(tr, 0, 0.5) if tr else None, KEYS_P1),
                           CPU(self.difficulty)]
        for f in self.fighters:
            f.meter = 0.0
            f.wins = 0
        self.round = 1
        self.stats = dict(max_combo=[0, 0], perfects=[0, 0])
        self.reset_round()

    def reset_round(self):
        cx = C.STAGE_W / 2
        self.fighters[0].reset(cx - 260, 1)
        self.fighters[1].reset(cx + 260, -1)
        self.projectiles = []
        self.texts = []
        self.rings = []
        self.particles.clear()
        self.timer = float(C.ROUND_TIME)
        self.hitstop = 0.0
        self.freeze = 0.0
        self.freeze_owner = None
        self.slowmo = 0.0
        self.banner = None
        self.round_winner = None
        self.combo_show = [None, None]
        self.cam_x = cx - W / 2
        self.training_refill = 0.0

    def start_match(self, mode):
        self.paused = False
        self.setup_match(mode)
        self.sound.play("go")
        if mode == "training":
            for f in self.fighters:
                f.set_state("idle")
            self.set_state("fight")
            self.show_banner("TRAINING", "B: dummy block on/off  ·  ESC: menu", (120, 220, 255), 2.5)
        else:
            self.set_state("intro")

    # ================================================================== loop
    def run(self):
        try:
            while self.running:
                dt = min(self.clock.tick(C.FPS) / 1000.0, 0.05)
                self.handle_events()
                self.update(dt)
                self.draw()
                pygame.display.flip()
                self.frame += 1
                if self.max_frames and self.frame >= self.max_frames:
                    self.running = False
        finally:
            if self.tracker:
                self.tracker.stop()
            pygame.quit()

    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.KEYDOWN:
                k = e.key
                if k == pygame.K_F1:
                    self.debug = not self.debug
                elif k == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif k == pygame.K_F2:
                    self.sound.enabled = not self.sound.enabled and bool(self.sound.sounds)
                elif self.state == "title":
                    if k == pygame.K_ESCAPE:
                        self.running = False
                    elif k == pygame.K_RETURN:
                        self.start_match("1p")
                    elif k in (pygame.K_LEFT, pygame.K_RIGHT):
                        i = (DIFFS.index(self.difficulty) + (1 if k == pygame.K_RIGHT else -1)) % len(DIFFS)
                        self.difficulty = DIFFS[i]
                        self.sound.play("blip")
                    for mode, _, _, _, key in MODES:
                        if k == key:
                            self.start_match(mode)
                elif self.state == "match_end":
                    if k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_r):
                        self.start_match(self.mode)
                    elif k == pygame.K_ESCAPE:
                        self.go_title()
                else:
                    if k in (pygame.K_ESCAPE, pygame.K_p):
                        if self.mode == "training" and k == pygame.K_ESCAPE:
                            self.go_title()
                        else:
                            self.paused = not self.paused
                    elif k == pygame.K_q and self.paused:
                        self.go_title()
                    elif k == pygame.K_b and self.mode == "training":
                        self.inputs[1].block = not self.inputs[1].block

    def hold(self, key, active, dt, duration=1.0, lockout=0.6):
        """Hareketi belirli süre tutunca True döner (menü seçimleri için)."""
        if not active:
            self.holds[key] = max(0.0, self.holds.get(key, 0.0) - dt * 2)
            return False
        if self.state_t < lockout:
            return False
        self.holds[key] = self.holds.get(key, 0.0) + dt / duration
        if self.holds[key] >= 1.0:
            self.holds[key] = 0.0
            return True
        return False

    # ================================================================== update
    def update(self, dt):
        self.t += dt
        if self.paused:
            return
        self.state_t += dt
        pressed = pygame.key.get_pressed()
        if self.state == "title":
            self.update_title(dt)
        elif self.state == "match_end":
            g = self.menu_gesture(dt)
            if g is not Gesture.PALM:
                self.hold_armed = True  # önce el bırakılmalı (blok tutarken kazara yeniden başlamasın)
            if self.hold("palm", g is Gesture.PALM and self.hold_armed, dt, 1.2, 1.5):
                self.start_match(self.mode)
            self.update_world(dt, [Intent(), Intent()])
        else:
            if self.state == "intro":
                self.update_intro()
            controls = self.state == "fight"
            intents = []
            for i, f in enumerate(self.fighters):
                opp = self.fighters[1 - i]
                it = self.inputs[i].read(dt, pressed, f, opp, self)
                intents.append(it if controls else Intent())
            if self.state == "fight" and self.mode != "training" and self.freeze <= 0:
                self.timer -= dt
                if self.timer <= 0:
                    self.timer = 0
                    self.time_over()
            if self.state == "round_end":
                self.update_round_end()
            self.update_world(dt, intents)

    def menu_gesture(self, dt):
        if self.menu_js is None:
            return Gesture.NONE
        self.menu_js.read(dt)
        return self.menu_js.gesture

    def update_title(self, dt):
        g = self.menu_gesture(dt)
        for mode, gesture, *_ in MODES:
            if self.hold(mode, g is gesture, dt, 1.0, 0.8):
                self.start_match(mode)
                return
        for f in self.fighters:
            f.update(dt, Intent(), self.fighters[1 - self.fighters.index(f)], self)
        self.stage.update(dt)
        self.update_camera(dt)

    def update_intro(self):
        if self.state_t >= 2.2:
            for f in self.fighters:
                f.set_state("idle")
            self.set_state("fight")

    def update_round_end(self):
        w = self.round_winner
        if w is not None and self.state_t > 1.8 and w.state in ("idle", "crouch", "walk", "block") and w.grounded:
            w.set_state("win")
        if self.state_t > 4.2:
            a, b = self.fighters
            if a.wins >= C.ROUNDS_TO_WIN or b.wins >= C.ROUNDS_TO_WIN:
                self.set_state("match_end")
                self.sound.play("win")
            else:
                self.round += 1
                self.reset_round()
                self.set_state("intro")

    def update_world(self, dt, intents):
        if self.freeze > 0:
            self.freeze -= dt
            dt_g = 0.0
        elif self.hitstop > 0:
            self.hitstop -= dt
            dt_g = 0.0
        else:
            dt_g = dt * (0.3 if self.slowmo > 0 else 1.0)
        self.slowmo = max(0.0, self.slowmo - dt)

        a, b = self.fighters
        prev = (a.x, b.x)
        for i, f in enumerate(self.fighters):
            f.update(dt_g, intents[i], self.fighters[1 - i], self)
        self.separate(prev)

        # vuruş kontrolü (önce ikisi de hesaplanır -> aynı anda vuruş = takas)
        hits = []
        for att, dfn in ((a, b), (b, a)):
            hb, hu = att.hitbox(), dfn.hurtbox()
            if hb is not None and hu is not None and hb.colliderect(hu):
                clip = hb.clip(hu)
                hits.append((att, dfn, att.move, clip.center, att.facing))
        for att, dfn, m, point, d in hits:
            att.move_hit = True
            self.resolve_hit(att, dfn, m, point, d)

        if dt_g > 0:
            for p in self.projectiles:
                p.update(dt_g, self)
        self.collide_projectiles()
        self.projectiles = [p for p in self.projectiles if p.alive]

        if self.mode == "training" and self.state == "fight":
            dummy, player = b, a
            player.meter = C.SUPER_COST
            if dummy.combo_taken == 0 and dummy.hp < C.MAX_HP:
                self.training_refill += dt
                if self.training_refill > 1.0:
                    dummy.hp = dummy.ghost_hp = float(C.MAX_HP)
                    self.training_refill = 0.0
            else:
                self.training_refill = 0.0

        self.particles.update(dt_g if dt_g > 0 else dt * 0.2)
        self.texts = [t for t in self.texts if t.update(dt)]
        self.rings = [r for r in self.rings if self._ring_update(r, dt)]
        for i in range(2):
            if self.combo_show[i]:
                n, tt = self.combo_show[i]
                self.combo_show[i] = (n, tt - dt) if tt - dt > 0 else None
        self.shake.update(dt)
        self.stage.update(dt)
        self.update_camera(dt)
        if self.banner:
            self.banner["t"] += dt
            if self.banner["t"] >= self.banner["dur"]:
                self.banner = None

    @staticmethod
    def _ring_update(r, dt):
        r[3] -= dt
        return r[3] > 0

    def separate(self, prev):
        a, b = self.fighters
        # itme kutuları
        if a.state not in ("down", "ko") and b.state not in ("down", "ko"):
            dx = b.x - a.x
            if abs(dx) < C.PUSH_WIDTH and abs(a.y - b.y) < 110:
                d = (1 if dx > 0 else -1) if dx != 0 else -a.facing
                overlap = C.PUSH_WIDTH - abs(dx)
                a.x -= d * overlap / 2
                b.x += d * overlap / 2
        # ekran içinde kal
        if abs(a.x - b.x) > C.MAX_SEPARATION:
            ma, mb = abs(a.x - prev[0]), abs(b.x - prev[1])
            mover, other = (a, b) if ma >= mb else (b, a)
            mover.x = max(other.x - C.MAX_SEPARATION, min(other.x + C.MAX_SEPARATION, mover.x))
        for f in self.fighters:
            f.x = max(C.STAGE_MARGIN, min(C.STAGE_W - C.STAGE_MARGIN, f.x))

    def update_camera(self, dt):
        a, b = self.fighters
        target = (a.x + b.x) / 2 - W / 2
        target = max(0.0, min(C.STAGE_W - W, target))
        self.cam_x += (target - self.cam_x) * min(1.0, dt * 8)

    # ------------------------------------------------------------------ combat
    def at_wall(self, f):
        return f.x <= C.STAGE_MARGIN + 4 or f.x >= C.STAGE_W - C.STAGE_MARGIN - 4

    def resolve_hit(self, att, dfn, m, point, direction, proj=None):
        if self.state not in ("fight", "round_end") or dfn.hp <= 0:
            return
        x, y = point
        if dfn.can_block(m):
            dfn.block_hit(m, direction)
            att.meter = min(C.SUPER_COST, att.meter + 2)
            dfn.meter = min(C.SUPER_COST, dfn.meter + 5)
            if self.at_wall(dfn) and proj is None:
                att.slide = -direction * m.push * 0.5
            self.particles.burst(x, y, (120, 200, 255), n=14, speed=(80, 300), life=(0.1, 0.3),
                                 angle=math.pi if direction > 0 else 0, spread=2.4)
            self.rings.append([x, y, (140, 210, 255), 0.18, 0.18])
            self.sound.play("block")
            self.hitstop = max(self.hitstop, 0.05)
            self.shake.add(2)
            if dfn.hp <= 0:
                self.on_ko(att, dfn)
            return
        scale = max(0.4, 1.0 - C.COMBO_SCALING * dfn.combo_taken)
        dmg = m.damage * scale
        if self.mode == "training":
            dmg = min(dmg, dfn.hp - 1)
        dfn.take_hit(att, m, dmg, direction)
        if self.at_wall(dfn) and proj is None:
            att.slide = -direction * m.push * 0.45
        att.meter = min(C.SUPER_COST, att.meter + dmg * 1.6)
        dfn.meter = min(C.SUPER_COST, dfn.meter + dmg * 0.8)
        att.last_label = m.label
        att.label_t = 1.2
        idx = self.fighters.index(att)
        if dfn.combo_taken >= 2:
            self.combo_show[idx] = (dfn.combo_taken, 1.6)
            self.stats["max_combo"][idx] = max(self.stats["max_combo"][idx], dfn.combo_taken)
        big = m.damage >= 10
        self.hitstop = max(self.hitstop, m.hitstop)
        self.shake.add(3 + dmg * 0.7)
        col = (255, 230, 120) if not big else (255, 160, 60)
        self.particles.burst(x, y, col, n=22 if big else 14, speed=(120, 520), life=(0.12, 0.35), size=(2, 5),
                             angle=0 if direction > 0 else math.pi, spread=2.2)
        self.particles.burst(x, y, (255, 255, 255), n=6, speed=(50, 200), life=(0.08, 0.2))
        self.rings.append([x, y, col, 0.22, 0.22])
        self.sound.play(m.sound)
        self.stage.cheer(0.12 + dmg * 0.03)
        if dfn.hp <= 0:
            self.on_ko(att, dfn)

    def collide_projectiles(self):
        ps = self.projectiles
        for i, p in enumerate(ps):
            if not p.alive:
                continue
            for q in ps[i + 1:]:
                if q.alive and q.owner is not p.owner and p.rect().colliderect(q.rect()):
                    for z, other in ((p, q), (q, p)):
                        if z.kind == "super" and other.kind == "fireball":
                            z.hits -= 1
                            z.alive = z.hits > 0
                        else:
                            z.alive = False
                    mx, my = (p.x + q.x) / 2 - self.cam_x, C.FLOOR_Y - (p.y + q.y) / 2
                    self.particles.burst(mx + self.cam_x, my, (200, 220, 255), n=30, speed=(80, 400),
                                         life=(0.2, 0.5))
                    self.sound.play("block")
        for p in ps:
            if not p.alive or p.hit_cd > 0:
                continue
            dfn = self.fighters[1] if p.owner is self.fighters[0] else self.fighters[0]
            hu = dfn.hurtbox()
            if hu is None or not p.rect().colliderect(hu):
                continue
            m = p.move
            if p.kind == "super" and p.hits == 1:
                m = dataclasses.replace(m, knockdown=True, launch=560, push=320, damage=10)
            p.hits -= 1
            p.hit_cd = 0.09
            if p.hits <= 0:
                p.alive = False
            self.resolve_hit(p.owner, dfn, m, p.rect().clip(hu).center, 1 if p.vx > 0 else -1, proj=p)

    # ------------------------------------------------------------------ events from fighters
    def has_fireball(self, f):
        return any(p.alive and p.owner is f for p in self.projectiles)

    def spawn_projectile(self, f, m):
        self.projectiles.append(Projectile(f, m))
        self.sound.play("handouken")
        f.last_label = m.label
        f.label_t = 1.2

    def on_super(self, f):
        self.freeze = 0.75
        self.freeze_owner = f
        self.sound.play("special")
        self.stage.cheer(1.0)
        self.shake.add(6)

    def on_jump(self, f):
        self.particles.burst(f.x, C.FLOOR_Y, (180, 160, 150), n=8, speed=(40, 140), life=(0.2, 0.4),
                             angle=-math.pi / 2, spread=2.6, glow=False)

    def on_land(self, f, heavy=False):
        self.particles.burst(f.x, C.FLOOR_Y, (180, 160, 150), n=16 if heavy else 8, speed=(60, 220),
                             life=(0.2, 0.5), angle=-math.pi / 2, spread=2.8, glow=False)
        self.sound.play("land", 0.8 if heavy else 0.4)
        if heavy:
            self.shake.add(8)

    def on_ko(self, winner, loser):
        if self.state != "fight":
            return
        self.set_state("round_end")
        self.round_winner = winner
        winner.wins += 1
        perfect = winner.hp >= C.MAX_HP
        if perfect:
            self.stats["perfects"][self.fighters.index(winner)] += 1
        self.slowmo = 1.4
        self.hitstop = 0.25
        self.show_banner("PERFECT!" if perfect else "K.O.", None, (255, 80, 60), 2.2)
        self.sound.play("explosion")
        self.sound.play("roar", 0.6)
        self.shake.add(22)
        self.stage.cheer(1.0)
        self.particles.burst(loser.x, C.FLOOR_Y - loser.y - 120, (255, 220, 120), n=70, speed=(100, 700),
                             life=(0.3, 1.0), size=(2, 6))

    def time_over(self):
        a, b = self.fighters
        self.set_state("round_end")
        if abs(a.hp - b.hp) < 0.5:
            self.round_winner = None
            a.wins += 1
            b.wins += 1
            sub = "DRAW"
        else:
            self.round_winner = a if a.hp > b.hp else b
            self.round_winner.wins += 1
            sub = f"{self.round_winner.name} wins the round"
        self.show_banner("TIME OVER", sub, (255, 200, 80), 2.6)
        self.sound.play("go")

    def show_banner(self, s, sub, color, dur):
        self.banner = dict(text=s, sub=sub, color=color, t=0.0, dur=dur)

    # ================================================================== draw
    def draw(self):
        w = self.world
        self.stage.draw(w, self.cam_x, self.t)
        if self.freeze > 0:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 20, 170))
            w.blit(ov, (0, 0))
            f = self.freeze_owner
            if f:
                blit_glow(w, (f.x - self.cam_x, C.FLOOR_Y - f.y - 120), 300, scale_color(f.colors["aura"], 0.6))
        # saldıran öne çizilir
        order = sorted(self.fighters, key=lambda f: 1 if f.state == "attack" else 0)
        for f in order:
            f.draw(w, self.cam_x)
        for p in self.projectiles:
            p.draw(w, self.cam_x)
        # partikülleri kamera ofsetiyle çiz
        cam = pygame.Vector2(self.cam_x, 0)
        for it in self.particles.items:
            it[0] -= cam.x
        self.particles.draw(w)
        for it in self.particles.items:
            it[0] += cam.x
        for x, y, col, life, max_life in self.rings:
            k = 1 - life / max_life
            pygame.draw.circle(w, col, (int(x - self.cam_x), int(y)), int(12 + 60 * k), max(1, int(6 * (1 - k))))
        for tx in self.texts:
            tx.draw(w)
        ox, oy = self.shake.offset()
        self.screen.fill((0, 0, 0))
        self.screen.blit(w, (ox, oy))

        if self.state == "title":
            self.draw_title()
        else:
            self.draw_hud()
            if self.state == "intro":
                self.draw_intro()
            elif self.state == "match_end":
                self.draw_match_end()
        if self.freeze > 0 and self.freeze_owner:
            k = min(1.0, (0.75 - self.freeze) / 0.15)
            text(self.screen, self.fonts.get(int(70 + 20 * k)), "SHIN HANDOUKEN!", (W // 2, H // 2 - 40),
                 self.freeze_owner.colors["aura"], alpha=int(255 * k))
        self.draw_banner()
        if self.paused:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 160))
            self.screen.blit(ov, (0, 0))
            text(self.screen, self.fonts.big, "PAUSED", (W // 2, H // 2 - 30))
            text(self.screen, self.fonts.small, "ESC / P: resume     Q: main menu", (W // 2, H // 2 + 30))
        if self.debug:
            self.draw_debug()

    # ------------------------------------------------------------------ HUD
    def draw_health(self, f, rect, reverse):
        s = self.screen
        pygame.draw.rect(s, (20, 14, 24), rect.inflate(8, 8), border_radius=4)
        pygame.draw.rect(s, (120, 20, 20), rect)
        inner = rect.copy()

        def part(frac, col):
            w = int(inner.w * max(0.0, min(1.0, frac)))
            r = pygame.Rect(inner.x, inner.y, w, inner.h)
            if reverse:
                r.right = inner.right
            pygame.draw.rect(s, col, r)

        part(f.ghost_hp / C.MAX_HP, (255, 70, 50))
        frac = f.hp / C.MAX_HP
        col = C.C_HP if frac > 0.25 else (C.C_HP_LOW if int(self.t * 6) % 2 else C.C_HP)
        part(frac, col)
        hl = pygame.Rect(inner.x, inner.y + 3, inner.w, 5)
        part_surf = pygame.Surface(hl.size, pygame.SRCALPHA)
        part_surf.fill((255, 255, 255, 60))
        s.blit(part_surf, hl.topleft)
        pygame.draw.rect(s, (250, 240, 220), rect.inflate(8, 8), 3, border_radius=4)

    def draw_hud(self):
        s, F = self.screen, self.fonts
        a, b = self.fighters
        r1 = pygame.Rect(40, 22, 500, 30)
        r2 = pygame.Rect(W - 540, 22, 500, 30)
        self.draw_health(a, r1, reverse=True)
        self.draw_health(b, r2, reverse=False)
        name2 = b.name + (" (CPU)" if self.mode == "1p" else " (DUMMY)" if self.mode == "training" else "")
        text(s, F.small, a.name, (r1.x, r1.bottom + 8), C.WHITE, "topleft")
        text(s, F.small, name2, (r2.right, r2.bottom + 8), C.WHITE, "topright")
        # süre
        box = pygame.Rect(W // 2 - 50, 10, 100, 62)
        panel(s, box, color=(20, 14, 24), alpha=230, border=(250, 240, 220), radius=8, width=3)
        tval = "∞" if self.mode == "training" else str(int(math.ceil(self.timer)))
        tcol = (255, 90, 70) if self.mode != "training" and self.timer < 10 else C.YELLOW
        text(s, F.big, tval, box.center, tcol)
        # raund galibiyetleri
        if self.mode != "training":
            for i in range(C.ROUNDS_TO_WIN):
                for k, f in enumerate(self.fighters):
                    x = W // 2 - 76 - i * 26 if k == 0 else W // 2 + 76 + i * 26
                    won = f.wins > i
                    pygame.draw.circle(s, (20, 14, 24), (x, 66), 10)
                    pygame.draw.circle(s, C.YELLOW if won else (80, 70, 90), (x, 66), 8)
        # süper barlar
        for k, f in enumerate(self.fighters):
            rr = pygame.Rect(40, H - 36, 300, 18) if k == 0 else pygame.Rect(W - 340, H - 36, 300, 18)
            pygame.draw.rect(s, (20, 14, 24), rr.inflate(6, 6), border_radius=4)
            full = f.meter >= C.SUPER_COST
            w_ = int(rr.w * f.meter / C.SUPER_COST)
            fill = pygame.Rect(rr.x, rr.y, w_, rr.h)
            if k == 1:
                fill.right = rr.right
            col = C.C_SUPER if not full else lerp_color(C.C_SUPER, C.WHITE, 0.5 + 0.5 * math.sin(self.t * 10))
            if full:
                blit_glow(s, rr.center, 160, scale_color(C.C_SUPER, 0.35))
            pygame.draw.rect(s, col, fill, border_radius=3)
            pygame.draw.rect(s, (220, 230, 255), rr.inflate(6, 6), 2, border_radius=4)
            lab = "SUPER  MAX!" if full else "SUPER"
            if k == 0:
                text(s, F.tiny, lab, (rr.x, rr.y - 20), C.C_SUPER if not full else C.YELLOW, "topleft")
            else:
                text(s, F.tiny, lab, (rr.right, rr.y - 20), C.C_SUPER if not full else C.YELLOW, "topright")
        # kombo ve hamle isimleri
        for k, f in enumerate(self.fighters):
            x = 150 if k == 0 else W - 150
            cs = self.combo_show[k]
            if cs:
                n, tt = cs
                alpha = int(255 * min(1.0, tt / 0.4))
                text(s, F.get(64), f"{n} HITS", (x, 250), C.YELLOW, alpha=alpha)
                text(s, F.small, "COMBO!", (x, 292), C.WHITE, alpha=alpha)
            if f.label_t > 0 and f.last_label:
                text(s, F.small, f.last_label, (x, 330), f.colors["aura"], alpha=int(255 * min(1.0, f.label_t / 0.3)))
        # girdi göstergeleri ve kamera
        for k in range(2):
            inp = self.inputs[k]
            js = getattr(inp, "joystick", None)
            if js is not None:
                x = 40 if k == 0 else W - 40 - 130
                self.draw_input_display(js, pygame.Rect(x, 84, 130, 56))
        if self.tracker:
            self.draw_preview(pygame.Rect(W // 2 - 112, 84, 224, 168), small=True)
        if self.mode == "training":
            self.draw_training_panel()

    def draw_input_display(self, js, rect):
        s = self.screen
        panel(s, rect, color=(14, 10, 22), alpha=180, radius=8)
        cx, cy = rect.x + 28, rect.centery
        mx, my = js.zone
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            on = (dx != 0 and dx == mx) or (dy != 0 and dy == my)
            pts = {(-1, 0): [(cx - 22, cy), (cx - 10, cy - 8), (cx - 10, cy + 8)],
                   (1, 0): [(cx + 22, cy), (cx + 10, cy - 8), (cx + 10, cy + 8)],
                   (0, -1): [(cx, cy - 22), (cx - 8, cy - 10), (cx + 8, cy - 10)],
                   (0, 1): [(cx, cy + 22), (cx - 8, cy + 10), (cx + 8, cy + 10)]}[(dx, dy)]
            pygame.draw.polygon(s, C.YELLOW if on else (70, 64, 90), pts)
        pygame.draw.circle(s, (120, 120, 140) if js.visible else (200, 60, 60), (cx, cy), 5)
        g = js.gesture
        if js.visible and g is not Gesture.NONE:
            gesture_icon(s, g, (rect.x + 82, rect.centery + 2), 34, GESTURE_COLOR[g])
        elif not js.visible:
            text(s, self.fonts.tiny, "no hand", (rect.x + 88, rect.centery), (230, 100, 100))
        if js.thrust_flash > 0:
            text(s, self.fonts.small, "POWER!", (rect.centerx, rect.bottom + 14), (255, 160, 60))

    def draw_zones(self, rect, js, center_x, x_lo, x_hi):
        s = self.screen
        x0 = rect.x + (center_x - C.DEAD_X) * rect.w
        x1 = rect.x + (center_x + C.DEAD_X) * rect.w
        xl, xr = rect.x + x_lo * rect.w, rect.x + x_hi * rect.w
        yj = rect.y + C.JUMP_Y * rect.h
        yc = rect.y + C.CROUCH_Y * rect.h
        if js is not None and js.visible:
            mx, my = js.zone
            ov = pygame.Surface(rect.size, pygame.SRCALPHA)
            if my == -1:
                pygame.draw.rect(ov, (255, 220, 60, 60), (xl - rect.x, 0, xr - xl, yj - rect.y))
            if my == 1:
                pygame.draw.rect(ov, (255, 220, 60, 60), (xl - rect.x, yc - rect.y, xr - xl, rect.bottom - yc))
            if mx == -1:
                pygame.draw.rect(ov, (80, 200, 255, 50), (xl - rect.x, 0, x0 - xl, rect.h))
            if mx == 1:
                pygame.draw.rect(ov, (80, 200, 255, 50), (x1 - rect.x, 0, xr - x1, rect.h))
            s.blit(ov, rect.topleft)
        col = (255, 255, 255)
        for x in (x0, x1):
            pygame.draw.line(s, col, (x, rect.y), (x, rect.bottom), 1)
        for y in (yj, yc):
            for x in range(int(xl), int(xr), 12):
                pygame.draw.line(s, col, (x, y), (min(x + 6, xr), y), 1)
        F = self.fonts.tiny
        text(s, F, "JUMP", ((xl + xr) / 2, rect.y + 12), C.YELLOW)
        text(s, F, "CROUCH", ((xl + xr) / 2, rect.bottom - 12), C.YELLOW)
        text(s, F, "◀", (xl + 12, rect.centery), (120, 210, 255))
        text(s, F, "▶", (xr - 12, rect.centery), (120, 210, 255))

    def draw_preview(self, rect, small=False):
        s, F = self.screen, self.fonts
        panel(s, rect.inflate(8, 8), color=(10, 8, 18), alpha=230, radius=8)
        frame, hands, fid = self.tracker.snapshot()
        if frame is None:
            text(s, F.small, "Starting camera...", rect.center)
            return
        surf, cid, csize = self._preview
        if cid != fid or csize != rect.size:
            img = pygame.image.frombuffer(frame.tobytes(), (frame.shape[1], frame.shape[0]), "RGB")
            surf = pygame.transform.smoothscale(img, rect.size)
            self._preview = (surf, fid, rect.size)
        s.blit(surf, rect)
        if self.state != "title" and self.mode == "2p":
            js0 = self.inputs[0].joystick
            js1 = self.inputs[1].joystick
            self.draw_zones(rect, js0, 0.25, 0.0, 0.5)
            self.draw_zones(rect, js1, 0.75, 0.5, 1.0)
            pygame.draw.line(s, (255, 80, 80), (rect.centerx, rect.y), (rect.centerx, rect.bottom), 3)
        else:
            js = self.menu_js if self.state == "title" else getattr(self.inputs[0], "joystick", None)
            self.draw_zones(rect, js, 0.5, 0.0, 1.0)
        for slot, h in hands.items():
            col = GESTURE_COLOR[h.gesture]
            pts = [(rect.x + x * rect.w, rect.y + y * rect.h) for x, y in h.points]
            for a, b in HAND_CONNECTIONS:
                pygame.draw.line(s, col, pts[a], pts[b], 2)
            for i, p in enumerate(pts):
                pygame.draw.circle(s, (255, 255, 255) if i in (4, 8, 12, 16, 20) else col,
                                   (int(p[0]), int(p[1])), 4 if i in (4, 8, 12, 16, 20) else 2)
            cx, cy = rect.x + h.center[0] * rect.w, rect.y + h.center[1] * rect.h
            pygame.draw.circle(s, col, (int(cx), int(cy)), 8 if small else 11, 3)
        if not hands and int(self.t * 3) % 2 == 0:
            text(s, F.small if small else F.mid, "SHOW YOUR HAND", rect.center, (255, 200, 80))
        pygame.draw.rect(s, (250, 240, 220), rect.inflate(6, 6), 2, border_radius=8)

    def draw_training_panel(self):
        s, F = self.screen, self.fonts
        r = pygame.Rect(W - 330, 160, 300, 300)
        panel(s, r, alpha=170, border=(90, 90, 130))
        rows = [("Fist", Gesture.FIST, "Jab  (crouch: low jab)"),
                ("Fist + THRUST", Gesture.FIST, "Power punch / Uppercut"),
                ("Index finger", Gesture.POINT, "Kick  (crouch: sweep)"),
                ("Open palm", Gesture.PALM, "Block (crouch: low)"),
                ("Two fingers", Gesture.PEACE, "Handouken / SUPER")]
        text(s, F.small, "MOVE LIST", (r.centerx, r.y + 18), C.YELLOW)
        for i, (hand, g, act) in enumerate(rows):
            y = r.y + 54 + i * 44
            gesture_icon(s, g, (r.x + 26, y + 4), 28, GESTURE_COLOR[g])
            text(s, F.tiny, hand, (r.x + 50, y - 8), C.WHITE, "topleft", shadow=False)
            text(s, F.tiny, act, (r.x + 50, y + 10), (190, 190, 210), "topleft", shadow=False)
        state = "ON" if self.inputs[1].block else "OFF"
        text(s, F.tiny, f"B: dummy block {state}", (r.centerx, r.bottom - 16), (150, 220, 255))

    # ------------------------------------------------------------------ screens
    def draw_title(self):
        s, F = self.screen, self.fonts
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((10, 6, 20, 110))
        s.blit(ov, (0, 0))
        blit_glow(s, (W // 2, 62), 300, (110, 40, 40))
        text(s, F.huge, "HAND TO HAND", (W // 2, 64), lerp_color((255, 200, 60), (255, 90, 50),
                                                                 0.5 + 0.5 * math.sin(self.t * 2)))
        text(s, F.small, "Gesture Street Fighter  ·  ME461", (W // 2, 124), (240, 230, 255))
        if self.tracker:
            self.draw_preview(pygame.Rect(W // 2 - 200, 156, 400, 300))
        else:
            r = pygame.Rect(W // 2 - 200, 156, 400, 300)
            panel(s, r, alpha=220, border=(90, 90, 130))
            lines = ["KEYBOARD MODE", "P1: A D move · W jump · S crouch", "J punch · U power · K kick",
                     "L block · I handouken", "P2: arrows · , m . / n", self.camera_msg[:44]]
            for i, ln in enumerate(lines):
                text(s, F.small if i == 0 else F.tiny, ln, (r.centerx, r.y + 40 + i * 40),
                     C.YELLOW if i == 0 else C.WHITE)

        # sol panel: hareket
        lp = pygame.Rect(40, 160, 330, 290)
        panel(s, lp, alpha=190, border=(90, 90, 130))
        text(s, F.small, "MOVE YOUR HAND", (lp.centerx, lp.y + 20), C.YELLOW)
        rows = [("◀  ▶", "Left / right", "walk"), ("▲", "Up", "jump"), ("▼", "Down", "crouch"),
                ("▲ + ◀▶", "Up + side", "jump forward")]
        for i, (sym, a, b) in enumerate(rows):
            y = lp.y + 66 + i * 52
            text(s, F.mid, sym, (lp.x + 64, y), (120, 210, 255))
            text(s, F.small, a, (lp.x + 130, y - 12), C.WHITE, "topleft")
            text(s, F.tiny, b, (lp.x + 131, y + 12), (190, 190, 210), "topleft", shadow=False)
        # sağ panel: saldırılar
        rp = pygame.Rect(W - 370, 160, 330, 290)
        panel(s, rp, alpha=190, border=(90, 90, 130))
        text(s, F.small, "MAKE A GESTURE", (rp.centerx, rp.y + 20), C.YELLOW)
        rows = [(Gesture.FIST, "Fist", "punch"), (Gesture.FIST, "Fist + thrust", "POWER PUNCH"),
                (Gesture.POINT, "Index finger", "kick"), (Gesture.PALM, "Open palm", "block"),
                (Gesture.PEACE, "Two fingers", "HANDOUKEN!")]
        for i, (g, a, b) in enumerate(rows):
            y = rp.y + 62 + i * 44
            gesture_icon(s, g, (rp.x + 34, y + 2), 30, GESTURE_COLOR[g])
            text(s, F.small, a, (rp.x + 64, y - 12), C.WHITE, "topleft")
            text(s, F.tiny, b, (rp.x + 65, y + 10), (190, 190, 210), "topleft", shadow=False)

        # mod kartları
        cw, gap = 300, 24
        x0 = (W - (3 * cw + 2 * gap)) // 2
        for i, (mode, g, title, sub, key) in enumerate(MODES):
            r = pygame.Rect(x0 + i * (cw + gap), 478, cw, 84)
            prog = self.holds.get(mode, 0.0)
            col = GESTURE_COLOR[g]
            if prog > 0:
                blit_glow(s, r.center, 190, scale_color(col, 0.4 * prog + 0.1))
            panel(s, r, color=(26, 20, 40), alpha=225, border=col if prog > 0 else (90, 90, 130), radius=10)
            gesture_icon(s, g, (r.x + 42, r.centery + 4), 44, col)
            text(s, F.mid, title, (r.x + 80, r.y + 14), C.WHITE, "topleft")
            text(s, F.tiny, f"{sub}  ·  key {pygame.key.name(key)}", (r.x + 81, r.y + 52), (190, 190, 210),
                 "topleft", shadow=False)
            if prog > 0:
                pygame.draw.rect(s, col, (r.x + 6, r.bottom - 8, int((r.w - 12) * prog), 4))
        hint = "Hold a gesture for 1 second to choose" if self.tracker else "Press 1 / 2 / 3"
        text(s, F.small, hint, (W // 2, 588), C.WHITE)
        text(s, F.tiny, f"CPU difficulty: ◀ {self.difficulty.upper()} ▶      F11: fullscreen      ESC: quit",
             (W // 2, 616), (200, 200, 220))

    def draw_intro(self):
        t = self.state_t
        a, b = self.fighters
        final = a.wins == C.ROUNDS_TO_WIN - 1 and b.wins == C.ROUNDS_TO_WIN - 1
        if t < 1.3:
            k = min(1.0, t / 0.2)
            label = "FINAL ROUND" if final else f"ROUND {self.round}"
            text(self.screen, self.fonts.get(int(60 + 40 * k)), label, (W // 2, H // 2 - 40), C.YELLOW,
                 alpha=int(255 * k))
            if t < 0.05:
                self.sound.play("beep")
        else:
            k = min(1.0, (t - 1.3) / 0.15)
            text(self.screen, self.fonts.get(int(150 - 30 * k)), "FIGHT!", (W // 2, H // 2 - 40), (255, 90, 50))
            if t - 1.3 < 0.05:
                self.sound.play("go")

    def draw_banner(self):
        bn = self.banner
        if not bn:
            return
        t, dur = bn["t"], bn["dur"]
        pop = min(1.0, t / 0.15)
        alpha = int(255 * min(1.0, (dur - t) / 0.4))
        y = H // 2 - 40
        blit_glow(self.screen, (W // 2, y), 280, scale_color(bn["color"], 0.4 * alpha / 255))
        text(self.screen, self.fonts.get(int(170 - 50 * pop)), bn["text"], (W // 2, y), bn["color"], alpha=alpha)
        if bn["sub"]:
            text(self.screen, self.fonts.mid, bn["sub"], (W // 2, y + 80), C.WHITE, alpha=alpha)

    def draw_match_end(self):
        s, F = self.screen, self.fonts
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, min(150, int(self.state_t * 300))))
        s.blit(ov, (0, 0))
        a, b = self.fighters
        r = pygame.Rect(0, 0, 640, 360)
        r.center = (W // 2, H // 2 + 20)
        if a.wins >= C.ROUNDS_TO_WIN and b.wins >= C.ROUNDS_TO_WIN:
            title, col = "DRAW GAME", C.WHITE
        else:
            win = a if a.wins >= C.ROUNDS_TO_WIN else b
            if self.mode == "1p":
                title, col = ("YOU WIN!", C.YELLOW) if win is a else ("YOU LOSE...", (255, 90, 80))
            else:
                title, col = f"{win.name} WINS!", win.colors["aura"]
        panel(s, r, color=(18, 12, 28), alpha=235, border=col, radius=14, width=3)
        text(s, F.big, title, (r.centerx, r.y + 56), col)
        rows = [("Rounds", f"{a.wins}  -  {b.wins}"),
                ("Max combo", f"{self.stats['max_combo'][0]}  -  {self.stats['max_combo'][1]}"),
                ("Perfect rounds", f"{self.stats['perfects'][0]}  -  {self.stats['perfects'][1]}")]
        text(s, F.small, a.name, (r.x + 385, r.y + 110), C.WHITE, "midright")
        text(s, F.small, b.name, (r.x + 415, r.y + 110), C.WHITE, "midleft")
        for i, (k, v) in enumerate(rows):
            y = r.y + 150 + i * 40
            text(s, F.small, k, (r.x + 60, y), (200, 200, 220), "midleft")
            text(s, F.small, v, (r.x + 400, y), C.WHITE)
        prog = self.holds.get("palm", 0.0)
        if prog > 0:
            pygame.draw.rect(s, (90, 220, 255), (r.x + 100, r.bottom - 70, int((r.w - 200) * prog), 10),
                             border_radius=4)
        msg = "Hold OPEN PALM or press SPACE for a rematch" if self.tracker else "SPACE: rematch"
        text(s, F.small, msg, (r.centerx, r.bottom - 40), C.WHITE)
        text(s, F.tiny, "ESC: main menu", (r.centerx, r.bottom - 14), (170, 170, 190))

    def draw_debug(self):
        a, b = self.fighters
        lines = [f"FPS {self.clock.get_fps():.0f}  state {self.state}",
                 f"P1 {a.state} {a.move.name if a.move else ''}  P2 {b.state} {b.move.name if b.move else ''}"]
        if self.tracker:
            lines.append(f"tracker {self.tracker.fps:.1f} fps")
            _, hands, _ = self.tracker.snapshot()
            for slot, h in hands.items():
                lines.append(f"hand{slot} {h.raw.name}/{h.gesture.name} fingers "
                             + "".join("1" if x else "0" for x in h.fingers)
                             + f" c=({h.center[0]:.2f},{h.center[1]:.2f}) size {h.size:.2f}")
        r = pygame.Rect(10, H - 120 - 22 * len(lines), 560, 22 * len(lines) + 10)
        panel(self.screen, r, alpha=210)
        for i, ln in enumerate(lines):
            text(self.screen, self.fonts.tiny, ln, (r.x + 10, r.y + 6 + i * 22), (160, 255, 160), "topleft",
                 shadow=False)
        # kutular
        for f in self.fighters:
            hu, hb = f.hurtbox(), f.hitbox()
            if hu:
                pygame.draw.rect(self.screen, (80, 255, 80), hu.move(-self.cam_x, 0), 1)
            if hb:
                pygame.draw.rect(self.screen, (255, 60, 60), hb.move(-self.cam_x, 0), 2)


def main(args):
    Game(args).run()
    return 0

