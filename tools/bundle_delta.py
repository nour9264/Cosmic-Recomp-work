"""Small binary patches for the game files the Ben additions change (chest-tap clips, Ben's transformation).

A patch stores which pieces of the player's unmodified file are reused and the new bytes in between, so it carries only the
additions. It records the SHA-256 of the file it applies to and of the result: a file that is not the expected original is left
alone, a file that already is the result is skipped, and a wrong result is never written.

    python tools/bundle_delta.py make <original file> <changed file> <patch file>
    python tools/bundle_delta.py apply <original file> <patch file> <output file>
"""
import hashlib
import struct
import sys
import zlib
from pathlib import Path

MAGIC = b'CDLT1'
BLOCK = 32
STEP = 4


def make(source, target):
    index = {}
    for offset in range(0, len(source) - BLOCK + 1, STEP):
        index.setdefault(source[offset:offset + BLOCK], offset)
    ops = bytearray()
    literal_from = 0
    position = 0
    end = len(target)

    def flush(upto):
        if upto > literal_from:
            ops.extend(b'\x01' + struct.pack('<I', upto - literal_from) + target[literal_from:upto])

    while position <= end - BLOCK:
        found = index.get(target[position:position + BLOCK])
        if found is None:
            position += 1
            continue
        start, at = found, position
        # Extend the match backwards into bytes that were being treated as literal, then forwards.
        while at > literal_from and start > 0 and source[start - 1] == target[at - 1]:
            start -= 1
            at -= 1
        length = 0
        limit = min(len(source) - start, end - at)
        while length + 256 <= limit and source[start + length:start + length + 256] == target[at + length:at + length + 256]:
            length += 256
        while length < limit and source[start + length] == target[at + length]:
            length += 1
        flush(at)
        ops.extend(b'\x00' + struct.pack('<II', start, length))
        position = literal_from = at + length
    flush(end)
    body = zlib.compress(bytes(ops), 9)
    return MAGIC + hashlib.sha256(source).digest() + hashlib.sha256(target).digest() + body


def apply(source, patch):
    if patch[:5] != MAGIC:
        raise ValueError('Not a patch file')
    want_source, want_target = patch[5:37], patch[37:69]
    if hashlib.sha256(source).digest() != want_source:
        raise ValueError('The file is not the expected original')
    ops = zlib.decompress(patch[69:])
    out = bytearray()
    at = 0
    while at < len(ops):
        if ops[at] == 0:
            start, length = struct.unpack_from('<II', ops, at + 1)
            out += source[start:start + length]
            at += 9
        else:
            length, = struct.unpack_from('<I', ops, at + 1)
            out += ops[at + 5:at + 5 + length]
            at += 5 + length
    if hashlib.sha256(out).digest() != want_target:
        raise ValueError('The patched file does not match the expected result')
    return bytes(out)


def digests(patch):
    """(source sha256, result sha256) as hex, read from a patch without applying it."""
    return patch[5:37].hex(), patch[37:69].hex()


if __name__ == '__main__':
    if len(sys.argv) != 5 or sys.argv[1] not in ('make', 'apply'):
        raise SystemExit(__doc__)
    first, second, third = (Path(p) for p in sys.argv[2:])
    if sys.argv[1] == 'make':
        third.write_bytes(make(first.read_bytes(), second.read_bytes()))
    else:
        third.write_bytes(apply(first.read_bytes(), second.read_bytes()))
    print('ok')
