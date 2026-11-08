"""Generate an offline Xbox form-registration experiment from local scripts."""

import argparse
from pathlib import Path
import struct

from prepare_all_aliens_candidate import Code, decode, encode
from prepare_pause_menu_extension import crc, records


FORM_IDS = 0xe1003dc4
PLATFORM_FORM = 0x4b5b4447
PLATFORM_UPGRADES = 0x0fa12932
FOUR_ARMS_CALLBACKS = (0x39a05949, 0x2c00026b)
UPGRADE_TABLE = 0xe6db5005
FOUR_ARMS_PROBE_ID = 19


def initialize_probe_upgrades(code):
    words, tokens = decode(code)
    if (len(words) != 133 or words[-1] != 0x21
            or [i for i, op in tokens if op == 0x21] != [132]
            or words[24:26] != [0x00000c08, UPGRADE_TABLE]):
        raise ValueError('Unexpected original InitUpgradeTable')
    c = Code()
    c.words.extend(words[:-1])
    c.get(0, UPGRADE_TABLE)
    c.false(0, 'done')
    c.num(1, FOUR_ARMS_PROBE_ID)
    c.index(2, 0, 1)
    c.false(2, 'initialize')
    c.jump('done')
    c.label('initialize')
    c.table(2)
    c.store(0, 1, 2)
    for field, count in ((0xfa7aeffb, 3), (0x4c6b3fe3, 4)):
        c.table(3)
        c.fieldput(2, field, 3)
        c.num(4, 0)
        for index in range(1, count + 1):
            c.num(5, index)
            c.store(3, 5, 4)
    c.label('done')
    c.done()
    return c.finish()


def registration(xbox, ps3):
    xbox_rows = list(records(xbox))
    xbox_codes = {key: code for key, _, code in xbox_rows}
    ps3_rows = {key: (args, code) for key, args, code in records(ps3)}
    if any(key in xbox_codes for key in FOUR_ARMS_CALLBACKS):
        raise ValueError('Four Arms callback ID already exists in the Xbox script')

    result = []
    for key, args, code in xbox_rows:
        if key == FORM_IDS:
            words, tokens = decode(code)
            if (len(words) != 132 or words[76:80] != [0x203, 0x41400000, 0x20119, 0xf54b5e78]
                    or words[128:] != [0x107, 0x6e819790, 0x122, 0x21]):
                raise ValueError('Unexpected Xbox form ID table')
            # Keep the existing ID map. The probe uses 19 for Four Arms
            # while displaying it as the twelfth alien.
            if any(kind == 3 and words[i + 1] == 0x41980000 for i, kind in tokens):
                raise ValueError('Proposed Four Arms probe ID already exists')
            words[128:128] = [0x107, 0x6e819790, 0x203, 0x41980000,
                              0x20119, crc('Fourarms')]
            code = struct.pack(f'>{len(words)}I', *words)
        elif key == PLATFORM_FORM:
            _, donor = ps3_rows[key]
            if (len(code) != 740 or len(donor) != 740 or code[-4:] != b'\0\0\0!'
                    or donor[:4] != b'\0\0\0\x16'
                    or b'g_fa\0' not in donor or b'atk_fa.ddf\0' not in donor):
                raise ValueError('Unexpected platform form registration')
            for body in (code, donor):
                if any(kind in (0x1d, 0x1e, 0x1f) for _, kind in decode(body)[1]):
                    raise ValueError('Platform registration contains a branch')
            code = code[:-4] + donor
        elif key == PLATFORM_UPGRADES:
            donor_args, donor = ps3_rows[key]
            for body, form in ((code, 'Rath'), (donor, 'Fourarms')):
                words, tokens = decode(body)
                if (len(words) != 192 or words[3] != crc(form)
                        or [i for i, op in tokens if op == 0x21] != [191]
                        or any(op in (0x1d, 0x1e, 0x1f) for _, op in tokens)):
                    raise ValueError('Unexpected platform upgrade initializer')
            if args != 0 or donor_args != args:
                raise ValueError('Unexpected platform upgrade initializer arguments')
            code = code[:-4] + donor
        result.append((key, args, code))
    result.extend((key, *ps3_rows[key]) for key in FOUR_ARMS_CALLBACKS)
    return encode(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xbox', type=Path)
    parser.add_argument('ps3', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.suffix != '.bin':
        parser.error('Use .bin for this offline experiment')
    args.output.write_bytes(registration(args.xbox.read_bytes(), args.ps3.read_bytes()))
