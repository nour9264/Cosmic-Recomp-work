"""Exercise the authored boss-form transaction with the engine calls modeled."""
from pathlib import Path

from prepare_all_aliens_candidate import ROOT, crc, records
from prepare_hero_time_candidate import authored
from prepare_ultimate_way_big_form import FORM_ID, form_scripts
from test_all_aliens_script import VM


vm = VM([1, 2, 3, 4])
original = (ROOT / Path('originals/global/scripts/globals.ds')).read_bytes()
for key, args, code in (*authored(discord_presence=True), *records(form_scripts(original))):
    vm.functions[key] = (args, code)
    vm.globals[key] = key

events = []
finish = []
overlay = vm.globals[crc('overlay')]
overlay[crc('cosmic_ultimate_way_big_request')] = lambda *_: 1
overlay[crc('cosmic_ultimate_way_big_form_trace')] = lambda _, event: events.append(int(event))
overlay[crc('cosmic_albedo_hud_enabled')] = lambda *_: 0
person = {
    crc('isdead'): lambda *_: False,
    crc('gethealth'): lambda *_: 42,
    crc('sethealth'): lambda _, value: events.append(('health', value)),
    crc('setscale'): lambda _, value: events.append(('scale', value)),
    0xb91d451b: lambda *_: None,
}
vm.globals[crc('player')] = {crc('person'): lambda *_: person}
vm.globals[crc('gCurrentCharacter')] = 18
stock_buttons = {1: 0xd44b7a60, 2: 0x89af0267, 3: 0x0137a091, 4: 0x93eb00b0}
vm.globals[crc('gFormData')][18] = {0x224117f6: stock_buttons}
vm.globals[0xe1003dc4] = lambda: {crc('waybig'): 18, crc('ultimatewaybig'): FORM_ID}
vm.globals[0x65661824] = lambda *_: None
vm.globals[0xb73871bc] = lambda *_: None
vm.globals[0x326f91f9] = lambda *args: finish.append(args)
vm.globals[crc('switch_character_cb')] = lambda: events.append('stock completion')
vm.globals[crc('CosmicHeroFlash')] = lambda: events.append('flash')

vm.run('Cosmic_ultimatewaybig_register')
assert vm.globals[crc('gFormData')][FORM_ID][0x224117f6] is stock_buttons
vm.run('CosmicUltimateWayBigPreload')
assert vm.events == [('load', 'l_tokd', 'g_uwb')]
vm.run('CosmicWayBigUpdate')
assert events == [0, 2, 4] and not finish

vm.complete()
# The encounter uses its own completion callback and can leave the regular
# alien wheel's transition flag set. Only a Way Big switch owns this lock.
vm.globals[0x597a958a] = True
vm.run('CosmicWayBigUpdate')
assert events[-3:] == [3, 6, 'flash']
assert vm.globals[crc('gCurrentCharacter')] == FORM_ID
assert finish[0][2] == crc('character_uwb')
vm.run('CosmicWayBigUpdate')
assert len(finish) == 1 and events[-1] == 5

vm.run(finish[0][-1])
assert events[-4:] == [8, 'stock completion', ('scale', 3), ('health', 42)]
vm.run('CosmicWayBigUpdate')
assert vm.globals[crc('gCurrentCharacter')] == 18
assert finish[1][2] == crc('character_waybig')
vm.run(finish[1][-1])
assert events[-4:] == [8, 'stock completion', ('scale', 3), ('health', 42)]
overlay[crc('cosmic_albedo_hud_enabled')] = lambda *_: 1
vm.run('CosmicWayBigUpdate')
assert finish[2][2] == crc('character_uwb_alt')
print('Ultimate Way Big VM: mission package, readiness, entry, return, scale and health restoration passed.')
