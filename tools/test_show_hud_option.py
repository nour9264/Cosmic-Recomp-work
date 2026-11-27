"""Static consistency check for the Show HUD option (no game files needed).

The option lives in three places that must agree on one key, `show_hud`, in `user/pc-gameplay.ini`:
the launcher checkbox, the in-game Options > Gameplay row, and the startup parse in the pc menu bridge.
Checks: the key and defaults match, the in-game row is saved at once and never sent to the script VM, the Gameplay rows
still fit in values_, and the launcher's read/save rules (as written in main.cpp) round-trip with the game's `on/off` lines.
"""
import re
from pathlib import Path
from prepare_all_aliens_candidate import ROOT

launcher = (ROOT / 'launcher/native/main.cpp').read_text(encoding='utf-8')
options = (ROOT / 'native-rex/src/options_video_preview.h').read_text(encoding='utf-8')
bridge = (ROOT / 'native-rex/src/pc_menu_bridge.h').read_text(encoding='utf-8')
photo = (ROOT / 'native-rex/src/photo_mode.h').read_text(encoding='utf-8')

# 1. launcher: the option exists, defaults to shown, and uses the generic on/off read and save.
assert '{"show_hud","Show HUD",true}' in launcher
assert 'line==prefix+"on"' in launcher and 'line==prefix+"off"' in launcher
# 2. game: one native-only row, applied immediately, saved under the same key, excluded from the script bits.
assert '"Background Controller Input","Show HUD",' in options
assert 'hud_row_=5' in options and 'gameplay_bits_[]={0,1,2,5,6,9}' in options
assert 'SaveVideoKey(host->user_data_root()/"pc-gameplay.ini","show_hud",next?"on":"off")' in options
assert 'if(i!=hud_row_)bits|=unsigned(values_[i])<<gameplay_bits_[i];' in options, 'the HUD row must not be sent to the script VM'
assert 'for(int i=0;i<controls_row_;++i)values_[i]=int((bits>>gameplay_bits_[i])&1u);' in options
rows = re.search(r'gameplay_rows_\[\]=\{(.*?)\};', options, re.S).group(1)
assert len(re.findall(r'"[^"]+"', rows)) == 9, 'Invert x2, Vibration, Albedo, Background, Show HUD, Customize, Wipe, FOV'
# 3. startup parse and default.
assert 'if(line=="show_hud=off")ben10::photo::show_hud=false;' in bridge
assert 'if(line=="show_hud=on")ben10::photo::show_hud=true;' in bridge
assert 'inline std::atomic<bool> show_hud{true};' in photo
# 4. HUD is hidden only while a level is being played, never in menus.
assert '!show_hud.load(std::memory_order_relaxed) && gameplay_provider && gameplay_provider()' in photo


def launcher_read(text, key, default):
    value = default
    for line in text.splitlines():
        if line == key + '=on': value = True
        if line == key + '=off': value = False
    return value


def launcher_save(text, key, value):
    kept = [l for l in text.splitlines() if not l.startswith(key + '=')]
    return '\n'.join(kept + [key + '=' + ('on' if value else 'off')]) + '\n'


ini = 'invert_pitch=on\nfov=10\n'
assert launcher_read(ini, 'show_hud', True) is True                      # missing key: HUD shown
ini = launcher_save(ini, 'show_hud', False)
assert launcher_read(ini, 'show_hud', True) is False and 'invert_pitch=on' in ini and 'fov=10' in ini
ini = launcher_save(ini, 'show_hud', True)
assert launcher_read(ini, 'show_hud', False) is True and ini.count('show_hud=') == 1
print('Show HUD option OK: launcher, in-game row and startup parse agree on show_hud (static check, not a run of the game).')
