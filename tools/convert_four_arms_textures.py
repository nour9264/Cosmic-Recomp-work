"""Retile the European PS3 Four Arms texture bank for a private Xbox candidate."""
import argparse
import hashlib
from pathlib import Path
import struct

from extract_discord_level_images import table, tiled_offset
from merge_alien_streams import entries


def retile_bc1(record):
    fmt, width, height = struct.unpack_from('>HHH', record, 4)
    if record[:4] != bytes.fromhex('90434000') or fmt != 0x11c:
        raise ValueError('Expected a resident BC1 texture')
    if min(width, height) < 32 or any(n & (n - 1) for n in (width, height)):
        raise ValueError('Unexpected texture dimensions')
    mip_count = struct.unpack_from('>I', record, 28)[0]
    if not 1 <= mip_count <= min(width, height).bit_length() - 5:
        raise ValueError('Unexpected mip count')
    output = bytearray(record[:128])
    offset = 128
    for _ in range(mip_count):
        cols, rows = width // 4, height // 4
        level_size = cols * rows * 8
        if offset + level_size > len(record):
            raise ValueError('Truncated PS3 mip')
        tiled = bytearray(((cols + 31) // 32) * ((rows + 31) // 32) * 8192)
        for y in range(rows):
            for x in range(cols):
                source = offset + (y * cols + x) * 8
                target = tiled_offset(x, y, cols, 3)
                for byte in range(8):
                    tiled[target + byte] = record[source + (byte ^ 1)]
        output.extend(tiled)
        offset += level_size
        width //= 2
        height //= 2
    if offset != len(record):
        raise ValueError('Unexpected trailing PS3 texture data')
    return bytes(output)


def rebuild_bank(section, convert_record, record_flags=None):
    records = table(section)
    base = struct.unpack_from('>I', section, 28)[0]
    directory = 32 + struct.unpack_from('>I', section, 44)[0]
    alignment = 1 << struct.unpack_from('>H', section, 12)[0]
    output = bytearray(section[:base])
    for index in range(len(records)):
        position = directory + index * 12
        key, info, _ = struct.unpack_from('>III', section, position)
        record = convert_record(records[key])
        output.extend(bytes((-len(output)) % alignment))
        flags = info >> 24 if record_flags is None else record_flags(record)
        struct.pack_into('>II', output, position + 4,
                         (flags << 24) | len(record), len(output) - base)
        output.extend(record)
    output.extend(bytes((-len(output)) % alignment))
    struct.pack_into('>I', output, 16, len(output) - base)
    table(output)
    return bytes(output)


def convert_bank(section):
    return rebuild_bank(section, retile_bc1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('donor', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    donor = args.donor.read_bytes()
    if hashlib.sha256(donor).hexdigest() != 'b36b1077cded79f3d59f150f100d69a351d1ba2dc1cb20fb6c217fac86285dda':
        raise SystemExit('Unsupported Four Arms archive. Expected the verified BLES01110 donor.')
    args.output.write_bytes(convert_bank(entries(donor)[0]))
