"""Add the imported aliens' R3-ring pictures to gtex_s.xbx.

The R3 roster ring draws each alien's picture from the form record's field
1f380178 (Four Arms' is the 256x256 texture c6baa5e5 in gtex_s.xbx). The imported
forms were registered with Four Arms' value, so the ring showed Four Arms. These
pictures (<alien>_ring.png, 256x256, from a private folder) are added next to it
under keys the registration now names. The ring's centre hologram (<alien>_holo.png, 256x256)
is added the same way; its key is returned by the form's own hologram function."""
import argparse
from pathlib import Path
import struct

import prepare_vilgax_import as importer
from extract_discord_level_images import table
from wheel_icon_texture import icon_texture

FOUR_ARMS_RING = 0xc6baa5e5
FOUR_ARMS_HOLOGRAM = 0x462e4988  # Four Arms' 512x512 hologram


def ring_key(name):
    return importer.crc(f'Cosmic_{name}_ring')


def hologram_key(name):
    return importer.crc(f'Cosmic_{name}_holo')


def add_pictures(icons, blob):
    """gtex_s.xbx bytes with the aliens' ring pictures and holograms (from the PNGs in `icons`) added; (bytes, names)."""
    records = dict(table(blob))
    directory = 32 + struct.unpack_from('>I', blob, 44)[0]
    flags = {}
    for index in range(len(records)):
        key, info, _ = struct.unpack_from('>III', blob, directory + 12 * index)
        flags[key] = info >> 24
    header = bytearray(records[FOUR_ARMS_RING][:128])
    struct.pack_into('>I', header, 28, 1)  # Base level only.
    added = []
    for name in importer.WHEEL_ICONS:
        picture = icons / f'{name}_ring.png'
        if picture.exists():
            records[ring_key(name)] = icon_texture(picture, bytes(header), 256)
            flags[ring_key(name)] = flags[FOUR_ARMS_RING]
            added.append(name)
    holo_header = bytearray(records[FOUR_ARMS_RING][:128])
    struct.pack_into('>I', holo_header, 28, 1)
    for name in importer.WHEEL_ICONS:
        picture = icons / f'{name}_holo.png'
        if picture.exists():
            records[hologram_key(name)] = icon_texture(picture, bytes(holo_header), 256)
            flags[hologram_key(name)] = flags[FOUR_ARMS_HOLOGRAM]
            added.append(name + ' hologram')
    if not added:
        raise SystemExit('No ring pictures found')
    by_record = {id(record): flags[key] for key, record in records.items()}
    align, section_id = struct.unpack_from('>H', blob, 12)[0], struct.unpack_from('>I', blob, 24)[0]
    return importer.bank(section_id, align, records, lambda record: by_record[id(record)]), added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('icons', type=Path)
    parser.add_argument('source', type=Path, help='gtex_s.xbx to read')
    parser.add_argument('output', type=Path, help='gtex_s.xbx to write')
    args = parser.parse_args()
    data, added = add_pictures(args.icons, args.source.read_bytes())
    args.output.write_bytes(data)
    print('Added', ', '.join(added))


if __name__ == '__main__':
    main()
