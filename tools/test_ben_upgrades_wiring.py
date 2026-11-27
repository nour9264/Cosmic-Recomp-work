"""Static wiring checks for the upgrade system (no game files needed).

Prices live twice, in the authored script (prepare_ben_upgrades.py) and in the native menu (upgrade_economy.h); the menu's
form wiring, the HUD arc hook, the launcher and the bridge build must name the same things. The VM behaviour itself is
checked by test_ben_upgrade_program.py and test_transformation_animation.py.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_ben_upgrades as upgrades  # noqa: E402

read = lambda rel: (ROOT / rel).read_text(encoding='utf-8-sig')

economy = read('native-rex/src/upgrade_economy.h')
numbers = lambda name: [int(x) for x in re.search(name + r'\{([\d, ]+)\}', economy).group(1).replace(' ', '').split(',')]
assert tuple(numbers('stat_costs')) == upgrades.COSTS, 'stat prices: native and script agree'
assert tuple(numbers('matrix_costs')) == upgrades.MATRIX_COSTS, 'matrix prices: native and script agree'
assert sum(upgrades.MATRIX_COSTS) + 2 * sum(upgrades.COSTS) == 450000, 'the whole economy adds up to the campaign total'
assert 'master_control_tier=5' in economy

cosmetics = read('native-rex/src/cosmetics_state.h')
assert 'costs{70000, 25000, 40000, 30000}' in cosmetics

# The menu: three pages, the gameplay page no longer carries the rows that were bought instead.
options = read('native-rex/src/options_video_preview.h')
assert 'upgrade_page_=(upgrade_page_+1)%3' in options and '"Ultimatrix Upgrades","Ben Upgrades","Cosmetics"' in options
assert 'if(selected_==albedo_row_ && !AlbedoOwned())return;' in options
assert '"All Aliens"' not in re.search(r'gameplay_rows_\[\]=\{(.*?)\};', options, re.S).group(1)

bridge = read('native-rex/src/pc_menu_bridge.h')
for registration in ('cosmic_ben_upgrade_menu_tick', 'cosmic_master_control_sync', 'cosmic_ben_transform_enabled',
                     'cosmic_ben_transform_pending', 'cosmic_ben_resize_hud_arc', 'cosmic_ben_hud_frame_ready'):
    assert f'add("{registration}"' in bridge, registration
assert 'add("cosmic_cosmetics_sync"' in bridge and 'inline void ApplyCosmetics(unsigned mask)' in bridge
assert 'if(!cosmetics::owned[cosmetics::Albedo].load())ben10::albedo_hud::enabled=false;' in bridge, 'Albedo stays locked until the save owns it'
assert 'CosmicBuyBenCosmetic' in read('tools/prepare_ben_upgrades.py') and 'upgrades::purchase=48u+unsigned(i)' in options
assert 'constexpr unsigned apply_flag=1u<<10;' in bridge, 'bit 7 is Transformation Animation, the apply flag moved'

# HUD arc: the hook tool and the observer agree, and the tool is part of the apply step.
assert 'ben10::upgrade_arc::ObserveArc' in read('tools/apply_ben_upgrade_arc.py')
assert 'add_ben_upgrade_arc(args.generated)' in read('tools/apply_game_integration.py')

# Bridge build: one switch carries the globals, the menu wrapper and the Hero Time/All Aliens variants.
build = read('tools/build_release_bridge.py')
assert "'--ben-upgrades'" in build and 'COSMIC_BEN_UPGRADES' in build and 'matrix_upgrades=args.ben_upgrades' in build
patch = read('launcher/four-arms/AllAliensPatch.cs')
for needle in ('CosmicMasterControlSync', 'UpgradeBenGlobals', 'UpgradeBenScreen', 'CosmicWayBigTapGate', 'CosmicNormalTransformRequest'):
    assert needle in patch, needle
assert len(re.findall(r'Hash\(current\)=="[0-9a-f]{64}"', patch)) == 3, 'only the three released profiles are listed; no hashes of private development installs'

# The asset tools take every path from ben_upgrade_paths and carry no personal path.
tools = sorted((ROOT / 'tools/ben_upgrades').glob('*.py'))
assert len(tools) >= 14, len(tools)
for path in tools:
    text = path.read_text(encoding='utf-8')
    compile(text, path.name, 'exec')
    for banned in ('ready-to-test', 'Nour', 'C:/Users', 'Downloads', 'Path.home', "Path('build/"):
        assert banned not in text, (path.name, banned)
    assert path.name == 'ben_upgrade_paths.py' or 'ben_upgrade_paths' in text, path.name
print('Upgrade system wiring checks OK (static; the game was not run).')
