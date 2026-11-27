"""Install the extra aliens, pictures and voices that ship with the launcher into an installation.

Run by the launcher right after the player's Xbox 360 ISO has been imported (action "install-bundled"), so nothing else has to be
supplied. Every file in bundled-assets/MANIFEST.json is checked (size and SHA-256) before anything is written. A folder that
already exists with different content is moved aside, never overwritten. The picture banks of the game are extended in place
(a backup is kept once): the Alien Force ring pictures and holograms in gtex_s.xbx, Cannonbolt's roster picture in global.xbx
and gtex_s.xbx. Ultimate Way Big is built here from the player's own Way Big files and the bundled export of the model. Running it again changes nothing.

    python import_bundled_assets.py --installation <installation> --bundle <bundled-assets> [--pictures <folder of PNGs>]
"""
import argparse
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def verify(bundle):
    manifest = json.loads((bundle / 'MANIFEST.json').read_text(encoding='utf-8'))
    entries = manifest['files']
    for entry in entries:
        path = bundle / entry['path']
        if not path.is_file() or path.stat().st_size != entry['size'] or sha256(path) != entry['sha256']:
            raise SystemExit(f"The bundled file {entry['path']} is missing or damaged; reinstall the launcher.")
    return entries


def same_tree(source, target):
    if not target.is_dir():
        return False
    names = sorted(p.name for p in source.iterdir() if p.is_file())
    return names == sorted(p.name for p in target.iterdir() if p.is_file()) and all(
        (source / n).read_bytes() == (target / n).read_bytes() for n in names)


def install_folder(source, target):
    """Copy a folder of bundled files to `target`; an existing different folder is moved aside first."""
    if same_tree(source, target):
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + '-installing-' + uuid.uuid4().hex[:8])
    shutil.copytree(source, staging)
    if target.exists():
        target.rename(target.with_name(target.name + '-previous-' + uuid.uuid4().hex[:8]))
    staging.rename(target)
    return True


def install_file(source, target):
    if target.is_file() and target.read_bytes() == source.read_bytes():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_name(target.name + '.cosmic-before-bundled')
        if not backup.exists():
            shutil.copyfile(target, backup)
    temporary = target.with_name(target.name + '.cosmic-new')
    shutil.copyfile(source, temporary)
    temporary.replace(target)
    return True


def replace_file(path, data, backup_suffix):
    backup = path.with_name(path.name + backup_suffix)
    if not backup.exists():
        shutil.copyfile(path, backup)
    temporary = path.with_name(path.name + '.cosmic-new')
    temporary.write_bytes(data)
    temporary.replace(path)


BUNDLE_FOR_WHEEL = None


def bundle_wheel_icons(pictures):
    folder = BUNDLE_FOR_WHEEL / 'pictures' / 'wheel-icons' if BUNDLE_FOR_WHEEL else None
    return folder if folder and folder.is_dir() else None


def add_pictures(installation, pictures):
    changed = []
    game = installation / 'game' / 'global'
    ring_bank = game / 'gtex_s.xbx'
    if pictures and pictures.is_dir() and ring_bank.is_file():
        import add_ring_pictures_to_gtex as ring
        blob = ring_bank.read_bytes()
        data, _ = ring.add_pictures(pictures, blob)
        if data != blob:
            replace_file(ring_bank, data, '.cosmic-before-alien-force')
            changed.append('ring pictures and holograms')
    wheel_folder = bundle_wheel_icons(pictures)
    if wheel_folder and (game / 'global.xbx').is_file():
        from add_cannonbolt_icon import add_to_global as add_record_to_global
        blob = (game / 'global.xbx').read_bytes()
        updated = blob
        for file in sorted(wheel_folder.glob('*.bin')):
            updated = add_record_to_global(updated, int(file.stem, 16), file.read_bytes())
        if updated != blob:
            replace_file(game / 'global.xbx', updated, '.cosmic-before-wheel-icons')
            changed.append('selection-wheel pictures (global.xbx)')
    if BUNDLE_FOR_WHEEL:
        from add_cannonbolt_icon import add_icon, add_to_global
        folder = BUNDLE_FOR_WHEEL / 'pictures' / 'global-records'
        if folder.is_dir() and (game / 'global.xbx').is_file():
            blob = (game / 'global.xbx').read_bytes()
            updated = blob
            for file in sorted(folder.glob('*.bin')):
                updated = add_to_global(updated, int(file.stem, 16), file.read_bytes())
            if updated != blob:
                replace_file(game / 'global.xbx', updated, '.cosmic-before-ucb-sprites')
                changed.append('Ultimate Cannonbolt effect sprites (global.xbx)')
        folder = BUNDLE_FOR_WHEEL / 'pictures' / 'gtex-records'
        if folder.is_dir() and ring_bank.is_file():
            blob = ring_bank.read_bytes()
            updated = blob
            for file in sorted(folder.glob('*.bin')):
                updated = add_icon(updated, int(file.stem, 16), file.read_bytes())
            if updated != blob:
                replace_file(ring_bank, updated, '.cosmic-before-ucb-pictures')
                changed.append('Ultimate Cannonbolt picture (gtex_s.xbx)')
    package = installation / 'vilgax' / 'cannonbolt' / 'g_cb.xbx'
    if package.is_file() and ring_bank.is_file() and (game / 'global.xbx').is_file():
        import prepare_vilgax_import as importer
        from add_cannonbolt_icon import add_icon, add_to_global
        from merge_alien_streams import entries
        key = importer.WHEEL_ICONS['cannonbolt']
        texture = importer.table(entries(package.read_bytes())[0])[key]
        global_blob, ring_blob = (game / 'global.xbx').read_bytes(), ring_bank.read_bytes()
        new_global, new_ring = add_to_global(global_blob, key, texture), add_icon(ring_blob, key, texture)
        if new_global != global_blob:
            replace_file(game / 'global.xbx', new_global, '.cosmic-before-cannonbolt')
            changed.append("Cannonbolt's roster picture (global.xbx)")
        if new_ring != ring_blob:
            replace_file(ring_bank, new_ring, '.cosmic-before-cannonbolt-ring')
            changed.append("Cannonbolt's roster picture (gtex_s.xbx)")
    return changed


def install_ben_additions(installation, bundle):
    """Ben's new Ultimatrix and the added animation clips, applied to the player's own untouched game files."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'ben_ultimatrix'))   # in the source tree; the launcher ships it beside this script
    import bundle_delta
    import ben_model_patch
    game = installation / 'game'
    done = []
    model = bundle / 'ben-model'
    if model.is_dir():
        levels = ben_model_patch.apply_all(game, model)
        if levels:
            done.append("Ben's new Ultimatrix (" + str(len(levels)) + ' levels)')
    deltas = bundle / 'deltas'
    for file in sorted(deltas.glob('*.cdelta')) if deltas.is_dir() else []:
        target = game / file.name[:-len('.cdelta')].replace('__', '/')
        if not target.is_file():
            continue
        patch = file.read_bytes()
        source_hash, result_hash = bundle_delta.digests(patch)
        current = hashlib.sha256(target.read_bytes()).hexdigest()
        if current == result_hash:
            continue
        if current != source_hash:
            print('Skipped ' + target.name + ': it is not the original file this addition was made for.', file=sys.stderr)
            continue
        replace_file(target, bundle_delta.apply(target.read_bytes(), patch), '.cosmic-before-ben-additions')
        done.append('additions to ' + target.name)
    entries = bundle / 'albedo'
    if entries.is_dir():
        target = installation / 'albedo-entries'
        new = False
        for file in sorted(entries.glob('*.entry')):
            new = install_file(file, target / file.name) or new
        pack = installation / 'user' / 'albedo-textures.bin'
        if new and pack.is_file():
            pack.unlink()   # rebuilt on the next start with the new Ultimatrix look
        if new:
            done.append('Albedo look of the new Ultimatrix')
    return done


def build_ultimate_way_big(installation, bundle):
    """Ultimate Way Big is built from the player's own Way Big files (game/l_tokd) and the bundled export of the model.

    Runs at import time, while the game folder is still the untouched copy of the ISO. Returns True when it built the form.
    """
    import subprocess
    target = installation / 'vilgax' / 'ultimatewaybig'
    export = bundle / 'ultimate-way-big-export'
    voice = bundle / 'user' / 'Ultimate_Way_Big_Clean.wav'
    game = installation / 'game'
    if (target / 'g_uwb.xbx').is_file() or not export.is_dir() or not voice.is_file() or not (game / 'l_tokd' / 'l_tokd_m.xbx').is_file():
        return False
    here = Path(__file__).resolve().parent
    work = installation / ('ultimate-way-big-' + uuid.uuid4().hex[:8])
    try:
        for command in ([sys.executable, '-B', str(here / 'prepare_ultimate_way_big.py'), '--level', str(game / 'l_tokd'),
                         '--assets', str(export), '--output', str(work / 'prepared'), '--voice', str(voice)],
                        [sys.executable, '-B', str(here / 'prepare_ultimate_way_big_form.py'), '--originals', str(game),
                         '--prepared', str(work / 'prepared'), '--output', str(work / 'bundle')]):
            done = subprocess.run(command, capture_output=True, text=True, cwd=str(here))
            if done.returncode:
                raise SystemExit('Ultimate Way Big could not be built from your game files: ' + (done.stderr.strip().splitlines() or ['unknown error'])[-1])
        install_folder(work / 'bundle', target)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--pictures', type=Path, help='folder with <alien>_ring.png and <alien>_holo.png (default: next to this script)')
    args = parser.parse_args()
    installation, bundle = args.installation, args.bundle
    if not (installation / 'game').is_dir():
        raise SystemExit('Prepare your Xbox 360 game first.')
    here = Path(__file__).resolve().parent
    pictures = args.pictures or next((p for p in (here / 'pictures', here / 'alien-force-pictures') if p.is_dir()), None)
    verify(bundle)
    global BUNDLE_FOR_WHEEL
    BUNDLE_FOR_WHEEL = bundle
    done = []
    for folder in ('four-arms', 'vilgax/chromastone', 'vilgax/jetray', 'vilgax/goop', 'vilgax/cannonbolt', 'vilgax/ultimatecannonbolt'):
        if install_folder(bundle / folder, installation / folder):
            done.append(folder)
    for file in sorted((bundle / 'user').iterdir()):
        if install_file(file, installation / 'user' / file.name):
            done.append('user/' + file.name)
    done += add_pictures(installation, pictures)
    done += install_ben_additions(installation, bundle)
    if build_ultimate_way_big(installation, bundle):
        done.append('vilgax/ultimatewaybig (built from your Way Big files)')
    print('Installed:', ', '.join(done) if done else 'nothing to do (already installed)')


if __name__ == '__main__':
    sys.exit(main())
