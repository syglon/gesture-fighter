"""Dövüşçü: durum makinesi, fizik, vuruş/hasar kutuları ve çizim."""
import math
from dataclasses import dataclass

import pygame

from gesture_fighter.draw import blit_glow

from . import config as C
from . import skeleton as sk
from .moves import AIR, CROUCH, GROUND, MOVES


@dataclass
class Intent:
    """Bir karede dövüşçüden istenen şey (el, klavye veya CPU üretir)."""
    move: int = 0            # -1 sol, +1 sağ (ekran yönü)
    crouch: bool = False
    jump: bool = False       # kenar (o karede tetiklendi)
    block: bool = False      # basılı tutma
    attack: str | None = None  # kenar: punch | heavy | kick | special


ACTIONABLE = ("idle", "walk", "crouch", "block")


class Fighter:
    def __init__(self, colors, x, facing):
        self.colors = colors
        self.name = colors["name"]
        self.wins = 0
        self.reset(x, facing)

    def reset(self, x, facing):
        self.x, self.y = float(x), 0.0
        self.vx = self.vy = 0.0
        self.slide = 0.0
        self.facing = facing
        self.hp = self.ghost_hp = float(C.MAX_HP)
        self.ghost_delay = 0.0
        self.meter = getattr(self, "meter", 0.0)
        self.state = "intro"
        self.state_t = 0.0
        self.move = None
        self.move_t = 0.0
        self.move_hit = False
        self.spawned = False
        self.stun = 0.0
        self.buffer = None
        self.buffer_t = 0.0
        self.crouching = False
        self.holding_block = False
        self.air_attacked = False
        self.flash = 0.0
        self.invuln = 0.0
        self.combo_taken = 0
        self.t = 0.0
        self.walk_phase = 0.0
        self.pose = dict(sk.POSES["idle"])
        self.last_label = None
        self.label_t = 0.0

    # ------------------------------------------------------------------ helpers
    def set_state(self, s):
        if s != self.state:
            self.state = s
            self.state_t = 0.0

    @property
    def grounded(self):
        return self.y <= 0 and self.vy == 0

    @property
    def actionable(self):
        return self.state in ACTIONABLE

    @property
    def phase(self):
        if self.state != "attack" or self.move is None:
            return None
        m, t = self.move, self.move_t
        if t < m.startup:
            return "startup"
        if t < m.startup + m.active:
            return "active"
        return "recovery"

    def world_rect(self, ox, oy, w, h, y_base=None):
        """Bakış çerçevesindeki kutuyu dünya (ekran-y aşağı) koordinatına çevirir."""
        k = C.SCALE
        cx = self.x + self.facing * ox * k
        cy = C.FLOOR_Y - ((self.y if y_base is None else y_base) + oy * k)
        return pygame.Rect(int(cx - w * k / 2), int(cy - h * k / 2), int(w * k), int(h * k))

    def hurtbox(self):
        if self.state in ("down", "ko") or self.invuln > 0:
            return None
        if self.state == "knock":
            if self.combo_taken >= 5:  # sonsuz havada kombo olmasın
                return None
            return self.world_rect(0, 60, 110, 70)
        if not self.grounded or self.state == "jump":
            return self.world_rect(0, 95, 56, 130)
        low = self.crouching and self.state in ("crouch", "block", "blockstun", "hitstun") or \
            (self.move is not None and self.move.crouching)
        if low:
            return self.world_rect(-2, 55, 64, 110)
        return self.world_rect(0, 86, 56, 172)

    def hitbox(self):
        if self.phase != "active" or self.move_hit or self.move.box[2] == 0:
            return None
        return self.world_rect(*self.move.box)

    def can_block(self, move):
        if not self.grounded:
            return False
        blocking = self.state in ("block", "blockstun") or (self.actionable and self.holding_block)
        if not blocking:
            return False
        if move.level == "low" and not self.crouching:
            return False
        if move.level == "high" and self.crouching:
            return False
        return True

    def resolve(self, button, crouch):
        if not self.grounded:
            return AIR.get(button)
        if button == "special":
            return "super" if self.meter >= C.SUPER_COST else "fireball"
        return (CROUCH if crouch else GROUND).get(button)

    # ------------------------------------------------------------------ actions
    def start_move(self, name, game):
        m = MOVES[name]
        if m.projectile == "fireball" and game.has_fireball(self):
            return False  # aynı anda tek ateş topu
        self.move = m
        self.move_t = 0.0
        self.move_hit = False
        self.spawned = False
        self.set_state("attack")
        self.state_t = 0.0
        if m.air:
            self.air_attacked = True
        else:
            self.vx = 0.0
        self.crouching = m.crouching
        if name == "super":
            self.meter -= C.SUPER_COST
            game.on_super(self)
        game.sound.play("whoosh", 0.5)
        return True

    def take_hit(self, att, m, dmg, direction):
        self.hp = max(0.0, self.hp - dmg)
        self.ghost_delay = 0.6
        self.flash = 0.12
        self.combo_taken += 1
        self.move = None
        if not self.grounded or m.knockdown or self.hp <= 0 or self.state == "knock":
            self.set_state("knock")
            self.vy = max(m.launch, 430.0)
            self.vx = direction * max(170.0, m.push * 0.55)
            self.y = max(self.y, 1.0)
        else:
            self.set_state("hitstun")
            self.state_t = 0.0
            self.stun = m.hitstun
            self.slide = direction * m.push

    def block_hit(self, m, direction):
        self.set_state("blockstun")
        self.state_t = 0.0
        self.stun = m.blockstun
        self.slide = direction * m.push * 0.8
        chip = m.damage * m.chip
        if chip > 0:
            self.hp = max(1.0, self.hp - chip)
            self.ghost_delay = 0.6

    # ------------------------------------------------------------------ update
    def update(self, dt, it, opp, game):
        self.t += dt
        self.state_t += dt
        self.flash = max(0.0, self.flash - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.label_t = max(0.0, self.label_t - dt)
        self.ghost_delay -= dt
        if self.ghost_delay <= 0 and self.ghost_hp > self.hp:
            self.ghost_hp = max(self.hp, self.ghost_hp - dt * 45)

        if it.attack:
            self.buffer, self.buffer_t = it.attack, C.INPUT_BUFFER
        else:
            self.buffer_t -= dt
            if self.buffer_t <= 0:
                self.buffer = None

        s = self.state
        if s in ("intro", "win"):
            self.vx = 0
        elif s == "ko":
            self._air_physics(dt)
        elif s in ("hitstun", "blockstun"):
            self.stun -= dt
            if self.stun <= 0:
                self.combo_taken = 0
                self.set_state("crouch" if self.crouching else "idle")
        elif s == "knock":
            if self._air_physics(dt):
                game.on_land(self, heavy=True)
                if self.hp <= 0:
                    self.set_state("ko")
                else:
                    self.set_state("down")
        elif s == "down":
            self.vx = 0
            if self.state_t > 0.6:
                self.set_state("getup")
                self.invuln = 0.4
        elif s == "getup":
            if self.state_t > 0.35:
                self.combo_taken = 0
                self.set_state("idle")
        elif s == "jump":
            if self.buffer and not self.air_attacked:
                name = self.resolve(self.buffer, False)
                if name:
                    self.buffer = None
                    self.start_move(name, game)
            if self.state == "jump" and self._air_physics(dt):
                game.on_land(self)
                self.set_state("land")
        elif s == "land":
            if self.state_t > 0.07:
                self.set_state("idle")
        elif s == "attack":
            self._update_attack(dt, it, opp, game)
        else:  # ACTIONABLE
            self._update_neutral(dt, it, opp, game)

        # yer fiziği
        if self.grounded and self.state not in ("knock", "jump") and not (self.move and self.move.air):
            self.x += (self.vx + self.slide) * dt
            self.slide *= max(0.0, 1.0 - 9.0 * dt)
            if abs(self.slide) < 5:
                self.slide = 0.0

        self._update_pose(dt)

    def face(self, opp):
        d = opp.x - self.x
        if abs(d) > 4:
            self.facing = 1 if d > 0 else -1

    def _update_neutral(self, dt, it, opp, game):
        self.face(opp)
        self.crouching = it.crouch
        self.holding_block = it.block
        self.air_attacked = False
        if self.buffer:
            name = self.resolve(self.buffer, it.crouch)
            self.buffer = None
            if name and self.start_move(name, game):
                return
        if it.jump:
            self.set_state("jump")
            self.vy = C.JUMP_VY
            self.vx = it.move * C.JUMP_VX
            self.y = 0.5
            self.crouching = False
            game.on_jump(self)
            return
        self.vx = 0.0
        if it.block:
            self.set_state("block")
        elif it.crouch:
            self.set_state("crouch")
        elif it.move:
            self.set_state("walk")
            fwd = it.move == self.facing
            self.vx = it.move * (C.WALK_FWD if fwd else C.WALK_BACK)
            self.walk_phase += dt * (11 if fwd else -9)
        else:
            self.set_state("idle")

    def _update_attack(self, dt, it, opp, game):
        m = self.move
        self.move_t += dt
        ph = self.phase
        if m.lunge and ph in ("startup", "active"):
            self.x += self.facing * m.lunge * dt
        if m.projectile and not self.spawned and self.move_t >= m.startup:
            self.spawned = True
            game.spawn_projectile(self, m)
        if m.air:
            if self._air_physics(dt):
                game.on_land(self)
                self.move = None
                self.set_state("land")
                return
        # kombo: isabet ettiyse bir sonraki saldırıya iptal et
        if self.move_hit and m.cancel and self.buffer and ph != "startup":
            name = self.resolve(self.buffer, it.crouch)
            if name and name != m.name and self.start_move(name, game):
                self.buffer = None
                return
        if self.move_t >= m.startup + m.active + m.recovery:
            if m.air:
                self.set_state("jump")
                self.move = None
                return
            self.move = None
            self.crouching = m.crouching and it.crouch
            self.set_state("crouch" if self.crouching else "idle")

    def _air_physics(self, dt):
        """Hava fiziği. Yere indiyse True döner."""
        self.vy -= C.GRAVITY * dt
        self.y += self.vy * dt
        self.x += self.vx * dt
        if self.y <= 0:
            self.y = 0.0
            self.vy = 0.0
            self.vx = 0.0
            return True
        return False

    # ------------------------------------------------------------------ pose / draw
    def _target_pose(self):
        s = self.state
        P = sk.POSES
        if s == "attack" and self.move:
            m = self.move
            ph = self.phase
            if ph == "startup":
                return P[m.windup], 22
            if ph == "active":
                return P[m.pose], 32
            k = (self.move_t - m.startup - m.active) / max(0.01, m.recovery)
            return sk.lerp_pose(P[m.pose], P[m.base], min(1.0, k)), 18
        if s == "walk":
            ph = self.walk_phase
            pose = dict(P["idle"])
            pose["ff"] = (26 + 14 * math.sin(ph), max(0.0, 9 * math.cos(ph)))
            pose["bf"] = (-32 - 14 * math.sin(ph), max(0.0, -9 * math.cos(ph)))
            pose["hy"] = 74 + 2 * abs(math.sin(ph))
            return pose, 16
        if s == "idle":
            pose = dict(P["idle"])
            b = math.sin(self.t * 4.5)
            pose["hy"] += b * 2
            pose["fh"] = (pose["fh"][0], pose["fh"][1] + b * 1.5)
            return pose, 14
        table = {
            "crouch": "crouch", "jump": "jump", "land": "crouch", "getup": "crouch", "down": "down",
            "ko": "air_hit" if self.y > 0 else "down", "knock": "air_hit", "win": "win", "intro": "intro",
            "block": "c_block" if self.crouching else "block",
            "blockstun": "c_block" if self.crouching else "block",
            "hitstun": "c_hit" if self.crouching else "hit",
        }
        name = table.get(s, "idle")
        speed = 30 if s in ("hitstun", "knock") else 16
        return P[name], speed

    def _update_pose(self, dt):
        target, speed = self._target_pose()
        self.pose = sk.lerp_pose(self.pose, target, min(1.0, dt * speed))

    def draw(self, surf, cam_x):
        ox = self.x - cam_x
        # gölge
        sw = max(30, 62 * C.SCALE - self.y * 0.1)
        sh = pygame.Surface((int(sw * 2), 14), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 120), sh.get_rect())
        surf.blit(sh, (ox - sw, C.FLOOR_Y - 7))
        aura = None
        if self.move is not None and self.move.name == "super":
            aura = self.colors["aura"]
        elif self.meter >= C.SUPER_COST:
            k = 0.5 + 0.5 * math.sin(self.t * 8)
            aura = tuple(int(c * 0.35 * k) for c in self.colors["aura"])
        if self.invuln > 0 and int(self.invuln * 20) % 2 == 0:
            return
        sk.render(surf, sk.solve(self.pose), ox, C.FLOOR_Y - self.y, self.facing, self.colors, self.t,
                  flash=min(1.0, self.flash / 0.12), aura=aura, scale=C.SCALE)
        if self.move is not None and self.move.name in ("fireball", "super") and self.phase == "startup":
            hx = ox - self.facing * 20 * C.SCALE
            k = self.move_t / self.move.startup
            col = (90, 170, 255) if self.move.name == "fireball" else (255, 210, 80)
            blit_glow(surf, (hx, C.FLOOR_Y - self.y - 70 * C.SCALE), (20 + 40 * k) * C.SCALE, col)
