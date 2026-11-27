"""Static checks for the normal-Cannonbolt finishing steps in tools/cannonbolt (no game files needed).

Each step pins the exact package it expects and chains to the next: the checks below keep that chain, the safety switches
and the "no personal or build-specific path" rule from drifting. The steps themselves are replayed against real files with
the commands in docs/CANNONBOLT.md.
"""
import re
from pathlib import Path

folder = Path(__file__).resolve().parent / 'cannonbolt'
# (script, g_cb sha it requires, atk_cb sha it requires or None)  in run order; the first step records its own input.
CHAIN = [
    ('port_normal_cb_vilgax_visuals.py', None, None),
    ('align_normal_cb_ground_impacts.py', 'c7e1125bb5b94fd8c6f6996608beaccb2972143764ee8c7d04f3f60f6d79118f', None),
    ('fade_normal_cb_ground_impacts.py', 'b1e5241aaa65464ec09d8f21f8bdd2145281a76e26782ad9cfbb537c8c3c5880', None),
    ('independent_normal_cb_impacts.py', '2748908ff61d8ea91e9aeca1b265ab77633e6af81e9ea3c782f9983363ba6d9c', None),
    ('normal_cb_visual_hit_ranges.py', '45bfb00a077417e9d0653558bbd31567c69b737ded270e0160d99f5bf0de88ed',
     '67e86abac9ea398e57783b4444759caa370ef81b52353f3bef749df9605691c0'),
    ('normal_cb_aerial_counter.py', '0e035cb59652cffb6a9bf58c3113ef5699f44ab8cbe190b6e70c91650b9e79a4',
     '67e86abac9ea398e57783b4444759caa370ef81b52353f3bef749df9605691c0'),
]
BANNED = ("ready-to-test", "Nour", "C:/", "C:\\", "Downloads", "Path.home")

listed = {name for name, _, _ in CHAIN}
assert listed <= {p.name for p in folder.glob('*.py')}, 'missing step'
# Every other script in the folder (the Ultimate Cannonbolt steps) follows the same rules: compiles, paths from cannonbolt_paths only.
others = sorted(p for p in folder.glob('*.py') if p.name not in listed and p.name != 'cannonbolt_paths.py')
assert len(others) >= 55, len(others)
for path in others:
    text = path.read_text(encoding='utf-8')
    compile(text, path.name, 'exec')
    for banned in BANNED:
        assert banned not in text, (path.name, banned)
    assert 'cannonbolt_paths' in text or path.name == 'author_alien_actions.py', path.name
    assert not re.search(r"runtime/ben10\.exe'\] ?== ?'[0-9a-f]{64}'", text), path.name
for name, cb_sha, atk_sha in CHAIN:
    text = (folder / name).read_text(encoding='utf-8')
    compile(text, name, 'exec')
    for banned in BANNED:
        assert banned not in text, (name, banned)
    assert "if '--install' in sys.argv:" in text, f'{name}: changes only with --install'
    assert 'from cannonbolt_paths import' in text and 'WORK' in text, name
    if cb_sha:
        assert cb_sha in text, f'{name}: pinned input package'
    if atk_sha:
        assert atk_sha in text, f'{name}: pinned attack table'
    assert not re.search(r"runtime/ben10\.exe'\] ?== ?'[0-9a-f]{64}'", text), f'{name}: no pinned executable hash'
paths = (folder / 'cannonbolt_paths.py').read_text(encoding='utf-8')
for variable in ('COSMIC_APP', 'COSMIC_WORK', 'COSMIC_VILGAX_DUMP'):
    assert variable in paths
# The independent-impact step finds the package saved by the fade step instead of a dated folder name.
assert "glob('*/before/installation/game/global/g_cb.xbx')" in (folder / 'independent_normal_cb_impacts.py').read_text(encoding='utf-8')
print('Cannonbolt pipeline checks OK: 6 visuals steps with pinned inputs chained; every other step compiles and takes its paths from cannonbolt_paths (static; steps not run).')
