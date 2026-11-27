"""Preflight the exact generated candidate, then install it with rollback."""
import hashlib
import json
import struct
import sys
from pathlib import Path

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, streamed_clip, merge_streams
from prepare_all_aliens_candidate import records

ROOT=(APP_ROOT/'installation').resolve()
G=ROOT/'game/global'
BASE=(WORK/'cannonbolt-approved-actions-native').resolve()
candidate=(BASE/sys.argv[1]).resolve()
assert candidate.parent==BASE
report=json.loads((candidate/'validation.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
staged={}
for item in report['files']:
    rel=Path(item['file']);path=(ROOT/rel).resolve()
    assert path.is_relative_to(ROOT) and path.is_file()
    before=(candidate/'before'/rel).read_bytes()
    after=(candidate/'after'/rel).read_bytes()
    assert sha(before)==item['before'] and sha(after)==item['after']
    assert path.read_bytes()==before, ('Installed input changed',str(rel))
    staged[path]=(before,after)

assert len(staged)==11
old,new=staged[G/'g_cb.xbx'];p0,p1=entries(old),entries(new)
assert {k:v for k,v in p0.items() if k not in (9,13)}=={k:v for k,v in p1.items() if k not in (9,13)}
clips0,clips1=m.table(p0[13]),m.table(p1[13]);channels=channel_records(p1[9]);new_ids=set(clips1)-set(clips0)
assert len(new_ids)==18
assert len(set(report['dodge'].values()))==2
assert {int(route['travel'],16) for route in report['routes']} <= new_ids
assert {int(route['strike'],16) for route in report['routes']} <= new_ids
assert {int(route['recovery'],16) for route in report['routes'] if int(route['recovery'],16)} <= new_ids
for code in ('cb','ucb'):
    before,after=staged[G/'scripts'/f'atk_{code}.ddf']
    changed=[]
    for offset in range(4,len(before),224):
        x,y=(struct.unpack_from('>56I',b,offset) for b in (before,after))
        if x!=y:
            assert x[:7]==y[:7] and x[10:]==y[10:]
            assert x[4] in (0xc0077403,0x70017403,0x100c7403,0x20047403)
            changed.append(x[0])
    assert len(changed)==4

# The launcher's exact resident-to-streamed conversion accepts these clips.
# Reconstruct each level in memory from its original bank and current archive
# inputs, using the staged Cannonbolt bank. Don't rewrite the level files:
# the launcher's normal Ensure() step will refresh them on next launch.
archives=[]
for name in ('ad','af','bc','ec','hm','nr','ra','sf','sm','ts','wh','ubc','uec','uhm','usf','usm'):
    path=G/f'g_{name}.xbx';archives.append((path.name,path.read_bytes()))
archives.append(('a_plyr.xbx',(G/'a_plyr.xbx').read_bytes()))
archives.append(('g_fa.xbx',(G/'g_fa.xbx').read_bytes()))
imported=[]
for d in (ROOT/'vilgax').iterdir():
    info=d/'form-ids.txt'
    if info.is_file():imported.append((int(info.read_text().split()[1]),d))
imported_clips=set()
for _,d in sorted(imported):
    for package in sorted(d.glob('g_*.xbx')):
        path=G/package.name
        data=staged[path][1] if path in staged else path.read_bytes()
        archives.append((package.name,data))
        parts=entries(data)
        if 13 in parts:imported_clips.update(entries(parts[13],True))

level_report=[]
for level in sorted((ROOT/'game').glob('l_*')):
    level_archives=archives+[(p.name,p.read_bytes()) for p in sorted(level.glob('g_*.xbx'))]
    for path in level.glob('a_*_s.xbx'):
        current=entries(path.read_bytes(),True)
        original_path=path.with_name(path.name+'.cosmic-animation-original')
        assert original_path.is_file()
        expected,_=merge_streams(original_path.read_bytes(),level_archives)
        expected=entries(expected)
        # Equivalent to the C# SameExceptClips upgrade check. Non-imported
        # content must match exactly and no previously installed key is lost.
        assert set(current)<=set(expected)
        assert set(expected)-set(current)<=imported_clips
        assert all(current[k]==expected[k] for k in current if k not in imported_clips)
        assert all(expected[k]==streamed_clip(clips1[k],channels) for k in new_ids)
        level_report.append({'level':level.name,'clips':len(expected),'new_cannonbolt_clips':len(new_ids)})
        print('Stream preflight:',level.name,len(new_ids),'new clips',flush=True)
assert len(level_report)==8
(candidate/'level-validation.json').write_text(json.dumps(level_report,indent=2))
if '--install' not in sys.argv:
    print('Preflight succeeded; no installation writes.')
    sys.exit(0)

replaced=[]
try:
    for path,(before,after) in staged.items():
        assert path.read_bytes()==before
        temp=path.with_name(path.name+'.cannonbolt-native-new')
        assert not temp.exists()
        temp.write_bytes(after)
        temp.replace(path)
        replaced.append(path)
        assert path.read_bytes()==after
except BaseException:
    for path in reversed(replaced):
        restore=path.with_name(path.name+'.cannonbolt-native-restore')
        assert not restore.exists()
        restore.write_bytes(staged[path][0]);restore.replace(path)
    raise
(candidate/'installed.json').write_text(json.dumps({'files':len(staged),'motions':6,'level_streams_preflighted':len(level_report),'gameplay_verified':False},indent=2))
print('INSTALLED',len(staged),'files, 6 motions,',len(level_report),'levels validated for next launcher refresh.')
