"""Prepare a private Four Arms bundle from an extracted European PS3_GAME folder."""

import argparse
from pathlib import Path
import subprocess
import tempfile

from convert_four_arms_meshes import convert_mesh_bank
from convert_four_arms_textures import convert_bank
from extract_discord_level_images import table
from merge_alien_streams import entries
from stage_four_arms_archive import convert_skin_bank, read_ps3_donor, replace_sections
from stage_four_arms_registration import initialize_probe_upgrades, registration
from prepare_pause_menu_extension import records


def prepare(ps3_game, xbox_game, decoder, output):
    files = read_ps3_donor(ps3_game)
    donor = files['g_fa.ps3']
    sections = entries(donor)
    global_dir = xbox_game / 'global'
    scripts = global_dir / 'scripts'
    xbox_mesh = entries((global_dir / 'g_hm.xbx').read_bytes())[4]
    xbox_skin = entries((global_dir / 'g_ra.xbx').read_bytes())[22]
    mesh_reference = next(iter(table(xbox_mesh).values()))
    archive = replace_sections(donor, {
        0: convert_bank(sections[0]),
        4: convert_mesh_bank(sections[4], mesh_reference),
        22: convert_skin_bank(sections[22], sections[4], xbox_skin),
    })
    globals_code = next(code for key, _, code in records((scripts / 'globals.ds').read_bytes())
                        if key == 0x5b258dcd)
    upgrade_initializer = initialize_probe_upgrades(globals_code)

    output = output.resolve()
    if output.exists():
        raise FileExistsError(f'Choose a new output directory: {output}')
    with tempfile.TemporaryDirectory(prefix='four-arms-import-', dir=output.parent) as temporary:
        work = Path(temporary)
        encrypted = work / 'gld_ps3.ds.sdat'
        decoded = work / 'gld_ps3.ds'
        encrypted.write_bytes(files['scripts/gld_ps3.ds.sdat'])
        subprocess.run([str(decoder.resolve()), '-d', str(encrypted), str(decoded), '0'],
                       cwd=work, check=True)
        ps3_script = decoded.read_bytes()
        if len(ps3_script) != 33232 or ps3_script[:4] != b'\x1b\xad\xba\xbe':
            raise ValueError('PS3 script decoder did not produce the verified script layout')
        platform_script = registration((scripts / 'gld_xbx.ds').read_bytes(), ps3_script)
        bundle = work / 'bundle'
        bundle.mkdir()
        (bundle / 'g_fa.xbx').write_bytes(archive)
        (bundle / 'atk_fa.ddf').write_bytes(files['scripts/atk_fa.ddf'])
        (bundle / 'four-arms-registration.bin').write_bytes(platform_script)
        (bundle / 'four-arms-upgrade-init.bin').write_bytes(upgrade_initializer)
        bundle.rename(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ps3_game', type=Path)
    parser.add_argument('xbox_game', type=Path, help='Extracted Xbox 360 game folder')
    parser.add_argument('decoder', type=Path, help='Path to the locally built make_npdata executable')
    parser.add_argument('output', type=Path, help='New private output directory')
    args = parser.parse_args()
    prepare(args.ps3_game, args.xbox_game, args.decoder, args.output)
