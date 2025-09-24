import sys
import random
from pathlib import Path
import math
import pygame

# ---------- Paths ----------
ROOT = Path(__file__).resolve().parent           # /.../main
DATA = ROOT.parent / "data"                      # /.../data

LOGO_FILE = DATA / "Daim.png"
BG_FILE = DATA / "windows_XP.jpg"
SOUND_FILE = DATA / "sound.mp3"

# ---------- Pygame setup ----------
pygame.init()
try:
    pygame.mixer.init()
    MIXER_OK = True
except Exception as e:
    print("Warning: pygame.mixer.init() failed:", e)
    MIXER_OK = False

WINDOWED_SIZE = (960, 600)
ASPECT_RATIO = WINDOWED_SIZE[0] / WINDOWED_SIZE[1]
# Minimum allowed window size (keeps things usable and prevents extreme skinny/tall windows)
MIN_WINDOW_SIZE = (480, 300)
FLAGS_WINDOWED = pygame.RESIZABLE | pygame.DOUBLEBUF
# track last good windowed size so we can restore after fullscreen
last_windowed_size = WINDOWED_SIZE
prev_window_size = WINDOWED_SIZE
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
    sw, sh = surface.get_size()
    lw, lh = logo_img.get_size()
    max_side = int(min(sw, sh) * 0.25)
    if max_side <= 0:
        max_side = 1
    scale = min(max_side / lw, max_side / lh, 1.0)
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

# ---- New helpers for time-based velocity ----
def speed_pixels_per_second(surface):
    """Pick speed relative to window size, so visual speed feels constant."""
    sw, sh = surface.get_size()
    return max(60, 0.35 * min(sw, sh))  # tweak multiplier for feel

def random_unit_diag():
    vx = random.choice([-1.0, 1.0])
    vy = random.choice([-1.0, 1.0])
    inv_len = 1.0 / math.hypot(vx, vy)
    return vx * inv_len, vy * inv_len

def make_velocity(surface, keep_dir=None):
    sps = speed_pixels_per_second(surface)
    if keep_dir is None:
        dx, dy = random_unit_diag()
    else:
        dx, dy = keep_dir
        mag = math.hypot(dx, dy)
        if mag < 1e-6:
            dx, dy = random_unit_diag()
        else:
            dx, dy = dx / mag, dy / mag
    return dx * sps, dy * sps

# ---------- Prepare assets ----------
bg_scaled = scale_bg_to_fill(screen, bg_src)
logo_img = fit_logo_to_window(screen, logo_src)
logo_rect = logo_img.get_rect()
logo_rect.topleft = safe_random_pos(screen, logo_rect)

# Position and velocity (floats for smooth dt motion)
pos_x = float(logo_rect.x)
pos_y = float(logo_rect.y)
vel_x, vel_y = make_velocity(screen)

is_fullscreen = False

def toggle_fullscreen():
    global is_fullscreen, screen, bg_scaled, logo_img, logo_rect, vel_x, vel_y, pos_x, pos_y
    global last_windowed_size, prev_window_size
    is_fullscreen = not is_fullscreen
    if is_fullscreen:
        # remember the last windowed size before entering fullscreen
        try:
            last_windowed_size = prev_window_size
        except Exception:
            last_windowed_size = WINDOWED_SIZE
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)
    else:
        # restore previous windowed size (keeps aspect)
        screen = pygame.display.set_mode(last_windowed_size, FLAGS_WINDOWED)
        prev_window_size = last_windowed_size
    bg_scaled = scale_bg_to_fill(screen, bg_src)
    logo_img_new = fit_logo_to_window(screen, logo_src)
    center = logo_rect.center
    logo_rect.size = logo_img_new.get_size()
    logo_img = logo_img_new
    logo_rect.center = center
    sw, sh = screen.get_size()
    logo_rect.left = max(0, min(logo_rect.left, sw - logo_rect.width))
    logo_rect.top = max(0, min(logo_rect.top, sh - logo_rect.height))
    pos_x, pos_y = float(logo_rect.x), float(logo_rect.y)
    vel_x, vel_y = make_velocity(screen, keep_dir=(vel_x, vel_y))

    # update prev_window_size in case fullscreen toggled back to windowed
    try:
        prev_window_size = screen.get_size()
    except Exception:
        prev_window_size = last_windowed_size

# ---------- Main loop ----------
running = True
while running:
    dt_ms = clock.tick(FPS)
    dt = dt_ms / 1000.0  # seconds since last frame

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_F11:
                toggle_fullscreen()
        elif event.type == pygame.VIDEORESIZE and not is_fullscreen:
            # Constrain resize to the target aspect ratio so the playfield doesn't become too tall or skinny.
            def constrain_size_to_aspect(requested_size, prev_size):
                req_w, req_h = requested_size
                prev_w, prev_h = prev_size
                min_w, min_h = MIN_WINDOW_SIZE
                req_w = max(req_w, min_w)
                req_h = max(req_h, min_h)
                # Choose which dimension the user is primarily changing
                if abs(req_w - prev_w) >= abs(req_h - prev_h):
                    # width-driven change
                    w = req_w
                    h = max(min_h, int(round(w / ASPECT_RATIO)))
                else:
                    # height-driven change
                    h = req_h
                    w = max(min_w, int(round(h * ASPECT_RATIO)))
                return (w, h)

            new_size = constrain_size_to_aspect((event.w, event.h), prev_window_size)
            screen = pygame.display.set_mode(new_size, FLAGS_WINDOWED)
            prev_window_size = new_size
            last_windowed_size = new_size
            bg_scaled = scale_bg_to_fill(screen, bg_src)
            old_center = logo_rect.center
            logo_img = fit_logo_to_window(screen, logo_src)
            logo_rect.size = logo_img.get_size()
            logo_rect.center = old_center
            sw, sh = screen.get_size()
            logo_rect.left = max(0, min(logo_rect.left, sw - logo_rect.width))
            logo_rect.top = max(0, min(logo_rect.top, sh - logo_rect.height))
            pos_x, pos_y = float(logo_rect.x), float(logo_rect.y)
            vel_x, vel_y = make_velocity(screen, keep_dir=(vel_x, vel_y))

    # --- Move using dt-based velocity ---
    pos_x += vel_x * dt
    pos_y += vel_y * dt
    logo_rect.x = int(pos_x)
    logo_rect.y = int(pos_y)

    bounced = False
    sw, sh = screen.get_size()

    if logo_rect.left <= 0:
        logo_rect.left = 0
        pos_x = float(logo_rect.x)
        vel_x = -vel_x
        bounced = True
    elif logo_rect.right >= sw:
        logo_rect.right = sw
        pos_x = float(logo_rect.x)
        vel_x = -vel_x
        bounced = True

    if logo_rect.top <= 0:
        logo_rect.top = 0
        pos_y = float(logo_rect.y)
        vel_y = -vel_y
        bounced = True
    elif logo_rect.bottom >= sh:
        logo_rect.bottom = sh
        pos_y = float(logo_rect.y)
        vel_y = -vel_y
        bounced = True

    if bounced:
        play_bounce()

    # Draw
    blit_bg(screen, bg_scaled)
    screen.blit(logo_img, logo_rect)
    pygame.display.flip()

pygame.quit()
