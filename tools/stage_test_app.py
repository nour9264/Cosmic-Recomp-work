"""Assemble a runnable test app from a local build of this source (no git needed, nothing published).

Takes the runtime and launcher the build produced, the three bridges, the importer scripts and the bundled assets from this
checkout, and the parts that are not built here (Visual C++ runtime DLLs, the embedded Python of the importer, licenses) from an
earlier staged release folder. The result is a portable folder: run CosmicRecomp.exe, choose your ISO, Prepare game.

    python tools/stage_test_app.py --native build/native-sse41 --frontend build/launcher --bridges build/bridges \
        --support <earlier staged release folder> --output <new folder>
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTER_SCRIPTS = [
    'prepare_four_arms_import.py', 'convert_four_arms_meshes.py', 'convert_four_arms_textures.py',
    'extract_discord_level_images.py', 'extract_four_arms_skin_weights.py', 'merge_alien_streams.py',
    'prepare_all_aliens_candidate.py', 'prepare_pause_menu_extension.py', 'stage_four_arms_archive.py',
    'stage_four_arms_registration.py', 'prepare_albedo_textures.py', 'import_alien_force.py', 'import_bundled_assets.py',
    'add_cannonbolt_icon.py', 'bundle_delta.py', 'ben_model_patch.py', 'prepare_ultimate_way_big.py', 'prepare_ultimate_way_big_form.py',
    'prepare_ultimate_cannonbolt.py', 'prepare_vilgax_import.py', 'wheel_icon_texture.py', 'add_ring_pictures_to_gtex.py',
    'way_big_portrait.rgb',
]
DOCS = ['README.md', 'RELEASE_NOTES.md', 'USER_GUIDE.md', 'BUILD.md', 'SOURCES.md', 'THIRD_PARTY.md', 'LICENSE']


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ('native', 'frontend', 'bridges', 'support', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    native, frontend, bridges, support, out = (p.resolve() for p in (args.native, args.frontend, args.bridges, args.support, args.output))
    if out.exists() and any(out.iterdir()):
        raise SystemExit('Choose a new, empty output folder.')
    runtime = out / 'runtime'
    runtime.mkdir(parents=True)
    # Runtime built here, plus the C++ runtime DLLs the build links against (not built here).
    for name in ('ben10.exe', 'rexruntime.dll', 'rexgpu-xenos.dll'):
        shutil.copyfile(native / name, runtime / name)
    for dll in sorted((support / 'runtime').glob('*.dll')):
        if not (runtime / dll.name).exists():
            shutil.copyfile(dll, runtime / dll.name)
    (runtime / 'pc-menu-api.txt').write_text('7\n', encoding='ascii')
    translations = ROOT / 'native-rex' / 'translations'
    if translations.is_dir():
        (runtime / 'translations').mkdir()
        for file in translations.glob('text-*.tsv'):
            shutil.copyfile(file, runtime / 'translations' / file.name)
    names = sorted(p.name for p in runtime.iterdir() if p.is_file())
    sums = {n: hashlib.sha256((runtime / n).read_bytes()).hexdigest() for n in names}
    (runtime / 'SHA256SUMS.txt').write_text(''.join(f'{sums[n]}  {n}\n' for n in names), encoding='ascii')
    # Launcher and the three bridges.
    shutil.copyfile(frontend / 'CosmicRecomp.exe', out / 'CosmicRecomp.exe')
    for folder, name in (('std', 'CosmicBridge.exe'), ('fa', 'CosmicFourArmsBridge.exe'), ('vx', 'CosmicVilgaxBridge.exe')):
        shutil.copyfile(bridges / folder / 'CosmicBridge.exe', out / name)
    # Importer: embedded Python and its helpers from the support folder, scripts and pictures from this checkout.
    importer = out / 'four-arms-importer'
    shutil.copytree(support / 'four-arms-importer', importer, ignore=shutil.ignore_patterns('*.py', '*.rgb', '__pycache__', 'pictures'))
    for name in IMPORTER_SCRIPTS:
        source = ROOT / 'tools' / name
        if not source.is_file():
            source = ROOT / 'tools' / 'ben_ultimatrix' / name
        shutil.copyfile(source, importer / name)
    shutil.copytree(ROOT / 'tools' / 'alien-force-pictures', importer / 'pictures')
    shutil.copytree(ROOT / 'bundled-assets', out / 'bundled-assets')
    if (support / 'licenses').is_dir():
        shutil.copytree(support / 'licenses', out / 'licenses')
    for name in DOCS:
        if (ROOT / name).is_file():
            shutil.copyfile(ROOT / name, out / name)
    (out / 'TEST_BUILD.json').write_text(json.dumps({
        'built_from': 'local checkout of the Alpha 9 source (generated game code from the owner\'s local code generation)',
        'runtime_sha256': sums, 'validation': 'Local test build; not proof of gameplay'}, indent=2) + '\n', encoding='utf-8')
    print(f'Staged {sum(1 for p in out.rglob("*") if p.is_file())} files into {out}')


if __name__ == '__main__':
    main()
