import importlib, traceback
try:
    import moviepy
    print('moviepy version:', getattr(moviepy, '__version__', None))
    print('moviepy file:', getattr(moviepy, '__file__', None))
    print('moviepy path:', getattr(moviepy, '__path__', None))
    spec = importlib.util.find_spec('moviepy.editor')
    print('moviepy.editor spec:', spec)
    try:
        from moviepy import editor as ed
        print('moviepy.editor imported:', ed)
    except Exception:
        print('moviepy.editor import failed:')
        traceback.print_exc()
except Exception:
    print('moviepy import failed:')
    traceback.print_exc()
