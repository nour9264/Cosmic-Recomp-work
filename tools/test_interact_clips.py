"""Checks tools/interact/install_interact_clips.py on a synthetic two-bone package (no game files needed)."""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'interact'))
import install_interact_clips as ic
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, animation_time_range, streamed_clip

TAGS = [0, 31]


def idle_clip(name=b'idle_01'):
    clip = bytearray(216 + 12 * len(TAGS))
    clip[:64] = name + b'\0' * (64 - len(name))
    struct.pack_into('>2I', clip, 72, len(TAGS), len(TAGS))
    struct.pack_into('>I', clip, 80, 0xffffffff)
    for i, tag in enumerate(TAGS):
        struct.pack_into('>H', clip, 88 + 2 * i, tag)
        for j in range(3):
            struct.pack_into('>I', clip, 216 + 12 * i + 4 * j, 0xffffffff)
    return bytes(clip)


def package():
    template = bytes.fromhex('7661707300010003') + struct.pack('>IIIH', 0, 0, 0, 4) + bytes(14)
    clip = idle_clip()
    rows = [(0x11111111, 0, vec(1)), (0x22222222, 0, vec(1)), (0x33333333, 0, vec(1))]
    clip = bytearray(clip)
    for i in range(len(TAGS)):
        for j in range(3):
            struct.pack_into('>I', clip, 216 + 12 * i + 4 * j, (i * 3 + j) % 3)
    sections = {9: m.build_vaps(9, 4, sorted(rows, key=lambda r: r[0] % max(1, len(rows) // 4))),
                13: m.build_vaps(13, 4, [(m.crc('idle_01'), 0, bytes(clip))])}
    return m.package(template, sections)


def vec(n):
    return ic.vec_channel([(0.0, 0.0, 0.0)] * n)


def pose(frames, moving):
    # one row per bone: position (3), quaternion w x y z, scale (3)
    return [[[0, 0, 0, 1, 0, 0, 0, 1, 1, 1], [0, 0, 0, 1, 0.1 * f if moving else 0, 0, 0, 1, 1, 1]] for f in range(frames)]


def main():
    raw = package()
    clips = {'interact_in_01': {'frames': pose(9, True)}, 'interact_01': {'frames': pose(22, True)},
             'interact_out_01': {'frames': pose(15, True)}}
    result, keys = ic.add_clips(raw, 'xx', TAGS, clips)
    parts = entries(result)
    channels = channel_records(parts[9])
    table = {k: c for k, f, c in m.vaps_rows(parts[13])}
    # Each clip sits on the original timeline: in 0, loop 1440, out 4960 ticks, keys 160 ticks apart.
    for name, frames, start in (('interact_in_01', 9, 0), ('interact_01', 22, 9), ('interact_out_01', 15, 31)):
        begin, end = animation_time_range(table[keys[name]], channels)
        assert (begin, end) == (start * 160, (start + frames - 1) * 160), (name, begin, end)
    assert m.crc('idle_01') in table
    # A bone that never moves keeps one key per channel; the first bone's rotation keeps all of them.
    clip = table[keys['interact_01']]
    pos_index, rot_index, scale_index = struct.unpack_from('>3I', clip, 216 + 12)   # bone 31 (moves)
    assert struct.unpack_from('>H', channels[rot_index], 4)[0] == 22
    pos_index, rot_index, scale_index = struct.unpack_from('>3I', clip, 216)        # bone 0 (still)
    assert struct.unpack_from('>H', channels[pos_index], 4)[0] == 1
    assert struct.unpack_from('>H', channels[rot_index], 4)[0] == 22
    # Installing twice replaces the first install instead of stacking its clips.
    again, _ = ic.add_clips(result, 'xx', TAGS, clips)
    assert len(m.vaps_rows(entries(again)[13])) == len(m.vaps_rows(parts[13])) == 4
    assert len(m.vaps_rows(entries(again)[9])) == len(m.vaps_rows(parts[9]))

    # Animation set: role 5 (Vilgax Attacks' idle) moves to 0x49, the three interact roles are added.
    idle = m.crc('idle_01')
    words = [3, 0] + [idle, 0, 0, 0x3f800000, 0x40a00000, 0, 1 << 24] + [idle, 0, 0, 0x3f800000, 0x40a00000, 0, 5 << 24] + \
            [0x1234, 0, 0, 0x3f800000, 0x40a00000, 0, 0x49 << 24]
    words += [0] * (491 - len(words))
    patched = struct.unpack('>491I', ic.patch_set(struct.pack('>491I', *words), idle, keys))
    roles = {(patched[2 + 7 * e], patched[8 + 7 * e] >> 24) for e in range(patched[0])}
    assert patched[0] == 6
    assert (idle, 1) in roles and (idle, 0x49) in roles and (0x1234, 0xfe) in roles       # a foreign 0x49 is moved aside
    assert (keys['interact_01'], 0x48) in roles and (keys['interact_in_01'], 0x4a) in roles and (keys['interact_out_01'], 5) in roles
    assert patched[2 + 7 * 6:] == tuple([0] * (491 - 2 - 7 * 6))
    again = struct.unpack('>491I', ic.patch_set(struct.pack('>491I', *patched), idle, keys))
    assert again == patched                                                                # running it again changes nothing
    print('Interact clips: timeline, key compaction, replace-on-reinstall and set roles passed.')


main()
