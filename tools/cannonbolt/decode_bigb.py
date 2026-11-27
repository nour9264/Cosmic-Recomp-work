"""Decode local BIGB player asset streams with bounded, verified lengths."""
import argparse
import hashlib
import struct
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump


def decode(data, expected):
    out = bytearray()
    pos = 0
    while pos < len(data):
        token = data[pos]
        pos += 1
        if token < 0x40:
            count = token + 1
            if pos + count > len(data) or len(out) + count > expected:
                raise ValueError('Invalid literal range')
            out.extend(data[pos:pos+count])
            pos += count
        elif token < 0x80:
            count = (token & 63) + 2
            if pos >= len(data) or len(out) + count > expected:
                raise ValueError('Invalid repeat range')
            out.extend(bytes([data[pos]]) * count)
            pos += 1
        else:
            if pos >= len(data):
                raise ValueError('Truncated reference')
            word = token * 256 + data[pos]
            pos += 1
            count = (word & 15) + 2
            distance = 4097 - (word >> 4)
            if not 0 < distance <= len(out) or len(out) + count > expected:
                raise ValueError('Invalid backward reference')
            for _ in range(count):
                out.append(out[-distance])
    if len(out) != expected:
        raise ValueError(f'Length mismatch {len(out)} != {expected}')
    return bytes(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archives', type=Path, nargs='+')
    args = parser.parse_args()
    for path in args.archives:
        raw = path.read_bytes()
        assert raw[:4] == b'BIGB' and struct.unpack_from('<I', raw, 8)[0] == 0xa3
        start = 16 + struct.unpack_from('<I', raw, 4)[0]
        _, _, size1, size2, packed1, packed2 = struct.unpack_from('<6I', raw, 124)
        assert start + packed1 + packed2 <= len(raw)
        for index, offset, packed, size in ((1, start, packed1, size1), (2, start+packed1, packed2, size2)):
            decoded = decode(raw[offset:offset+packed], size)
            dst = path.with_suffix(f'.stream{index}.bin')
            dst.write_bytes(decoded)
            print(dst.name, len(decoded), hashlib.sha256(decoded).hexdigest())


if __name__ == '__main__':
    main()
