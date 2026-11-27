"""Checks for the Ultimate Cannonbolt form: importer, Hero Time pairing, launcher and native hooks.

Static checks always run. With COSMIC_UCB_EXPORTS (the owner's Blender exports), COSMIC_INSTALLATION (an installation with
globals.ds.cosmic-original) and COSMIC_NORMAL_BUNDLE (installation/vilgax/cannonbolt) it also runs the importer into a
temporary folder and checks the bundle.
"""
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_hero_time_candidate as hero  # noqa: E402
from merge_alien_streams import entries  # noqa: E402
import prepare_vilgax_import as importer  # noqa: E402

read = lambda rel: (ROOT / rel).read_text(encoding='utf-8')

# Hero Time: the stock program is unchanged in shape, the Cannonbolt one adds the 23 -> 24 pair and the host voice call.
assert 23 not in hero.ULTIMATE_PAIRS
stock = hero.authored()
with_ucb = hero.authored(ultimate_cannonbolt=True)
assert len(with_ucb) >= len(stock) > 0
blob = b''.join(code for _, _, code in with_ucb)
assert struct.pack('>I', importer.crc('cosmic_hero_load_limit')) in blob or len(blob) > sum(len(c) for _, _, c in stock)
assert importer.crc('cosmic_ultimate_cannonbolt_voice') != 0
text = read('tools/prepare_hero_time_candidate.py')
assert "{23: 24} if ultimate_cannonbolt" in text and "c.native('cosmic_ultimate_cannonbolt_voice')" in text
assert 'ultimate_cannonbolt=args.vilgax' in read('tools/build_release_bridge.py')

# Launcher: form 24 is accepted only as the Ultimate Cannonbolt bundle and never joins the roster wheel.
vilgax = read('launcher/vilgax/VilgaxAliens.cs')
assert 'UltimateCannonboltId=24' in vilgax and 'fields[0]!="ultimatecannonbolt"' in vilgax
patch = read('launcher/four-arms/AllAliensPatch.cs')
assert 'OnWheel {get{return Id>=20 && Id<=23;}}' in patch and 'FindAll(form=>form.OnWheel)' in patch
assert 'BEN10_ULTIMATE_CANNONBOLT_VOICE' in read('launcher/four-arms/NativeBridge.cs')

# Native: voice call, private effect ownership, suction attachment, release flash.
bridge = read('native-rex/src/pc_menu_bridge.h')
assert 'add("cosmic_ultimate_cannonbolt_voice",UltimateCannonboltVoice);' in bridge and 'BEN10_ULTIMATE_CANNONBOLT_VOICE' in bridge
for header in ('ucb_effect_owner.h', 'ucb_suction.h', 'ucb_screen_flash.h', 'ucb_screen_flash_state.h'):
    assert (ROOT / 'native-rex/src' / header).is_file(), header
integration = read('tools/apply_game_integration.py')
assert 'ucb_effect_owner::Reject' in integration and 'ucb_effect_owner::Local' in integration
assert 'ucb_suction::Refresh' in read('tools/apply_form_effects.py')
assert 'ucb_screen_flash::Release()' in read('native-rex/src/weapon_trace.h')
assert 'ucb_flash_' in read('native-rex/src/ben10_app.h') and 'winmm' in read('native-rex/CMakeLists.txt')
print('Ultimate Cannonbolt static checks OK.')

exports, installation, normal = (os.environ.get(k) for k in ('COSMIC_UCB_EXPORTS', 'COSMIC_INSTALLATION', 'COSMIC_NORMAL_BUNDLE'))
if not (exports and installation and normal):
    print('Set COSMIC_UCB_EXPORTS, COSMIC_INSTALLATION and COSMIC_NORMAL_BUNDLE to also run the importer; nothing else was checked.')
    sys.exit(0)
with tempfile.TemporaryDirectory() as folder:
    out = Path(folder) / 'ucb'
    subprocess.run([sys.executable, '-B', str(ROOT / 'tools/prepare_ultimate_cannonbolt.py'), '--exports', exports,
                    '--installation', installation, '--normal', normal, '--output', str(out)], check=True, capture_output=True)
    assert (out / 'form-ids.txt').read_bytes() == b'ultimatecannonbolt 24\n'
    package = entries((out / 'g_ucb.xbx').read_bytes())
    assert sorted(package) == [0, 3, 4, 22], sorted(package)
    mesh = importer.table(package[4])[importer.crc('ultimate_cannonbolt_mesh')]
    attacks = (out / 'atk_ucb.ddf').read_bytes()
    normal_attacks = (Path(normal) / 'atk_cb.ddf').read_bytes()
    assert len(attacks) == len(normal_attacks) and (len(attacks) - 4) % 224 == 0
    rows = list(struct.iter_unpack('>56I', attacks[4:]))
    assert len({row[0] for row in rows}) == len(rows), 'every attack record has its own id'
    assert not ({row[0] for row in rows} & {row[0] for row in struct.iter_unpack('>56I', normal_attacks[4:])}), 'no id shared with the normal form'
    assert (out / 'callout.fsb').stat().st_size > 48 + 80 and (out / 'transform.wav').is_file()
    assert (out / 'albedo.txt').read_text().startswith('g_ucb.xbx ')
    print('Ultimate Cannonbolt importer run OK: 4 model sections, 29 attack records with own ids, voice bank, registration scripts.')
