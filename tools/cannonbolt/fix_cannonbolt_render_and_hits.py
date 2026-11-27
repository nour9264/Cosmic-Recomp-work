"""Apply the proven imported-alien layout and punch-reaction repairs to the live build."""
import datetime
import hashlib
import json
import struct
import sys
from pathlib import Path

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
from merge_alien_streams import entries
from prepare_vilgax_import import package, table
from fix_vilgax_punch_reactions import patch_attacks

HERE = WORK
ROOT = APP_ROOT/'installation'
GLOBAL = ROOT / 'game/global'
ORDER = (0, 3, 4, 9, 12, 13, 14, 22, 24)
sha = lambda b: hashlib.sha256(b).hexdigest()


def physical_order(blob):
    count = struct.unpack_from('>I', blob, 8)[0]
    at = 32 + struct.unpack_from('>I', blob, 44)[0]
    return tuple(k for k, _, _ in sorted(
        struct.iter_unpack('>3I', blob[at:at + 12 * count]), key=lambda r: r[2]))


def normalize(blob):
    parts = entries(blob)
    order = tuple(k for k in ORDER if k in parts)
    assert set(order) == set(parts)
    revised = package(blob, parts, order)
    assert physical_order(revised) == order
    assert entries(revised) == parts  # unchanged mesh, skin, scripts, VFX, audio
    return revised


def main():
    for code in ('cs', 'gp', 'jr', 'bc', 'wh'):
        assert physical_order((GLOBAL / f'g_{code}.xbx').read_bytes()) == ORDER
    pairs = [
        ('game/global/g_cb.xbx', 'vilgax/cannonbolt/g_cb.xbx'),
        ('game/global/g_ucb.xbx', 'vilgax/ultimatecannonbolt/g_ucb.xbx'),
        ('game/global/scripts/atk_ucb.ddf', 'vilgax/ultimatecannonbolt/atk_ucb.ddf'),
    ]
    normal_attack = (GLOBAL / 'scripts/atk_cb.ddf').read_bytes()
    revisions = []
    for pair in pairs:
        old = (ROOT / pair[0]).read_bytes()
        assert (ROOT / pair[1]).read_bytes() == old
        if pair[0].endswith('.xbx'):
            new = normalize(old)
            print(pair[0], physical_order(old), '->', physical_order(new))
        else:
            clips = table(entries((GLOBAL / 'g_cb.xbx').read_bytes())[13])
            new, count = patch_attacks(old, clips)
            assert count == 16
            for offset in range(4, len(old), 224):
                before, after = (struct.unpack_from('>56I', b, offset) for b in (old, new))
                assert before[15] == after[15]  # balanced damage stays byte-identical
                assert before[:23] == after[:23] and before[24:45] == after[24:45]
                if before[40] != 0x47c02d3b or clips[before[8]][:64].split(b'\0')[0] == b'airattack_01':
                    assert before == after
            print('Restored stock target hit reactions for', count, 'Ultimate punches')
        for name in pair:
            revisions.append((name, old, new))
    out = HERE / ('cannonbolt-render-hitfix-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    out.mkdir()
    for name, old, new in revisions:
        saved = out / 'pre-install' / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(old)
        candidate = out / 'candidate' / name
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(new)
    for name, old, new in revisions:
        target = ROOT / name
        assert target.read_bytes() == old
        staged = target.with_suffix(target.suffix + '.renderfix-new')
        staged.write_bytes(new)
        staged.replace(target)
        assert target.read_bytes() == new
    assert (GLOBAL / 'scripts/atk_cb.ddf').read_bytes() == normal_attack
    (out / 'validation.json').write_text(json.dumps({
        'files': {name: {'before': sha(old), 'after': sha(new)} for name, old, new in revisions},
        'normal_attack_unchanged': sha(normal_attack),
        'payloads_preserved': True, 'ultimate_punches_fixed': 16,
    }, indent=2))
    print('Installed and verified both copies; backup:', out)


if __name__ == '__main__':
    main()
