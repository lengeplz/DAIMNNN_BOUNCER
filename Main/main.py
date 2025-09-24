import sys
import random
from pathlib import Path

import pygame

# ---------- Paths ----------
ROOT = Path(__file__).resolve().parent           # /.../main
DATA = ROOT.parent / "data"                      # /.../data

LOGO_FILE = DATA / "Daim.png"
BG_FILE = DATA / "windows_XP.jpg"
SOUND_FILE = DATA / "sound.mp3"

# ---------- Pygame setup ----------
pygame.init()
# Sound is optional; mixer can fail on some systems
try:
    pygame.mixer.init()
    MIXER_OK = True
except Exception as e:
    print("Warning: pygame.mixer.init() failed:", e)
    MIXER_OK = False

WINDOWED_SIZE = (960, 600)
FLAGS_WINDOWED = pygame.RESIZABLE | pygame.DOUBLEBUF
screen = pygame.display.set_mode(WINDOWED_SIZE, FLAGS_WINDOWED)
pygame.display.set_caption("Daim DVD Screensaver")

clock = pygame.time.Clock()
FPS = 60

# ---------- Load assets ----------
def fail(msg):
    print(msg)
    pygame.quit()
    sys.exit(1)

try:
    logo_src = pygame.image.load(str(LOGO_FILE)).convert_alpha()
except Exception as e:
    fail(f"Failed to load logo {LOGO_FILE} : {e}")

try:
    bg_src = pygame.image.load(str(BG_FILE)).convert()
except Exception as e:
    fail(f"Failed to load background {BG_FILE} : {e}")

bounce_sfx = None
if MIXER_OK and SOUND_FILE.exists():
    try:
        bounce_sfx = pygame.mixer.Sound(str(SOUND_FILE))
    except Exception as e:
        print(f"Warning: couldn't load sound {SOUND_FILE}: {e}")

# ---------- Helpers ----------
def scale_bg_to_fill(surface, bg):
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
    x = (sw - bw) // 2
    y = (sh - bh) // 2
    surface.blit(bg_scaled, (x, y))

def fit_logo_to_window(surface, logo_img):
    """Return a version of the logo that fits nicely in the current window."""
    sw, sh = surface.get_size()
    lw, lh = logo_img.get_size()

    # Target: logo should not exceed 25% of min(screen_w, screen_h)
    max_side = int(min(sw, sh) * 0.25)
    if max_side <= 0:
        max_side = 1  # avoid zero-size in extreme cases

    scale = min(max_side / lw, max_side / lh, 1.0)  # only downscale
    if scale < 1.0:
        new_size = (max(1, int(lw * scale)), max(1, int(lh * scale)))
        return pygame.transform.smoothscale(logo_img, new_size)
    return logo_img

def safe_random_pos(surface, rect):
    sw, sh = surface.get_size()
    x_max = max(0, sw - rect.width)
    y_max = max(0, sh - rect.height)
    return random.randint(0, x_max), random.randint(0, y_max)

def play_bounce():
    if bounce_sfx:
        bounce_sfx.play()

# Prepare bg + logo for current window
bg_scaled = scale_bg_to_fill(screen, bg_src)
logo_img = fit_logo_to_window(screen, logo_src)
logo_rect = logo_img.get_rect()
logo_rect.topleft = safe_random_pos(screen, logo_rect)

# Non-zero initial speed
speed = [random.choice([-4, -3, 3, 4]), random.choice([-4, -3, 3, 4])]

is_fullscreen = False

def toggle_fullscreen():
    global is_fullscreen, screen, bg_scaled, logo_img, logo_rect
    is_fullscreen = not is_fullscreen
    if is_fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)
    else:
        screen = pygame.display.set_mode(WINDOWED_SIZE, FLAGS_WINDOWED)

    # Recompute background + resize logo to fit the new size
    bg_scaled = scale_bg_to_fill(screen, bg_src)
    logo_img_new = fit_logo_to_window(screen, logo_src)

    # Keep logo centre when rescaling
    center = logo_rect.center
    logo_rect.size = logo_img_new.get_size()
    logo_img = logo_img_new
    logo_rect.center = center

    # Clamp inside the screen to avoid negative space issues
    sw, sh = screen.get_size()
    logo_rect.left = max(0, min(logo_rect.left, sw - logo_rect.width))
    logo_rect.top = max(0, min(logo_rect.top, sh - logo_rect.height))

# ---------- Main loop ----------
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_F11:
                toggle_fullscreen()

        elif event.type == pygame.VIDEORESIZE and not is_fullscreen:
            # Recreate window at new size and rescale assets
            screen = pygame.display.set_mode(event.size, FLAGS_WINDOWED)
            bg_scaled = scale_bg_to_fill(screen, bg_src)

            # Downscale logo if needed after resize
            old_center = logo_rect.center
            logo_img = fit_logo_to_window(screen, logo_src)
            logo_rect.size = logo_img.get_size()
            logo_rect.center = old_center

            # Clamp inside bounds
            sw, sh = screen.get_size()
            logo_rect.left = max(0, min(logo_rect.left, sw - logo_rect.width))
            logo_rect.top = max(0, min(logo_rect.top, sh - logo_rect.height))

    # Move
    logo_rect.x += speed[0]
    logo_rect.y += speed[1]

    bounced = False
    sw, sh = screen.get_size()

    # Bounce X
    if logo_rect.left <= 0:
        logo_rect.left = 0
        speed[0] = -speed[0]
        bounced = True
    elif logo_rect.right >= sw:
        logo_rect.right = sw
        speed[0] = -speed[0]
        bounced = True

    # Bounce Y
    if logo_rect.top <= 0:
        logo_rect.top = 0
        speed[1] = -speed[1]
        bounced = True
    elif logo_rect.bottom >= sh:
        logo_rect.bottom = sh
        speed[1] = -speed[1]
        bounced = True

    if bounced:
        play_bounce()

    # Draw
    blit_bg(screen, bg_scaled)
    screen.blit(logo_img, logo_rect)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
