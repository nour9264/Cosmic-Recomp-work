"""Build a private Xbox-compatible pack of original PlayStation face icons."""

import argparse
import io
from pathlib import Path
import struct

from extract_discord_level_images import table, tiled_offset
from prepare_albedo_textures import fingerprint


# The Xbox bank has separate variants for HUD, tutorial and menu use.
FACE_ICONS = (
    (0x32A453D7, (0xD82646FD, 0x5556421E, 0xD155D06F, 0x5E1525CF, 0x96F5AABF, 0xEC35F9DF)),
    (0x70C9D4C7, (0x56A9411E, 0x5FDAD78C, 0xDBD945FD, 0x187AAD5C, 0xD09A222C)),
    (0xB57415BF, (0xBBD26CFD, 0xF50180BF, 0x36A2681E, 0x8FC1D3DF, 0x3DE10FCF, 0xB2A1FA6F)),
    (0x836A170F, (0xFA086880, 0x39AB8021, 0xF14B0F51, 0x7E0BFAF1, 0x62BAFE3C, 0x436BD341, 0x77786C63)),
)
PAGE = 16384
ROUND_ICONS = (
    (0x927F8AEA, (0x10FBCFF1,)),
    (0xD5DFF03A, (0x9FBB3A51,)),
    (0xE8BFD98A, (0x2D9BE641,)),
    (0x5A9F059A, (0x575BB521,)),
)


def retile(record):
    magic, fmt, width, height = struct.unpack_from('>IHHH', record)
    if (magic, fmt) != (0xA0848000, 0x102) or width != height or width not in (64, 128) or len(record) != 128 + width * width * 5 // 4:
        raise ValueError('Unexpected PlayStation button texture layout')
    output = bytearray(PAGE * 2)
    offset = 128
    for level in range(2):
        blocks = width >> (level + 2)
        page = 0 if level == 0 else PAGE
        for y in range(blocks):
            for x in range(blocks):
                target = page + tiled_offset(x, y, 32, 4)
                block = record[offset:offset + 16]
                output[target:target + 16:2] = block[1::2]
                output[target + 1:target + 16:2] = block[::2]
                offset += 16
    if offset != len(record):
        raise ValueError('Unexpected PlayStation mip data size')
    return output


def keyboard_keycap(label, width, shoulder=False, tutorial=False):
    from PIL import Image, ImageDraw, ImageFont

    icon = Image.new('RGBA', (64, 64))
    draw = ImageDraw.Draw(icon)
    if tutorial:
        draw.rounded_rectangle((1, 4, 62, 59), radius=8, fill='#f5f5f5',
                               outline='#131820', width=2)
        for size in range(44, 11, -1):
            font = ImageFont.load_default(size=size)
            if draw.textlength(label, font=font) <= 53:
                break
        draw.text((32, 31), label, anchor='mm', font=font,
                  fill='#101820', stroke_width=1)
    elif shoulder:
        background, lettering = ('#000000', '#ffffff') if label == 'L1' else ('#eeeeee', '#101820')
        draw.rounded_rectangle((2, 6, 61, 57), radius=11, fill=background,
                               outline='#ffffff', width=2)
        draw.text((32, 31), label, anchor='mm', fill=lettering, stroke_width=1,
                  font_size=33)
    else:
        draw.rounded_rectangle((3, 13, 60, 49), radius=7, fill='#222831',
                               outline='#ffffff', width=3)
        draw.text((32, 31), label, anchor='mm', fill='white',
                  font_size=15 if len(label) > 1 else 26)
    return encode_icon(icon, width)


def encode_icon(icon, width):
    from PIL import Image

    levels = bytearray(b'\0' * 128)
    for side in (width, width // 2):
        buffer = io.BytesIO()
        icon.resize((side, side), Image.Resampling.LANCZOS).save(
            buffer, format='DDS', pixel_format='DXT5')
        data = buffer.getvalue()
        if data[84:88] != b'DXT5' or len(data) != 128 + side * side:
            raise ValueError('Could not encode the keyboard keycap')
        levels += data[128:]
    struct.pack_into('>IHHH', levels, 0, 0xA0848000, 0x102, width, width)
    return retile(levels)


def default_face_icon(shape):
    from PIL import Image, ImageDraw

    icon = Image.new('RGBA', (128, 128))
    draw = ImageDraw.Draw(icon)
    draw.ellipse((8, 8, 119, 119), fill='#171b23', outline='#c6cbd3', width=4)
    if shape == 'cross':
        draw.line((45, 45, 83, 83), fill='#a9bdff', width=8)
        draw.line((83, 45, 45, 83), fill='#a9bdff', width=8)
    elif shape == 'square':
        draw.rectangle((44, 44, 84, 84), outline='#efa4cb', width=7)
    elif shape == 'triangle':
        draw.line(((64, 39), (89, 84), (39, 84), (64, 39)), fill='#86e0b5', width=7, joint='curve')
    elif shape == 'circle':
        draw.ellipse((42, 42, 86, 86), outline='#ff9f9f', width=7)
    return encode_icon(icon, 128)[:PAGE]


def prepare(xbox_bank, ps3_bank, keyboard=False):
    xbox = table(xbox_bank.read_bytes())
    ps3 = table(ps3_bank.read_bytes())
    payload = bytearray(b'ALBD\x02\x00\x00\x00')
    icons = FACE_ICONS + ROUND_ICONS
    payload += struct.pack('<I', sum(len(keys) for _, keys in icons))
    for label, (donor, keys) in zip(('SPACE', 'BKSP', 'L', 'P') * 2, icons):
        width = struct.unpack_from('>H', ps3[donor], 6)[0]
        replacement = keyboard_keycap(label, width) if keyboard else retile(ps3[donor])
        for key in keys:
            record = xbox[key]
            if struct.unpack_from('>IHHH', record) != (0xA0848000, 0x102, width, width) or len(record) != 128 + 2 * PAGE:
                raise ValueError(f'Unexpected Xbox button texture layout: {key:08x}')
            base, mip = record[128:128 + PAGE], record[128 + PAGE:]
            blocks = width // 4
            def block_at(x, y):
                offset = tiled_offset(x, y, 32, 4)
                return base[offset:offset + 16]
            active = b''.join(block_at(x, y) for y in range(blocks) for x in range(blocks))
            signature = fingerprint(block_at(blocks // 2, blocks // 2) +
                                    block_at(blocks // 2, blocks // 2 - 2))
            payload += struct.pack('<6I3Q', key, width, width, 20, PAGE, PAGE, signature,
                                   fingerprint(active), fingerprint(mip))
            payload += replacement
    return payload


def prepare_prompt_sprites(ps3_bank=None):
    # The game's prompt codes 1–4 mean A, X, Y, B.
    prompt_order = (0x927F8AEA, 0xE8BFD98A, 0x5A9F059A, 0xD5DFF03A)
    if ps3_bank is None:
        sprites = [default_face_icon(shape) for shape in ('cross', 'square', 'triangle', 'circle')]
    else:
        ps3 = table(ps3_bank.read_bytes())
        sprites = [retile(ps3[donor])[:PAGE] for donor in prompt_order]
    labels = ('L1', '1', 'L2', 'Q', 'R2', 'E', 'R3', 'K',
              'SPACE', 'BKSP', 'L', 'P')
    sprites.extend(keyboard_keycap(label, 128, shoulder=len(label) < 3,
                                  tutorial=index >= 8)[:PAGE]
                   for index, label in enumerate(labels))
    return b'PSIC\x03\0\0\0' + b''.join(sprites)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xbox_bank', type=Path, nargs='?')
    parser.add_argument('ps3_bank', type=Path, nargs='?')
    parser.add_argument('output', type=Path, nargs='?')
    parser.add_argument('--default-prompt-sprites', type=Path, metavar='OUTPUT')
    parser.add_argument('--keyboard', action='store_true')
    parser.add_argument('--prompt-sprites', action='store_true')
    args = parser.parse_args()
    if args.default_prompt_sprites:
        args.default_prompt_sprites.write_bytes(prepare_prompt_sprites())
    else:
        if not (args.xbox_bank and args.ps3_bank and args.output):
            parser.error('Supply Xbox bank, PS3 bank and output, or use --default-prompt-sprites')
        data = (prepare_prompt_sprites(args.ps3_bank) if args.prompt_sprites
                else prepare(args.xbox_bank, args.ps3_bank, args.keyboard))
        args.output.write_bytes(data)
