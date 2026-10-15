# Gesture Fighter — ME461

**Team Bad Bots**

| Member |
|---|
| Rahmi Eren Çakır |
| Mert Koçoğlu |
| Efe Keleş |

A 2D fighting game controlled entirely by **hand gestures in front of a webcam**. No keyboard, mouse or
controller is needed: the camera finds your hand with MediaPipe, a rule-based classifier recognises the
gesture, and the game turns it into an attack, a shield or a special move.

There are two modes:

- **1 Player — Boss fight:** fight the three-phase boss OVERLORD-461.
- **2 Players — Versus:** two players stand side by side in front of one camera and fight each other.

---

## 1. Requirements

| | |
|---|---|
| Python | 3.10 or newer (developed and tested with Python 3.10 on Ubuntu 22.04) |
| Webcam | any USB or built-in camera; without one the game runs in keyboard mode |
| Packages | `mediapipe`, `opencv-python`, `pygame`, `numpy` (see `requirements.txt`) |

The hand-tracking model (`models/hand_landmarker.task`, ~7.5 MB) is included. If it is missing, the game
downloads it automatically on the first run.

## 2. Installation and running

**Linux / macOS**

```bash
cd gesture-fighter
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python webcam_game.py
```

**Windows (PowerShell or CMD)**

```bat
cd gesture-fighter
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python webcam_game.py
```

The game opens in **fullscreen**. Press **`F`** at any time to switch to a window, and `F` again to go back
to fullscreen. It works on any screen resolution: the game is drawn on a fixed 1280×720 canvas that is scaled
smoothly to your monitor while keeping its 16:9 shape (screens with a different shape get thin black bars).
In windowed mode the window is shrunk automatically on screens smaller than 1280×720.

**Command-line options**

| Option | Effect |
|---|---|
| `--versus` | Skip the menu and start a 2-player match |
| `--difficulty easy\|normal\|hard` | Boss difficulty (default `normal`; also changeable in the menu with ◀ ▶) |
| `--camera N` | Use camera number N (default 0) |
| `--keyboard` | Do not use the camera; play with the keyboard only |
| `--windowed` | Start in a 1280×720 window instead of fullscreen |
| `--mute` | No sound or music |
| `--no-mirror` | Do not mirror the camera image |

## 3. Controls

### 3.1 Hand gestures

Hold your hand in front of the camera with the palm facing it, about 50–80 cm away.

| Gesture | Action | Details |
|---|---|---|
| ✊ Fist | **Punch** | Fast projectile, 5 damage, no energy cost |
| 🖐️ Open palm | **Shield** | Blocks shots and lasers while held; drains energy. Opened **within 0.25 s before a hit** it becomes a **PARRY** and sends the shot back |
| ☝️ Index finger | **Fireball** | Slower projectile, 13 damage, costs 18 energy |
| ✌️ Index + middle | **Special beam** | Available when the gold SPECIAL bar is full; a huge beam you can steer by moving your hand |
| 🤟 Index + little finger | **Mirror** | **Versus only.** See section 4.3 |
| Hand up / down | **Move** | Your fighter follows the height of your hand (the dashed lines in the camera preview show the range) |

- An attack fires as soon as you **make** the gesture; if you keep holding it, it repeats more slowly.
  Switching quickly (✊ → 🖐️ → ✊) is the fastest way to punch.
- The thumb is ignored, so 🤟 and 🤘 both work for the mirror.
- The camera preview at the top of the screen shows the detected hand skeleton and gesture. Press **F1**
  to see the raw gesture and finger states (e.g. `fingers 1001` = index and little finger open).

### 3.2 Menus

| Screen | Gesture | Key |
|---|---|---|
| Main menu → 1 Player | hold 🖐️ open palm for 1 second | `SPACE` / `ENTER` |
| Main menu → 2 Players | hold ✌️ two fingers for 1 second | `V` |
| End screen → play again | hold 🖐️ open palm for 1 second | `SPACE` / `ENTER` / `R` |
| End screen → main menu | — | `ESC` |

### 3.3 Keyboard (fallback without a camera, or to test)

Holding a key is the same as holding the gesture.

| | Punch | Shield | Fire | Special | Mirror | Move |
|---|---|---|---|---|---|---|
| 1 Player | `1` / `J` | `2` / `K` | `3` / `L` | `4` / `;` | — | `W` `S` or `↑` `↓` |
| Versus, P1 | `1` | `2` | `3` | `4` | `5` | `W` `S` |
| Versus, P2 | `7` / num `1` | `8` / num `2` | `9` / num `3` | `0` / num `4` | `-` / num `5` | `↑` `↓` |

### 3.4 Other keys

| Key | Action |
|---|---|
| `ESC` / `P` | Pause / resume during a fight (`Q` while paused returns to the menu); `ESC` in the main menu quits |
| `F1` | Debug panel (FPS, raw and filtered gesture, finger states, tracker FPS) |
| `F` (or `F11`) | Switch between fullscreen and a window |
| `M` | Mute / unmute sound and music |
| `◀` `▶` (or `A` `D`) | Change boss difficulty in the main menu |

## 4. Game modes

### 4.1 Common mechanics

- **Health** — 100 in 1-player, 150 in versus. A short invulnerability follows every hit.
- **Energy (blue bar)** — 100, regenerates when you are not shielding. Fireballs and the shield use it;
  if it runs out while shielding, your guard breaks for 1.3 s.
- **Special (gold bar)** — fills when you deal damage, parry and block. When it is full, gold rings appear
  at your feet; show ✌️ to fire the beam.
- **Combo** — hits that land within 2.2 s of each other give up to +50 % damage.

### 4.2 1 Player — Boss fight

You stand on the left, the boss OVERLORD-461 (650 HP) floats on the right. Its health is split into three
phases; at 66 % and 33 % it becomes faster and adds new attacks:

| Phase | Attacks |
|---|---|
| 1 | aimed orb, 3-shot spread, laser |
| 2 | 3-shot burst, 5-shot spread, laser, homing missiles |
| 3 | 4-shot burst, 7-shot spread, double laser, homing missiles, bullet wall with a gap |

Every attack is announced: the boss's eye glows before it fires, and lasers flash a warning band first.
Red homing missiles can be shot down with punches and fireballs. The end screen shows time, accuracy,
parries, best combo and a rank from S to C. Difficulty changes the boss's damage, attack rate and shot speed.

### 4.3 2 Players — Versus

- The camera image is split down the middle: **the hand in the left half controls P1 (left, blue), the
  hand in the right half controls P2 (right, pink)**. Stand side by side, each in your own half.
- **Best of 3 rounds**, 60 seconds each. When time runs out, the player with more health wins the round.
- **Projectile clashes:** a fireball beats a punch; a parried or mirrored shot beats both; equal shots cancel.
- **Special beam:** it does not lock on, you aim it with your hand. A shield lets only 15 % through but drains
  energy fast.
- **🤟 Mirror (versus only):** costs **40 energy** and places a mirror in the middle of the arena for
  **3 seconds**. Your opponent's shots that reach it fly back at them with 1.2× damage, and their special beam
  stops at the mirror. Your own shots pass through. Each shot can be reflected only once, so a shot never gets
  stuck between two mirrors. Cooldown: **8 seconds**; the panel under your health bar shows `MIRROR READY` or
  the time left.
- The final screen compares both players: damage, accuracy, parries, combos, specials, mirrors and reflects.

## 5. Tips for a good demo

- **Light matters most.** Play in a well-lit room and avoid a bright window behind you.
- Keep your hand 50–80 cm from the camera with the palm facing it; in versus, keep each hand in its own half.
- Make gestures clearly; the game accepts a gesture after it is seen in 3 of the last 4 frames (~0.15 s).
- If a gesture is not recognised, press **F1** and check the `fingers` pattern
  (index, middle, ring, little): ✊ `0000`, 🖐️ `1111`, ☝️ `1000`, ✌️ `1100`, 🤟 `1001`.

## 6. How it works

```
Camera frame ──► MediaPipe Hand Landmarker ──► 21 landmarks ──► finger tests ──► gesture rules
   (OpenCV)          (background thread)                        (ratio + angle)     + 3-of-4 filter
                                                                                         │
                     Draw ◄── Game update (attacks, boss, collisions) ◄── controllers ◄──┘
                                       (main thread, 60 FPS)
```

- **Hand tracking:** OpenCV reads the camera; Google's pre-trained MediaPipe Hand Landmarker returns 21
  points per hand. It runs in a background thread (~20–25 FPS) so the game itself stays at 60 FPS.
- **Gesture classification (no machine learning of our own):** a finger is *open* when
  (1) the distance wrist→tip divided by wrist→middle joint is above 1.10, **and** (2) the bend at the middle
  joint is below 70°. Both are ratios/angles, so they do not depend on how far the hand is or how it is
  rotated. The pattern of open fingers is then mapped to a gesture; the thumb is ignored because it is the
  least reliable finger.
- **Filtering:** a majority vote over the last 4 frames removes single-frame errors.
- **Sound and music** are synthesised with NumPy when the game starts — there are no audio files. The menu plays
  an upbeat platformer-style chiptune theme and fights play a faster, more intense one.

## 7. Project structure

```
webcam_game.py            entry point, command-line options
requirements.txt          Python packages
models/
  hand_landmarker.task    MediaPipe hand model
gesture_fighter/
  config.py               every tunable number (damage, health, speeds, thresholds, difficulty)
  hand_tracker.py         camera + MediaPipe in a background thread; P1/P2 split for versus
  gestures.py             finger tests, gesture rules, anti-flicker filter
  controls.py             hand / keyboard input → one ControlState per player
  entities.py             fighter (poses, death animation), boss, projectiles, lasers, beam, mirror
  game.py                 main loop, menus, rounds, combat rules, collisions, HUD
  fx.py, draw.py          particles, screen shake, drawing helpers
  sound.py                synthesised sound effects and chiptune music
```

Balance values can be changed in `gesture_fighter/config.py` without touching the code; the two gesture
thresholds are at the top of `gesture_fighter/gestures.py`.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| "Camera 0 could not be opened" / keyboard mode starts | Close other apps using the camera, or try `--camera 1` |
| Hand not detected | More light, move the hand closer, keep the palm toward the camera |
| Gestures flicker | Check the `fingers` pattern with F1; spread your fingers more clearly |
| No sound | The game runs silently if no audio device is found; check that `--mute` was not given |
| Error mentioning TensorFlow / NumPy | Already handled in the code (TensorFlow is hidden from MediaPipe); using a fresh virtual environment as in section 2 also avoids it |
