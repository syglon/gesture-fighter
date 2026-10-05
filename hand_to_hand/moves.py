"""Saldırı verileri (frame data). Süreler saniye cinsinden.

box = (ileri_merkez, yükseklik_merkez, genişlik, yükseklik): aktif karelerdeki vuruş kutusu
level: "mid" (her blokla engellenir), "low" (çömelerek blok), "high" (ayakta blok; zıplama saldırıları)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Move:
    name: str
    label: str
    startup: float
    active: float
    recovery: float
    damage: float
    box: tuple = (0, 0, 0, 0)
    hitstun: float = 0.30
    blockstun: float = 0.20
    push: float = 250
    level: str = "mid"
    knockdown: bool = False
    launch: float = 0.0
    lunge: float = 0.0
    windup: str = "idle"
    pose: str = "idle"
    base: str = "idle"          # toparlanırken dönülen poz
    hitstop: float = 0.06
    sound: str = "punch"
    projectile: str | None = None
    cancel: bool = False        # isabet ederse başka saldırıya iptal edilebilir (kombo)
    air: bool = False
    chip: float = 0.0           # bloklanınca verilen hasar oranı
    crouching: bool = False


MOVES = {m.name: m for m in [
    Move("jab", "JAB", 0.07, 0.08, 0.17, 5, (62, 142, 56, 32), 0.30, 0.18, 230,
         windup="jab_w", pose="jab", cancel=True),
    Move("heavy", "POWER PUNCH", 0.15, 0.10, 0.33, 12, (74, 138, 66, 44), 0.46, 0.28, 440,
         lunge=200, windup="heavy_w", pose="heavy", hitstop=0.11, sound="heavy", cancel=True),
    Move("kick", "ROUNDHOUSE", 0.12, 0.10, 0.28, 9, (86, 92, 86, 44), 0.38, 0.24, 330,
         windup="kick_w", pose="kick", hitstop=0.08, sound="kick", cancel=True),
    Move("c_jab", "LOW JAB", 0.06, 0.08, 0.16, 4, (60, 100, 54, 30), 0.28, 0.17, 200,
         windup="c_jab_w", pose="c_jab", base="crouch", cancel=True, crouching=True),
    Move("sweep", "SWEEP", 0.14, 0.12, 0.45, 9, (84, 14, 96, 30), 0.50, 0.26, 250, "low",
         knockdown=True, launch=260, windup="sweep_w", pose="sweep", base="crouch", hitstop=0.09,
         sound="kick", crouching=True),
    Move("uppercut", "UPPERCUT", 0.09, 0.14, 0.42, 12, (34, 175, 58, 124), 0.50, 0.26, 250,
         knockdown=True, launch=820, windup="upper_w", pose="upper", base="crouch", hitstop=0.12,
         sound="heavy", crouching=True),
    Move("j_punch", "JUMP PUNCH", 0.06, 0.60, 0.05, 8, (52, 108, 56, 46), 0.40, 0.22, 240, "high",
         windup="jump", pose="j_punch", base="jump", air=True),
    Move("j_heavy", "JUMP SMASH", 0.09, 0.60, 0.05, 11, (56, 104, 62, 50), 0.46, 0.26, 300, "high",
         windup="j_heavy_w", pose="j_punch", base="jump", air=True, hitstop=0.1, sound="heavy"),
    Move("j_kick", "FLYING KICK", 0.07, 0.60, 0.05, 10, (64, 20, 66, 46), 0.42, 0.24, 300, "high",
         windup="jump", pose="j_kick", base="jump", air=True, sound="kick"),
    Move("fireball", "HANDOUKEN", 0.22, 0.05, 0.40, 9, hitstun=0.42, blockstun=0.30, push=300,
         windup="fire_w", pose="fire", projectile="fireball", chip=0.25, hitstop=0.08),
    Move("super", "SHIN HANDOUKEN", 0.40, 0.05, 0.65, 6, hitstun=0.26, blockstun=0.18, push=110,
         windup="fire_w", pose="fire", projectile="super", chip=0.3, hitstop=0.05, knockdown=False),
]}

# Yer/çömelme/hava durumuna göre buton -> saldırı
GROUND = {"punch": "jab", "heavy": "heavy", "kick": "kick"}
CROUCH = {"punch": "c_jab", "heavy": "uppercut", "kick": "sweep"}
AIR = {"punch": "j_punch", "heavy": "j_heavy", "kick": "j_kick"}
