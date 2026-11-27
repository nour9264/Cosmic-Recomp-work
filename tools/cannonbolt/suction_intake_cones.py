"""Replace side streaks with tapered intake cones and remove late smoke."""
import math,struct,hashlib,sys,json
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
H = WORK;I=APP_ROOT/'installation';O=H/'suction-intake-cones';O.mkdir(exist_ok=True)
raw=(I/'game/global/g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();assert hashlib.sha256(raw).hexdigest()=='43f949b0155e5c2c6a06c52fe047ac1ea2f2b3c2f3cfaf17dc04efbc593935c6';p=entries(raw)
key=m.crc('ucb_suction_side_ribbons');root=m.effect_root('cannonbolt');ground=m.crc('ucb_suction_ground_ribbons')
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(s,rows):p[s]=m.build_vaps(s,struct.unpack_from('>H',p[s],12)[0],rows)
# Two actual conical surfaces, wide mouth outside, narrow throat touching
# the side spike. No diagonal slope. Their existing descent track is kept.
vertices=[];indices=[];colors=[];rings=24;segments=24
for sign in (-1,1):
    base=len(vertices)
    for i in range(rings+1):
        t=i/rings;rad=.39*(1-t)**.85+.065;x=sign*(2.43-1.45*t)
        for j in range(segments+1):
            angle=math.tau*j/segments
            vertices.append((x,.82+rad*math.cos(angle),rad*math.sin(angle),t,j/segments))
            fade=min(1,t*5)*min(1,(1-t)*24);a=round(105*fade*(.55+.45*t));colors.append(bytes((a,212,224,232)))
    for i in range(rings):
        for j in range(segments):
            a=base+i*(segments+1)+j;b=a+segments+1;c=a+1;d=b+1;indices.extend((a,b,c,b,d,c,c,b,a,c,d,b))
vb=b''.join(struct.pack('>5f',*v) for v in vertices);ib=struct.pack(f'>{len(indices)}H',*indices)
rows=[]
for k,f,v in m.vaps_rows(p[4]):
    if k==key:
        at,_,_=m.mesh_buffers(v,xbox=True);head=bytearray(v[:at]);meta=struct.unpack_from('<I',head,28)[0];ia=(at+len(vb)+31)&~31
        struct.pack_into('>I',head,4,len(vertices));struct.pack_into('>I',head,16,len(indices));struct.pack_into('<I',head,20,meta+ia-376);struct.pack_into('>I',head,384,(len(indices)<<16)|(struct.unpack_from('>I',head,384)[0]&0xffff));v=bytes(head)+vb+bytes(ia-at-len(vb))+ib;assert m.mesh_buffers(v,xbox=True)==(at,vb,ib)
    rows.append((k,f,v))
bank(4,rows);bank(3,[(k,f,v[:32]+b''.join(colors) if k==key else v) for k,f,v in m.vaps_rows(p[3])])
# Keep wisps moving toward the spike; the outer mouth starts transparent,
# opacity rises along their inward path and disappears at the narrow throat.
groups={m.crc(f'ucb_suction_side_{sign}'):sign for sign in (-1,1)};outs={m.crc(f'ucb_suction_out_{i}'):i for i in range(6)};nodes=[];seen=set()
for k,f,v in m.vaps_rows(p[14]):
    if k in (root,key):
        h,b=m.node_parts(v);out=[]
        if k==key:h[19:26]=fs(3.0,-2.5,.05,-.5,2.5,1.4,.5)
        for block in b:
            if block[0]==14:
                pp=[];group=None
                for pk,pt,pv in m.property_entries(block):
                    if pt==0x1000c:group=pk
                    if k==key and group in groups:
                        sign=groups[group];yaw=-sign*math.pi/2;opts={0x462ce4f5:fs(sign*2.42,.82,0,0,math.sin(yaw/2),0,math.cos(yaw/2)),0x9d762289:[7],0xe7965460:fs(29),0x3de73088:fs(.23),0x0f26fef6:fs(6.2),0x118a27c7:fs(.18),0x9c822a32:fs(.10),0x7cb5a078:fs(.03,.10,.10),0xd7943d68:fs(.04,.03,.03),0x5a6ce323:[0x00ffffff],0xc365b299:[0x40ffffff],0xb462820f:[0xc0ffffff],0x2a0617ac:[0x00ffffff]};pv=opts.get(pk,pv);seen.add(group)
                    if k==root and group in outs:
                        # Remove front/back plume only; remaining release
                        # particles expire before the 1.5s clip ends.
                        if pk==0xe7965460 and outs[group] in (0,3):pv=fs(0)
                        elif pk==0x3de73088:pv=fs(.18)
                    pp.append((pk,pt,pv))
                block=m.node_properties(pp)
            out.append(block)
        v=m.node_record(h,out)
    nodes.append((k,f,v))
assert seen==set(groups);bank(14,nodes);result=m.package(raw,p);chk=entries(result);old=entries(raw)
assert all(chk[s]==v for s,v in old.items() if s not in (3,4,14));assert all(m.table(chk[14])[k]==v for k,v in m.table(old[14]).items() if k not in (root,key));assert all(m.table(chk[4])[k]==v for k,v in m.table(old[4]).items() if k!=key)
(O/'g_cb.xbx').write_bytes(result);report=dict(old_cb_sha=hashlib.sha256(raw).hexdigest(),new_cb_sha=hashlib.sha256(result).hexdigest(),intake_cones=2,front_back_smoke_disabled=True,descent_and_core_flash_preserved=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
