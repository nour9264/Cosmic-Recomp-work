"""Checks for the normal Cannonbolt import (made from the owner's own Vilgax Attacks copy).

Always runs the static checks (identity, special routes, sound names, launcher id range, importer behaviour kept for the other
aliens). With COSMIC_VILGAX_DUMP (the extracted Vilgax Attacks folder) and COSMIC_INSTALLATION (an installation folder with
Four Arms imported) it also runs the importer into a temporary folder and checks the bundle it writes:
  python tools/test_cannonbolt_import.py
"""
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_vilgax_import as importer  # noqa: E402
from add_cannonbolt_icon import add_icon, add_to_global  # noqa: E402
from merge_alien_streams import entries, channel_records, streamed_clip  # noqa: E402

SPECIALS = {0x549d5666: 'balldash_01', 0x239a66f0: 'superball_01', 0xba93374a: 'powerflop_01', 0xcaf9c3c5: 'burnout_run_01'}

# Static: identity and routes.
assert importer.ALIENS['cannonbolt'] == 'cb'
assert importer.FORM_IDENTITIES['cannonbolt'] == (23, 16.0)
assert importer.WHEEL_ICONS['cannonbolt'] == 0xf3b76348
assert importer.SPECIAL_CLIPS['cannonbolt'] == SPECIALS
assert importer.SPECIAL_EDGES['cannonbolt'] == {0xcaf9c3c5: ('burnout_in_01', 'burnout_out_01')}
assert set(importer.SPECIAL_SOUNDS['cannonbolt']) == set(SPECIALS) and 'cannonbolt' in importer.SPECIAL_SOUNDS_ENABLED
assert importer.CALLOUT_SAMPLES['cannonbolt'] == b'cannonbolt.wav'
assert len({v[0] for f in importer.FORM_IDENTITIES.values() for v in [f]}) == len(importer.FORM_IDENTITIES), 'form ids are unique'
text = (ROOT / 'tools/prepare_vilgax_import.py').read_text(encoding='utf-8')
# Only Cannonbolt gets the key-sorted payload; the other imported aliens keep the layout they were tested with.
assert "package(template, sections, sorted(sections) if name == 'cannonbolt' else None)" in text
assert "'cannonbolt'" in (ROOT / 'tools/prepare_albedo_textures.py').read_text(encoding='utf-8')
assert 'id>UltimateWayBigId' in (ROOT / 'launcher/vilgax/VilgaxAliens.cs').read_text(encoding='utf-8'), 'launcher accepts form id 23 (below the Ultimate forms)'

# Static: the icon helper adds once, keeps every other record and flag, and is idempotent.
key = importer.WHEEL_ICONS['cannonbolt']
picture = bytes(range(256)) * 4
base = importer.bank(0, 5, {1: b'a' * 64, 2: b'b' * 96}, lambda data: 0)  # alignment is log2: 32 bytes
grown = add_icon(base, key, picture)
rows = {k: (f, d) for k, f, d in importer.vaps_rows(grown)}
assert set(rows) == {1, 2, key} and rows[key][1] == picture and rows[key][0] == 4
assert add_icon(grown, key, picture) == grown, 'adding twice changes nothing'
print('Cannonbolt static checks OK.')

dump, installation = os.environ.get('COSMIC_VILGAX_DUMP'), os.environ.get('COSMIC_INSTALLATION')
if not (dump and installation):
    print('Set COSMIC_VILGAX_DUMP and COSMIC_INSTALLATION to also run the importer; nothing else was checked.')
    sys.exit(0)

with tempfile.TemporaryDirectory() as folder:
    out = Path(folder) / 'cannonbolt'
    subprocess.run([sys.executable, '-B', str(ROOT / 'tools/prepare_vilgax_import.py'), dump, installation, 'cannonbolt', str(out)],
                   check=True, capture_output=True)
    assert (out / 'form-ids.txt').read_text().split() == ['cannonbolt', '23']
    package = (out / 'g_cb.xbx').read_bytes()
    sections = entries(package)
    assert sorted(sections) == [0, 3, 4, 9, 12, 13, 14, 22, 24], sorted(sections)
    mesh = next(d for k, _, d in importer.vaps_rows(sections[4]) if k == 0x58ec2e03)
    assert struct.unpack_from('>I', mesh, 8)[0] == 1, 'one vertex stream for both draw ranges'
    assert key in importer.table(sections[0]), 'the roster picture travels with the package'
    clips, channels = importer.table(sections[13]), channel_records(sections[9])
    attacks = (out / 'atk_cb.ddf').read_bytes()
    routed = set()
    for words in struct.iter_unpack('>56I', attacks[4:]):
        if words[40] in SPECIALS:
            clip = SPECIALS[words[40]]
            assert words[8] == importer.crc(f'cannonbolt_{clip}')
            assert clips[words[8]].startswith(clip.encode() + bytes(1))
            assert words[36] and words[37], 'start and stop events are present'
            streamed_clip(clips[words[8]], channels)
            routed.add(words[40])
    assert routed == set(SPECIALS), 'every special attack route reaches a clip'
    assert (out / 'sounds.txt').read_text().count('cbolt') >= 4
    # The picture goes into a real global.xbx without disturbing its other sections.
    real = Path(installation) / 'game/global/global.xbx'
    if real.exists():
        original = real.read_bytes()
        before = entries(original)
        stripped_rows = [r for r in importer.vaps_rows(before[0]) if r[0] != key]
        trimmed = dict(before)
        trimmed[0] = importer.bank(0, struct.unpack_from('>H', before[0], 12)[0], {k: d for k, _, d in stripped_rows},
                                   lambda data, flags={id(d): f for _, f, d in stripped_rows}: flags[id(data)])
        offset = 32 + struct.unpack_from('>I', original, 44)[0]
        order = [k for k, _, _ in sorted(struct.iter_unpack('>3I', original[offset:offset + 12 * len(before)]), key=lambda r: r[2])]
        stripped = importer.package(original, trimmed, order)
        added = entries(add_to_global(stripped, key, importer.table(sections[0])[key]))
        assert all(added[k] == trimmed[k] for k in trimmed if k != 0), 'other sections untouched'
        records = {k: d for k, _, d in importer.vaps_rows(added[0])}
        assert records[key] == importer.table(sections[0])[key], 'the importer picture is what gets added'
        assert {k: d for k, d in records.items() if k != key} == {k: d for k, _, d in stripped_rows}, 'no other picture changes'
        print('Icon added to global.xbx without touching other sections.')
    print('Cannonbolt importer run OK: package sections, one vertex stream, roster picture, 4 special routes, sounds.')
