"""Install the locally validated Goop patch into the authorized test build."""
import sys,json,hashlib,shutil,datetime
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from vilgax_animation_paths import APP as APP_ROOT, BLEND, REPO, WORK
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
root=(APP_ROOT/'installation').resolve()
patch=(BLEND/'goop-native-patch');report=json.loads((patch/'validation.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha((root/'vilgax/goop/g_gp.xbx').read_bytes())==report['source_sha256'],'Source changed; refusing stale patch'
changes={}
for name in ('g_gp.xbx','xbx-records.bin','atk_gp.ddf'):changes[root/'vilgax/goop'/name]=(patch/name).read_bytes()
changes[root/'game/global/g_gp.xbx']=(patch/'g_gp.xbx').read_bytes()
changes[root/'game/global/scripts/atk_gp.ddf']=(patch/'atk_gp.ddf').read_bytes()
p=root/'game/global/scripts/xbx.ddf';records=m.ddf_records(p.read_bytes());new=m.ddf_records(b'\x1b\xad\xba\xbe'+(patch/'xbx-records.bin').read_bytes())
assert set(new)<=set(records);records.update(new);changes[p]=b'\x1b\xad\xba\xbe'+b''.join(h+b for h,b in records.values())
backup=patch/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir()
manifest=[]
for path,data in changes.items():
 assert path.is_relative_to(root) and path.is_file()
 rel=path.relative_to(root);dst=backup/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dst)
 manifest.append({'path':rel.as_posix(),'before':sha(path.read_bytes()),'after':sha(data)})
(backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
for path,data in changes.items():
 temp=path.with_name(path.name+'.goop-new');temp.write_bytes(data);temp.replace(path)
 assert sha(path.read_bytes())==sha(data)
print('Installed 6 Goop package/data files. Backup:',backup)
print('Launcher will refresh level animation streams from the installed package.')
