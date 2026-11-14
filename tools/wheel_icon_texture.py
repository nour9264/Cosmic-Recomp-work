"""Encode a 128x128 PNG as an Xbox 360 DXT5 selection-wheel icon texture.

The wheel pictures of the aliens are 128x128 DXT5 textures (format 0x102): 32x32
blocks of 16 bytes, each 16-bit pair byte-swapped, in one tile. The 128-byte
header is taken from an existing icon of the same format."""
import struct
import zlib

from extract_discord_level_images import tiled_offset


def read_png(path):
    """8-bit RGBA, non-interlaced PNG to (width, height, bytes)."""
    data = open(path, 'rb').read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Not a PNG file')
    cursor, idat, width = 8, b'', 0
    while cursor < len(data):
        size, kind = struct.unpack_from('>I4s', data, cursor)
        body = data[cursor + 8:cursor + 8 + size]
        if kind == b'IHDR':
            width, height, depth, color, _, _, interlace = struct.unpack('>IIBBBBB', body)
            if (depth, color, interlace) != (8, 6, 0):
                raise ValueError('Expected an 8-bit RGBA PNG without interlacing')
        elif kind == b'IDAT':
            idat += body
        cursor += 12 + size
    raw = zlib.decompress(idat)
    stride = width * 4
    out = bytearray()
    previous = bytearray(stride)
    for row in range(height):
        kind = raw[row * (stride + 1)]
        line = bytearray(raw[row * (stride + 1) + 1:(row + 1) * (stride + 1)])
        for i in range(stride):
            left = line[i - 4] if i >= 4 else 0
            up = previous[i]
            upleft = previous[i - 4] if i >= 4 else 0
            if kind == 1:
                line[i] = (line[i] + left) & 255
            elif kind == 2:
                line[i] = (line[i] + up) & 255
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 255
            elif kind == 4:
                guess = left + up - upleft
                distances = (abs(guess - left), abs(guess - up), abs(guess - upleft))
                nearest = (left, up, upleft)[distances.index(min(distances))]
                line[i] = (line[i] + nearest) & 255
        out += line
        previous = line
    return width, height, bytes(out)


def rgb565(r, g, b):
    return ((r * 31 + 127) // 255 << 11) | ((g * 63 + 127) // 255 << 5) | ((b * 31 + 127) // 255)


def from565(value):
    r, g, b = value >> 11, (value >> 5) & 63, value & 31
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)


def encode_block(pixels):
    """16 RGBA pixels to one 16-byte DXT5 block (PC layout)."""
    alphas = [p[3] for p in pixels]
    hi, lo = max(alphas), min(alphas)
    if hi == lo:
        alpha_bytes, indices = bytes([hi, lo]), 0
    else:
        # Eight-alpha mode (a0 > a1): index 0 = a0, 1 = a1, 2..7 interpolate.
        palette = [hi, lo] + [((7 - i) * hi + i * lo) // 7 for i in range(1, 7)]
        indices = 0
        for n, a in enumerate(alphas):
            best = min(range(8), key=lambda k: abs(palette[k] - a))
            indices |= best << (3 * n)
        alpha_bytes = bytes([hi, lo])
    alpha_part = alpha_bytes + indices.to_bytes(6, 'little')
    opaque = [p for p in pixels if p[3] > 24] or pixels
    # Colour endpoints from the bounding box of the visible pixels.
    lows = [min(p[c] for p in opaque) for c in range(3)]
    highs = [max(p[c] for p in opaque) for c in range(3)]
    c0, c1 = rgb565(*highs), rgb565(*lows)
    if c0 < c1:
        c0, c1 = c1, c0
    if c0 == c1:
        color_part = struct.pack('<HH', c0, c1) + bytes(4)
    else:
        e0, e1 = from565(c0), from565(c1)
        table = [e0, e1, tuple((2 * x + y) // 3 for x, y in zip(e0, e1)), tuple((x + 2 * y) // 3 for x, y in zip(e0, e1))]
        bits = 0
        for n, p in enumerate(pixels):
            source = p[:3] if p[3] > 24 else opaque[0][:3]
            best = min(range(4), key=lambda k: sum((a - b) ** 2 for a, b in zip(table[k], source)))
            bits |= best << (2 * n)
        color_part = struct.pack('<HH', c0, c1) + bits.to_bytes(4, 'little')
    return alpha_part + color_part


def icon_texture(png_path, header, size=128):
    """A complete texture record: header (128 bytes) plus the encoded size x size pixels (base level only)."""
    width, height, rgba = read_png(png_path)
    if (width, height) != (size, size) or len(header) != 128:
        raise ValueError(f'Wheel pictures are {size}x{size} with a 128-byte header')
    # Transparent pixels take the colour of the nearest opaque neighbour in the block (handled
    # in encode_block); premultiplying here would darken the edges, so it is not done.
    blocks_wide = size // 4
    tile = bytearray(blocks_wide * blocks_wide * 16)
    for by in range(blocks_wide):
        for bx in range(blocks_wide):
            pixels = []
            for y in range(4):
                for x in range(4):
                    at = ((by * 4 + y) * size + bx * 4 + x) * 4
                    pixels.append(tuple(rgba[at:at + 4]))
            block = bytearray(encode_block(pixels))
            block[0::2], block[1::2] = block[1::2], block[0::2]  # Xbox: 16-bit words swapped.
            offset = tiled_offset(bx, by, blocks_wide, 4)
            tile[offset:offset + 16] = block
    return bytes(header) + bytes(tile)
