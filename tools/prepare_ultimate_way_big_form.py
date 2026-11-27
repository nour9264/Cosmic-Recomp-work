"""Build the local resource and registration bundle for a distinct boss form."""
import argparse
from pathlib import Path
import struct

from prepare_all_aliens_candidate import Code, encode, records
from prepare_ultimate_way_big import DIFFUSE_KEYS, FORMS, MESH_KEYS, NORMAL, SHADING_MAPS
from prepare_vilgax_import import bank, crc, package, replace_arguments, vaps_rows
from merge_alien_streams import entries

FORM_ID = 25
FORM = 'ultimatewaybig'
BOSS_INIT = 0xb7269b14
STOCK_CHARACTERS = {'ben': 'character_waybig', 'albedo': 'character_evil_waybig'}
ULTIMATE_CHARACTERS = {'ben': 'character_uwb', 'albedo': 'character_uwb_alt'}
READY = 'cosmic_ultimate_way_big_form_ready'
SWITCHING = 'cosmic_ultimate_way_big_form_switching'
HEALTH = 'cosmic_ultimate_way_big_form_health'


def trace(code, event):
    code.get(29, 'overlay')
    code.num(28, event)
    code.method(29, 'cosmic_ultimate_way_big_form_trace', [29, 28])


def character_records(original):
    if original[:4] != bytes.fromhex('1badbabe'):
        raise ValueError('Expected the stock character data file')
    rows = {}
    position = 4
    while position < len(original):
        key, _, _, _, _, size = struct.unpack_from('>6I', original, position)
        end = position + 24 + size
        if end > len(original) or key in rows:
            raise ValueError('Invalid stock character row')
        rows[key] = original[position:end]
        position = end
    result = []
    for mode in FORMS:
        # Ben's definition supplies the player behavior in either mode.
        donor = bytearray(rows[crc(STOCK_CHARACTERS['ben'])])
        if donor[24:41] != b'character_waybig\x00' or struct.unpack_from('>I', donor, 60)[0] != NORMAL:
            raise ValueError('Unexpected Way Big character row')
        name = ULTIMATE_CHARACTERS[mode]
        donor[24:48] = name.encode('ascii').ljust(24, b'\x00')
        struct.pack_into('>I', donor, 0, crc(name))
        struct.pack_into('>I', donor, 60, MESH_KEYS[mode])
        result.append(donor)
    return b''.join(result)


def resources(prepared, stock_model_bank):
    character = (prepared / 'g_wayb.xbx').read_bytes()
    source = entries(character)
    level = entries((prepared / 'l_tokd.xbx').read_bytes())
    sections = {}
    for part, original, requested in (
        (0, source[0], set(DIFFUSE_KEYS.values()) | {key for _, _, key, _ in SHADING_MAPS}),
        (4, source[4], set(MESH_KEYS.values())),
        (22, level[22], set(MESH_KEYS.values())),
    ):
        rows = [(key, flag, data) for key, flag, data in vaps_rows(original) if key in requested]
        selected = {key: data for key, _, data in rows}
        flags = {id(data): flag for _, flag, data in rows}
        if selected.keys() != requested:
            raise ValueError(f'Missing prepared resources in section {part}')
        sections[part] = bank(part, struct.unpack_from('>H', original, 12)[0],
                              selected, lambda data: flags[id(data)])
    # The stock model loader's resident lookup starts at type 3. The mesh
    # bytes in type 4 and the skin in type 22 are insufficient on their own.
    flag, descriptor = next((flag, data) for key, flag, data in vaps_rows(stock_model_bank)
                            if key == NORMAL)
    if flag != 0 or len(descriptor) != 32 or struct.unpack_from('>I', descriptor, 8)[0] != NORMAL:
        raise ValueError('Unexpected stock Way Big model descriptor')
    descriptors = {key: descriptor[:8] + struct.pack('>I', key) + descriptor[12:]
                   for key in MESH_KEYS.values()}
    sections[3] = bank(3, struct.unpack_from('>H', source[3], 12)[0], descriptors)
    return package(character, sections, sorted(sections))


def form_scripts(original):
    donor = next((args, code) for key, args, code in records(original) if key == BOSS_INIT)
    args, code = donor
    if (args != 1 or len(code) != 116 * 4 or
            struct.unpack_from('>2I', code, 4 * 4) != (0x00020117, crc('waybig'))):
        raise ValueError('Unexpected stock Way Big setup script')
    form_init = bytearray(code)
    # Keep the encounter's separate Way Big flag on the player.
    struct.pack_into('>I', form_init, 5 * 4, crc(FORM))
    c = Code()
    c.get(0, 'gFormData')
    c.num(1, FORM_ID)
    c.table(2)
    c.store(0, 1, 2)
    c.emit(3 << 8 | 5, crc(ULTIMATE_CHARACTERS['ben']))
    c.fieldput(2, 'character', 3)
    c.emit(3 << 8 | 4, 0x675f7577, 0x62000000)  # g_uwb
    c.fieldput(2, 'characterFile', 3)
    c.emit(3 << 8 | 4, *struct.unpack('>3I', b'atk_wb.ddf\x00\x00'))
    c.fieldput(2, 0x7fb535f8, 3)
    c.get(3, 'Cosmic_ultimatewaybig_init')
    c.fieldput(2, 0x89d9800b, 3)
    # Special-attack dispatch indexes this table using gCurrentCharacter.
    c.num(4, 18); c.index(5, 0, 4)
    c.field(6, 5, 0x224117f6); c.fieldput(2, 0x224117f6, 6)
    c.done()
    program = [(crc('Cosmic_ultimatewaybig_register'), 0, c.finish())]
    # The first 70 words apply the character, stock rig and weapon slots.
    # The tail runs the encounter intro and sets initial player state.
    if struct.unpack_from('>2I', code, 68 * 4) != (0x050a0720, 1):
        raise ValueError('Unexpected Way Big setup boundary')
    end = struct.pack('>I', 0x21)
    for mode in FORMS:
        renamed = replace_arguments(form_init[:70 * 4] + end, {
            crc('character_waybig'): crc(ULTIMATE_CHARACTERS[mode]),
        })
        program.append((crc('Cosmic_ultimatewaybig_setup_' + mode), 1, renamed))
    program.append((crc('CosmicUltimateWayBigRestore'), 1, code[:70 * 4] + end))
    c = Code()
    c.native('cosmic_albedo_hud_enabled', 1)
    c.num(2, 1); c.binary(0x10, 3, 1, 2)
    c.false(3, 'ben')
    c.call('Cosmic_ultimatewaybig_setup_albedo', [0])
    c.jump('end')
    c.label('ben')
    c.call('Cosmic_ultimatewaybig_setup_ben', [0])
    c.label('end')
    c.done()
    program.append((crc('Cosmic_ultimatewaybig_init'), 1, c.finish()))
    for name in ('costs', 'upgrades'):
        c = Code()
        c.done()
        program.append((crc('Cosmic_ultimatewaybig_' + name), 0, c.finish()))

    c = Code()
    trace(c, 0)
    c.boolean(0, False); c.put(0, READY); c.put(0, SWITCHING)
    c.get(0, 0xf3d407b1); c.method(0, 'getcurrentmission', [0], 1)
    c.false(1, 'no_mission')
    # Use the same mission directory and loader as the stock g_wayb package.
    c.emit(2 << 8 | 4, 0x6c5f746f, 0x6b640000)
    c.emit(3 << 8 | 4, 0x675f7577, 0x62000000)
    c.get(4, 'CosmicUltimateWayBigLoaded')
    trace(c, 2)
    c.method(1, 0xbc35779c, [1, 2, 3, 4])
    c.jump('end')
    c.label('no_mission'); trace(c, 1)
    c.label('end'); c.done()
    program.append((crc('CosmicUltimateWayBigPreload'), 0, c.finish()))

    c = Code()
    trace(c, 3)
    c.boolean(0, True); c.put(0, READY); c.done()
    program.append((crc('CosmicUltimateWayBigLoaded'), 1, c.finish()))

    c = Code()
    trace(c, 8)
    c.call('switch_character_cb')
    c.boolean(1, False); c.put(1, SWITCHING)
    c.get(0, HEALTH)
    c.get(1, 'player'); c.false(1, 'end')
    c.method(1, 'person', [1], 2); c.false(2, 'end')
    # The encounter applies this actor scale after its stock opening setup.
    # The mid-fight switch skips that opening, but resets the actor scale.
    c.num(3, 3); c.method(2, 'setscale', [2, 3])
    c.method(2, 'sethealth', [2, 0])
    c.label('end'); c.done()
    program.append((crc('CosmicUltimateWayBigSwitched'), 0, c.finish()))

    c = Code()
    c.get(1, 'player'); c.false(1, 'end')
    c.method(1, 'person', [1], 2); c.false(2, 'end')
    c.method(2, 'isdead', [2], 3); c.false(3, 'alive')
    c.native('cosmic_ultimate_way_big_reset'); c.jump('end')
    c.label('alive')
    c.get(5, 'overlay'); c.method(5, 'cosmic_ultimate_way_big_request', [5, 2], 4)
    c.num(1, 1); c.binary(0x10, 3, 4, 1); c.false(3, 'end')
    c.get(1, READY); c.false(1, 'package_pending')
    c.get(1, SWITCHING); c.false(1, 'unlocked'); trace(c, 5); c.jump('end')
    c.label('unlocked')
    c.method(2, 'gethealth', [2], 3); c.put(3, HEALTH)
    c.get(1, 'gCurrentCharacter'); c.num(3, FORM_ID)
    c.binary(0x10, 4, 1, 3); c.false(4, 'enter')
    trace(c, 7)
    c.boolean(6, True); c.put(6, SWITCHING)
    c.get(5, 'CosmicUltimateWayBigSwitched')
    c.call('CosmicUltimateWayBigRestore', [5]); c.jump('end')
    c.label('enter')
    c.num(3, 18); c.binary(0x10, 4, 1, 3); c.false(4, 'unexpected_form')
    c.get(6, 'gFormData'); c.num(7, FORM_ID); c.index(8, 6, 7)
    c.false(8, 'missing_form'); c.field(9, 8, 0x89d9800b); c.false(9, 'missing_form')
    trace(c, 6)
    c.boolean(6, True); c.put(6, SWITCHING)
    c.call('CosmicHeroFlash')
    c.get(5, 'CosmicUltimateWayBigSwitched'); c.move(40, 5)
    c.emit(0x01280920, 20)
    c.jump('end')
    c.label('package_pending'); trace(c, 4); c.jump('end')
    c.label('missing_form'); trace(c, 9); c.jump('end')
    c.label('unexpected_form'); trace(c, 10)
    c.label('end'); c.done()
    program.append((crc('CosmicUltimateWayBigTick'), 0, c.finish()))
    return encode(program)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--originals', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    scripts = args.originals / 'global' / 'scripts'
    files = {
        'g_uwb.xbx': resources(args.prepared, (args.originals / 'l_tokd' / 'l_tokd_m.xbx').read_bytes()),
        'character-records.bin': character_records((scripts / 'char.ddf').read_bytes()),
        'forms.bin': form_scripts((scripts / 'globals.ds').read_bytes()),
        'form-ids.txt': f'{FORM} {FORM_ID}\n'.encode('ascii'),
        'player-records.bin': b'',
        'xbx-records.bin': b'',
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output / name).write_bytes(data)


if __name__ == '__main__':
    main()
