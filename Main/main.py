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

# enable key repeat so holding arrows will continuously emit KEYDOWN events
try:
    pygame.key.set_repeat(200, 80)
except Exception:
    pass

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

# Speed multiplier controls (user-adjustable between MIN and MAX)
SPEED_MIN = 0.5
SPEED_MAX = 2.0
SPEED_STEP = 1.1  # factor applied when pressing right/left
speed_multiplier = 1.0

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

# separate tap sound for speed changes
TAP_FILE = DATA / "tap.mp3"
tap_sfx = None
if MIXER_OK and TAP_FILE.exists():
    try:
        tap_sfx = pygame.mixer.Sound(str(TAP_FILE))
    except Exception as e:
        print(f"Warning: couldn't load tap sound {TAP_FILE}: {e}")

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

def play_tap():
    if tap_sfx:
        tap_sfx.play()

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
    return dx * sps * speed_multiplier, dy * sps * speed_multiplier

# ---------- Prepare assets ----------
bg_scaled = scale_bg_to_fill(screen, bg_src)

# We'll render the game into a centered play surface that preserves the ASPECT_RATIO.
def compute_play_area(screen_size):
    sw, sh = screen_size
    # Fit the largest play area with desired aspect ratio inside the screen
    if sw / sh >= ASPECT_RATIO:
        # window is wider than target -> full height, limited width
        ph = max(1, sh)
        pw = max(1, int(round(ph * ASPECT_RATIO)))
    else:
        # window is taller than target -> full width, limited height
        pw = max(1, sw)
        ph = max(1, int(round(pw / ASPECT_RATIO)))
    ox = (sw - pw) // 2
    oy = (sh - ph) // 2
    return pw, ph, ox, oy

# create initial play surface and fit logo inside it
pw, ph, ox, oy = compute_play_area(screen.get_size())
play_surf = pygame.Surface((pw, ph))
bg_scaled = scale_bg_to_fill(play_surf, bg_src)
logo_img = fit_logo_to_window(play_surf, logo_src)
logo_rect = logo_img.get_rect()
logo_rect.topleft = safe_random_pos(play_surf, logo_rect)

# Font for HUD
try:
    pygame.font.init()
    HUD_FONT = pygame.font.Font(None, 20)
except Exception:
    HUD_FONT = None

# HUD fade timings (seconds)
HUD_TOTAL_DURATION = 0.7
HUD_FADE_IN = 0.2
HUD_VISIBLE = max(0.0, HUD_TOTAL_DURATION - HUD_FADE_IN - 0.2)  # leave some for fade out
HUD_FADE_OUT = HUD_TOTAL_DURATION - HUD_FADE_IN - HUD_VISIBLE
# timestamp when HUD was last triggered (seconds), or None
hud_trigger_time = None

# Position and velocity (floats for smooth dt motion)
pos_x = float(logo_rect.x)
pos_y = float(logo_rect.y)
# velocities are in pixels/sec relative to play area size
vel_x, vel_y = make_velocity(play_surf)

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
    # Recompute play surface and assets based on the current window size.
    pw, ph, ox, oy = compute_play_area(screen.get_size())
    global play_surf
    play_surf = pygame.Surface((pw, ph))
    bg_scaled = scale_bg_to_fill(play_surf, bg_src)
    logo_img_new = fit_logo_to_window(play_surf, logo_src)
    center = logo_rect.center
    logo_rect.size = logo_img_new.get_size()
    logo_img = logo_img_new
    # Keep center within new play area bounds
    logo_rect.center = (max(0, min(center[0], pw)), max(0, min(center[1], ph)))
    pos_x, pos_y = float(logo_rect.x), float(logo_rect.y)
    vel_x, vel_y = make_velocity(play_surf, keep_dir=(vel_x, vel_y))

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
            elif event.key == pygame.K_RIGHT:
                # increase speed by factor, capped
                old = speed_multiplier
                speed_multiplier = min(SPEED_MAX, speed_multiplier * SPEED_STEP)
                if speed_multiplier != old:
                    # scale current velocity to match new multiplier
                    ratio = speed_multiplier / old if old != 0 else speed_multiplier
                    vel_x *= ratio
                    vel_y *= ratio
                    play_tap()
                    try:
                        hud_trigger_time = pygame.time.get_ticks() / 1000.0
                    except Exception:
                        hud_trigger_time = None
            elif event.key == pygame.K_LEFT:
                # decrease speed by factor, capped
                old = speed_multiplier
                speed_multiplier = max(SPEED_MIN, speed_multiplier / SPEED_STEP)
                if speed_multiplier != old:
                    ratio = speed_multiplier / old if old != 0 else speed_multiplier
                    vel_x *= ratio
                    vel_y *= ratio
                    play_tap()
                    try:
                        hud_trigger_time = pygame.time.get_ticks() / 1000.0
                    except Exception:
                        hud_trigger_time = None
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

            # When the user resizes (including clicking the maximize button), we let
            # the OS-set window size be the real `screen` size, but we compute a
            # centered play area that preserves the aspect ratio and draw black
            # bars around it. This keeps the gameplay area stable while visually
            # filling the screen with black letter/pillar boxes.
            new_size = (event.w, event.h)
            screen = pygame.display.set_mode(new_size, FLAGS_WINDOWED)
            prev_window_size = new_size
            last_windowed_size = new_size
            pw, ph, ox, oy = compute_play_area(screen.get_size())
            play_surf = pygame.Surface((pw, ph))
            bg_scaled = scale_bg_to_fill(play_surf, bg_src)
            old_center = logo_rect.center
            logo_img = fit_logo_to_window(play_surf, logo_src)
            logo_rect.size = logo_img.get_size()
            # clamp center inside play area
            logo_rect.center = (max(0, min(old_center[0], pw)), max(0, min(old_center[1], ph)))
            sw, sh = screen.get_size()
            pos_x, pos_y = float(logo_rect.x), float(logo_rect.y)
            vel_x, vel_y = make_velocity(play_surf, keep_dir=(vel_x, vel_y))

    # --- Move using dt-based velocity inside play surface coordinates ---
    pos_x += vel_x * dt
    pos_y += vel_y * dt
    logo_rect.x = int(pos_x)
    logo_rect.y = int(pos_y)

    bounced = False
    # collisions use play surface size (pw, ph)
    pw, ph = play_surf.get_size()

    if logo_rect.left <= 0:
        logo_rect.left = 0
        pos_x = float(logo_rect.x)
        vel_x = -vel_x
        bounced = True
    elif logo_rect.right >= pw:
        logo_rect.right = pw
        pos_x = float(logo_rect.x)
        vel_x = -vel_x
        bounced = True

    if logo_rect.top <= 0:
        logo_rect.top = 0
        pos_y = float(logo_rect.y)
        vel_y = -vel_y
        bounced = True
    elif logo_rect.bottom >= ph:
        logo_rect.bottom = ph
        pos_y = float(logo_rect.y)
        vel_y = -vel_y
        bounced = True

    if bounced:
        play_bounce()

    # Draw: clear screen to black, draw play_surf centered and scaled to play area
    screen.fill((0, 0, 0))
    # draw background into play surface and then blit logo
    bg_scaled = scale_bg_to_fill(play_surf, bg_src)
    blit_bg(play_surf, bg_scaled)
    play_surf.blit(logo_img, logo_rect)
    # HUD: show current speed multiplier
    if HUD_FONT:
        hud_text = f"Speed: {speed_multiplier:.2f}x"
        surf = HUD_FONT.render(hud_text, True, (255, 255, 255))
        alpha = 0
        if hud_trigger_time is not None:
            now = pygame.time.get_ticks() / 1000.0
            t = now - hud_trigger_time
            if t < 0:
                alpha = 0
            elif t < HUD_FADE_IN:
                alpha = int(255 * (t / HUD_FADE_IN))
            elif t < (HUD_FADE_IN + HUD_VISIBLE):
                alpha = 255
            elif t < (HUD_FADE_IN + HUD_VISIBLE + HUD_FADE_OUT):
                rem = t - (HUD_FADE_IN + HUD_VISIBLE)
                alpha = int(255 * (1.0 - (rem / HUD_FADE_OUT)))
            else:
                alpha = 0
                hud_trigger_time = None

        if alpha > 0:
            # semi-transparent background for readability
            bg = pygame.Surface((surf.get_width() + 8, surf.get_height() + 6), pygame.SRCALPHA)
            bg.fill((0, 0, 0, int(160 * (alpha / 255.0))))
            play_surf.blit(bg, (6, 6))
            # apply alpha to text surface
            text_surf = surf.copy()
            text_surf.set_alpha(alpha)
            play_surf.blit(text_surf, (10, 8))
    # compute current play area position in window
    pw, ph, ox, oy = compute_play_area(screen.get_size())
    screen.blit(play_surf, (ox, oy))
    pygame.display.flip()

pygame.quit()
