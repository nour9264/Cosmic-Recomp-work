"""Catalog original Cannonbolt animation records and their validated stream ranges.

The move-to-clip association follows the L/L/H, H/H/H, H/H/S and S/H
sequences; the native clip names and registration pointers are verified in
the local disc data. Track semantics and retargeting are still experimental.
"""
import hashlib
import json
import math
import struct
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump

root = WORK
data = (root / '99_95.stream1.bin').read_bytes()
clips = [
    ('Backspin Burnout', 0x42eeeb, 'atk_llh_b', 0xe43a0, 0x490824),
    ('Spin Cycle', 0x42ee97, 'atk_hhh_b', 0xdf020, 0x490854),
    ('Meteor Bolt', 0x42edc7, 'atk_hhs_b', 0xde080, 0x49085c),
    ('Suction Blast', 0x42ecb1, 'Atk_SH_B', 0xd9120, 0x4908d4),
    ('Suction Blast lead-in', None, 'Atk_SH', 0xc19a0, 0x4908cc),
]
records = []
for move, title_at, name, at, pointer_at in clips:
    if title_at is not None:
        assert data[title_at:].split(b'\0', 1)[0].decode() == move
    assert data[at:at+32].split(b'\0', 1)[0].decode() == name
    assert struct.unpack_from('<I', data, pointer_at)[0] == at
    fields = struct.unpack_from('<12I', data, at+0x50)
    count = fields[1]
    times = struct.unpack_from(f'<{count}f', data, fields[2])
    assert all(math.isfinite(t) for t in times)
    assert all(a <= b for a, b in zip(times, times[1:])) and abs(times[-1]-1) < 0.001
    assert all(at <= p < len(data) for p in fields[2:9] if p)
    end = max(fields[8:10])
    assert end > at
    payload = data[at:end]
    (root / (name+'.record.bin')).write_bytes(payload)
    records.append(dict(move=move, clip=name, source_offset=at,
                        registration_pointer=pointer_at, sample_count=count,
                        normalized_times=times, stream_pointers=fields,
                        record_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
                        retargeted=False))
(root / 'cannonbolt-clip-catalog.json').write_text(json.dumps(records, indent=2))
print('Cataloged', len(records), 'source animation records; no runtime changes.')
