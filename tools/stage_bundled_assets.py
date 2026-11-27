"""Collect the prepared extra aliens, pictures and voices from a finished installation into bundled-assets/.

The launcher's import step copies bundled-assets/ into a new installation (tools/import_bundled_assets.py), so players need
only their Xbox 360 ISO. This tool is run by the repository owner when the content changes; it reads one installation and
writes the folder plus MANIFEST.json (size, SHA-256 and origin of every file). Nothing is deleted or changed in the source.

    python tools/stage_bundled_assets.py --installation <installation> [--out bundled-assets] [--ultimate-way-big-export <folder>]
"""
import argparse
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

ORIGINS = {
    'four-arms': 'PS3 edition (Four Arms), prepared by prepare_four_arms_import.py',
    'vilgax/chromastone': 'Ben 10: Alien Force - Vilgax Attacks (Xbox 360), prepared by prepare_vilgax_import.py',
    'vilgax/jetray': 'Ben 10: Alien Force - Vilgax Attacks (Xbox 360), prepared by prepare_vilgax_import.py',
    'vilgax/goop': 'Ben 10: Alien Force - Vilgax Attacks (Xbox 360), prepared by prepare_vilgax_import.py',
    'vilgax/cannonbolt': 'Ben 10: Alien Force - Vilgax Attacks (Xbox 360), finished by tools/cannonbolt',
    'vilgax/ultimatecannonbolt': "owner's Blender model; Protector of the Earth (PS2) effects and audio; finished by tools/cannonbolt",
    'user/upgrade-portraits.rgba': 'upgrade menu pictures (rendered from game and owner models)',
    'user/master-control-portrait.rgba': 'upgrade menu picture',
    'user/cosmetic-previews.rgba': "cosmetic pictures made from the owner's reference images",
    'user/hud-upgrade-frames.rgba': 'upgrade HUD frame art',
    'user/options-ultimatrix-hd.rgba': "the game's Ultimatrix picture, upscaled by the owner",
    'user/ben-transform-select.wav': "Ben's transformation select sound from Vilgax Attacks (Xbox 360)",
    'user/Ultimate_Way_Big_Clean.wav': 'Ultimate Way Big transformation voice (supplied by the owner)',
}
# The Ultimate Cannonbolt transformation voice travels inside vilgax/ultimatecannonbolt (transform.wav, callout.fsb).
FOLDERS = ['four-arms', 'vilgax/chromastone', 'vilgax/jetray', 'vilgax/goop', 'vilgax/cannonbolt', 'vilgax/ultimatecannonbolt']
FILES = [k for k in ORIGINS if k.startswith('user/')]


sys.path.insert(0, str(Path(__file__).resolve().parent))


DELTA_FILES = ['global/a_plyr.xbx', 'global/g_bc.xbx', 'global/g_ec.xbx', 'global/g_hm.xbx', 'global/g_sf.xbx', 'global/g_sm.xbx',
               'l_tokd/g_wayb.xbx',
               # the Ultimates' interact clips (tools/interact/install_interact_clips.py)
               'global/g_ubc.xbx', 'global/g_uec.xbx', 'global/g_uhm.xbx', 'global/g_usf.xbx', 'global/g_usm.xbx']
BEN_TEXTURE = 0x14934253
GLOBAL_SPRITES = [0x0b645fdf, 0x32295b91, 0x5e246511, 0x89556671, 0xc72d34ab, 0xd4ec60ee]   # records added to global.xbx
GTEX_RECORDS = [0x76757ac1]                                                                # record added to gtex_s.xbx


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('bundled-assets'))
    parser.add_argument('--originals', type=Path, help='the untouched game folder (extracted ISO); needed for the Ben additions')
    parser.add_argument('--ultimate-way-big-export', type=Path,
                        help="the owner's Ultimate Way Big export folder (mesh-export.bin, textures); kept for the later import step")
    args = parser.parse_args()
    source, out = args.installation, args.out
    plan = []
    for folder in FOLDERS:
        for file in sorted((source / folder).iterdir()):
            if file.is_file():
                plan.append((f'{folder}/{file.name}', file, ORIGINS[folder]))
    for relative in FILES:
        plan.append((relative, source / relative, ORIGINS[relative]))
    if args.ultimate_way_big_export:
        for file in sorted(args.ultimate_way_big_export.iterdir()):
            if file.is_file():
                plan.append((f'ultimate-way-big-export/{file.name}', file, "owner's Blender export of Ultimate Way Big (mesh, textures)"))
    # The selection-wheel pictures of Chromastone, Jetray and Goop are records inside the game's global.xbx; take the finished ones.
    from merge_alien_streams import entries
    import prepare_vilgax_import as importer
    wheel = importer.table(entries((source / 'game/global/global.xbx').read_bytes())[0])
    wheel_dir = out / 'pictures' / 'wheel-icons'
    wheel_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    for name in ('chromastone', 'jetray', 'goop'):
        key = importer.WHEEL_ICONS[name]
        (wheel_dir / f'{key:08x}.bin').write_bytes(wheel[key])
        extracted.append((f'pictures/wheel-icons/{key:08x}.bin', wheel_dir / f'{key:08x}.bin', f'selection-wheel picture of {name} (owner-made art)'))
    plan += extracted
    # Ultimate Cannonbolt's rock, dust and funnel sprites live in the game's own picture banks (tools/cannonbolt/global_vfx_sprites.py
    # and the Ultimate Cannonbolt picture); without them the effect draws as black blocks.
    gtex = importer.table((source / 'game/global/gtex_s.xbx').read_bytes())
    for folder, records, keys in (('global-records', wheel, GLOBAL_SPRITES), ('gtex-records', gtex, GTEX_RECORDS)):
        (out / 'pictures' / folder).mkdir(parents=True, exist_ok=True)
        for key in keys:
            path = out / 'pictures' / folder / f'{key:08x}.bin'
            path.write_bytes(records[key])
            plan.append((f'pictures/{folder}/{key:08x}.bin', path, 'Ultimate Cannonbolt effect sprite or picture (rubble, dust, wind funnel), prepared by tools/cannonbolt'))
    if args.originals:
        import bundle_delta
        sys.path.insert(0, str(Path(__file__).resolve().parent / 'ben_ultimatrix'))
        import ben_model_patch
        ben_out = out / 'ben-model'
        ben_model_patch.extract(source / 'game' / 'l_mili', ben_out)
        for file in sorted(ben_out.iterdir()):
            plan.append((f'ben-model/{file.name}', file, "owner's Ben Ultimatrix model data (new mesh and texture)"))
        (out / 'deltas').mkdir(parents=True, exist_ok=True)
        for relative in DELTA_FILES:
            patch = bundle_delta.make((args.originals / relative).read_bytes(), (source / 'game' / relative).read_bytes())
            name = relative.replace('/', '__') + '.cdelta'
            (out / 'deltas' / name).write_bytes(patch)
            plan.append((f'deltas/{name}', out / 'deltas' / name, "additions to the game's own file (chest-tap clips, Ben's transformation), stored as a patch"))
        pack = (source / 'user' / 'albedo-textures.bin').read_bytes()
        at, count = 12, struct.unpack_from('<I', pack, 8)[0]
        for _ in range(count):
            key, width, height, fmt, base, mip = struct.unpack_from('<IIIIII', pack, at)
            size = 48 + base + mip
            if key in (BEN_TEXTURE, *GTEX_RECORDS):
                (out / 'albedo').mkdir(parents=True, exist_ok=True)
                (out / 'albedo' / f'{key:08x}.entry').write_bytes(pack[at:at + size])
                plan.append((f'albedo/{key:08x}.entry', out / 'albedo' / f'{key:08x}.entry', 'Albedo (red) look of the new Ultimatrix texture'))
            at += size
    missing = [relative for relative, file, _ in plan if not file.is_file()]
    if missing:
        raise SystemExit('Missing in the installation: ' + ', '.join(missing))
    entries = []
    for relative, file, origin in plan:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if file.resolve() != target.resolve():
            shutil.copy2(file, target)
        entries.append({'path': relative, 'size': target.stat().st_size, 'sha256': sha256(target), 'origin': origin})
    (out / 'MANIFEST.json').write_text(json.dumps({'version': 1, 'files': entries}, indent=1) + '\n', encoding='utf-8')
    print(f'Staged {len(entries)} files, {sum(e["size"] for e in entries) / 1048576:.1f} MB, into {out}')


if __name__ == '__main__':
    main()
