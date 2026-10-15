"""All game settings in one place. Edit this file to change the game balance."""

SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

# Arena (the vertical band the fighters can move in)
ARENA_TOP = 240
ARENA_BOTTOM = 650
FLOOR_Y = 660
PLAYER_Y_MIN = ARENA_TOP + 60
PLAYER_Y_MAX = ARENA_BOTTOM - 60

# The hand's vertical position in this band of the camera image is mapped to the arena (0 = top, 1 = bottom)
HAND_Y_MIN = 0.2
HAND_Y_MAX = 0.8

# Camera
CAMERA_W, CAMERA_H = 640, 480
PREVIEW_W, PREVIEW_H = 400, 300  # downscaled preview image produced by the tracker thread

# Gesture smoothing: the same gesture must be seen at least M times in the last N frames
GESTURE_WINDOW = 4
GESTURE_REQUIRED = 3

# ---------------- Player ----------------
PLAYER_X = 190
PLAYER_MAX_HP = 100
PLAYER_MAX_ENERGY = 100
ENERGY_REGEN = 24          # per second
ENERGY_REGEN_DELAY = 0.5   # delay after lowering the shield
SHIELD_DRAIN = 9           # per second while the shield is up
SHIELD_RADIUS = 80
SHIELD_BLOCK_COST = 1.4    # blocked damage * this = energy lost
PARRY_WINDOW = 0.25        # a shot that arrives within this time after raising the shield is parried back
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

# ---------------- Two-player VERSUS (P1 left, P2 right) ----------------
P1_COLOR = (90, 220, 255)
P2_COLOR = (255, 110, 200)
VS_P1_X = 170
VS_P2_X = SCREEN_W - 170
VS_ROUND_TIME = 60          # seconds
VS_MAX_HP = 150             # player health in versus (so rounds last longer)
VS_ROUNDS_TO_WIN = 2        # best of 3 rounds
VS_SPECIAL_DPS = 34         # special beam against a player (weaker than against the boss)
VS_BEAM_BLOCK_DRAIN = 45    # energy lost per second while blocking a beam
VS_BEAM_CHIP = 0.15         # share of beam damage that gets through a shield
VS_SPECIAL_GAIN_DEALT = 1.4 # special bar gained per damage dealt
VS_SPECIAL_GAIN_TAKEN = 0.7 # special bar gained per damage taken
VS_REFLECT_MULT = 1.5       # damage multiplier of a parried shot

# MIRROR (🤟 index + little finger) — versus only: places a mirror in the middle that sends the opponent's shots back
MIRROR_ENERGY = 40          # energy cost
MIRROR_DURATION = 3.0       # how long the mirror stays up (s)
MIRROR_COOLDOWN = 8.0       # cooldown before it can be used again (s, from the cast)
MIRROR_OFFSET = 60          # the mirror sits this many pixels from the screen centre, on its owner's side
MIRROR_DAMAGE_MULT = 1.2    # damage multiplier of a reflected shot
MIRROR_SPEED_MULT = 1.1     # speed multiplier of a reflected shot
MIRROR_MAX_BOUNCES = 1      # a shot is reflected at most this many times, then passes through mirrors (never stuck between two)

# ---------------- Boss ----------------
BOSS_X = 1060
BOSS_MAX_HP = 650
BOSS_RADIUS = 92
BOSS_NAME = "OVERLORD-461"

DIFFICULTY = {
    # damage, attack interval and projectile speed multipliers
    "easy":   dict(damage=0.5, interval=1.35, speed=0.85),
    "normal": dict(damage=0.8, interval=1.0, speed=1.0),
    "hard":   dict(damage=1.15, interval=0.85, speed=1.1),
}

# ---------------- Colours ----------------
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
C_PUNCH = (255, 220, 140)
C_SHIELD = (90, 220, 255)
C_FIRE = (255, 120, 40)
C_MIRROR = (200, 175, 255)
C_SPECIAL = (255, 210, 60)
C_PARRY = (255, 240, 120)
C_HP = (80, 230, 120)
C_HP_LOW = (240, 70, 70)
C_ENERGY = (70, 170, 255)
C_BOSS_HP = (230, 60, 90)
C_UI_BG = (14, 14, 28)
C_UI_BORDER = (200, 200, 230)
