"""Connect UCB's special weapon initialization to its inherited CB VFX tree."""
import hashlib,json,sys,struct
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from prepare_all_aliens_candidate import records,encode
from merge_alien_streams import entries
H = WORK;I=APP_ROOT/'installation';O=H/'ucb-vfx-attached';O.mkdir(exist_ok=True)
p=I/'vilgax/ultimatecannonbolt/forms.bin';raw=p.read_bytes();r=records(raw);key=m.crc('Cosmic_ultimatecannonbolt_init');old=0x0f7ab4af;new=m.effect_root('cannonbolt')
cb=entries((I/'vilgax/cannonbolt/g_cb.xbx').read_bytes());nodes=m.table(cb[14]);assert new in nodes
h,blocks=m.node_parts(nodes[new]);children=next(b[3:] for b in blocks if b[0]==0x14);assert all(m.crc('ucb_'+move+'_'+label) in children for move,label in [('spin','wind_0'),('spin','wind_1'),('spin','wind_2'),('backspin','rock_0'),('backspin','rock_1'),('backspin','ground_dust')])
out=[];hits=0
for k,a,v in r:
    if k==key:
        assert v.count(struct.pack('>I',old))==1
        nv=m.replace_arguments(v,{old:new});assert len(nv)==len(v) and nv.count(struct.pack('>I',new))==1 and struct.pack('>I',old) not in nv
        assert sum(x!=y for x,y in zip(v,nv))==4;v=nv;hits+=1
    out.append((k,a,v))
assert hits==1;result=encode(out);assert [(k,a,v)for k,a,v in records(result) if k!=key]==[(k,a,v)for k,a,v in r if k!=key]
(O/'forms.bin').write_bytes(result);report=dict(old_sha=hashlib.sha256(raw).hexdigest(),previous_root=hex(old),new_root=hex(new),children=len(children),gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
