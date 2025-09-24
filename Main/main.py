import sys
import random
from pathlib import Path
import math
import os
import subprocess
import pygame
# optional fast array ops for resampling sounds
try:
    import numpy as np
    NUMPY_OK = True
except Exception:
    np = None
    NUMPY_OK = False

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

# Prepare for pitch/speed-shifted bounce playback (uses resampling)
orig_bounce_array = None
bounce_cache = {}  # map rounded multiplier -> Sound

# get mixer format info if available
try:
    MIXER_INFO = pygame.mixer.get_init()  # (freq, size, channels)
except Exception:
    MIXER_INFO = None

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
    # Play bounce sound; when NumPy is available, resample to match speed_multiplier
    if not bounce_sfx:
        return
    if NUMPY_OK and bounce_sfx is not None:
        key = round(speed_multiplier, 2)
        s = bounce_cache.get(key)
        if s:
            s.play()
            return
        # lazily load original array
        global orig_bounce_array
        try:
            if orig_bounce_array is None:
                orig_bounce_array = pygame.sndarray.array(bounce_sfx)
        except Exception:
            # fallback
            try:
                bounce_sfx.play()
            except Exception:
                pass
            return

        try:
            arr = orig_bounce_array
            # arr may be int16 or similar; convert to float for interpolation
            orig_len = arr.shape[0]
            if speed_multiplier == 1.0 or orig_len < 2:
                bounce_cache[key] = bounce_sfx
                bounce_sfx.play()
                return
            new_len = max(1, int(round(orig_len / float(speed_multiplier))))
            # generate indices in original sample space
            orig_idx = np.arange(orig_len)
            new_idx = np.linspace(0, orig_len - 1, new_len)
            if arr.ndim == 1:
                resampled = np.interp(new_idx, orig_idx, arr.astype(np.float32)).astype(arr.dtype)
            else:
                # stereo or multi-channel
                chans = arr.shape[1]
                resampled = np.zeros((new_len, chans), dtype=arr.dtype)
                for c in range(chans):
                    resampled[:, c] = np.interp(new_idx, orig_idx, arr[:, c].astype(np.float32)).astype(arr.dtype)
            new_sound = pygame.sndarray.make_sound(resampled)
            bounce_cache[key] = new_sound
            new_sound.play()
            return
        except Exception:
            # any error -> fallback to normal playback
            try:
                bounce_sfx.play()
            except Exception:
                pass
            return
    else:
        try:
            bounce_sfx.play()
        except Exception:
            pass

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

# Approach-to-center settings (when hitting the corner)
APPROACH_TIME = 0.8  # seconds to glide back to center (use easing)
approach_active = False
# approach easing state
approach_elapsed = 0.0
approach_start_x = 0.0
approach_start_y = 0.0
approach_target_x = 0.0
approach_target_y = 0.0
# how close (fraction of play area) to the corner counts as "near" for forced approach
NEAR_PERCENT = 0.01  # 1% of width/height

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

def ease_out_cubic(t: float) -> float:
    """Simple ease-out cubic for smoother glide (t in [0,1])."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return 1.0 - pow(1.0 - t, 3)

def play_endgame_then_restart():
    """Attempt to play `data/endgame.mp4` (MoviePy preferred). After the video
    finishes, restore the game window and reset the logo state to restart the
    screensaver."""
    global screen, play_surf, bg_scaled, logo_img, logo_rect
    global pos_x, pos_y, vel_x, vel_y, last_windowed_size, prev_window_size
    video_path = DATA / "endgame.mp4"
    if not video_path.exists():
        # nothing to play; just restart
        restart_game_state()
        return

    # Try MoviePy first (plays inside the pygame window)
    try:
        import moviepy.editor as mpy
        clip = mpy.VideoFileClip(str(video_path))
        vw, vh = clip.size
        # Resize our window to the video's native size for playback
        try:
            screen = pygame.display.set_mode((vw, vh), FLAGS_WINDOWED)
        except Exception:
            screen = pygame.display.set_mode((vw, vh))
        # play frames
        for frame in clip.iter_frames(fps=clip.fps, dtype='uint8'):
            # frame is (h, w, 3) RGB ndarray -> swap to (w, h, 3) for surfarray
            try:
                surf = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
            except Exception:
                # fallback: convert via frombuffer
                surf = pygame.image.frombuffer(frame.tobytes(), (vw, vh), 'RGB')
            screen.blit(surf, (0, 0))
            pygame.display.flip()
            # handle quick events so window remains responsive
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit(0)
        clip.close()
    except Exception:
        # Fallback: open with the OS default player and wait for it to finish
        try:
            # Use PowerShell Start-Process -Wait so we block until the player exits
            subprocess.run(["powershell", "-Command", "Start-Process", "-FilePath", str(video_path), "-Wait"], check=False)
        except Exception:
            try:
                os.startfile(str(video_path))
            except Exception:
                # cannot play; just continue
                pass

    # After playback restore previous windowed size and restart the game
    try:
        screen = pygame.display.set_mode(last_windowed_size, FLAGS_WINDOWED)
    except Exception:
        screen = pygame.display.set_mode(last_windowed_size)
    prev_window_size = last_windowed_size
    # recompute play surface and restart
    restart_game_state()

def restart_game_state():
    """Reset logo, play surface and motion to restart the screensaver loop."""
    global play_surf, bg_scaled, logo_img, logo_rect
    global pos_x, pos_y, vel_x, vel_y
    global approach_active, approach_elapsed
    pw, ph, ox, oy = compute_play_area(screen.get_size())
    play_surf = pygame.Surface((pw, ph))
    bg_scaled = scale_bg_to_fill(play_surf, bg_src)
    logo_img = fit_logo_to_window(play_surf, logo_src)
    logo_rect.size = logo_img.get_size()
    logo_rect.topleft = safe_random_pos(play_surf, logo_rect)
    pos_x = float(logo_rect.x)
    pos_y = float(logo_rect.y)
    vel_x, vel_y = make_velocity(play_surf)
    approach_active = False
    approach_elapsed = 0.0

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
    pw, ph = play_surf.get_size()

    if approach_active:
        # Eased interpolation from start to target over APPROACH_TIME
        approach_elapsed += dt
        t = min(1.0, approach_elapsed / APPROACH_TIME)
        e = ease_out_cubic(t)
        nx = approach_start_x + (approach_target_x - approach_start_x) * e
        ny = approach_start_y + (approach_target_y - approach_start_y) * e
        logo_rect.x = int(nx)
        logo_rect.y = int(ny)
        pos_x = float(logo_rect.x)
        pos_y = float(logo_rect.y)
        if t >= 1.0:
            # reached center
            logo_rect.center = (pw // 2, ph // 2)
            pos_x = float(logo_rect.x)
            pos_y = float(logo_rect.y)
            vel_x = 0.0
            vel_y = 0.0
            approach_active = False
            # Play endgame video and restart when done
            try:
                play_endgame_then_restart()
            except Exception:
                # ensure we still restart even if video playback fails
                restart_game_state()
    else:
        pos_x += vel_x * dt
        pos_y += vel_y * dt
        logo_rect.x = int(pos_x)
        logo_rect.y = int(pos_y)

        bounced_x = False
        bounced_y = False

        if logo_rect.left <= 0:
            logo_rect.left = 0
            pos_x = float(logo_rect.x)
            vel_x = -vel_x
            bounced_x = True
        elif logo_rect.right >= pw:
            logo_rect.right = pw
            pos_x = float(logo_rect.x)
            vel_x = -vel_x
            bounced_x = True

        if logo_rect.top <= 0:
            logo_rect.top = 0
            pos_y = float(logo_rect.y)
            vel_y = -vel_y
            bounced_y = True
        elif logo_rect.bottom >= ph:
            logo_rect.bottom = ph
            pos_y = float(logo_rect.y)
            vel_y = -vel_y
            bounced_y = True

        # If both axes bounced in the same frame (corner "sweet spot"), or we're very close
        # to a corner (within NEAR_PERCENT of both axes), start approach-to-center.
        # This is strict (1%) so it doesn't trigger too often.
        pw_f = float(pw)
        ph_f = float(ph)
        near_x = (logo_rect.left <= pw_f * NEAR_PERCENT) or ((pw_f - logo_rect.right) <= pw_f * NEAR_PERCENT)
        near_y = (logo_rect.top <= ph_f * NEAR_PERCENT) or ((ph_f - logo_rect.bottom) <= ph_f * NEAR_PERCENT)
        if (bounced_x and bounced_y) or (near_x and near_y):
            cx, cy = pw // 2, ph // 2
            # initialize eased approach
            approach_active = True
            approach_elapsed = 0.0
            approach_start_x = float(logo_rect.x)
            approach_start_y = float(logo_rect.y)
            approach_target_x = float(cx - (logo_rect.width // 2))
            approach_target_y = float(cy - (logo_rect.height // 2))
            # keep velocities zeroed while we approach
            vel_x = 0.0
            vel_y = 0.0
            # don't play bounce sound for corner hit; it's handled by movement end
            bounced = False
        else:
            bounced = bounced_x or bounced_y

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
