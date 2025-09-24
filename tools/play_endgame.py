import sys
from pathlib import Path
import pygame

try:
    from moviepy.video.io.VideoFileClip import VideoFileClip
except Exception as e:
    print("moviepy not available:", e)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VIDEO = DATA / "endgame.mp4"

if not VIDEO.exists():
    print("endgame.mp4 not found in data/ folder")
    sys.exit(1)

pygame.init()
try:
    clip = VideoFileClip(str(VIDEO))
except Exception as e:
    print("Failed to open video:", e)
    pygame.quit()
    sys.exit(1)

vw, vh = clip.size
screen = pygame.display.set_mode((vw, vh))
pygame.display.set_caption('Endgame Preview')

try:
    for frame in clip.iter_frames(fps=clip.fps, dtype='uint8'):
        # frame is HxWx3
        try:
            surf = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
        except Exception:
            surf = pygame.image.frombuffer(frame.tobytes(), (frame.shape[1], frame.shape[0]), 'RGB')
        if surf.get_size() != (vw, vh):
            surf = pygame.transform.smoothscale(surf, (vw, vh))
        screen.blit(surf, (0, 0))
        pygame.display.flip()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                clip.close()
                pygame.quit()
                sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                clip.close()
                pygame.quit()
                sys.exit(0)
    clip.close()
finally:
    pygame.quit()

print('Playback finished')
