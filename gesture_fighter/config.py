"""Tüm oyun ayarları tek yerde. Denge (balance) değişiklikleri için burayı düzenleyin."""

SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

# Arena (karakterlerin dikeyde hareket edebildiği bölge)
ARENA_TOP = 240
ARENA_BOTTOM = 650
FLOOR_Y = 660
PLAYER_Y_MIN = ARENA_TOP + 60
PLAYER_Y_MAX = ARENA_BOTTOM - 60

# Kameradaki elin dikey konumu bu aralıkta haritalanır (0 = üst, 1 = alt)
HAND_Y_MIN = 0.22
HAND_Y_MAX = 0.78

# Kamera
CAMERA_W, CAMERA_H = 640, 480
PREVIEW_W, PREVIEW_H = 400, 300  # izleyici thread'inin ürettiği küçültülmüş görüntü

# Hareket algılama yumuşatma: son N karede en az M kez aynı hareket görülmeli
GESTURE_WINDOW = 4
GESTURE_REQUIRED = 3

# ---------------- Oyuncu ----------------
PLAYER_X = 190
PLAYER_MAX_HP = 100
PLAYER_MAX_ENERGY = 100
ENERGY_REGEN = 24          # /sn
ENERGY_REGEN_DELAY = 0.5   # kalkan indirildikten sonra bekleme
SHIELD_DRAIN = 9           # kalkan açıkken /sn
SHIELD_RADIUS = 80
SHIELD_BLOCK_COST = 1.4    # engellenen hasar * bu = enerji kaybı
PARRY_WINDOW = 0.25        # kalkan açıldıktan sonraki bu süre içinde gelen mermi geri yansır
GUARD_BREAK_TIME = 1.3
PLAYER_IFRAMES = 0.45

PUNCH = dict(damage=5, speed=1150, radius=16, cooldown=0.18, hold_repeat=0.45, energy=0)
FIRE = dict(damage=13, speed=780, radius=21, cooldown=0.30, hold_repeat=0.75, energy=18)

SPECIAL_MAX = 100
SPECIAL_DURATION = 1.7
SPECIAL_DPS = 55
SPECIAL_GAIN_PER_DAMAGE = 0.4
SPECIAL_GAIN_PARRY = 15
SPECIAL_GAIN_BLOCK = 3

COMBO_WINDOW = 2.2
COMBO_BONUS_PER_HIT = 0.05
COMBO_BONUS_MAX = 0.5

# ---------------- Boss ----------------
BOSS_X = 1060
BOSS_MAX_HP = 650
BOSS_RADIUS = 92
BOSS_NAME = "OVERLORD-461"

DIFFICULTY = {
    # hasar çarpanı, saldırı aralığı çarpanı, mermi hızı çarpanı
    "easy":   dict(damage=0.5, interval=1.35, speed=0.85),
    "normal": dict(damage=0.8, interval=1.0, speed=1.0),
    "hard":   dict(damage=1.15, interval=0.85, speed=1.1),
}

# ---------------- Renkler ----------------
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
C_PUNCH = (255, 220, 140)
C_SHIELD = (90, 220, 255)
C_FIRE = (255, 120, 40)
C_SPECIAL = (255, 210, 60)
C_PARRY = (255, 240, 120)
C_HP = (80, 230, 120)
C_HP_LOW = (240, 70, 70)
C_ENERGY = (70, 170, 255)
C_BOSS_HP = (230, 60, 90)
C_UI_BG = (14, 14, 28)
C_UI_BORDER = (200, 200, 230)
