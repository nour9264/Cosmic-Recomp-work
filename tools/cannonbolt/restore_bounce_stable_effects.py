"""Restore the gameplay-confirmed effect tree while retaining the requested height."""
import hashlib,json,sys,struct
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip

H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'ultimate-bounce-ball-v7-stable';O.mkdir(exist_ok=True)
sha=lambda x:hashlib.sha256(x).hexdigest();stable=H/'ultimate-bounce-ball-v4-height';last=H/'ultimate-bounce-ball-v6-crash-fix'
rs=json.loads((stable/'validation.json').read_text());rl=json.loads((last/'validation.json').read_text())
raw=(G/'g_cb.xbx').read_bytes();current=(G/'scripts/atk_ucb.ddf').read_bytes();base=(stable/'g_cb.xbx').read_bytes();d=(stable/'atk_ucb.ddf').read_bytes()
assert sha(raw)==rl['new_cb_sha'] and sha(current)==rl['unchanged_ucb_sha']
assert sha(base)==rs['new_cb_sha'] and sha(d)==rs['new_ucb_sha']
assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes() and current==(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
p=entries(base);a=entries(raw);old=dict(p);key=0xc9fb4de3;clip=m.table(p[13])[key];slot=struct.unpack_from('>I',clip,216+132*4)[0]
assert p[13]==a[13]
ch=channel_records(p[9]);newch=channel_records(a[9]);assert len(ch)==len(newch) and [i for i,(x,y) in enumerate(zip(ch,newch)) if x!=y]==[slot]
p[9]=a[9];new=m.package(base,p);check=entries(new)
assert len(new)==len(base) and all(check[k]==v for k,v in old.items() if k!=9) and check[9]==a[9]
assert all(streamed_clip(v,ch)==streamed_clip(v,newch) for k,v in m.table(p[13]).items() if k!=key)
(O/'g_cb.xbx').write_bytes(new);(O/'atk_ucb.ddf').write_bytes(d)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(new),old_ucb_sha=sha(current),new_ucb_sha=sha(d),normal_ddf_sha=rs['normal_ddf_sha'],effect_tree_restored=True,height_multiplier=1.2,peak_heights=[x*1.2 for x in rs['peak_heights']],contacts=rs['contacts'],gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
