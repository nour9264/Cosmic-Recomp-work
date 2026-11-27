"""Grow the spin mesh smoothly; restore the approved suction sound and enlarge its flash."""
import hashlib,json,math,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
from wheel_icon_texture import encode_block
from extract_discord_level_images import tiled_offset
H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'spin-growth-suction-flash';O.mkdir(exist_ok=True)
raw=(G/'g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(raw);gr=(G/'global.xbx').read_bytes();gp=entries(gr)
u=(G/'g_ucb.xbx').read_bytes();assert u==(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes();prev=(H/'suction-extended-release/pre-install/vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes()
sha=lambda v:hashlib.sha256(v).hexdigest();assert sha(raw)=='c723921253d538ac47efafd674fb637ec4dc1f65908b33a2dafaacb5bce01c31';assert sha(prev)=='2976b7dce6e3105f0d07dc7c6e4c34e8ab3de275137112978d984e0c2d184939'
assert all(entries(prev)[k]==v for k,v in entries(u).items() if k!=24)
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(a,s,rows):a[s]=m.build_vaps(s,struct.unpack_from('>H',a[s],12)[0],rows)
helix=m.crc('ucb_spin_helix_mesh');root=m.effect_root('cannonbolt');flash=m.crc('ucb_suction_core_flash');n=m.table(p[14]);nodes=[]
# Same native scale track format used by the existing release ring; grow from
# roughly ball height to the approved full height in the first 0.7 seconds.
points=[(0,.78,.22),(800,.88,.38),(1760,.96,.68),(3360,1.,1.)]
scale=[0x19,4+10*len(points),0x0d0a5003,(len(points)<<16)|len(points)]
for time,radius,height in points:scale.extend(fs(time)+[0]*6+fs(radius,height,radius))
for k,f,v in m.vaps_rows(p[14]):
    if k==helix:
        h,b=m.node_parts(v);assert not any(x[0]==0x19 for x in b);b.insert(0,scale);v=m.node_record(h,b)
    elif k==root:
        h,b=m.node_parts(v);out=[]
        for block in b:
            if block[0]==14:
                pp=[];group=None
                for pk,pt,pv in m.property_entries(block):
                    if pt==0x1000c:group=pk
                    if group==flash:pv={0x9d762289:[1],0x118a27c7:fs(7.0),0x9c822a32:fs(8.0),0x3de73088:fs(.20),0x5a6ce323:[0xffffffff],0xc365b299:[0xffffffff],0xb462820f:[0x55ffffff],0x2a0617ac:[0x00ffffff]}.get(pk,pv)
                    pp.append((pk,pt,pv))
                block=m.node_properties(pp)
            out.append(block)
        v=m.node_record(h,out)
    nodes.append((k,f,v))
bank(p,14,nodes);newcb=m.package(raw,p);chk=entries(newcb);assert all(chk[k]==v for k,v in entries(raw).items() if k!=14);assert all(m.table(chk[14])[k]==v for k,v in n.items() if k not in (root,helix))
# Only the existing release flash texture changes: broad white core with soft
# edges. A brief world-space flash, not a persistent screen overlay.
texkey=m.crc('ucb_suction_release_flash');oldtex=m.table(gp[0]);record=oldtex[texkey];assert len(record)==16512;pixels=[]
for y in range(128):
    for x in range(128):
        r=math.hypot(2*x/127-1,2*y/127-1);t=max(0,min(1,(1-r)/.32));a=round(255*t*t*(3-2*t));pixels.append((255,255,255,a))
tile=bytearray(16384)
for y in range(32):
    for x in range(32):
        b=encode_block([pixels[(4*y+j)*128+4*x+i] for j in range(4) for i in range(4)]);off=tiled_offset(x,y,32,4);tile[off:off+16]=bytes(b[i^1] for i in range(16))
bank(gp,0,[(k,f,record[:128]+tile if k==texkey else v) for k,f,v in m.vaps_rows(gp[0])]);newglobal=m.package(gr,gp);assert all(m.table(entries(newglobal)[0])[k]==v for k,v in oldtex.items() if k!=texkey)
(O/'g_cb.xbx').write_bytes(newcb);(O/'g_ucb.xbx').write_bytes(prev);(O/'global.xbx').write_bytes(newglobal)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(newcb),old_ucb_sha=sha(u),new_ucb_sha=sha(prev),old_global_sha=sha(gr),new_global_sha=sha(newglobal),growth_seconds=.7,previous_audio_restored=True,flash_seconds=.20,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
