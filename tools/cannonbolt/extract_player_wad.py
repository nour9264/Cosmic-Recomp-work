"""Extract only player asset archives from the locally owned PS2 disc files."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
args = parser.parse_args()
out = Path(__file__).resolve().parent
directory = (args.source / 'Game.dir').read_bytes()
count, = struct.unpack_from('<I', directory)
assert len(directory) == 4 + count * 72
rows = {}
for name, size, sector in struct.iter_unpack('<64sII', directory[4:]):
    name = name.split(b'\0', 1)[0].decode('ascii')
    assert name not in rows
    rows[name] = (size, sector * 2048)
wad = args.source / 'Game.wad'
length = wad.stat().st_size
assert all(offset + size <= length for size, offset in rows.values())
manifest = {}
with wad.open('rb') as stream:
    for name in ('levels.txt', '05_10.pss', '99_95.pss'):
        size, offset = rows[name]
        stream.seek(offset)
        data = stream.read(size)
        assert len(data) == size
        if name.endswith('.pss'):
            assert data.startswith(b'BIGB')
        (out / name).write_bytes(data)
        manifest[name] = {'offset': offset, 'size': size, 'sha256': hashlib.sha256(data).hexdigest()}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print('Extracted verified player and hero viewer containers; no gameplay files changed.')
