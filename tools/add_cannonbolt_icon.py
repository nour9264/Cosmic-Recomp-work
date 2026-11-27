"""Add Cannonbolt's selection-wheel picture to global.xbx and gtex_s.xbx.

The R3 roster ring draws each alien's picture by texture key and only finds the ones resident at that time. Chromastone,
Jetray and Goop use pictures from a private folder (tools/add_wheel_icons_to_global.py); Cannonbolt keeps the picture the
importer found in Vilgax Attacks, which `prepare_vilgax_import.py cannonbolt` stores in the package's texture section.
Inputs are read, never changed: pass the original global.xbx and gtex_s.xbx and new output paths.

    python tools/add_cannonbolt_icon.py g_cb.xbx global.xbx gtex_s.xbx --out-global new/global.xbx --out-ring new/gtex_s.xbx
"""
import argparse
import struct
from pathlib import Path

from merge_alien_streams import entries
from prepare_vilgax_import import WHEEL_ICONS, bank, package, table, vaps_rows


def add_icon(texture_bank, key, texture):
    """The texture bank with `key` added; an existing `key` is left alone (returns the bank unchanged)."""
    rows = vaps_rows(texture_bank)
    records = {entry: data for entry, _, data in rows}
    assert len(records) == len(rows), 'duplicate keys in the texture bank'
    if key in records:
        return texture_bank
    records[key] = texture
    flags = {id(data): flag for _, flag, data in rows}
    flags[id(texture)] = 4
    alignment = struct.unpack_from('>H', texture_bank, 12)[0]
    return bank(0, alignment, records, lambda data: flags[id(data)])


def add_to_global(global_xbx, key, texture):
    """global.xbx with the picture in section 0, other sections and the payload order untouched."""
    sections = entries(global_xbx)
    offset = 32 + struct.unpack_from('>I', global_xbx, 44)[0]
    rows = struct.iter_unpack('>3I', global_xbx[offset:offset + 12 * len(sections)])
    order = [name for name, _, _ in sorted(rows, key=lambda row: row[2])]
    sections[0] = add_icon(sections[0], key, texture)
    return package(global_xbx, sections, order)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path, help='Cannonbolt g_cb.xbx made by prepare_vilgax_import.py')
    parser.add_argument('global_xbx', type=Path)
    parser.add_argument('gtex_s', type=Path)
    parser.add_argument('--out-global', type=Path, required=True)
    parser.add_argument('--out-ring', type=Path, required=True)
    args = parser.parse_args()
    key = WHEEL_ICONS['cannonbolt']
    texture = table(entries(args.package.read_bytes())[0])[key]
    args.out_global.write_bytes(add_to_global(args.global_xbx.read_bytes(), key, texture))
    args.out_ring.write_bytes(add_icon(args.gtex_s.read_bytes(), key, texture))
    print(f'Added Cannonbolt picture {key:08x} to {args.out_global.name} and {args.out_ring.name}.')


if __name__ == '__main__':
    main()
