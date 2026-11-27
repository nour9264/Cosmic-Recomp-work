"""Align the two raised suction streams and animate their descent with the ball."""
import hashlib,json,math,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records
H = WORK;I=APP_ROOT/'installation';O=H/'suction-intake-alignment';O.mkdir(exist_ok=True)
raw=(I/'game/global/g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();assert hashlib.sha256(raw).hexdigest()=='f57bea06ec966eb468721211cec9617d7e69c59bb68f3fb8761c07c6746a7717';p=entries(raw)
root=m.effect_root('cannonbolt');key=m.crc('ucb_suction_side_ribbons');groups={m.crc(f'ucb_suction_side_{s}'):s for s in (-1,1)}
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(s,rows):p[s]=m.build_vaps(s,struct.unpack_from('>H',p[s],12)[0],rows)
# Preserve topology and original material. Both streams lie along the same
# horizontal local X axis at the lateral spike height.
rows=[];colors=[]
for k,f,v in m.vaps_rows(p[4]):
    if k==key:
        at,vb,ib=m.mesh_buffers(v,xbox=True);assert len(vb)==4*33*5*20;q=bytearray(v)
        for i in range(len(vb)//20):
            section,j=divmod(i,165);t,u=divmod(j,5);t/=32;u/=4;sign=-1 if section<2 else 1;plane=section%2
            x=sign*(2.65-1.67*t);half=.20*(1-t)+.085;offset=(2*u-1)*half
            struct.pack_into('>3f',q,at+i*20,x,.88+(offset if plane==0 else 0),offset if plane==1 else 0)
            # Outer end fades in gradually; brighter air converges at spike.
            a=round((65+135*t)*min(1,t*5)*min(1,(1-t)*30)*math.sin(math.pi*u)**.75);colors.append(bytes((a,211,226,238)))
        v=bytes(q);assert m.mesh_buffers(v,xbox=True)[2]==ib
    rows.append((k,f,v))
assert len(colors)==660;bank(4,rows)
bank(3,[(k,f,v[:32]+b''.join(colors) if k==key else v) for k,f,v in m.vaps_rows(p[3])])
# Extract the exact ball translation from the existing Suction Blast clip.
# Its local Y decreases by .20 and Z rises by .089 during the .22m dip.
# Convert the displacement to signed vertical distance (same animated axis).
clip=m.table(p[13])[0x754d9887];ch=channel_records(p[9]);payload=ch[struct.unpack_from('>I',clip,216+132*4)[0]];samples=list(struct.iter_unpack('>4f',payload[8:]));assert len(samples)==46
origin=samples[0][1:];points=[]
for i in (0,5,14,29,34,35):
    time,*pos=samples[i];delta=[x-y for x,y in zip(pos,origin)];vertical=math.copysign(math.sqrt(sum(x*x for x in delta)),delta[1]);points.append((time,vertical))
assert abs(points[-1][1]+.22)<.002
# Native position track: header, 10 words per key (time, tangents, position).
track=[0x15,4+10*len(points),0x050ad001,(len(points)<<16)|len(points)]
for time,y in points:track.extend(fs(time)+[0]*6+fs(0,y,0))
assert len(track)==track[1]
# The moving wisps must be on this same animated child instead of the root.
n=m.table(p[14]);rh,rb=m.node_parts(n[root]);moved=[];newroot=[]
for block in rb:
    if block[0]!=14:newroot.append(block);continue
    pp=[];group=None
    for k,t,v in m.property_entries(block):
        if t==0x1000c:group=k
        if group in groups:
            sign=groups[group];yaw=-sign*math.pi/2
            opts={0x462ce4f5:fs(sign*2.53,.88,0,0,math.sin(yaw/2),0,math.cos(yaw/2)),0x9d762289:[6],0xe7965460:fs(24),0x3de73088:fs(.26),0x0f26fef6:fs(5.9),0x118a27c7:fs(.12),0x9c822a32:fs(.19),0x7cb5a078:fs(.03,.035,.035),0xd7943d68:fs(.10,.04,.06),0x5a6ce323:[0x08ffffff],0xc365b299:[0x60ffffff],0xb462820f:[0x90ffffff]}
            moved.append((k,t,opts.get(k,v)))
        else:pp.append((k,t,v))
    newroot.append(m.node_properties(pp))
assert {k for k,t,v in moved if t==0x1000c}==set(groups)
h,b=m.node_parts(n[key]);h[19:26]=fs(3.1,-2.85,.40,-.4,2.85,1.2,.4);newchild=[]
for block in b:
    if block[0]==14:block=m.node_properties(m.property_entries(block)+moved)
    newchild.append(block)
newchild.insert(1,track)
bank(14,[(k,f,m.node_record(rh,newroot) if k==root else m.node_record(h,newchild) if k==key else v) for k,f,v in m.vaps_rows(p[14])]);result=m.package(raw,p);check=entries(result)
assert all(check[s]==v for s,v in entries(raw).items() if s not in (3,4,14));assert all(m.table(check[14])[k]==v for k,v in n.items() if k not in (root,key));assert all(m.table(check[4])[k]==v for k,v in m.table(entries(raw)[4]).items() if k!=key)
(O/'g_cb.xbx').write_bytes(result);report=dict(old_cb_sha=hashlib.sha256(raw).hexdigest(),new_cb_sha=hashlib.sha256(result).hexdigest(),intake_height=.88,descent_keys=points,ground_and_blast_preserved=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
