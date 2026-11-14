"""Add the imported aliens' selection-wheel pictures to global.xbx.

The R3 roster ring draws every alien's picture by texture key and only finds the
ones resident at that time. Four Arms' picture lives in global.xbx; the imported
aliens' pictures live in their own packages, which are not loaded on that screen
(the ring then shows Four Arms' picture). This adds them to global.xbx's texture
bank, next to Four Arms'. The pictures come from a private folder of 128x128 PNGs
(<alien>.png), which is not committed."""
import argparse
from pathlib import Path
import struct

import prepare_vilgax_import as importer
from extract_discord_level_images import table
from wheel_icon_texture import icon_texture

FOUR_ARMS_ICON = 0xbc29c46d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vilgax', type=Path, help='Extracted Vilgax Attacks Xbox 360 folder')
    parser.add_argument('icons', type=Path, help='Folder with chromastone.png, jetray.png, goop.png')
    parser.add_argument('source', type=Path, help='global.xbx to read')
    parser.add_argument('output', type=Path, help='global.xbx to write')
    args = parser.parse_args()
    blob = args.source.read_bytes()
    sections = importer.entries(blob)
    textures = sections[0]
    records = dict(table(textures))
    directory = 32 + struct.unpack_from('>I', textures, 44)[0]
    flags = {}
    for index in range(len(records)):
        key, info, _ = struct.unpack_from('>III', textures, directory + 12 * index)
        flags[key] = info >> 24
    gtex = importer.entries((args.vilgax / 'global/gtex_s.xbx').read_bytes(), True)
    added = []
    for name, key in importer.WHEEL_ICONS.items():
        picture = args.icons / f'{name}.png'
        if not picture.exists():
            continue
        header = importer.convert_texture(gtex[key])[:128]
        records[key] = icon_texture(picture, header)
        flags[key] = flags[FOUR_ARMS_ICON]
        added.append(name)
    if not added:
        raise SystemExit('No wheel pictures found in ' + str(args.icons))
    by_record = {id(record): flags[key] for key, record in records.items()}
    section = importer.bank(0, struct.unpack_from('>H', textures, 12)[0], records, lambda record: by_record[id(record)])
    sections[0] = section
    args.output.write_bytes(importer.package(blob, sections))
    print('Added', ', '.join(added))


if __name__ == '__main__':
    main()
