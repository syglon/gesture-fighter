"""Basit ama adil CPU rakip: tepki süresi, blok/anti-air olasılıkları zorluğa göre değişir."""
import random

from . import config as C
from .fighter import Intent


class CPU:
    def __init__(self, difficulty="normal"):
        self.p = C.CPU[difficulty]
        self.think_t = 0.6
        self.plan = Intent()
        self.plan_t = 0.0
        self.combo_key = None

    def read(self, dt, pressed, me=None, opp=None, game=None):
        p = self.p
        self.think_t -= dt
        self.plan_t -= dt
        attack = None

        # isabet ettiyse kombo devamı (tepki süresinden bağımsız, "ezberlenmiş kombo"); her saldırı için bir kez
        if me.state == "attack" and me.move is not None and me.move_hit and me.move.cancel:
            key = (me.move.name, round(me.t - me.move_t, 3))
            if key != self.combo_key:
                self.combo_key = key
                if random.random() < p["combo"]:
                    attack = random.choice(["special", "heavy", "kick"]) if me.move.name in ("jab", "c_jab") \
                        else "special"

        # zıplarken rakibe yaklaşınca havada saldır
        if me.state == "jump" and not me.air_attacked and me.vy < 350 and abs(opp.x - me.x) < 280:
            if random.random() < p["aggression"] * dt * 12:
                attack = random.choice(["kick", "kick", "punch", "heavy"])

        if self.think_t <= 0 and me.actionable:
            self.think_t = p["reaction"] * random.uniform(0.7, 1.3)
            attack = attack or self._decide(me, opp, game)

        intent = Intent(move=self.plan.move if self.plan_t > 0 else 0,
                        crouch=self.plan.crouch and self.plan_t > 0,
                        block=self.plan.block and self.plan_t > 0,
                        jump=self.plan.jump and self.plan_t > 0, attack=attack)
        self.plan.jump = False  # zıplama tek seferlik
        return intent

    def _hold(self, dur, **kw):
        self.plan = Intent(**kw)
        self.plan_t = dur

    def _decide(self, me, opp, game):
        p = self.p
        dist = abs(opp.x - me.x)
        toward = 1 if opp.x > me.x else -1
        r = random.random()

        # tehditler
        incoming = [pr for pr in game.projectiles if pr.owner is opp and (me.x - pr.x) * pr.vx > 0
                    and abs(me.x - pr.x) < 540]
        if incoming:
            if r < p["block"] * 0.6:
                self._hold(0.5, block=True)
            elif r < p["block"] + 0.15:
                self._hold(0.1, jump=True, move=toward)
            return None
        if not opp.grounded and opp.state in ("jump", "attack") and dist < 330:
            if r < p["antiair"]:
                self._hold(0.25, crouch=True)
                return "heavy"  # çömelerek güçlü yumruk = uppercut
            if r < p["antiair"] + p["block"] * 0.5:
                self._hold(0.4, block=True)
                return None
        if opp.state == "attack" and opp.phase in ("startup", "active") and dist < 300:
            if r < p["block"]:
                low = opp.move is not None and opp.move.level == "low"
                self._hold(0.45, block=True, crouch=low)
                return None

        # saldırı / hareket
        if dist > 540:
            if r < p["fireball"] and not game.has_fireball(me):
                self._hold(0.2)
                return "special"
            self._hold(random.uniform(0.3, 0.7), move=toward)
            return None
        if dist > 215:
            if r < 0.12 * p["aggression"]:
                self._hold(0.1, jump=True, move=toward)
                self.think_t = 0.35
                return None
            if r < 0.3 and dist < 290:
                return "kick"
            if r < 0.3 + p["fireball"] * 0.4 and not game.has_fireball(me):
                return "special"
            self._hold(random.uniform(0.2, 0.5), move=toward if r < 0.75 + 0.2 * p["aggression"] else -toward)
            return None
        # yakın mesafe
        if r < p["aggression"]:
            choice = random.choices(["punch", "heavy", "kick", "sweep"], [4, 2, 2, 1.5])[0]
            if choice == "sweep":
                self._hold(0.3, crouch=True)
                return "kick"
            return choice
        if r < p["aggression"] + 0.2:
            self._hold(0.35, block=True)
        else:
            self._hold(0.3, move=-toward)
        return None

