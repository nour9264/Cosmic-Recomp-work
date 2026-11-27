"""Checks for the bundled aliens, pictures and voices and the installer that puts them into an installation (no game files needed).

Verifies the manifest against the files, that the installer copies everything, changes nothing on a second run, refuses a damaged
bundle and moves a different existing folder aside instead of overwriting it.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'bundled-assets'
manifest = json.loads((BUNDLE / 'MANIFEST.json').read_text(encoding='utf-8'))
listed = {e['path']: e for e in manifest['files']}
on_disk = {p.relative_to(BUNDLE).as_posix() for p in BUNDLE.rglob('*') if p.is_file()} - {'MANIFEST.json'}
assert on_disk == set(listed), (sorted(on_disk ^ set(listed)))
for path, entry in listed.items():
    data = (BUNDLE / path).read_bytes()
    assert len(data) == entry['size'] and hashlib.sha256(data).hexdigest() == entry['sha256'], path
    assert entry['origin'], path
required = {'four-arms/g_fa.xbx', 'vilgax/chromastone/g_cs.xbx', 'vilgax/jetray/g_jr.xbx', 'vilgax/goop/g_gp.xbx',
            'vilgax/cannonbolt/g_cb.xbx', 'vilgax/ultimatecannonbolt/g_ucb.xbx', 'vilgax/ultimatecannonbolt/transform.wav',
            'user/Ultimate_Way_Big_Clean.wav', 'user/ben-transform-select.wav', 'user/upgrade-portraits.rgba',
            'user/cosmetic-previews.rgba'}
assert required <= set(listed), sorted(required - set(listed))
assert (ROOT / '.gitignore').read_text(encoding='utf-8').count('!bundled-assets/') >= 1

tool = [sys.executable, '-B', str(ROOT / 'tools/import_bundled_assets.py')]
with tempfile.TemporaryDirectory() as folder:
    installation = Path(folder) / 'installation'
    (installation / 'game').mkdir(parents=True)          # no picture banks here: only the copy step is exercised
    run = lambda bundle=BUNDLE: subprocess.run(tool + ['--installation', str(installation), '--bundle', str(bundle)], capture_output=True, text=True)
    first = run()
    assert first.returncode == 0 and 'four-arms' in first.stdout, first.stderr
    for path in listed:
        if not path.startswith(('ultimate-way-big-export/', 'pictures/', 'ben-model/', 'deltas/', 'albedo/')):
            assert (installation / path).read_bytes() == (BUNDLE / path).read_bytes(), path
    assert 'nothing to do' in run().stdout, 'second run changes nothing'
    # A different existing folder is moved aside, not overwritten.
    (installation / 'vilgax/goop/extra.txt').write_text('local edit')
    assert run().returncode == 0
    assert any(p.name.startswith('goop-previous-') for p in (installation / 'vilgax').iterdir())
    assert not (installation / 'vilgax/goop/extra.txt').exists()
    # A damaged bundle is refused before anything is written.
    damaged = Path(folder) / 'damaged'
    shutil.copytree(BUNDLE, damaged)
    target = damaged / 'vilgax/jetray/g_jr.xbx'
    target.write_bytes(target.read_bytes()[:-1] + b'\x00' if target.read_bytes()[-1] != 0 else target.read_bytes()[:-1] + b'\x01')
    shutil.rmtree(installation / 'vilgax')
    refused = run(damaged)
    assert refused.returncode != 0 and not (installation / 'vilgax').exists(), 'damaged bundle must not install'
print(f'Bundled assets OK: {len(listed)} files match the manifest; installer copies, is idempotent, keeps old folders and refuses damage.')
