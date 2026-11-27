"""Add elevated bilateral air intake ribbons; preserve approved ground swirl."""
import math,struct,sys,json,hashlib
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'suction-side-intakes';O.mkdir(exist_ok=True)
raw=(G/'g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(raw)
assert hashlib.sha256(raw).hexdigest()=='484a4bc1757381f19d3760d2061fb7eabebbb3a0dd630565265004f6713e1f9f'
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(s,rows):p[s]=m.build_vaps(s,struct.unpack_from('>H',p[s],12)[0],m.bucket_sorted(rows))
root=m.effect_root('cannonbolt');ground=m.crc('ucb_suction_ground_ribbons');key=m.crc('ucb_suction_side_ribbons');start=m.crc('ucb_suction_vfx_start');stop=m.crc('ucb_suction_pull_stop')
# Each intake is a tapered, gently bent stream with two perpendicular
# surfaces around the same center line. They reach the two outer side spikes,
# not the floor; the existing ground swirl is left byte-identical.
vertices=[];indices=[];colors=[]
for sign in (-1,1):
    for plane in (0,1):
        base=len(vertices)
        for i in range(33):
            t=i/32;x=sign*(2.65-1.67*t);y=1.50-.58*t;z=.13*math.sin(math.pi*t);half=.34*(1-t)+.075
            for j in range(5):
                u=j/4;offset=(2*u-1)*half
                vertices.append((x,y+(offset if plane==0 else 0),z+(offset if plane==1 else 0),t,u))
                alpha=round(185*min(1,t*7)*min(1,(1-t)*15)*math.sin(math.pi*u)**.7);colors.append(bytes((alpha,211,226,238)))
        for i in range(32):
            for j in range(4):
                a=base+i*5+j;b=a+5;c=a+1;d=b+1;indices.extend((a,b,c,b,d,c,c,b,a,c,d,b))
vb=b''.join(struct.pack('>5f',*v) for v in vertices);ib=struct.pack(f'>{len(indices)}H',*indices)
donor=m.table(p[4])[ground];at,_,_=m.mesh_buffers(donor,xbox=True);head=bytearray(donor[:at]);meta=struct.unpack_from('<I',head,28)[0];ia=(at+len(vb)+31)&~31
struct.pack_into('>I',head,4,len(vertices));struct.pack_into('>I',head,16,len(indices));struct.pack_into('<I',head,20,meta+ia-376);struct.pack_into('>I',head,384,(len(indices)<<16)|(struct.unpack_from('>I',head,384)[0]&0xffff));mesh=bytes(head)+vb+bytes(ia-at-len(vb))+ib;assert m.mesh_buffers(mesh,xbox=True)==(at,vb,ib)
colhead=bytearray(m.table(p[3])[ground][:32]);struct.pack_into('>I',colhead,8,key);bank(4,m.vaps_rows(p[4])+[(key,at//32,mesh)]);bank(3,m.vaps_rows(p[3])+[(key,1,bytes(colhead)+b''.join(colors))])
# Static local-space ribbons: same renderer as the approved ground effect.
# Identity rotation track keeps intakes on the player's left/right.
n=m.table(p[14]);h,b=m.node_parts(n[ground]);h[0]=key;h[19:26]=fs(3.3,-2.85,.55,-.5,2.85,1.95,.5)
curve=struct.pack('>BBHHH',16,2,0x5002,2,2)+struct.pack('>3hbB',0,0,0,127,0)+struct.pack('>3hbB',0,0,0,127,34);words=list(struct.unpack(f'>{len(curve)//4}I',curve));child=[]
for block in b:
    if block[0]==0x16:block=[0x16,len(words)+2]+words
    elif block[0]==0:block=[0,4,key,key]
    child.append(block)
oldch=channel_records(p[9]);oldclips=m.table(p[13]);p[9],p[13]=m.merge_channels(p[9],p[13],[(key,0,curve)]);nc=channel_records(p[9]);assert all(streamed_clip(v,oldch)==streamed_clip(m.table(p[13])[k],nc) for k,v in oldclips.items())
outs={m.crc(f'ucb_suction_out_{i}') for i in range(6)};flash=m.crc('ucb_suction_core_flash');nodes=[]
for nk,f,v in m.vaps_rows(p[14]):
    if nk==root:
        rh,rb=m.node_parts(v);out=[]
        for block in rb:
            if block[0]==0x14:block=[0x14,block[1]+1,block[2]+1]+block[3:]+[key]
            elif block[0]==14:
                props=[];group=None;template=[]
                for k,t,pv in m.property_entries(block):
                    if t==0x1000c:group=k
                    if group==m.crc('ucb_suction_in_0'):template.append((k,t,list(pv)))
                    if group in outs:pv={0x9d762289:[7],0xe7965460:fs(48),0x3de73088:fs(.34),0x0f26fef6:fs(12),0x118a27c7:fs(.68),0x9c822a32:fs(.90),0x5a6ce323:[0xf0ffffff],0xc365b299:[0xffffffff],0xb462820f:[0x90ffffff]}.get(k,pv)
                    elif group==flash:pv={0x9d762289:[2],0x3de73088:fs(.22),0x118a27c7:fs(2.15),0x9c822a32:fs(2.65),0xc365b299:[0xffffffff]}.get(k,pv)
                    props.append((k,t,pv))
                assert template
                # Moving wisps travel into each elevated ribbon, giving the
                # visible flow direction from outside to the spike ends.
                for sign in (-1,1):
                    yaw=-sign*math.pi/2;pitch=.30;sy,cy=math.sin(yaw/2),math.cos(yaw/2);sp,cp=math.sin(pitch/2),math.cos(pitch/2)
                    overrides={0x462ce4f5:fs(sign*2.54,1.48,0,cy*sp,sy*cp,-sy*sp,cy*cp),0x9d762289:[5],0xe7965460:fs(22),0x3de73088:fs(.26),0x0f26fef6:fs(6.1),0x118a27c7:fs(.19),0x9c822a32:fs(.25),0x7cb5a078:fs(.04,.04,.07),0xd7943d68:fs(.11,.09,.11),0x5a6ce323:[0x30ffffff],0xc365b299:[0x9affffff],0xb462820f:[0x65ffffff]}
                    props.extend((m.crc(f'ucb_suction_side_{sign}') if t==0x1000c else k,t,overrides.get(k,pv)) for k,t,pv in template)
                for i,event in enumerate((start,stop)):
                    props.extend([(m.crc(f'ucb_suction_side_forward_{i}'),0x1000c,[m.EVENT_GROUP]),(0x939b68a0,0x201000c,[event]),(0x8541406c,0x201000c,[event]),(0x557c4b4d,0x201000c,[key])])
                block=m.node_properties(props)
            out.append(block)
        v=m.node_record(rh,out)
    nodes.append((nk,f,v))
bank(14,nodes+[(key,0,m.node_record(h,child))]);result=m.package(raw,p);check=entries(result)
assert all(check[k]==v for k,v in entries(raw).items() if k not in (3,4,9,13,14));assert all(m.table(check[14])[k]==v for k,v in n.items() if k!=root);assert all(m.table(check[4])[k]==v for k,v in m.table(entries(raw)[4]).items())
(O/'g_cb.xbx').write_bytes(result);report=dict(old_cb_sha=hashlib.sha256(raw).hexdigest(),new_cb_sha=hashlib.sha256(result).hexdigest(),side_ribbons=2,blast_size_multiplier=2.65/1.95,ground_unchanged=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
