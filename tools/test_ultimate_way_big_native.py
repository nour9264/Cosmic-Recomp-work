"""Static wiring checks for Ultimate Way Big (no game files needed).

The authored form scripts are checked by test_ultimate_way_big_form.py; this checks that the native side, the launcher, the
apply tools and the Hero Time program name the same things.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_hero_time_candidate as hero  # noqa: E402
from prepare_vilgax_import import crc  # noqa: E402

read = lambda rel: (ROOT / rel).read_text(encoding='utf-8-sig')

header = read('native-rex/src/ultimate_way_big.h')
assert 'kBenMesh = 0xec5e50dc' in header and 'kAlbedoMesh = 0x1e6840cb' in header and 'kVertices = 16264' in header
assert 'BEN10_ULTIMATE_WAY_BIG_FORM' in header and 'original * 1.5' in header, '1.5x damage, separate-form switch'

swap = read('native-rex/src/way_big_draw_swap.h')
assert 'BenDeviceSwap' not in swap, 'first-generation device swap stays out'
for needle in ('Ben10SampleWayBigL3()', 'Ben10ObserveWayBigForm(', '0x46bf1d36', '0x170e338a', 'SetWayBigBeamAppearance(true, false)'):
    assert needle in swap, needle
assert 'transformation_animation_pending' in read('native-rex/src/pc_menu_bridge.h'), 'the upgrade system gates the form change while its animation plays'

bridge = read('native-rex/src/pc_menu_bridge.h')
for needle in ('add("cosmic_ultimate_way_big_request",UltimateWayBigRequest,2);', 'add("cosmic_ultimate_way_big_reset",UltimateWayBigReset);',
               'UltimateWayBigReset(ctx,base);', 'Ultimate_Way_Big_Clean.wav'):
    assert needle in bridge, needle

integration = read('tools/apply_game_integration.py')
assert 'SelectWayBigBeamTint' in integration and 'ultimate_way_big::Damage' in integration and 'sub_82140398' in integration
assert 'SelectWayBigBeamTint' in read('native-rex/src/albedo_textures.h') and 'WayBigBeamTint::Cyan' in read('native-rex/src/albedo_textures.cpp')

# Launcher: id 25 only for the folder `ultimatewaybig`, never on the wheel, package into l_tokd, env flag for the native side.
vilgax = read('launcher/vilgax/VilgaxAliens.cs')
assert 'UltimateWayBigId=25' in vilgax and 'fields[0]!="ultimatewaybig"' in vilgax
assert 'OnWheel {get{return Id>=20 && Id<=23;}}' in read('launcher/four-arms/AllAliensPatch.cs')
assert 'WayBigMission(byte[] mission)' in read('launcher/four-arms/AllAliensPatch.cs')
assert 'AllAliensPatch.WayBigMission(target)' in read('launcher/DiscordPresencePatch.cs')
bridge_cs = read('launcher/four-arms/NativeBridge.cs')
assert 'BEN10_ULTIMATE_WAY_BIG_FORM' in bridge_cs and '"l_tokd"' in bridge_cs

# Hero Time: the update program only exists when presence/native hooks are on, and the stock program has none.
rows = {k for k, _, _ in hero.authored(discord_presence=True, ultimate_cannonbolt=True)}
assert crc('CosmicWayBigUpdate') in rows and crc('CosmicWayBigUpdate') not in {k for k, _, _ in hero.authored()}
assert re.search(r"c\.native\('cosmic_ultimate_way_big_reset'\)", read('tools/prepare_hero_time_candidate.py'))
print('Ultimate Way Big wiring checks OK (static; the game was not run).')
