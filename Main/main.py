import sys
import random
from pathlib import Path

import pygame

# ---------- Paths ----------
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

LOGO_FILE = DATA / "Daim.png"
BG_FILE = DATA / "windows_XP.jpg"
SOUND_FILE = DATA / "sound.mp3"

# ---------- Pygame setup ----------
pygame.init()
pygame.mixer.init()

# Start windowed but resizable; F11 toggles fullscreen.
WINDOWED_SIZE = (960, 600)
flags = pygame.RESIZABLE | pygame.DOUBLEBUF
screen = pygame.display.set_mode(WINDOWED_SIZE, flags)
pygame.display.set_caption("Daim DVD Screensaver")

clock = pygame.time.Clock()
FPS = 60

# ---------- Load assets ----------
try:
    logo_img = pygame.image.load(str(LOGO_FILE)).convert_alpha()
except Exception as e:
    print(f"Failed to load {LOGO_FILE}: {e}")
    pygame.quit()
    sys.exit(1)

try:
    bg_img = pygame.image.load(str(BG_FILE)).convert()
except Exception as e:
    print(f"Failed to load {BG_FILE}: {e}")
    pygame.quit()
    sys.exit(1)

# Sound is optional: continue without if it fails to load.
bounce_sfx = None
try:
    if SOUND_FILE.exists():
        bounce_sfx = pygame.mixer.Sound(str(SOUND_FILE))
except Exception as e:
    print(f"Warning: couldn't load sound ({SOUND_FILE}): {e}")

# ---------- Helpers ----------
def scale_bg_to_fill(surface, bg):
    """Scale background to fill the window (cover behaviour)."""
    sw, sh = surface.get_size()
    bw, bh = bg.get_size()
    if sw == 0 or sh == 0:
        return bg
    scale = max(sw / bw, sh / bh)
    new_size = (int(bw * scale), int(bh * scale))
    return pygame.transform.smoothscale(bg, new_size)

def blit_bg(surface, bg_scaled):
    sw, sh = surface.get_size()
    bw, bh = bg_scaled.get_size()
    # centre the scaled background
    x = (sw - bw) // 2
    y = (sh - bh) // 2
    surface.blit(bg_scaled, (x, y))

bg_scaled = scale_bg_to_fill(screen, bg_img)

# Logo start position & speed
logo_rect = logo_img.get_rect()
logo_rect.x = random.randint(0, screen.get_width() - logo_rect.width)
logo_rect.y = random.randint(0, screen.get_height() - logo_rect.height)

# Choose a non-zero speed on both axes
speed = [random.choice([-4, -3, 3, 4]), random.choice([-4, -3, 3, 4])]

# Prevent double sound when hitting a corner: play once per frame.
def play_bounce():
    if bounce_sfx:
        bounce_sfx.play()

is_fullscreen = False

def toggle_fullscreen():
    global is_fullscreen, screen, bg_scaled
    is_fullscreen = not is_fullscreen
    if is_fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)
    else:
        screen = pygame.display.set_mode(WINDOWED_SIZE, flags)
    bg_scaled = scale_bg_to_fill(screen, bg_img)

