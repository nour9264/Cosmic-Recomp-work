"""Prepare a private Albedo texture pack from the supported Xbox 360 assets."""
import argparse
from pathlib import Path
import struct

from extract_discord_level_images import table, tiled_offset


def fingerprint(data):
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
    return value


def tint(color, kind, x, y):
    red = ((color >> 11) & 31) * 255 // 31
    green = ((color >> 5) & 63) * 255 // 63
    blue = (color & 31) * 255 // 31
    if kind == 'way_big_beam':
        return ((green * 31 + 127) // 255 << 11) | ((red * 63 + 127) // 255 << 5) | (color & 31)
    if kind == 'way_big_portrait':
        # Keep the original portrait and silhouette. Match Ben's palette on
        # the face, chest and armor, and use the red Albedo backdrop.
        if green > red + 12 and green > blue + 12:
            red, green = green, red // 3
        elif blue > red + 12 and blue > green + 12:
            red, blue = min(255, blue * 2), red // 2
        elif red > green + 20 and red > blue + 20 and green < red // 2:
            red, green = green // 2, min(255, red * 2)
        elif y >= 155 and max(red, green, blue) - min(red, green, blue) < 14 and 60 < red < 180:
            red = green = blue = min(255, red + 108)
        return ((red * 31 + 127) // 255 << 11) | ((green * 63 + 127) // 255 << 5) | ((blue * 31 + 127) // 255)
    if kind == 'swampfire' and not (176 <= x < 232 and y < 32 or x >= 416 and y >= 456):
        return color
    if kind == 'terraspin_detail' and not (x < 40 and y < 56):
        return color
    if kind == 'terraspin_body' and not (328 <= x < 447 and 346 <= y < 509 or
                                         476 <= x < 600 and 279 <= y < 402):
        return color
    if kind == 'ultimate_humungousaur_skin' and not (224 <= x < 346 and y < 68):
        return color
    if green > red + 12 and green > blue + 12:
        red, green = green, red // 3
    elif (kind == 'ben' and 144 <= x < 346 and y < 178 and (x < 283 or y < 143)
          and red < 145 and red > green + 9 and green >= blue):
        gray = min(255, 52 + int((red * .5 + green * .35 + blue * .15) * 2.6))
        red, green, blue = gray, gray, min(255, gray + 5)
    elif kind == 'ben' and x >= 346 and y >= 131 and blue > red + 15 and blue > green + 10:
        gray = (red + green + blue) // 7
        red = green = blue = gray
    else:
        return color
    return ((red * 31 + 127) // 255 << 11) | ((green * 63 + 127) // 255 << 5) | ((blue * 31 + 127) // 255)


def recolor_block(data, offset, kind, x, y, bc3):
    a, b, low, high = struct.unpack_from('>4H', data, offset)
    left, right = tint(a, kind, x, y), tint(b, kind, x, y)
    if (left, right) == (a, b):
        return
    if bc3:
        struct.pack_into('>2H', data, offset, left, right)
        return
    four_colors = a > b
    if left == right and four_colors:
        left, right = (left, right - 1) if left else (1, 0)
    if (left > right) != four_colors:
        left, right = right, left
        # Preserve each texel's original palette role when endpoints exchange.
        if four_colors:
            low ^= 0x5555
            high ^= 0x5555
        else:
            low ^= (~(low >> 1)) & 0x5555
            high ^= (~(high >> 1)) & 0x5555
    struct.pack_into('>4H', data, offset, left, right, low, high)


def encode_portrait_block(data, offset, pixels):
    def rgb565(pixel):
        r, g, b = pixel
        return ((r * 31 + 127) // 255 << 11) | ((g * 63 + 127) // 255 << 5) | ((b * 31 + 127) // 255)

    def rgb(pixel):
        return ((pixel >> 11) * 255 // 31, ((pixel >> 5) & 63) * 255 // 63, (pixel & 31) * 255 // 31)

    def distance(left, right):
        return sum((a - b) ** 2 for a, b in zip(left, right))

    first = max(pixels, key=lambda pixel: distance(pixel, pixels[0]))
    second = max(pixels, key=lambda pixel: distance(pixel, first))
    a, b = sorted((rgb565(first), rgb565(second)), reverse=True)
    left, right = rgb(a), rgb(b)
    palette = (left, right, tuple((2*x+y)//3 for x,y in zip(left,right)),
               tuple((x+2*y)//3 for x,y in zip(left,right)))
    indices = sum(min(range(4), key=lambda i: distance(pixel, palette[i])) << (2*j)
                  for j,pixel in enumerate(pixels))
    struct.pack_into('>4H', data, offset, a, b, indices & 0xffff, indices >> 16)


def recolor_texture(payload, width, height, kind, bc3, portrait=None):
    # Xbox 360 tiled BC1/BC3. Levels with a short side of 16 texels or less
    # share a packed tile. See the pinned SDK's texture util for the layout.
    data = bytearray(payload)
    tail = min(width, height).bit_length() - 5
    block_bytes = 16 if bc3 else 8
    tile_bytes = 1024 * block_bytes
    base_size = ((width + 127) // 128) * ((height + 127) // 128) * tile_bytes
    offset = 0
    seen = set()
    for level in range(max(width, height).bit_length()):
        if offset == len(payload):
            break
        scale = 1 << level
        w, h = max(1, width >> level), max(1, height >> level)
        pitch = ((max(1, width >> min(level, tail)) + 127) // 128) * 32
        sx = sy = 0
        if level >= tail:
            delta = level - tail
            if delta < 3:
                sx = (16 >> delta) // 4
            else:
                sy = ((height >> tail) >> (delta - 2)) // 4
        for y in range((h + 3) // 4):
            for x in range((w + 3) // 4):
                block = offset + tiled_offset(x + sx, y + sy, pitch, 4 if bc3 else 3)
                if block + block_bytes > len(data) or block in seen:
                    raise ValueError('Unexpected compressed mip layout')
                seen.add(block)
                color = block + block_bytes - 8
                if portrait is not None:
                    pixels = []
                    for dy in range(4):
                        for dx in range(4):
                            px = min(width - 1, (x * 4 + dx) * scale + scale // 2)
                            py = min(height - 1, (y * 4 + dy) * scale + scale // 2)
                            at = (py * width + px) * 3
                            pixels.append(portrait[at:at + 3])
                    encode_portrait_block(data, color, pixels)
                else:
                    recolor_block(data, color, kind, (x * 4 + 2) * scale, (y * 4 + 2) * scale, bc3)
        if level < tail:
            offset += pitch * (((h + 127) // 128) * 32) * block_bytes
    if offset not in (len(payload), len(payload) - tile_bytes):
        raise ValueError('Unexpected compressed payload size')
    return base_size, data


def prepare(originals, output, four_arms=None):
    actors = (
        ('l_romd/l_romd_t.xbx', 0, 0x14934253, 'watch'),
        ('l_romd/l_romd_t.xbx', 0, 0x89f54dfd, 'ben'),
        ('global/g_sf.xbx', 256, 0x9626a768, 'swampfire'),
        ('global/g_ad.xbx', 256, 0x219a9d19, 'alien'),
        ('global/g_af.xbx', 256, 0x3caac3bd, 'alien'),
        ('global/g_af.xbx', 256, 0xc633800f, 'alien'),
        ('global/g_bc.xbx', 256, 0x7cd48930, 'alien'),
        ('global/g_ec.xbx', 256, 0xc45731cc, 'alien'),
        ('global/g_hm.xbx', 256, 0x5e902eaf, 'alien'),
        ('global/g_nr.xbx', 256, 0xd7c89bea, 'alien'),
        ('global/g_ra.xbx', 256, 0x2af6d111, 'alien'),
        ('global/g_sm.xbx', 256, 0x007f04ba, 'alien'),
        ('global/g_ts.xbx', 256, 0x13b5f65c, 'terraspin_detail'),
        ('global/g_ts.xbx', 256, 0x786d334a, 'terraspin_body'),
        ('global/g_wh.xbx', 256, 0xee52dd03, 'alien'),
        ('global/g_ubc.xbx', 256, 0x3afd5b65, 'alien'),
        ('global/g_uec.xbx', 256, 0xdea70962, 'alien'),
        ('global/g_uhm.xbx', 256, 0x4a563824, 'alien'),
        ('global/g_uhm.xbx', 256, 0xf79c54ea, 'ultimate_humungousaur_skin'),
        ('global/g_usf.xbx', 256, 0x396d73cd, 'alien'),
        ('global/g_usm.xbx', 256, 0xa8e7b9b8, 'alien'),
        ('global/g_usm.xbx', 256, 0xef47c368, 'alien'),  # Face and eyes, separate from the badge.
        # Ben's Way Big keeps his stock eyes and badge when used by the boss.
        # Evil Way Big has its own red eyes and emblem in the original assets.
        ('global/global.xbx', 256, 0xc8c35802, 'menu_trim'),
        ('global/global.xbx', 256, 0xa57fdd41, 'menu_trim'),
        ('global/global.xbx', 256, 0x8f250b9a, 'menu_trim'),
        ('global/global.xbx', 256, 0xe9c69775, 'flash'),
        ('global/global.xbx', 256, 0x17dd02a0, 'flash'),
        ('global/gtex_s.xbx', 0, 0xa393f51a, 'way_big_portrait'),
        ('l_tokd/g_wayb.xbx', 256, 0xc6b6cca5, 'way_big_beam'),
        ('l_tokd/g_ewayb.xbx', 256, 0x52a1d375, 'way_big_beam'),
    )
    if four_arms is not None:
        # The Four Arms player mesh uses this diffuse atlas for its eyes
        # and chest badge. Leave its other material maps intact.
        actors += ((four_arms.resolve(), 256, 0xdc07749a, 'alien'),)
    pack = bytearray(b'ALBD\x04\x00\x00\x00')
    pack += struct.pack('<I', len(actors))
    portrait_path = Path(__file__).with_name('way_big_portrait.rgb')
    portrait = portrait_path.read_bytes()
    for archive, offset, key, kind in actors:
        record = table((originals / archive).read_bytes()[offset:])[key]
        fmt, width, height = struct.unpack_from('>HHH', record, 4)
        compression = {0x90434000: 18, 0xa0848000: 20}.get(struct.unpack_from('>I', record)[0])
        valid_format = fmt in (0x11c, 0x104) or (kind in ('menu_trim', 'way_big_portrait') and fmt == 0x102)
        if not valid_format or compression is None or any(n < 32 or n > 1024 or n & (n - 1) for n in (width,height)):
            raise ValueError(f'Unsupported Albedo texture {key:08x}')
        payload = record[128:]
        if kind == 'flash':
            # Only the transformation sprites use this unrestricted palette.
            # The 128px glow also stores a 64px mip on its second page.
            base_size = 8192
            if len(payload) not in (base_size, 2 * base_size):
                raise ValueError(f'Unexpected transformation sprite size {key:08x}')
            recolored = bytearray(payload)
            for block in range(0, len(payload), 8):
                recolor_block(recolored, block, kind, 0, 0, False)
        else:
            art = portrait if kind == 'way_big_portrait' else None
            if art is not None and (compression != 20 or len(art) != width * height * 3):
                raise ValueError('Invalid approved Way Big portrait size or compression')
            base_size, recolored = recolor_texture(payload, width, height, kind, compression == 20, art)
        if recolored == payload:
            raise ValueError(f'Albedo texture unchanged {key:08x}')
        sample = payload[base_size//4:base_size//4+64] + payload[base_size//2:base_size//2+64]
        pack += struct.pack('<IIIIIIQQQ', key, width, height, compression, base_size, len(payload) - base_size,
                            fingerprint(sample), fingerprint(payload[:base_size]),
                            fingerprint(payload[base_size:]))
        pack += recolored
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(pack)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('originals', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--four-arms', type=Path)
    args = parser.parse_args()
    prepare(args.originals, args.output, args.four_arms)
