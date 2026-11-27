"""Static checks for the remaining tweaks: launcher status, VM guard, live refresh rate, imported alien animation tools.

No game files needed; the tools themselves are described in docs/GAMEPLAY_TWEAKS.md.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
read = lambda rel: (ROOT / rel).read_text(encoding='utf-8-sig')

# VM guard: the header, the hook tool and the apply step agree.
guard = read('native-rex/src/vm_guard.h')
assert 'BadObject' in guard and '0xE0000000u' in guard
tool = read('tools/apply_vm_guard.py')
assert 'sub_82239928' in tool and 'vm_guard::BadObject' in tool and 'ctx.r3.u64 = 0' in tool
assert 'add_vm_guard(args.generated)' in read('tools/apply_game_integration.py')

# Effect guard: a null effect instance (double jump of Ultimate Swampfire) skips its set-up instead of ending the game.
effect_guard = read('native-rex/src/effect_guard.h')
effect_tool = read('tools/apply_effect_guard.py')
assert 'Skipped' in effect_guard and 'sub_821EA860' in effect_tool and 'ctx.r3.u32 != 0' in effect_tool
assert 'add_effect_guard(args.generated)' in read('tools/apply_game_integration.py')

# Launcher: status file written through one atomic helper by both bridges; no private-install hashes added.
installed = read('launcher/InstalledGame.cs')
assert 'PublishLauncherStatus(string root, string value)' in installed and 'File.Replace(temporary, path, null)' in installed
for rel in ('launcher/NativeBridge.cs', 'launcher/four-arms/NativeBridge.cs'):
    assert 'InstalledGame.PublishLauncherStatus(Root, value);' in read(rel), rel
assert 'case "standard-no-reuse":' in installed
assert 'effectLimit' in read('launcher/UltimateVoiceLinks.cs')
launcher = read('launcher/native/main.cpp')
for key in ('"all_aliens"', '"hero_time"', '"albedo_hud_preview"'):
    assert key not in launcher, f'{key} is bought in the upgrade menu now'
assert '{"show_hud","Show HUD",true}' in launcher

# Live frame limit: the guest refresh rate follows the chosen limit.
bridge = read('native-rex/src/pc_menu_bridge.h')
assert 'SetFlagByName("video_mode_refresh_rate",Rate==120?"120":"60")' in bridge
assert 'PieceStretch' not in bridge, 'pause-frame stretch experiment stays out'

# Imported alien animation tools: every path comes from vilgax_animation_paths.
folder = ROOT / 'tools/vilgax_animations'
files = sorted(folder.glob('*.py'))
assert len(files) == 11, len(files)
for path in files:
    text = path.read_text(encoding='utf-8-sig')
    compile(text, path.name, 'exec')
    for banned in ('alpha8-release', 'Nour', 'C:/Users', 'Downloads', "Path('build/"):
        assert banned not in text, (path.name, banned)
    assert path.name == 'vilgax_animation_paths.py' or 'vilgax_animation_paths' in text, path.name
compile(read('tools/update_alien_force_art.py'), 'update_alien_force_art.py', 'exec')
print('Remaining-tweak wiring checks OK (static; the game was not run).')
