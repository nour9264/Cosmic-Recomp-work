from pathlib import Path
import sys
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
sys.path.insert(0, str(REPO / 'tools'))
from make_hologram_pictures import write_png

root=WORK
raw=(APP_ROOT/'installation/user/options-ultimatrix.rgba').read_bytes()
assert len(raw)==2*128*128*4
for i in range(2):
    write_png(root/f'original-badge-{i}.png',128,128,raw[i*65536:(i+1)*65536])
