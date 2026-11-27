"""Isolate the crashing sound component; retain the new bounce visuals/height."""
import hashlib,json,sys,struct
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries

H = WORK;I=APP_ROOT/'installation';G=I/'game/global';P=H/'ultimate-bounce-ball-v5-impact';O=H/'ultimate-bounce-ball-v6-crash-fix';O.mkdir(exist_ok=True)
sha=lambda v:hashlib.sha256(v).hexdigest();r=json.loads((P/'validation.json').read_text())
raw=(G/'g_cb.xbx').read_bytes();d=(G/'scripts/atk_ucb.ddf').read_bytes();assert sha(raw)==r['new_cb_sha'] and sha(d)==r['new_ucb_sha'];assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes()
p=entries(raw);old=dict(p);root=m.effect_root('cannonbolt');sound=m.crc('ucb_bounce_impact_sound');rows=[];removed=[]
for k,f,v in m.vaps_rows(p[14]):
    if k==root:
        h,blocks=m.node_parts(v);out=[]
        for b in blocks:
            if b[0]==14:
                props=[];skip=False
                for a,t,x in m.property_entries(b):
                    if t==0x1000c:
                        skip=a==sound
                        if skip:assert x==[0xf88ec384]
                    if skip:removed.append((a,t,x))
                    else:props.append((a,t,x))
                b=m.node_properties(props)
            out.append(b)
        v=m.node_record(h,out)
    rows.append((k,f,v))
assert len(removed)==8 and (0x5e237e06,0x201000c,[m.crc('cbolt_land_big')]) in removed
p[14]=m.build_vaps(14,struct.unpack_from('>H',p[14],12)[0],rows);new=m.package(raw,p);check=entries(new)
assert all(check[k]==v for k,v in old.items() if k!=14)
assert all(m.table(check[14])[k]==v for k,v in m.table(old[14]).items() if k!=root)
(O/'g_cb.xbx').write_bytes(new)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(new),unchanged_ucb_sha=sha(d),removed_component='ucb_bounce_impact_sound',height_multiplier=r['height_multiplier'],visual=r['visual'],contacts=r['contacts'],gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
