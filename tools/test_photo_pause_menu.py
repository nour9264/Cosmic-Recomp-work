"""Build the release bridge and check the pause-menu Photo Mode patch against local original scripts.

Needs a local copy of the game's original scripts (frontend.ds, menu.ds, misscr.ds, xbx_us.txt); nothing is distributed.
Checks, using the bridge's own GameMenuPatch.Ensure on throw-away folders:
  1. a fresh install gets the Photo Mode row directly under Upgrade Forms (so: Resume, Upgrade Forms, Photo Mode, Options, ...),
     the PHOTO MODE label in the English table and the extra script function;
  2. an install made by the previous build (PhotoPauseRow off) is upgraded in place to exactly the fresh result;
  3. a second Ensure changes nothing; an unknown edit is still rejected.
"""
import argparse, json, os, shutil, struct, subprocess, tempfile
from pathlib import Path
from prepare_pause_menu_extension import records, crc
from prepare_all_aliens_candidate import ROOT

parser = argparse.ArgumentParser()
parser.add_argument('--originals', type=Path, default=ROOT / 'originals/global/scripts')
parser.add_argument('--output-dir', type=Path)
args = parser.parse_args()
FILES = ['frontend.ds', 'menu.ds', 'misscr.ds', 'xbx_us.txt']
for name in FILES:
    if not (args.originals / name).is_file():
        raise SystemExit(f'Missing original {name} in {args.originals}')
out = args.output_dir or Path(tempfile.mkdtemp(prefix='photo-pause-'))
out.mkdir(parents=True, exist_ok=True)
os.environ.update(TEMP=str(ROOT / 'data/temp'), TMP=str(ROOT / 'data/temp'))
(ROOT / 'data/temp').mkdir(parents=True, exist_ok=True)
subprocess.run(['python', '-B', str(ROOT / 'tools/build_release_bridge.py'), '--hero-time', '--gpu-diagnostics', '--performance-alpha5',
                '--ultimate-voices', '--discord-presence', '--four-arms', '--vilgax', '--output-dir', str(out / 'bridge')], check=True)
ps = out / 'run.ps1'
ps.write_text(r'''
param($bridge,$originals,$work)
$asm=[Reflection.Assembly]::LoadFrom($bridge)
$menu=$asm.GetTypes() | Where-Object { $_.Name -eq 'GameMenuPatch' } | Select-Object -First 1
$aliens=$asm.GetTypes() | Where-Object { $_.Name -eq 'AllAliensPatch' } | Select-Object -First 1
$flags=[Reflection.BindingFlags]'Public,NonPublic,Static'
$ensure=$menu.GetMethod('Ensure',$flags); $photo=$aliens.GetField('PhotoPauseRow',$flags)
function Fresh($name){ $g=Join-Path $work $name; $s=Join-Path $g 'global\scripts'; New-Item -ItemType Directory -Force $s | Out-Null
  foreach($f in 'frontend.ds','menu.ds','misscr.ds','xbx_us.txt'){ Copy-Item (Join-Path $originals $f) (Join-Path $s $f) -Force }; return [string]$g }
function Run([string]$g){ try { $ensure.Invoke($null,@([string]$g,[byte[]]$null)) | Out-Null; 'ok' } catch { $_.Exception.InnerException.Message } }
function Hashes($g){ $s=Join-Path $g 'global\scripts'; 'frontend.ds','menu.ds','xbx_us.txt' | ForEach-Object { (Get-FileHash (Join-Path $s $_)).Hash } }
$r=@{}
$a=Fresh 'fresh'; $r.fresh=Run $a; $r.freshHashes=@(Hashes $a)
$photo.SetValue($null,$false); $b=Fresh 'old'; $r.old=Run $b; $r.oldHashes=@(Hashes $b); $photo.SetValue($null,$true)
$r.upgrade=Run $b; $r.upgradeHashes=@(Hashes $b)
$r.again=Run $b; $r.againHashes=@(Hashes $b)
$c=Fresh 'tampered'; $r.tamperedFirst=Run $c
$fe=Join-Path $c 'global\scripts\frontend.ds'; $bytes=[IO.File]::ReadAllBytes($fe); $bytes[100]=$bytes[100] -bxor 0xFF; [IO.File]::WriteAllBytes($fe,$bytes)
$r.tamperedSecond=Run $c
$r | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $work 'result.json') -Encoding utf8
''', encoding='utf-8')
work = out / 'work'
shutil.rmtree(work, ignore_errors=True)
work.mkdir()
subprocess.run(['powershell', '-NoProfile', '-File', str(ps), str(out / 'bridge/CosmicBridge.exe'), str(args.originals), str(work)], check=True)
result = json.loads((work / 'result.json').read_text(encoding='utf-8-sig'))
assert result['fresh'] == 'ok' and result['old'] == 'ok', result
assert result['upgrade'] == 'ok', 'the previous install must upgrade in place: ' + str(result['upgrade'])
assert result['upgradeHashes'] == result['freshHashes'], 'upgrade must equal a fresh install'
assert result['againHashes'] == result['upgradeHashes'], 'a second Ensure must change nothing'
assert result['oldHashes'] != result['freshHashes'], 'the new patch must change the scripts'
assert result['tamperedSecond'] != 'ok', 'an unknown edit must still be rejected'
scripts = work / 'fresh/global/scripts'
rows = {k: (a, c) for k, a, c in records((scripts / 'frontend.ds').read_bytes())}
code = rows[crc('pausemenu_enter')][1]
words = [struct.unpack_from('>I', code, i)[0] for i in range(0, len(code), 4)]
callbacks = [words[i + 1] for i in range(len(words) - 1) if words[i] == 0x00001007]
expected = [0x7c9a9aee, 0xd4ec2cf2, crc('CosmicPhotoMode'), 0xb4db5294, 0x21441cdd, 0x9a4e47e6, crc('CosmicQuitToLauncher')]
assert callbacks == expected, [hex(x) for x in callbacks]
assert crc('CosmicPhotoMode') in rows and rows[crc('CosmicPhotoMode')][0] == 1
text = (scripts / 'xbx_us.txt').read_bytes()
assert b'PHOTO MODE\0' in text
print('Photo Mode pause-menu patch OK: row order, upgrade from the previous install, idempotence, rejection of unknown edits.')
