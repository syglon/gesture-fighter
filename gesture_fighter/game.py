"""Ana oyun: durum makinesi, çarpışmalar ve arayüz.

İki mod var:
  * solo   — tek oyuncu boss'a karşı (title → countdown → fight → victory/defeat)
  * versus — iki oyuncu karşı karşıya, 3 rauntta 2 kazanan
             (title → countdown → fight → round_end → ... → match_end)
Versus'ta kamera ikiye bölünür: görüntünün sol yarısındaki el P1 (solda), sağ yarısındaki el P2 (sağda).
"""
import math
import random
import sys

import pygame

from . import config as C
from .controls import (KEYMAP_VS_P1, KEYMAP_VS_P2, CombinedController, ControlState, HandController,
                       KeyboardController)
from .draw import (Fonts, bar, blit_glow, build_background, gesture_icon, lerp, lerp_color, panel,
                   scale_color, text)
from .entities import Boss, Fighter, Projectile, SpecialBeam, circle_rect_hit
from .fx import FloatingText, Particles, Shake
from .gestures import GESTURE_ACTION, GESTURE_COLOR, GESTURE_HAND, HAND_CONNECTIONS, Gesture

W, H = C.SCREEN_W, C.SCREEN_H
LEGEND = [Gesture.FIST, Gesture.PALM, Gesture.POINT, Gesture.PEACE]
TIPS = [
    "Move your hand UP / DOWN to dodge and to aim.",
    "Open your palm right before a hit to PARRY it back!",
    "Red missiles can be shot down with punches and fireballs.",
    "Land hits in a row to build a COMBO damage bonus.",
    "Two fingers unleash the SPECIAL beam when the gold bar is full.",
    "VERSUS: fireballs beat punches — and a parry sends them straight back.",
]
DIFFS = ["easy", "normal", "hard"]
CLASH_RANK = {"punch": 0, "fire": 1, "reflect": 2}  # versus: çarpışan mermilerden güçlü olan devam eder


def new_stats():
    return dict(shots=0, hits=0, parries=0, blocks=0, dmg_taken=0.0, max_combo=0, specials=0, damage=0.0)


class Game:
    def __init__(self, args):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        flags = pygame.SCALED | (pygame.FULLSCREEN if args.fullscreen else 0)
        self.screen = pygame.display.set_mode((W, H), flags)
        pygame.display.set_caption("Gesture Fighter — ME461")
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()
        from .sound import SoundBank
        self.sound = SoundBank(enabled=not args.mute)
        self.difficulty = args.difficulty

        self.tracker = None
        self.camera_msg = "Keyboard mode (--keyboard)"
        if not args.keyboard:
            from .hand_tracker import HandTracker
            tracker = HandTracker(args.camera, split=False, mirror=not args.no_mirror)
            ok, msg = tracker.start()
            self.camera_msg = msg
            if ok:
                self.tracker = tracker
            else:
                print(f"[game] {msg} — klavye moduna geçiliyor.")

        self.bg = build_background()
        self.world = pygame.Surface((W, H))
        self._preview = (None, -1, None)
        self.debug = False
        self.paused = False
        self.running = True
        self.max_frames = args.frames  # test için: N kare sonra çık
        self.frame = 0

        self.particles = Particles()
        self.shake = Shake()
        self.set_mode("solo")
        self.new_match()
        self.boss.x = self.boss.home_x
        self.boss.set_state("gloat")
        self.set_state("title")
        if args.versus:  # --versus: menüyü atla
            self.start_match("versus")

    # ================================================================== setup
    @property
    def versus(self):
        return self.mode == "versus"

    def set_mode(self, mode):
        """solo / versus arasında geçiş: kamera bölünmesi ve kontrolcüler."""
        self.mode = mode
        tr = self.tracker
        if tr:
            tr.set_split(mode == "versus")
        if mode == "versus":
            self.controllers = [
                CombinedController(HandController(tr, 0) if tr else None, KeyboardController(KEYMAP_VS_P1)),
                CombinedController(HandController(tr, 1) if tr else None, KeyboardController(KEYMAP_VS_P2)),
            ]
        else:
            self.controllers = [CombinedController(HandController(tr, 0) if tr else None)]
        self.controls = [ControlState() for _ in self.controllers]

    def set_state(self, s):
        self.state = s
        self.state_t = 0.0
        self.holds = {}
        self.armed = set()  # el önce bırakılmalı (kalkanı tutarken kazara yeniden başlamasın)

    def new_match(self):
        n = 2 if self.versus else 1
        self.match_stats = [new_stats() for _ in range(n)]
        self.wins = [0] * n
        self.round = 1
        self.match_time = 0.0
        self.new_fight()

    def new_fight(self):
        """Yeni dövüş (solo) ya da yeni raunt (versus)."""
        if self.versus:
            self.players = [Fighter(C.VS_P1_X, 1, C.P1_COLOR, "P1"), Fighter(C.VS_P2_X, -1, C.P2_COLOR, "P2")]
            for p in self.players:
                p.max_hp = C.VS_MAX_HP
                p.hp = p.ghost_hp = float(C.VS_MAX_HP)
            self.boss = None
        else:
            self.players = [Fighter(color=C.P1_COLOR, name="YOU")]
            self.boss = Boss(self.difficulty)
        for p, st in zip(self.players, self.match_stats):
            p.stats = st  # istatistikler raunt boyunca birikir
        self.projectiles = []
        self.lasers = []
        self.texts = []
        self.particles.clear()
        self.fight_time = 0.0
        self.round_timer = float(C.VS_ROUND_TIME)
        self.slowmo = 0.0
        self.hitstop = 0.0
        self.red_flash = 0.0
        self.banner = None
        self.end_timer = None
        self.end_kind = None
        self.round_winner = None
        self.explode_t = 0.0
        self._notify_t = {}

    def opponent(self, p):
        return self.players[1] if p is self.players[0] else self.players[0]

    def pick_target(self):
        """Boss'un hedefi (solo modda tek oyuncu)."""
        alive = [p for p in self.players if p.hp > 0]
        return alive[0] if alive else None

    # ================================================================== loop
    def run(self):
        try:
            while self.running:
                dt = min(self.clock.tick(C.FPS) / 1000.0, 0.05)
                self.handle_events()
                keys = pygame.key.get_pressed()
                self.controls = [c.read(dt, keys) for c in self.controllers]
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
                elif k == pygame.K_m:
                    self.sound.enabled = not self.sound.enabled and bool(self.sound.sounds)
                elif self.state == "title":
                    if k == pygame.K_ESCAPE:
                        self.running = False
                    elif k in (pygame.K_SPACE, pygame.K_RETURN):
                        self.start_match("solo")
                    elif k == pygame.K_v:
                        self.start_match("versus")
                    elif k in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                        step = -1 if k in (pygame.K_LEFT, pygame.K_a) else 1
                        i = (DIFFS.index(self.difficulty) + step) % len(DIFFS)
                        self.difficulty = DIFFS[i]
                        self.sound.play("blip")
                elif self.state in ("fight", "countdown", "round_end"):
                    if k in (pygame.K_ESCAPE, pygame.K_p):
                        self.paused = not self.paused
                    elif k == pygame.K_q and self.paused:
                        self.go_title()
                elif self.state in ("victory", "defeat", "match_end"):
                    if k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_r):
                        self.start_match(self.mode)
                    elif k == pygame.K_ESCAPE:
                        self.go_title()

    def go_title(self):
        self.paused = False
        self.set_mode("solo")
        self.new_match()
        self.boss.x = self.boss.home_x
        self.boss.set_state("gloat")
        self.set_state("title")

    def start_match(self, mode):
        self.paused = False
        if mode != self.mode:
            self.set_mode(mode)
        self.new_match()
        self.start_countdown()

    def start_countdown(self):
        self.set_state("countdown")
        self.sound.play("beep")

    def hold_confirm(self, key, active, dt, duration=1.2, lockout=1.0):
        """Bir hareketi `duration` saniye tutunca True döner. Önce elin bırakılması gerekir."""
        if not active:
            self.armed.add(key)
            self.holds[key] = max(0.0, self.holds.get(key, 0.0) - dt * 2)
            return False
        if self.state_t < lockout or key not in self.armed:
            return False
        self.holds[key] = self.holds.get(key, 0.0) + dt / duration
        if self.holds[key] >= 1.0:
            self.holds[key] = 0.0
            return True
        return False

    # ================================================================== update
    def update(self, dt):
        if self.paused:
            return
        self.state_t += dt
        if self.state == "title":
            self.update_idle_actors(dt)
            g = self.controls[0].gesture
            if self.hold_confirm("solo", g is Gesture.PALM, dt, 1.2, 0.5):
                self.start_match("solo")
            elif self.hold_confirm("versus", g is Gesture.PEACE, dt, 1.2, 0.5):
                self.start_match("versus")
        elif self.state == "countdown":
            prev = int(self.state_t - dt)
            self.update_idle_actors(dt)
            now = int(self.state_t)
            if now != prev and now < 3:
                self.sound.play("beep")
            if self.state_t >= 3.0:
                self.set_state("fight")
                if self.boss:
                    self.boss.set_state("idle")
                self.show_banner("FIGHT!", None, C.C_SPECIAL, 1.0)
                self.sound.play("go")
        elif self.state in ("fight", "round_end"):
            self.update_fight(dt)
        elif self.state in ("victory", "defeat", "match_end"):
            self.update_idle_actors(dt)
            palm = any(c.gesture is Gesture.PALM for c in self.controls)
            if self.hold_confirm("again", palm, dt, duration=1.2, lockout=1.5):
                self.start_match(self.mode)

    def move_player(self, p, ctrl, dt):
        if ctrl.y is not None:
            p.target_y = lerp(C.PLAYER_Y_MIN, C.PLAYER_Y_MAX, ctrl.y)
        p.y += (p.target_y - p.y) * min(1.0, dt * 12)

    def update_idle_actors(self, dt):
        """Menü/geri sayım/sonuç: oyuncular sadece hareket eder ve elini gösterir, saldırı yok."""
        for p, ctrl in zip(self.players, self.controls):
            p.update_timers(dt)
            if p.hp > 0:
                self.move_player(p, ctrl, dt)
                p.gesture = ctrl.gesture
                p.shield_on = p.gesture is Gesture.PALM
                p.shield_t = 1.0
            else:
                p.shield_on = False
        if self.boss:
            self.boss.update(dt, self)
        for pr in self.projectiles:
            pr.update(dt, self)
        self.projectiles = [pr for pr in self.projectiles if pr.alive]
        self.particles.update(dt)
        self.texts = [t for t in self.texts if t.update(dt)]
        self.shake.update(dt)
        self.update_banner(dt)
        if self.state in ("victory", "match_end") and random.random() < dt * 3:
            x, y = random.uniform(200, W - 200), random.uniform(120, 400)
            col = random.choice([C.C_SPECIAL, C.C_SHIELD, C.C_FIRE, (200, 120, 255)])
            self.particles.burst(x, y, col, n=40, speed=(60, 320), life=(0.6, 1.4), gravity=180)

    def update_fight(self, dt_real):
        if self.hitstop > 0:
            self.hitstop -= dt_real
            dt = dt_real * 0.08
        else:
            dt = dt_real * (0.35 if self.slowmo > 0 else 1.0)
        self.slowmo = max(0.0, self.slowmo - dt_real)

        if self.end_kind is None:
            self.fight_time += dt
            self.match_time += dt
        for p, ctrl in zip(self.players, self.controls):
            if p.hp > 0 and self.end_kind is None:
                self.update_player(p, dt, ctrl)
            else:
                p.update_timers(dt)
                p.shield_on = False
                if p.hp <= 0:
                    p.beam = None
        if self.boss:
            self.boss.update(dt, self)

        for pr in self.projectiles:
            pr.update(dt, self)
        for L in self.lasers:
            L.update(dt)
        if self.versus:
            self.collide_versus()
            for p in self.players:
                self.update_beam_versus(p, dt)
            if self.end_kind is None:
                self.round_timer -= dt
                if self.round_timer <= 0:
                    self.round_timer = 0.0
                    self.time_over()
        else:
            self.update_lasers(dt)
            self.update_beam(self.players[0], dt)
            self.collide()
        self.projectiles = [pr for pr in self.projectiles if pr.alive]
        self.lasers = [L for L in self.lasers if L.alive]

        self.particles.update(dt)
        self.texts = [t for t in self.texts if t.update(dt)]
        self.shake.update(dt_real)
        self.red_flash = max(0.0, self.red_flash - dt_real * 2)
        self.update_banner(dt_real)

        if self.end_kind is None:
            return
        self.end_timer -= dt_real
        if self.versus:
            if self.end_timer <= 0:
                self.next_round()
            return
        b = self.boss
        if self.end_kind == "victory":
            self.explode_t -= dt_real
            if self.explode_t <= 0 and self.end_timer > 0.6:
                self.explode_t = 0.12
                ang = random.uniform(0, math.tau)
                x = b.x + math.cos(ang) * random.uniform(0, b.radius)
                y = b.y + math.sin(ang) * random.uniform(0, b.radius)
                self.particles.burst(x, y, random.choice([b.color, (255, 220, 120), (255, 255, 255)]),
                                     n=26, speed=(80, 420), life=(0.3, 0.9))
                self.shake.add(6)
                if random.random() < 0.4:
                    self.sound.play("boss_hit")
        if self.end_timer <= 0:
            if self.end_kind == "victory":
                self.particles.burst(b.x, b.y, (255, 255, 255), n=160, speed=(150, 900), life=(0.6, 1.6),
                                     size=(3, 8))
                self.particles.burst(b.x, b.y, b.color, n=120, speed=(100, 600), life=(0.6, 1.6))
                b.set_state("dead")  # boss yok oldu
                self.shake.add(25)
                self.sound.play("explosion")
                self.sound.play("win")
            else:
                self.sound.play("lose")
            self.set_state(self.end_kind)

    # ------------------------------------------------------------------ player
    def update_player(self, p, dt, ctrl):
        p.update_timers(dt)
        self.move_player(p, ctrl, dt)

        g = ctrl.gesture
        entered = g is not p.gesture
        p.gesture = g
        locked = p.beam is not None

        # kalkan
        want = g is Gesture.PALM and p.guard_break <= 0 and not locked and p.energy > 1
        if want and not p.shield_on:
            p.shield_on = True
            p.shield_t = 0.0
            self.sound.play("shield", 0.7)
        elif not want and p.shield_on:
            p.shield_on = False
        if p.shield_on:
            p.shield_t += dt
            p.energy -= C.SHIELD_DRAIN * dt
            p.energy_delay = C.ENERGY_REGEN_DELAY
            if p.energy <= 0:
                self.guard_break(p)
        else:
            p.energy_delay -= dt
            if p.energy_delay <= 0:
                p.energy = min(C.PLAYER_MAX_ENERGY, p.energy + C.ENERGY_REGEN * dt)

        if locked:
            p.pending = None
            return

        # saldırılar: hareket yeni yapıldığında hemen, tutulursa belirli aralıkla tekrar
        if g in (Gesture.FIST, Gesture.POINT):
            spec = C.PUNCH if g is Gesture.FIST else C.FIRE
            if entered:
                p.pending = g
                p.hold_timer = 0.0
            else:
                p.hold_timer += dt
                if p.hold_timer >= spec["hold_repeat"]:
                    p.pending = g
                    p.hold_timer = 0.0
        else:
            p.pending = None
        if p.pending is not None and p.cooldown <= 0:
            self.player_attack(p, p.pending)
            p.pending = None
        if g is Gesture.PEACE and entered:
            self.try_special(p)

    def player_attack(self, p, g):
        spec = C.PUNCH if g is Gesture.FIST else C.FIRE
        if p.energy < spec["energy"]:
            self.notify(f"noenergy{p.name}", "NO ENERGY", p.x, p.y - 100, C.C_ENERGY)
            self.sound.play("fizzle")
            p.cooldown = 0.3
            return
        if spec["energy"]:
            p.energy -= spec["energy"]
            p.energy_delay = max(p.energy_delay, 0.3)
        p.cooldown = spec["cooldown"]
        p.attack_anim = 1.0
        hx, hy = p.hand_pos
        if g is Gesture.FIST:
            kind, col, snd = "punch", C.C_PUNCH, "punch"
        else:
            kind, col, snd = "fire", C.C_FIRE, "fire"
        if self.versus:
            col = lerp_color(col, p.color, 0.35)
        pr = Projectile(hx + p.facing * 14, hy, p.facing * spec["speed"], 0, spec["radius"],
                        spec["damage"], "player", kind, col)
        pr.shooter = p
        self.spawn(pr)
        p.stats["shots"] += 1
        self.particles.burst(hx, hy, col, n=8, speed=(60, 220), life=(0.1, 0.3),
                             angle=0 if p.facing > 0 else math.pi, spread=1.6)
        self.sound.play(snd)

    def try_special(self, p):
        if p.special >= C.SPECIAL_MAX:
            p.special = 0.0
            p.beam = SpecialBeam(p, dps=C.VS_SPECIAL_DPS if self.versus else C.SPECIAL_DPS)
            if self.versus:
                p.beam.color = lerp_color(C.C_SPECIAL, p.color, 0.35)
            p.shield_on = False
            p.stats["specials"] += 1
            self.sound.play("special")
            self.shake.add(10)
            self.hitstop = 0.12
            self.texts.append(FloatingText(p.x + p.facing * 60, p.y - 110, "SPECIAL!", C.C_SPECIAL, self.fonts.big,
                                           1.2))
        else:
            self.notify(f"special{p.name}", f"SPECIAL {int(p.special)}%", p.x + p.facing * 30, p.y - 100,
                        C.C_SPECIAL)
            self.sound.play("fizzle")

    def guard_break(self, p):
        p.energy = 0.0
        p.shield_on = False
        p.guard_break = C.GUARD_BREAK_TIME
        p.energy_delay = C.ENERGY_REGEN_DELAY
        self.texts.append(FloatingText(p.x + p.facing * 20, p.y - 100, "GUARD BREAK!", (255, 90, 90),
                                       self.fonts.mid, 1.2))
        self.sound.play("fizzle")
        self.shake.add(8)

    # ------------------------------------------------------------------ world api (boss kullanır)
    def spawn(self, proj):
        self.projectiles.append(proj)

    def add_laser(self, laser):
        self.lasers.append(laser)

    def clear_boss_attacks(self):
        for pr in self.projectiles:
            if pr.owner == "boss":
                pr.alive = False
                self.particles.burst(pr.x, pr.y, pr.color, n=6, speed=(40, 160), life=(0.2, 0.5))
        self.lasers.clear()

    def on_boss_phase(self, phase):
        self.clear_boss_attacks()
        sub = {2: "The core is overheating...", 3: "OVERDRIVE — it's desperate!"}.get(phase)
        self.show_banner(f"PHASE {phase}", sub, self.boss.color, 2.0)
        self.sound.play("roar")
        self.shake.add(16)
        self.particles.burst(self.boss.x, self.boss.y, self.boss.color, n=80, speed=(100, 600), life=(0.4, 1.2))

    # ------------------------------------------------------------------ combat (ortak)
    @staticmethod
    def combo_mult(p):
        return 1.0 + min(C.COMBO_BONUS_MAX, max(0, p.combo - 1) * C.COMBO_BONUS_PER_HIT)

    def register_hit(self, p, dmg, kind):
        """Saldıran oyuncunun kombo/istatistik/özel bar güncellemesi. Kombo çarpanlı hasarı döndürür."""
        p.combo += 1
        p.combo_timer = C.COMBO_WINDOW
        p.stats["max_combo"] = max(p.stats["max_combo"], p.combo)
        dmg *= self.combo_mult(p)
        p.stats["damage"] += dmg
        gain = C.VS_SPECIAL_GAIN_DEALT if self.versus else C.SPECIAL_GAIN_PER_DAMAGE
        p.special = min(C.SPECIAL_MAX, p.special + dmg * gain)
        if kind in ("punch", "fire"):
            p.stats["hits"] += 1
        return dmg

    def damage_player(self, p, dmg, x, y):
        p.hp = max(0.0, p.hp - dmg)
        p.iframes = C.PLAYER_IFRAMES
        p.hurt_flash = 1.0
        p.combo = 0
        p.stats["dmg_taken"] += dmg
        if self.versus:
            p.special = min(C.SPECIAL_MAX, p.special + dmg * C.VS_SPECIAL_GAIN_TAKEN)
        else:
            self.red_flash = 0.5
        self.shake.add(13)
        self.hitstop = max(self.hitstop, 0.06)
        self.sound.play("hurt")
        self.particles.burst(x, y, (255, 70, 70), n=24, speed=(80, 380), life=(0.2, 0.6))
        self.texts.append(FloatingText(p.x, p.y - 90, f"-{int(round(dmg))}", (255, 90, 90), self.fonts.mid, 0.9))
        if p.hp <= 0:
            if self.versus:
                self.round_won(self.opponent(p))
            else:
                self.player_defeated(p)

    def block(self, p, pr):
        pr.alive = False
        p.energy -= pr.damage * C.SHIELD_BLOCK_COST
        p.energy_delay = C.ENERGY_REGEN_DELAY
        p.special = min(C.SPECIAL_MAX, p.special + C.SPECIAL_GAIN_BLOCK)
        p.stats["blocks"] += 1
        self.shake.add(3)
        self.sound.play("block", 0.8)
        self.particles.burst(pr.x, pr.y, C.C_SHIELD, n=14, speed=(80, 300), life=(0.15, 0.4),
                             angle=0 if p.facing > 0 else math.pi, spread=2.4)
        if p.energy <= 0:
            self.guard_break(p)

    def parry(self, p, pr, target_pos, dmg):
        """Mermiyi `target_pos`'a doğru geri gönderir; artık `p`'nin mermisi ve `dmg` hasar verir."""
        pr.owner = "player"
        pr.shooter = p
        pr.kind = "reflect"
        pr.color = C.C_PARRY
        pr.homing = 0.0
        pr.trail.clear()
        speed = max(750.0, math.hypot(pr.vx, pr.vy) * 1.6)
        ang = math.atan2(target_pos[1] - pr.y, target_pos[0] - pr.x)
        pr.vx, pr.vy = math.cos(ang) * speed, math.sin(ang) * speed
        pr.damage = dmg
        p.special = min(C.SPECIAL_MAX, p.special + C.SPECIAL_GAIN_PARRY)
        p.stats["parries"] += 1
        self.hitstop = max(self.hitstop, 0.09)
        self.shake.add(6)
        self.sound.play("parry")
        self.particles.burst(pr.x, pr.y, C.C_PARRY, n=30, speed=(100, 500), life=(0.2, 0.6))
        self.notify(f"parry{p.name}", "PARRY!", p.x + p.facing * 50, p.y - 110, C.C_PARRY, cooldown=0.25,
                    font=self.fonts.big)

    def beam_particles(self, p, beam):
        x_end = W if p.facing > 0 else 0
        lo, hi = sorted((beam.x0, x_end))
        for _ in range(3):
            self.particles.emit(random.uniform(lo, hi), beam.y + random.uniform(-beam.half_h, beam.half_h),
                                random.uniform(200, 600) * p.facing, random.uniform(-60, 60),
                                random.choice([beam.color, (255, 255, 220), (255, 150, 40)]),
                                life=random.uniform(0.15, 0.35), size=random.uniform(2, 5))

    # ------------------------------------------------------------------ combat: solo (boss)
    def damage_boss(self, p, dmg, x, y, kind):
        b = self.boss
        dmg = self.register_hit(p, dmg, kind)
        b.take_damage(dmg)
        col = {"punch": C.C_PUNCH, "fire": C.C_FIRE, "reflect": C.C_PARRY}.get(kind, C.WHITE)
        font = self.fonts.mid if kind != "reflect" else self.fonts.big
        self.texts.append(FloatingText(x + random.uniform(-20, 20), y - 30, str(int(round(dmg))), col, font, 0.8))
        self.particles.burst(x, y, col, n=18 if kind == "punch" else 30, speed=(80, 420), life=(0.2, 0.6),
                             angle=math.pi, spread=2.6)
        self.sound.play("boss_hit")
        if kind in ("fire", "reflect"):
            self.shake.add(6)
            self.hitstop = max(self.hitstop, 0.04)
        else:
            self.shake.add(2)
        if b.hp <= 0:
            self.boss_defeated()

    def collide(self):
        b = self.boss
        p = self.players[0]
        player_alive = p.hp > 0 and self.end_kind is None
        for pr in self.projectiles:
            if not pr.alive:
                continue
            if pr.owner == "player":
                if (pr.x - b.x) ** 2 + (pr.y - b.y) ** 2 <= (b.radius * 0.9 + pr.radius) ** 2:
                    pr.alive = False
                    if b.vulnerable:
                        self.damage_boss(pr.shooter or p, pr.damage, pr.x, pr.y, pr.kind)
                    else:
                        self.particles.burst(pr.x, pr.y, (170, 170, 190), n=10, speed=(60, 200), life=(0.1, 0.3))
                        if b.state == "transition":
                            self.notify("immune", "IMMUNE", b.x - 60, b.y - 120, (200, 200, 220))
                continue
            # --- boss mermisi
            if pr.kind == "missile":
                for q in self.projectiles:
                    if q.alive and q.owner == "player" and \
                            (q.x - pr.x) ** 2 + (q.y - pr.y) ** 2 <= (q.radius + pr.radius + 6) ** 2:
                        q.alive = False
                        pr.alive = False
                        self.particles.burst(pr.x, pr.y, (255, 140, 60), n=26, speed=(80, 360), life=(0.2, 0.6))
                        self.sound.play("boss_hit", 0.6)
                        self.shake.add(3)
                        break
                if not pr.alive:
                    continue
            if not player_alive:
                continue
            if p.shield_on:
                sx, sy = p.shield_center
                if (pr.x - sx) ** 2 + (pr.y - sy) ** 2 <= (C.SHIELD_RADIUS + pr.radius) ** 2:
                    if p.in_parry_window:
                        self.parry(p, pr, (b.x, b.y), max(12.0, pr.damage * 2.0))
                    else:
                        self.block(p, pr)
                    continue
            if p.iframes <= 0 and circle_rect_hit(pr.x, pr.y, pr.radius * 0.85, p.hitbox):
                pr.alive = False
                self.damage_player(p, pr.damage, pr.x, pr.y)

    def update_lasers(self, dt):
        p = self.players[0]
        if p.hp <= 0 or self.end_kind is not None:
            return
        hb = p.hitbox.inflate(0, -30)
        for L in self.lasers:
            if not L.firing:
                continue
            if not L.started:
                L.started = True
                self.sound.play("laser_fire")
                self.shake.add(6)
            if not (hb.top < L.y + L.half_h and hb.bottom > L.y - L.half_h):
                continue
            if p.shield_on:
                if id(p) not in L.blocked_by:
                    L.blocked_by.add(id(p))
                    if p.in_parry_window:
                        p.special = min(C.SPECIAL_MAX, p.special + C.SPECIAL_GAIN_PARRY)
                        p.stats["parries"] += 1
                        self.sound.play("parry")
                        self.notify("parry", "PERFECT!", p.x + 50, p.y - 110, C.C_PARRY, 0.25, self.fonts.big)
                    else:
                        self.sound.play("block")
                        p.stats["blocks"] += 1
                if not p.in_parry_window or L.t - L.warn > C.PARRY_WINDOW:
                    p.energy -= 55 * dt
                p.energy_delay = C.ENERGY_REGEN_DELAY
                sx, sy = p.shield_center
                if random.random() < 0.7:
                    self.particles.emit(sx + C.SHIELD_RADIUS * p.facing, L.y + random.uniform(-20, 20),
                                        -p.facing * random.uniform(50, 250), random.uniform(-200, 200),
                                        L.color, life=0.3, size=3)
                if p.energy <= 0:
                    self.guard_break(p)
            elif id(p) not in L.hit and p.iframes <= 0:
                L.hit.add(id(p))
                self.damage_player(p, L.damage, p.x, L.y)

    def update_beam(self, p, dt):
        b = self.boss
        beam = p.beam
        if beam is None:
            return
        beam.update(dt)
        if not beam.alive:
            p.beam = None
            return
        y, x0 = beam.y, beam.x0
        self.beam_particles(p, beam)
        for pr in self.projectiles:
            if pr.alive and pr.owner == "boss" and abs(pr.y - y) < beam.half_h + pr.radius and \
                    (pr.x - x0) * p.facing > 0:
                pr.alive = False
                self.particles.burst(pr.x, pr.y, pr.color, n=8, speed=(60, 200), life=(0.1, 0.3))
        if b.vulnerable and abs(b.y - y) < beam.half_h + b.radius * 0.8:
            dmg = beam.dps * dt * self.combo_mult(p)
            b.take_damage(dmg)
            p.stats["damage"] += dmg
            beam.dmg_accum += dmg
            p.combo_timer = C.COMBO_WINDOW
            self.shake.add(3)
            if random.random() < 0.5:
                self.particles.burst(b.x - b.radius * 0.8, y, beam.color, n=4, speed=(100, 400),
                                     life=(0.2, 0.5), angle=math.pi, spread=2.0)
            if beam.dmg_accum >= 8:
                self.texts.append(FloatingText(b.x - 40 + random.uniform(-30, 30), b.y - 60, str(int(beam.dmg_accum)),
                                               beam.color, self.fonts.mid, 0.7))
                beam.dmg_accum = 0.0
            if b.hp <= 0:
                self.boss_defeated()

    def boss_defeated(self):
        if self.end_kind is not None:
            return
        self.end_kind = "victory"
        self.end_timer = 3.0
        self.slowmo = 1.2
        self.boss.set_state("dying")
        self.boss.queue.clear()
        self.players[0].beam = None
        self.clear_boss_attacks()
        self.show_banner("K.O.!", None, C.C_SPECIAL, 2.5)
        self.sound.play("roar")
        self.sound.play("explosion")
        self.shake.add(20)

    def player_defeated(self, p):
        if self.end_kind is not None:
            return
        self.end_kind = "defeat"
        self.end_timer = 2.2
        self.slowmo = 1.5
        self.boss.set_state("gloat")
        self.boss.queue.clear()
        p.shield_on = False
        self.show_banner("DEFEATED", None, (255, 80, 80), 2.2)
        self.particles.burst(p.x, p.y, (255, 80, 80), n=80, speed=(80, 500), life=(0.4, 1.2))

    # ------------------------------------------------------------------ combat: versus
    def collide_versus(self):
        prs = self.projectiles
        # karşı karşıya gelen mermiler: güçlü olan devam eder, eşitse ikisi de yok olur
        for i, pr in enumerate(prs):
            if not pr.alive:
                continue
            for q in prs[i + 1:]:
                if not q.alive or q.shooter is pr.shooter:
                    continue
                if (pr.x - q.x) ** 2 + (pr.y - q.y) ** 2 > (pr.radius + q.radius) ** 2:
                    continue
                rp, rq = CLASH_RANK.get(pr.kind, 0), CLASH_RANK.get(q.kind, 0)
                if rp <= rq:
                    pr.alive = False
                if rq <= rp:
                    q.alive = False
                self.particles.burst((pr.x + q.x) / 2, (pr.y + q.y) / 2, (255, 230, 180), n=20, speed=(80, 350),
                                     life=(0.15, 0.4))
                self.sound.play("block", 0.6)
                self.shake.add(3)
                if not pr.alive:
                    break
        if self.end_kind is not None:
            return
        for pr in prs:
            if not pr.alive or pr.shooter is None:
                continue
            att = pr.shooter
            dfn = self.opponent(att)
            if dfn.hp <= 0:
                continue
            if dfn.shield_on:
                sx, sy = dfn.shield_center
                if (pr.x - sx) ** 2 + (pr.y - sy) ** 2 <= (C.SHIELD_RADIUS + pr.radius) ** 2:
                    if dfn.in_parry_window:
                        self.parry(dfn, pr, (att.x, att.y), pr.damage * C.VS_REFLECT_MULT)
                    else:
                        self.block(dfn, pr)
                    continue
            if dfn.iframes <= 0 and circle_rect_hit(pr.x, pr.y, pr.radius * 0.85, dfn.hitbox):
                pr.alive = False
                dmg = self.register_hit(att, pr.damage, pr.kind)
                self.damage_player(dfn, dmg, pr.x, pr.y)
                if pr.kind in ("fire", "reflect"):
                    self.hitstop = max(self.hitstop, 0.08)

    def update_beam_versus(self, p, dt):
        beam = p.beam
        if beam is None:
            return
        beam.update(dt)
        if not beam.alive:
            p.beam = None
            return
        self.beam_particles(p, beam)
        y, x0 = beam.y, beam.x0
        opp = self.opponent(p)
        # ışın, rakibin mermilerini yok eder
        for pr in self.projectiles:
            if pr.alive and pr.shooter is opp and abs(pr.y - y) < beam.half_h + pr.radius and \
                    (pr.x - x0) * p.facing > 0:
                pr.alive = False
                self.particles.burst(pr.x, pr.y, pr.color, n=8, speed=(60, 200), life=(0.1, 0.3))
        if self.end_kind is not None or opp.hp <= 0 or abs(opp.y - y) > beam.half_h + 45:
            return
        dmg = beam.dps * dt * self.combo_mult(p)
        if opp.shield_on:  # kalkan ışını büyük ölçüde durdurur ama enerjiyi hızla eritir
            opp.energy -= C.VS_BEAM_BLOCK_DRAIN * dt
            opp.energy_delay = C.ENERGY_REGEN_DELAY
            dmg *= C.VS_BEAM_CHIP
            sx, sy = opp.shield_center
            if random.random() < 0.8:
                self.particles.emit(sx + opp.facing * C.SHIELD_RADIUS, y + random.uniform(-25, 25),
                                    opp.facing * random.uniform(50, 250), random.uniform(-200, 200),
                                    beam.color, life=0.3, size=3)
            if opp.energy <= 0:
                self.guard_break(opp)
        opp.hp = max(0.0, opp.hp - dmg)
        opp.hurt_flash = max(opp.hurt_flash, 0.4)
        opp.stats["dmg_taken"] += dmg
        p.stats["damage"] += dmg
        p.combo_timer = C.COMBO_WINDOW
        beam.dmg_accum += dmg
        self.shake.add(3)
        if beam.dmg_accum >= 5:
            self.texts.append(FloatingText(opp.x + random.uniform(-20, 20), opp.y - 80, str(int(beam.dmg_accum)),
                                           beam.color, self.fonts.mid, 0.6))
            beam.dmg_accum = 0.0
        if opp.hp <= 0:
            self.round_won(p)

    def round_won(self, winner, banner=None):
        if self.end_kind is not None:
            return
        loser = self.opponent(winner)
        self.wins[self.players.index(winner)] += 1
        self.round_winner = winner
        self.end_kind = "round"
        self.end_timer = 3.2
        self.slowmo = 1.4
        for p in self.players:
            p.beam = None
            p.shield_on = False
        perfect = winner.hp >= winner.max_hp
        title = banner or ("PERFECT!" if perfect else "K.O.!")
        self.show_banner(title, f"{winner.name} wins round {self.round}", winner.color, 2.6)
        self.sound.play("explosion")
        self.sound.play("roar", 0.5)
        self.shake.add(22)
        if loser.hp <= 0:
            self.particles.burst(loser.x, loser.y, loser.color, n=90, speed=(80, 520), life=(0.4, 1.2))
        self.set_state("round_end")

    def time_over(self):
        a, b = self.players
        if abs(a.hp - b.hp) < 0.5:
            self.end_kind = "round"
            self.end_timer = 3.0
            self.round_winner = None
            self.show_banner("TIME OVER", "Draw — no point", C.WHITE, 2.4)
            self.set_state("round_end")
            return
        self.round_won(a if a.hp > b.hp else b, banner="TIME OVER")

    def next_round(self):
        if max(self.wins) >= C.VS_ROUNDS_TO_WIN:
            self.sound.play("win")
            self.set_state("match_end")
            return
        self.round += 1
        self.new_fight()
        self.start_countdown()

    # ------------------------------------------------------------------ misc
    def notify(self, key, s, x, y, color, cooldown=0.8, font=None):
        now = self.match_time + self.state_t
        if now - self._notify_t.get(key, -99) < cooldown:
            return
        self._notify_t[key] = now
        self.texts.append(FloatingText(x, y, s, color, font or self.fonts.small, 0.9))

    def show_banner(self, s, sub, color, dur):
        self.banner = dict(text=s, sub=sub, color=color, t=0.0, dur=dur)

    def update_banner(self, dt):
        if self.banner:
            self.banner["t"] += dt
            if self.banner["t"] >= self.banner["dur"]:
                self.banner = None

    # ================================================================== draw
    def draw(self):
        self.draw_world()
        if self.state == "title":
            self.draw_title()
        else:
            self.draw_hud()
            if self.state == "countdown":
                self.draw_countdown()
            elif self.state in ("victory", "defeat"):
                self.draw_end()
            elif self.state == "match_end":
                self.draw_match_end()
        self.draw_banner()
        if self.paused:
            self.draw_pause()
        if self.debug:
            self.draw_debug()

    def draw_world(self):
        w = self.world
        w.blit(self.bg, (0, 0))
        for L in self.lasers:
            L.draw(w)
        if self.boss and self.boss.state != "dead":
            self.boss.draw(w, self)
        for p in self.players:
            if p.hp > 0:
                p.draw(w, self.fonts)
            if self.versus and p.hp > 0:
                text(w, self.fonts.tiny, p.name, (p.x, p.y - 96), p.color)
        for p in self.players:
            if p.beam is not None:
                p.beam.draw(w)
        for pr in self.projectiles:
            pr.draw(w)
        self.particles.draw(w)
        for t in self.texts:
            t.draw(w)
        ox, oy = self.shake.offset()
        self.screen.fill((0, 0, 0))
        self.screen.blit(w, (ox, oy))
        if self.red_flash > 0:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            a = int(110 * self.red_flash)
            pygame.draw.rect(ov, (255, 0, 0, a), ov.get_rect(), 40)
            ov.fill((255, 0, 0, a // 3), special_flags=pygame.BLEND_RGBA_MAX)
            self.screen.blit(ov, (0, 0))

    # ------------------------------------------------------------------ HUD
    def draw_hud(self):
        if self.versus:
            self.draw_hud_versus()
            return
        s, f, b = self.screen, self.fonts, self.boss
        self.draw_player_panel(self.players[0])
        panel(s, (W - 418, 10, 404, 118), border=(80, 80, 120))
        text(s, f.small, C.BOSS_NAME, (W - 404, 22), b.color, "topleft")
        text(s, f.small, f"PHASE {b.phase}", (W - 30, 22), C.WHITE, "topright")
        brect = pygame.Rect(W - 404, 50, 376, 30)
        bar(s, brect, b.hp / b.max_hp, C.C_BOSS_HP, ghost=b.ghost_hp / b.max_hp)
        for k in (1 / 3, 2 / 3):
            x = brect.x + 3 + int((brect.w - 6) * k)
            pygame.draw.line(s, (240, 240, 255), (x, brect.y - 3), (x, brect.bottom + 3), 2)
        mins, secs = divmod(int(self.fight_time), 60)
        text(s, f.tiny, f"TIME {mins:02d}:{secs:02d}", (W - 30, 92), (200, 200, 220), "topright")
        text(s, f.tiny, self.difficulty.upper(), (W - 404, 92), (200, 200, 220), "topleft")
        self.draw_preview(pygame.Rect(W // 2 - 150, 8, 300, 225))
        self.draw_legend(H - 52)

    def draw_hud_versus(self):
        s, f = self.screen, self.fonts
        rects = [pygame.Rect(14, 10, 404, 84), pygame.Rect(W - 418, 10, 404, 84)]
        for k, (p, r) in enumerate(zip(self.players, rects)):
            self.draw_player_panel_compact(p, r, mirror=k == 1)
            # raunt galibiyetleri
            for i in range(C.VS_ROUNDS_TO_WIN):
                x = r.x + 24 + i * 28 if k == 0 else r.right - 24 - i * 28
                won = self.wins[k] > i
                pygame.draw.circle(s, (20, 14, 30), (x, r.bottom + 18), 11)
                pygame.draw.circle(s, p.color if won else (70, 64, 90), (x, r.bottom + 18), 8)
        self.draw_preview(pygame.Rect(W // 2 - 130, 8, 260, 195))
        box = pygame.Rect(W // 2 - 44, 212, 88, 44)
        panel(s, box, color=(20, 14, 30), alpha=230, border=(230, 230, 250), radius=8)
        tcol = (255, 90, 70) if self.round_timer < 10 else C.C_SPECIAL
        text(s, f.mid, str(int(math.ceil(self.round_timer))), box.center, tcol)
        text(s, f.tiny, f"ROUND {self.round}", (W // 2, 268), (210, 210, 230))
        self.draw_legend(H - 52)

    def draw_player_panel(self, p):
        s, f = self.screen, self.fonts
        panel(s, (14, 10, 404, 154), border=(80, 80, 120))
        text(s, f.small, p.name, (30, 22), C.C_SHIELD, "topleft")
        hp_frac = p.hp / p.max_hp
        text(s, f.small, f"{int(math.ceil(p.hp))}/{p.max_hp}", (404, 22), C.WHITE, "topright")
        bar(s, (28, 48, 376, 28), hp_frac, lerp_color(C.C_HP_LOW, C.C_HP, (hp_frac - 0.2) / 0.5),
            ghost=p.ghost_hp / p.max_hp)
        text(s, f.tiny, "ENERGY", (30, 84), C.C_ENERGY, "topleft")
        bar(s, (104, 82, 300, 20), p.energy / C.PLAYER_MAX_ENERGY,
            C.C_ENERGY if p.guard_break <= 0 else (110, 110, 130))
        sp = p.special / C.SPECIAL_MAX
        text(s, f.tiny, "SPECIAL", (30, 118), C.C_SPECIAL, "topleft")
        if sp >= 1:
            pulse = 0.5 + 0.5 * math.sin(self.state_t * 8)
            blit_glow(s, (254, 124), 120, scale_color(C.C_SPECIAL, 0.4 * pulse))
        bar(s, (104, 112, 300, 26), sp, C.C_SPECIAL if sp < 1 else lerp_color(C.C_SPECIAL, C.WHITE, 0.3))
        if sp >= 1:
            gesture_icon(s, Gesture.PEACE, (226, 116), 22, C.WHITE)
            text(s, f.tiny, "READY!", (276, 125), (40, 30, 0), shadow=False)
        if p.combo >= 2:
            k = min(1.0, p.combo_timer / C.COMBO_WINDOW)
            text(s, f.mid, f"{p.combo} HIT COMBO", (24, 176), lerp_color((150, 150, 150), C.C_SPECIAL, k), "topleft")
            text(s, f.tiny, f"+{int((self.combo_mult(p) - 1) * 100)}% damage", (26, 214), C.WHITE, "topleft")

    def draw_player_panel_compact(self, p, r, mirror=False):
        """Versus için küçük panel; P2'de (mirror) her şey ayna simetrisi, barlar sağdan dolar."""
        s, f = self.screen, self.fonts
        panel(s, r, border=p.color)
        hp_frac = p.hp / p.max_hp
        hp_col = lerp_color(C.C_HP_LOW, C.C_HP, (hp_frac - 0.2) / 0.5)
        half = (r.w - 70) // 2
        sp = p.special / C.SPECIAL_MAX
        sp_col = C.C_SPECIAL if sp < 1 else lerp_color(C.C_SPECIAL, C.WHITE, 0.3)
        en_col = C.C_ENERGY if p.guard_break <= 0 else (110, 110, 130)

        def mx(x, w=0):
            """Sol paneldeki x konumunu, sağ panel için aynala."""
            return r.right - (x - r.x) - w if mirror else x

        a_l, a_r = ("topright", "topleft") if mirror else ("topleft", "topright")
        text(s, f.small, p.name, (mx(r.x + 14), r.y + 8), p.color, a_l)
        hp_rect = pygame.Rect(mx(r.x + 56, r.w - 120), r.y + 8, r.w - 120, 24)
        bar(s, hp_rect, hp_frac, hp_col, ghost=p.ghost_hp / p.max_hp, reverse=mirror)
        text(s, f.small, f"{int(math.ceil(p.hp))}", (mx(r.right - 14), r.y + 8), C.WHITE, a_r)
        text(s, f.tiny, "EN", (mx(r.x + 56), r.y + 52), C.C_ENERGY, a_l)
        en_rect = pygame.Rect(mx(r.x + 82, half - 52), r.y + 50, half - 52, 18)
        bar(s, en_rect, p.energy / C.PLAYER_MAX_ENERGY, en_col, reverse=mirror)
        sx = r.x + 40 + half
        text(s, f.tiny, "SP", (mx(sx), r.y + 52), C.C_SPECIAL, a_l)
        sp_rect = pygame.Rect(mx(sx + 26, half - 16), r.y + 50, half - 16, 18)
        if sp >= 1:
            blit_glow(s, sp_rect.center, 70, scale_color(C.C_SPECIAL, 0.4 * (0.5 + 0.5 * math.sin(self.state_t * 8))))
        bar(s, sp_rect, sp, sp_col, reverse=mirror)
        if p.combo >= 2:
            text(s, f.small, f"x{p.combo}", (mx(r.x + 14), r.y + 46), C.C_SPECIAL, a_l)

    def draw_legend(self, y):
        s, f = self.screen, self.fonts
        cw, gap = 250, 12
        x0 = (W - (4 * cw + 3 * gap)) // 2
        for i, g in enumerate(LEGEND):
            r = pygame.Rect(x0 + i * (cw + gap), y, cw, 44)
            users = [p for p in self.players if p.gesture is g and p.hp > 0]
            active = bool(users)
            col = GESTURE_COLOR[g]
            if active:
                blit_glow(s, r.center, 150, scale_color(col, 0.35))
            panel(s, r, color=(30, 26, 50) if not active else scale_color(col, 0.35),
                  alpha=200, border=col if active else (70, 70, 100), radius=8)
            gesture_icon(s, g, (r.x + 26, r.y + 24), 30, col)
            text(s, f.small, GESTURE_ACTION[g], (r.x + 52, r.y + 4), C.WHITE, "topleft")
            hint = GESTURE_HAND[g]
            if g is Gesture.POINT:
                hint += f"  · {C.FIRE['energy']} EN"
            elif g is Gesture.PEACE and not self.versus:
                hint += f"  · {int(self.players[0].special)}%"
            elif g is Gesture.PALM:
                hint += "  · parry!"
            text(s, f.tiny, hint, (r.x + 53, r.y + 25), (190, 190, 210), "topleft", shadow=False)
            if self.versus:
                for k, p in enumerate(users):
                    tag = pygame.Rect(r.right - 34 - k * 34, r.y + 4, 30, 18)
                    pygame.draw.rect(s, p.color, tag, border_radius=5)
                    text(s, f.tiny, p.name, tag.center, (10, 10, 20), shadow=False)

    def draw_preview(self, rect, big=False):
        s, f = self.screen, self.fonts
        panel(s, rect.inflate(8, 8), color=(10, 10, 20), alpha=230, radius=8)
        if self.tracker is None:
            text(s, f.small, "KEYBOARD MODE", (rect.centerx, rect.y + 24), C.C_SPECIAL)
            if self.versus:
                lines = ["P1: 1 2 3 4  ·  W / S", "P2: 7 8 9 0  ·  ↑ / ↓",
                         "(punch · shield · fire · special)"]
            else:
                lines = ["1 / J : Punch", "2 / K : Shield", "3 / L : Fire", "4 / ; : Special", "W S / ↑ ↓ : Move"]
            for i, ln in enumerate(lines):
                text(s, f.tiny, ln, (rect.centerx, rect.y + 58 + i * 24), C.WHITE)
            text(s, f.tiny, self.camera_msg[:36], (rect.centerx, rect.bottom - 14), (255, 120, 120))
            return
        frame, hands, fid = self.tracker.snapshot()
        if frame is None:
            text(s, f.small, "Starting camera...", rect.center, C.WHITE)
            return
        surf, cid, csize = self._preview
        if cid != fid or csize != rect.size:
            img = pygame.image.frombuffer(frame.tobytes(), (frame.shape[1], frame.shape[0]), "RGB")
            surf = pygame.transform.smoothscale(img, rect.size)
            self._preview = (surf, fid, rect.size)
        s.blit(surf, rect)
        # el yüksekliği aralığı kılavuzu
        for v in (C.HAND_Y_MIN, C.HAND_Y_MAX):
            yy = rect.y + int(v * rect.h)
            for x in range(rect.x, rect.right, 16):
                pygame.draw.line(s, (255, 255, 255), (x, yy), (min(x + 8, rect.right), yy), 1)
        if self.versus:
            pygame.draw.line(s, (255, 255, 255), (rect.centerx, rect.y), (rect.centerx, rect.bottom), 3)
            for k, p in enumerate(self.players):
                text(s, f.small, p.name, (rect.x + rect.w * (0.25 + 0.5 * k), rect.y + 16), p.color)
        for slot, h in hands.items():
            col = GESTURE_COLOR[h.gesture]
            pts = [(rect.x + x * rect.w, rect.y + y * rect.h) for x, y in h.points]
            for a, bb in HAND_CONNECTIONS:
                pygame.draw.line(s, col, pts[a], pts[bb], 3 if big else 2)
            for i, pt in enumerate(pts):
                tip = i in (4, 8, 12, 16, 20)
                pygame.draw.circle(s, (255, 255, 255) if tip else col, (int(pt[0]), int(pt[1])), 5 if tip else 3)
            cx, cy = rect.x + h.center[0] * rect.w, rect.y + h.center[1] * rect.h
            ring = self.players[slot].color if self.versus and slot < len(self.players) else col
            pygame.draw.circle(s, ring, (int(cx), int(cy)), 11, 3)
        if self.versus:
            for k in range(2):
                if k not in hands and int(self.state_t * 3) % 2 == 0:
                    text(s, f.tiny if not big else f.small, f"{self.players[k].name}: SHOW HAND",
                         (rect.x + rect.w * (0.25 + 0.5 * k), rect.centery), (255, 200, 80))
            border = (200, 200, 220)
        else:
            h = hands.get(0)
            if h is None and int(self.state_t * 3) % 2 == 0:
                text(s, f.mid if big else f.small, "SHOW YOUR HAND", rect.center, (255, 200, 80))
            border = GESTURE_COLOR[h.gesture] if h is not None else (90, 90, 110)
        pygame.draw.rect(s, border, rect.inflate(6, 6), 3, border_radius=8)
        # alt etiket
        lab = pygame.Rect(rect.x, rect.bottom - 30, rect.w, 30)
        panel(s, lab, color=(0, 0, 0), alpha=150, radius=0)
        if self.versus:
            for k, p in enumerate(self.players):
                h = hands.get(k)
                g = h.gesture if h is not None else Gesture.NONE
                cx = lab.x + lab.w * (0.25 + 0.5 * k)
                if g is not Gesture.NONE:
                    gesture_icon(s, g, (cx - 36, lab.y + 17), 20, GESTURE_COLOR[g])
                    text(s, f.tiny, GESTURE_ACTION[g], (cx - 22, lab.centery), GESTURE_COLOR[g], "midleft")
                else:
                    text(s, f.tiny, "-", (cx, lab.centery), (150, 150, 170))
        else:
            h = hands.get(0)
            g = h.gesture if h is not None else Gesture.NONE
            if g is not Gesture.NONE:
                gesture_icon(s, g, (lab.x + 22, lab.y + 17), 24, GESTURE_COLOR[g])
                text(s, f.small, f"{GESTURE_HAND[g]} → {GESTURE_ACTION[g]}", (lab.x + 42, lab.centery),
                     GESTURE_COLOR[g], "midleft")
            else:
                text(s, f.tiny, "camera · move hand up/down to move", lab.center, (180, 180, 200))

    # ------------------------------------------------------------------ screens
    def draw_title(self):
        s, f = self.screen, self.fonts
        t = self.state_t
        blit_glow(s, (W // 2, 78), 320, (70, 30, 110))
        text(s, f.huge, "GESTURE FIGHTER", (W // 2, 78), lerp_color(C.C_SPECIAL, C.C_FIRE, 0.5 + 0.5 * math.sin(t * 2)))
        text(s, f.small, "ME461  ·  Camera-controlled gesture battles", (W // 2, 140), (210, 200, 240))
        self.draw_preview(pygame.Rect(W // 2 - 200, 166, 400, 300), big=True)

        # mod seçimi: açık el = boss, iki parmak = versus
        y = 496
        cards = [("solo", Gesture.PALM, "1 PLAYER", "vs boss", "SPACE"),
                 ("versus", Gesture.PEACE, "2 PLAYERS", "versus", "V")]
        cw, gap = 380, 30
        x0 = (W - (2 * cw + gap)) // 2
        for i, (key, g, title, sub, k) in enumerate(cards):
            r = pygame.Rect(x0 + i * (cw + gap), y, cw, 62)
            prog = self.holds.get(key, 0.0)
            col = GESTURE_COLOR[g]
            if prog > 0:
                blit_glow(s, r.center, 200, scale_color(col, 0.2 + 0.3 * prog))
            panel(s, r, color=(26, 20, 40), alpha=225, border=col if prog > 0 else (90, 90, 130), radius=10)
            gesture_icon(s, g, (r.x + 38, r.centery + 3), 40, col)
            text(s, f.mid, title, (r.x + 72, r.y + 6), C.WHITE, "topleft")
            how = f"hold {GESTURE_HAND[g].lower()}  ·  " if self.tracker else ""
            text(s, f.tiny, f"{sub}  ·  {how}key {k}", (r.x + 73, r.y + 40), (190, 190, 210), "topleft", shadow=False)
            if prog > 0:
                pygame.draw.rect(s, col, (r.x + 6, r.bottom - 7, int((r.w - 12) * prog), 4))
        text(s, f.tiny, f"Boss difficulty: ◀ {self.difficulty.upper()} ▶    F11: fullscreen    ESC: quit",
             (W // 2, y + 82), (190, 190, 210))
        tip = TIPS[int(t / 4) % len(TIPS)]
        text(s, f.small, "TIP: " + tip, (W // 2, y + 112), (255, 220, 140))
        self.draw_legend(H - 52)

    def draw_countdown(self):
        n = 3 - int(self.state_t)
        frac = self.state_t % 1.0
        size = int(180 - 60 * frac)
        font = self.fonts.get(max(20, size))
        if self.versus:
            final = self.wins[0] == self.wins[1] == C.VS_ROUNDS_TO_WIN - 1
            text(self.screen, self.fonts.big, "FINAL ROUND" if final else f"ROUND {self.round}",
                 (W // 2, H // 2 - 90), C.WHITE)
        text(self.screen, font, str(max(1, n)), (W // 2, H // 2 + 20), C.C_SPECIAL, alpha=int(255 * (1 - frac * 0.6)))
        msg = ("P1: left half of the camera  ·  P2: right half" if self.versus
               else "Get ready — move your hand to see your fighter move!")
        text(self.screen, self.fonts.small, msg, (W // 2, H // 2 + 130), C.WHITE)

    def draw_banner(self):
        bn = self.banner
        if not bn:
            return
        t, dur = bn["t"], bn["dur"]
        pop = min(1.0, t / 0.15)
        alpha = int(255 * min(1.0, (dur - t) / 0.4))
        size = int(lerp(160, 110, pop))
        y = H // 2 - 20
        blit_glow(self.screen, (W // 2, y), 260, scale_color(bn["color"], 0.35 * alpha / 255))
        text(self.screen, self.fonts.get(size), bn["text"], (W // 2, y), bn["color"], alpha=alpha)
        if bn["sub"]:
            text(self.screen, self.fonts.mid, bn["sub"], (W // 2, y + 80), C.WHITE, alpha=alpha)

    def _end_overlay(self):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, min(150, int(self.state_t * 300))))
        self.screen.blit(ov, (0, 0))

    def _again_prompt(self, r):
        s, f = self.screen, self.fonts
        prog = self.holds.get("again", 0.0)
        if prog > 0:
            bar(s, (r.x + 110, r.bottom - 66, r.w - 220, 12), prog, C.C_SHIELD)
        msg = "Hold OPEN PALM or press SPACE to fight again" if self.tracker else "SPACE: fight again"
        text(s, f.small, msg, (r.centerx, r.bottom - 36), C.WHITE)
        text(s, f.tiny, "ESC: main menu", (r.centerx, r.bottom - 12), (170, 170, 190))

    def draw_end(self):
        s, f = self.screen, self.fonts
        self._end_overlay()
        win = self.state == "victory"
        col = C.C_SPECIAL if win else (255, 80, 80)
        r = pygame.Rect(0, 0, 620, 420)
        r.center = (W // 2, H // 2 + 10)
        panel(s, r, color=(16, 12, 30), alpha=235, border=col, radius=14, width=3)
        text(s, f.big, "VICTORY!" if win else "DEFEATED", (r.centerx, r.y + 50), col)
        p = self.players[0]
        st = p.stats
        acc = f"{100 * st['hits'] / st['shots']:.0f}%" if st["shots"] else "-"
        mins, secs = divmod(int(self.fight_time), 60)
        rows = [
            ("Time", f"{mins:02d}:{secs:02d}"),
            ("HP left" if win else "Boss HP left",
             f"{int(p.hp)}" if win else f"{int(100 * self.boss.hp / self.boss.max_hp)}%"),
            ("Accuracy", f"{acc}  ({st['hits']}/{st['shots']})"),
            ("Parries / Blocks", f"{st['parries']} / {st['blocks']}"),
            ("Max combo", str(st["max_combo"])),
            ("Specials used", str(st["specials"])),
        ]
        for i, (k, v) in enumerate(rows):
            yy = r.y + 112 + i * 36
            text(s, f.small, k, (r.x + 60, yy), (200, 200, 220), "midleft")
            text(s, f.small, v, (r.right - 60, yy), C.WHITE, "midright")
        if win:
            rank = self.rank()
            rc = {"S": C.C_SPECIAL, "A": C.C_HP, "B": C.C_SHIELD, "C": (200, 200, 200)}[rank]
            blit_glow(s, (r.right - 70, r.y + 50), 70, scale_color(rc, 0.5))
            text(s, f.big, rank, (r.right - 70, r.y + 50), rc)
        self._again_prompt(r)

    def draw_match_end(self):
        s, f = self.screen, self.fonts
        self._end_overlay()
        a, b = self.wins
        winner = self.players[0] if a > b else self.players[1]
        r = pygame.Rect(0, 0, 680, 450)
        r.center = (W // 2, H // 2 + 10)
        panel(s, r, color=(16, 12, 30), alpha=235, border=winner.color, radius=14, width=3)
        blit_glow(s, (r.centerx, r.y + 52), 200, scale_color(winner.color, 0.35))
        text(s, f.big, f"{winner.name} WINS!", (r.centerx, r.y + 52), winner.color)
        mins, secs = divmod(int(self.match_time), 60)
        text(s, f.small, f"Rounds {a} - {b}   ·   Time {mins:02d}:{secs:02d}", (r.centerx, r.y + 100),
             (200, 200, 220))

        def acc(st):
            return f"{100 * st['hits'] / st['shots']:.0f}%" if st["shots"] else "-"

        rows = [("Damage dealt", lambda st: str(int(st["damage"]))),
                ("Accuracy", acc),
                ("Parries / Blocks", lambda st: f"{st['parries']} / {st['blocks']}"),
                ("Max combo", lambda st: str(st["max_combo"])),
                ("Specials", lambda st: str(st["specials"]))]
        cols_x = [r.right - 230, r.right - 90]
        for k, p in enumerate(self.players):
            text(s, f.mid, p.name, (cols_x[k], r.y + 146), p.color)
        for i, (label, fn) in enumerate(rows):
            yy = r.y + 190 + i * 34
            text(s, f.small, label, (r.x + 50, yy), (200, 200, 220), "midleft")
            for k, st in enumerate(self.match_stats):
                text(s, f.small, fn(st), (cols_x[k], yy), C.WHITE)
        self._again_prompt(r)

    def rank(self):
        hp = self.players[0].hp
        t = self.fight_time
        if t < 100 and hp >= 60:
            return "S"
        if t < 140 and hp >= 35:
            return "A"
        if hp >= 15 or t < 160:
            return "B"
        return "C"

    def draw_pause(self):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        self.screen.blit(ov, (0, 0))
        text(self.screen, self.fonts.big, "PAUSED", (W // 2, H // 2 - 30), C.WHITE)
        text(self.screen, self.fonts.small, "ESC / P: resume      Q: main menu", (W // 2, H // 2 + 30), (200, 200, 220))

    def draw_debug(self):
        boss = self.boss.state if self.boss else "-"
        lines = [f"FPS {self.clock.get_fps():.0f}", f"state {self.state}  boss {boss}  mode {self.mode}"]
        if self.tracker:
            _, hands, _ = self.tracker.snapshot()
            lines.append(f"tracker {self.tracker.fps:.1f} fps  split {self.tracker.split}")
            for slot, h in sorted(hands.items()):
                lines.append(f"hand{slot} raw {h.raw.name} stable {h.gesture.name} fingers "
                             + "".join("1" if x else "0" for x in h.fingers))
                lines.append(f"  center {h.center[0]:.2f},{h.center[1]:.2f} size {h.size:.2f}")
        lines.append(f"proj {len(self.projectiles)} parts {len(self.particles.items)}")
        r = pygame.Rect(10, H - 70 - 22 * len(lines), 430, 22 * len(lines) + 10)
        panel(self.screen, r, alpha=210)
        for i, ln in enumerate(lines):
            text(self.screen, self.fonts.tiny, ln, (r.x + 10, r.y + 6 + i * 22), (160, 255, 160), "topleft",
                 shadow=False)


def main(args):
    Game(args).run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(0)
