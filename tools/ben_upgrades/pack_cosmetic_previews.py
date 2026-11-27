"""Blender headless: crop the three cosmetic reference pictures to squares and write cosmetic-previews.rgba.

Run: blender -b -P pack_cosmetic_previews.py
Output order: Play as Albedo, Realistic Ultimatrix, Potis Altiare (256x256 RGBA8, top row first).
"""
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
import bpy, numpy as np
from pathlib import Path

H = WORK
SRC = H / 'cosmetic-previews'
# (file, centre x fraction, centre y fraction, side as a fraction of the shorter edge)
ITEMS = [('albedo.jpg', 0.52, 0.50, 1.0),
         ('realistic-ultimatrix.jpg', 0.40, 0.50, 1.0),
         ('potis-altiare.webp', 0.50, 0.30, 1.0)]
SIDE = 256

out = bytearray()
for name, fx, fy, fraction in ITEMS:
    image = bpy.data.images.load(str(SRC / name))
    w, h = image.size
    pixels = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]   # top row first
    side = int(min(w, h) * fraction)
    x0 = int(np.clip(fx * w - side / 2, 0, w - side))
    y0 = int(np.clip(fy * h - side / 2, 0, h - side))
    crop = pixels[y0:y0 + side, x0:x0 + side]
    square = bpy.data.images.new('sq_' + name, side, side, alpha=True)
    square.pixels = crop[::-1].reshape(-1).tolist()          # Blender stores bottom row first
    square.scale(SIDE, SIDE)
    data = np.array(square.pixels[:], dtype=np.float32).reshape(SIDE, SIDE, 4)[::-1]
    data[..., 3] = 1.0
    # Blender holds linear floats for non-colour-managed loads; the files are plain sRGB bytes, so no conversion.
    out += (np.clip(data, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes()
    print(name, (w, h), 'crop', (x0, y0, side))
(H / 'cosmetic-previews.rgba').write_bytes(bytes(out))
print('wrote', len(out), 'bytes')
