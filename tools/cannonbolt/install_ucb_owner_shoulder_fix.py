"""Install the corrected Ultimate Cannonbolt shoulder skin (replaces mesh/skin record 0x05ba3d56 in g_ucb.xbx).

    python tools/cannonbolt/install_ucb_owner_shoulder_fix.py <corrected g_ucb.xbx from the owner's Blender export>
The earlier build also swapped the runtime executable here; the owner-local effect code now lives in native-rex/src."""
import datetime
import hashlib
import json
import sys
from pathlib import Path

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
from merge_alien_streams import entries
import prepare_vilgax_import as m

HERE = WORK;APP=APP_ROOT;I=APP/'installation';G=I/'game/global';RT=APP/'runtime'
SHA=lambda b:hashlib.sha256(b).hexdigest()
model_path=G/'g_ucb.xbx';old_model=model_path.read_bytes();bundle=I/'vilgax/ultimatecannonbolt/g_ucb.xbx'
assert old_model==bundle.read_bytes()
new_model=Path(sys.argv[1]).read_bytes()
a,b=entries(old_model),entries(new_model)
assert set(a)==set(b) and all(a[k]==b[k] for k in a if k not in (4,22))
key=0x05ba3d56;assert m.table(a[4])[key]!=m.table(b[4])[key] and m.table(a[22])[key]!=m.table(b[22])[key]
assert all(m.table(a[4])[k]==m.table(b[4])[k] for k in m.table(a[4]) if k!=key)
changes={model_path:(old_model,new_model),bundle:(old_model,new_model)}
preserved={p:p.read_bytes() for p in (G/'g_cb.xbx',I/'vilgax/cannonbolt/g_cb.xbx',G/'scripts/atk_cb.ddf',G/'scripts/atk_ucb.ddf')}
backup=HERE/'owner-shoulder-install'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');backup.mkdir(parents=True)
report=[]
for p,(before,after) in changes.items():
    assert p.read_bytes()==before
    rel=p.relative_to(APP)
    for folder,data in [('before',before),('after',after)]:
        save=backup/folder/rel;save.parent.mkdir(parents=True,exist_ok=True);save.write_bytes(data)
    report.append({'file':str(rel),'before':SHA(before),'after':SHA(after)})
installed=[]
try:
    for p,(before,after) in changes.items():
        temp=p.with_name(p.name+'.owner-shoulder-new');assert not temp.exists();temp.write_bytes(after);temp.replace(p)
        installed.append(p);assert p.read_bytes()==after
except BaseException:
    for p in reversed(installed):
        restore=p.with_name(p.name+'.owner-shoulder-restore');assert not restore.exists();restore.write_bytes(changes[p][0]);restore.replace(p)
    raise
assert all(p.read_bytes()==data for p,data in preserved.items())
(backup/'validation.json').write_text(json.dumps({'files':report,'unchanged_attacks_and_animation_bank':True,'gameplay_verified':False},indent=2))
print('Installed shoulder skin. Backup:',backup)
