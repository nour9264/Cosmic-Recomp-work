"""Refresh local Alien Force roster and R3 pictures without rebuilding their forms."""
import argparse
from pathlib import Path
import struct

from add_ring_pictures_to_gtex import hologram_key, ring_key
from merge_alien_streams import entries
from prepare_albedo_textures import fingerprint, recolor_texture
from prepare_vilgax_import import ALIENS, WHEEL_ICONS, vaps_rows
from wheel_icon_texture import icon_texture


FORMS = ('chromastone', 'jetray', 'goop')


def spans(blob, *, section=False):
    base, = struct.unpack_from('>I', blob, 28)
    count, directory = struct.unpack_from('>I4xI', blob, 36)
    for key, info, offset in struct.iter_unpack('>III', blob[32+directory:32+directory+count*12]):
        length = info if section else info & 0xffffff
        yield key, slice(base + offset, base + offset + length)


def replace_pictures(blob, pictures):
    updated = bytearray(blob)
    locations = dict(spans(blob))
    for key, (png, size) in pictures.items():
        at = locations[key]
        old = blob[at]
        if struct.unpack_from('>IHHHI', old)[:4] != (0xa0848000, 0x102, size, size):
            raise ValueError(f'Unexpected picture format for {key:08x}')
        replacement = icon_texture(png, old[:128], size)
        if len(replacement) != len(old):
            raise ValueError(f'Picture {key:08x} would move other archive records')
        updated[at] = replacement
    return bytes(updated)


def refresh_hologram_pack(pack, textures):
    if pack[:8] != b'ALBD\x04\0\0\0':
        raise ValueError('Expected the installed Albedo texture pack format')
    count, = struct.unpack_from('<I', pack, 8)
    output = bytearray(pack[:12])
    row = struct.Struct('<IIIIIIQQQ')
    offset = 12
    remaining = set(textures)
    for _ in range(count):
        key, width, height, fmt, base, mip, *_ = row.unpack_from(pack, offset)
        end = offset + row.size + base + mip
        if key not in remaining:
            output.extend(pack[offset:end])
        else:
            if (width, height, fmt, mip) != (256, 256, 20, 0):
                raise ValueError(f'Unexpected Albedo hologram dimensions for {key:08x}')
            source = textures[key][128:]
            size, red = recolor_texture(source, width, height, 'hologram', True)
            if size != base or len(source) != base or source == red:
                raise ValueError(f'Invalid Albedo hologram for {key:08x}')
            sample = source[base//4:base//4+64] + source[base//2:base//2+64]
            output += row.pack(key, width, height, fmt, base, mip,
                               fingerprint(sample), fingerprint(source), fingerprint(b''))
            output += red
            remaining.remove(key)
        offset = end
    if remaining or offset != len(pack):
        raise ValueError('Missing holograms or trailing Albedo pack data')
    return bytes(output)


def prepare(installation, pictures, output):
    updates = {}
    for name in FORMS:
        filename = f'g_{ALIENS[name]}.xbx'
        relative = Path('vilgax') / name / filename
        blob = (installation / relative).read_bytes()
        at = dict(spans(blob, section=True))[0]
        section = replace_pictures(blob[at], {WHEEL_ICONS[name]: (pictures/f'{name}.png', 128)})
        updated = blob[:at.start] + section + blob[at.stop:]
        before, after = entries(blob), entries(updated)
        if any(before[k] != after[k] for k in before if k != 0):
            raise ValueError(f'{filename} changed outside its texture section')
        updates[relative] = updated
        updates[Path('game/global') / filename] = updated

    bank = Path('game/global/gtex_s.xbx')
    ring_pictures = {ring_key(name): (pictures/f'{name}_ring.png', 256) for name in FORMS}
    ring_pictures.update({hologram_key(name): (pictures/f'{name}_holo.png', 256) for name in FORMS})
    updates[bank] = replace_pictures((installation / bank).read_bytes(), ring_pictures)
    keys = {hologram_key(name) for name in FORMS}
    holograms = {key: data for key, _, data in vaps_rows(updates[bank]) if key in keys}
    pack = Path('user/albedo-textures.bin')
    updates[pack] = refresh_hologram_pack((installation / pack).read_bytes(), holograms)
    for relative, data in updates.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installation', type=Path)
    parser.add_argument('pictures', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    prepare(args.installation, args.pictures, args.output)
