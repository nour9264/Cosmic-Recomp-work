"""Checks for Ben's new Ultimatrix model swap (no game files needed; pass --staged to also check a real builder output).

1. The draw-range constants in the native hook agree with each other and with the builder's index layout
   ([green][piece][realistic][piece]).
2. The hook is wired: Ben's 10089-vertex model goes to BenDeviceRange, which reads the cosmetics switches.
3. The cosmetics file keys the native loader reads are the ones documented (pc-cosmetics.ini).
4. The Albedo pack tool: a synthetic ALBD v4 pack gets the new entry added, a same-key entry is replaced, other entries
   are kept byte for byte, and a result that would exceed 64 entries is refused.
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'ben_ultimatrix'))
from make_albedo_pack_entries import build, entry, MAX_ENTRIES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--staged', type=Path, help='output folder of build_ben_ultimatrix_assets.py to compare against')
args = parser.parse_args()

swap = (ROOT / 'native-rex/src/way_big_draw_swap.h').read_text(encoding='utf-8')
constants = dict(re.findall(r'k(\w+) = (\d+)', re.search(r'constexpr uint16_t (kGreenStart.*?);', swap, re.S).group(1)))
green_start, green_count, green_piece, real_start, real_count, real_piece = (
    int(constants[k]) for k in ('GreenStart', 'GreenCount', 'GreenPieceCount', 'RealStart', 'RealCount', 'RealPieceCount'))
piece = green_piece - green_count
assert piece > 0 and real_piece - real_count == piece, 'the same Bolts Tears index run follows both devices'
assert real_start == green_start + green_piece, 'realistic indices start right after the green device and its piece'
assert max(green_start, real_start, real_piece) < 65536, 'draw ranges are 16-bit fields'
if args.staged:
    manifest = json.loads((args.staged / 'manifest.json').read_text())
    assert (manifest['green_start'], manifest['green_count'], manifest['piece_count'], manifest['real_start'], manifest['real_count']) == \
           (green_start, green_count, piece, real_start, real_count), 'builder output disagrees with the native constants'

assert 'REX_LOAD_U32(ctx.r4.u32 + 72) == 10089u' in swap and 'BenDeviceRange(ctx, base);' in swap
assert 'cosmetics::realistic_on.load' in swap and 'cosmetics::bolts_on.load' in swap
state = (ROOT / 'native-rex/src/cosmetics_state.h').read_text(encoding='utf-8')
# Only the ON/OFF choices are kept in pc-cosmetics.ini; ownership and the balance live in the game save (script sync).
for key in ('"realistic"', '"bolts"'):
    assert f'key == {key}' in state, key
assert 'owned_* and spent lines are ignored' in state
assert 'pc-cosmetics.ini' in state
bridge = (ROOT / 'native-rex/src/pc_menu_bridge.h').read_text(encoding='utf-8')
assert 'ben10::cosmetics::Load(host->user_data_root());' in bridge
textures = (ROOT / 'native-rex/src/albedo_textures.cpp').read_text(encoding='utf-8')
assert 'item.width > 2048' in textures and 'width > 2048 || height > 2048' in textures, '2048 px replacement textures'


def fake_entry(key, size=4096 * 2):
    return struct.pack('<IIIIIIQQQ', key, 64, 64, 18, 4096, 4096, 0, 0, 0) + bytes([key & 255]) * size


def fake_pack(keys):
    return b'ALBD\x04\0\0\0' + struct.pack('<I', len(keys)) + b''.join(fake_entry(k) for k in keys)


base = 2048 // 128 * (2048 // 128) * 8192
green = bytes(128) + bytes(range(256)) * ((base + 8192) // 256)
albedo = bytes(128) + bytes(reversed(range(256))) * ((base + 8192) // 256)
assert len(green) == len(albedo) and len(green) - 128 > base
new_entry = entry(0x14934253, green, albedo)
assert struct.unpack_from('<IIIII', new_entry)[:3] == (0x14934253, 2048, 2048) and new_entry.endswith(albedo[128:])
pack = fake_pack([1, 2, 3])
result, before, after, dropped = build(pack, [(0x14934253, green, albedo)])
assert (before, after, dropped) == (3, 4, 0) and struct.unpack_from('<I', result, 8)[0] == 4
assert result[12:12 + len(fake_entry(1))] == fake_entry(1), 'existing entries are kept byte for byte'
again, _, after2, dropped2 = build(result, [(0x14934253, green, albedo)])
assert (after2, dropped2) == (4, 1) and again == result, 'adding the same key twice replaces, never duplicates'
try:
    build(fake_pack(list(range(1, MAX_ENTRIES + 1))), [(0x14934253, green, albedo)])
    raise SystemExit('a pack over 64 entries must be refused')
except AssertionError:
    pass
print('Ben Ultimatrix checks OK: hook constants, wiring, cosmetics keys, 2048 px limit, Albedo pack tool.')
