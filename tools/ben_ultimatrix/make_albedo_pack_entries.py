"""Add Ben's new Ultimatrix textures (green + Albedo recolour) to a copy of the Albedo texture pack.

The pack (`user/albedo-textures.bin`, magic ALBD v4) maps a texture key to its replacement bytes; the game renders the
Albedo variant when Play as Albedo is on. This tool never touches the installed pack: it reads `--pack` and writes `--out`.

  python tools/ben_ultimatrix/make_albedo_pack_entries.py --staged build/ben-ultimatrix/staged \\
      --pack installation/user/albedo-textures.bin --out build/ben-ultimatrix/albedo-textures.bin
"""
import argparse
import json
import struct
from pathlib import Path

MAX_ENTRIES = 64


def fingerprint(data):
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
    return value


def entry(key, green, albedo):
    """One 2048x2048 DXT5 replacement: a 48-byte header, then the Albedo bytes (the green bytes are only fingerprinted)."""
    pg, pa = green[128:], albedo[128:]
    assert len(pg) == len(pa)
    width = height = 2048
    base = width // 128 * (height // 128) * 8192
    assert len(pg) > base
    sample = pg[base // 4:base // 4 + 64] + pg[base // 2:base // 2 + 64]
    return struct.pack('<IIIIIIQQQ', key, width, height, 18, base, len(pg) - base,
                       fingerprint(sample), fingerprint(pg[:base]), fingerprint(pg[base:])) + pa


def build(raw, extra, raw_entries=()):
    """Returns (pack bytes, old count, new count, dropped). Entries with the same key are replaced."""
    assert raw[:8] == b'ALBD\x04\0\0\0'
    count = struct.unpack_from('<I', raw, 8)[0]
    pos, keep, dropped = 12, [], 0
    replaced = {k for k, _, _ in extra} | {k for k, _ in raw_entries}
    for _ in range(count):
        key, width, height, fmt, base, mip = struct.unpack_from('<IIIIII', raw, pos)
        size = 48 + base + mip
        if key in replaced:
            dropped += 1
        else:
            keep.append(raw[pos:pos + size])
        pos += size
    assert pos == len(raw), 'the pack ends where its entries end'
    entries = keep + [entry(*e) for e in extra] + [blob for _, blob in raw_entries]
    assert len(entries) <= MAX_ENTRIES
    return raw[:8] + struct.pack('<I', len(entries)) + b''.join(entries), count, len(entries), dropped


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--staged', type=Path, required=True, help='output folder of build_ben_ultimatrix_assets.py (both variants)')
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--extra-entries', type=Path, help='folder of ready entry_*.bin files to append (other aliens)')
    args = parser.parse_args()
    manifest = json.loads((args.staged / 'manifest.json').read_text())
    extra = [(manifest['texture'], (args.staged / 'texture_green.bin').read_bytes(), (args.staged / 'texture_albedo.bin').read_bytes())]
    raw_entries = []
    if args.extra_entries:
        raw_entries = [(struct.unpack_from('<I', p.read_bytes(), 0)[0], p.read_bytes()) for p in sorted(args.extra_entries.glob('entry_*.bin'))]
    data, before, after, dropped = build(args.pack.read_bytes(), extra, raw_entries)
    args.out.write_bytes(data)
    print(f'{before} entries -> {after} ({dropped} replaced), {len(raw_entries)} extra entries; wrote {args.out}')
