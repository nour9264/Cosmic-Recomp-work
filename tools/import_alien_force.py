"""Prepare the Alien Force aliens (Chromastone, Jetray, Goop) from a locally extracted Vilgax Attacks folder.

Run by the launcher's "Import Alien Force aliens" action, the way the Four Arms import is. Every alien is built into a
temporary folder first and moved into <installation>/vilgax/<alien> only when all of them succeeded, so a failed
import leaves the installation as it was. Only the user's own files are read; no game data enters Git.
"""
import argparse
import os
import shutil
import sys
import uuid
from pathlib import Path

# The aliens' selection-wheel pictures, R3-ring pictures and holograms (art made from Vilgax Attacks renders) come with the
# importer; both modules read their folder from the environment, so it is set before they are used.
PICTURES = Path(__file__).resolve().parent / 'pictures'
if not PICTURES.is_dir():
    PICTURES = Path(__file__).resolve().parent / 'alien-force-pictures'
if PICTURES.is_dir():
    os.environ['COSMIC_WHEEL_ICON_DIR'] = str(PICTURES)
    os.environ['COSMIC_RING_PICTURES'] = str(PICTURES)

import prepare_vilgax_import as importer


def add_ring_pictures(installation):
    """Put the ring pictures and holograms into the game's picture bank (global/gtex_s.xbx), keeping a backup once."""
    if not PICTURES.is_dir():
        return
    import add_ring_pictures_to_gtex as ring
    bank = installation / 'game' / 'global' / 'gtex_s.xbx'
    backup = bank.with_name(bank.name + '.cosmic-before-alien-force')
    if not backup.exists():
        shutil.copyfile(bank, backup)
    data, _ = ring.add_pictures(PICTURES, bank.read_bytes())
    temporary = bank.with_name(bank.name + '.cosmic-new')
    temporary.write_bytes(data)
    temporary.replace(bank)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vilgax', type=Path, help='Extracted Ben 10 Alien Force: Vilgax Attacks Xbox 360 folder')
    parser.add_argument('installation', type=Path, help='Cosmic Recomp installation folder (with Four Arms imported)')
    args = parser.parse_args()
    for needed in ('global/scripts/char.ddf', 'global/gtex_s.xbx'):
        if not (args.vilgax / needed).is_file():
            sys.exit(f'This is not an extracted Vilgax Attacks folder: {needed} is missing.')
    target = args.installation / 'vilgax'
    staging = args.installation / ('vilgax-import-' + uuid.uuid4().hex)
    try:
        for name in sorted(importer.FORM_IDENTITIES):
            files, report = importer.prepare_bundle(args.vilgax, args.installation / 'game', args.installation, name)
            folder = staging / name
            folder.mkdir(parents=True)
            for file, data in files.items():
                (folder / file).write_bytes(data)
            print(name, report)
        target.mkdir(exist_ok=True)
        for name in sorted(importer.FORM_IDENTITIES):
            destination = target / name
            if destination.exists():
                shutil.move(str(destination), str(target / (name + '-previous-' + uuid.uuid4().hex[:8])))
            shutil.move(str(staging / name), str(destination))
        add_ring_pictures(args.installation)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == '__main__':
    main()
