"""HAND TO HAND — tüm ayarlar. Denge/kontrol değişiklikleri için burayı düzenleyin."""

W, H = 1280, 720
FPS = 60

# Sahne
FLOOR_Y = 640          # zeminin ekrandaki y'si
STAGE_W = 1800         # sahne ekrandan geniş, kamera dövüşçüleri takip eder
STAGE_MARGIN = 50
MAX_SEPARATION = W - 140

# Fizik
SCALE = 1.35          # karakter boyutu (iskelet birimleri -> piksel)
GRAVITY = 2700
JUMP_VY = 1250
JUMP_VX = 340
WALK_FWD = 290
WALK_BACK = 220
PUSH_WIDTH = 78        # dövüşçüler birbirinin içine giremez

# Maç
MAX_HP = 100
ROUND_TIME = 60
ROUNDS_TO_WIN = 2
SUPER_COST = 100
INPUT_BUFFER = 0.25    # el algılama gecikmesini tolere etmek için saldırı tamponu
COMBO_SCALING = 0.12   # komboda her vuruşta hasar bu oranda azalır (min %40)

# ---------------- El = joystick ----------------
# Kamerada (aynalanmış, normalize) elin konumu:
#   merkezden sağa/sola -> yürü, üst bölge -> zıpla, alt bölge -> çömel
DEAD_X = 0.07          # merkez etrafında ölü bölge (yarım genişlik)
JUMP_Y = 0.28          # elin merkezi bu çizginin üstündeyse zıpla
CROUCH_Y = 0.70        # bu çizginin altındaysa çömel
# Yumruk yapmış eli kameraya doğru (veya hızla) savurmak = güçlü yumruk
THRUST_SPEED = 1.7     # normalize birim / sn
THRUST_GROWTH = 1.25   # elin görüntüdeki boyutu bu oranda büyürse (kameraya doğru yumruk)
THRUST_WINDOW = 0.25
THRUST_COOLDOWN = 0.55

# ---------------- CPU ----------------
CPU = {
    "easy":   dict(reaction=0.40, block=0.20, antiair=0.15, aggression=0.40, combo=0.15, fireball=0.25),
    "normal": dict(reaction=0.27, block=0.45, antiair=0.40, aggression=0.60, combo=0.50, fireball=0.35),
    "hard":   dict(reaction=0.16, block=0.72, antiair=0.70, aggression=0.75, combo=0.85, fireball=0.45),
}

# ---------------- Karakterler ----------------
P1 = dict(name="TAKUMI", gi=(236, 236, 242), belt=(28, 28, 34), band=(225, 40, 50), skin=(238, 196, 158),
          hair=(38, 28, 24), glove=(210, 45, 45), aura=(90, 170, 255))
P2 = dict(name="BLAZE", gi=(205, 52, 40), belt=(25, 25, 25), band=(255, 205, 60), skin=(222, 176, 136),
          hair=(235, 196, 92), glove=(55, 70, 210), aura=(255, 150, 50))

# Renkler
WHITE = (255, 255, 255)
YELLOW = (255, 215, 60)
C_HP = (250, 210, 40)
C_HP_LOW = (240, 70, 50)
C_SUPER = (80, 180, 255)
