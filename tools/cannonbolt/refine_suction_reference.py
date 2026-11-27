"""Ground-level converging air ribbons and a short, expanding release flash."""
import math,struct,sys,json,hashlib
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
from wheel_icon_texture import encode_block
from extract_discord_level_images import tiled_offset
H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'suction-reference-vfx';O.mkdir(exist_ok=True)
raw=(G/'g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(raw);gr=(G/'global.xbx').read_bytes();gp=entries(gr)
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(a,s,rows):a[s]=m.build_vaps(s,struct.unpack_from('>H',a[s],12)[0],m.bucket_sorted(rows))
root=m.effect_root('cannonbolt');helix=m.crc('ucb_spin_helix_mesh');key=m.crc('ucb_suction_ground_ribbons');start=m.crc('ucb_suction_vfx_start');stop=m.crc('ucb_suction_pull_stop');blast=m.crc('ucb_suction_release');blaststop=m.crc('ucb_suction_blast_stop')
# Ground ribbons curve inward from all directions in true world-space geometry.
vertices=[];indices=[];colors=[]
for strand in range(6):
    base=len(vertices)
    for j in range(25):
        t=j/24;r=2.45-1.61*t;angle=strand*math.tau/6+.72*t;half=.28*(1-t)+.065
        for side in range(5):
            u=side/4;phi=angle+(u-.5)*2*half/r
            vertices.append((r*math.sin(phi),.10+.08*math.sin(math.pi*t),r*math.cos(phi),t,u))
            a=round(220*math.sin(math.pi*t)**.35*math.sin(math.pi*u)**.65);colors.append(bytes((a,225,225,225)))
    for j in range(24):
        for side in range(4):
            a=base+j*5+side;b=a+5;c=a+1;d=b+1;indices.extend((a,b,c,b,d,c,c,b,a,c,d,b))
vb=b''.join(struct.pack('>5f',*v) for v in vertices);ib=struct.pack(f'>{len(indices)}H',*indices)
donor=m.table(p[4])[helix];at,_,_=m.mesh_buffers(donor,xbox=True);head=bytearray(donor[:at]);meta=struct.unpack_from('<I',head,28)[0];ia=(at+len(vb)+31)&~31
struct.pack_into('>I',head,4,len(vertices));struct.pack_into('>I',head,16,len(indices));struct.pack_into('<I',head,20,meta+ia-376);struct.pack_into('>I',head,384,(len(indices)<<16)|(struct.unpack_from('>I',head,384)[0]&0xffff))
mesh=bytes(head)+vb+bytes(ia-at-len(vb))+ib;assert m.mesh_buffers(mesh,xbox=True)==(at,vb,ib)
colhead=bytearray(m.table(p[3])[helix][:32]);struct.pack_into('>I',colhead,8,key);col=bytes(colhead)+b''.join(colors)
bank(p,4,m.vaps_rows(p[4])+[(key,at//32,mesh)]);bank(p,3,m.vaps_rows(p[3])+[(key,1,col)])
# Use exactly the proven node renderer and quaternion format. The suction
# ribbon rotates gently inwards rather than inheriting the fast tall tornado.
n=m.table(p[14]);h,b=m.node_parts(n[helix]);h[0]=key;h[19:26]=fs(2.65,-2.6,-.05,-2.6,2.6,.3,2.6)
curve=bytearray(struct.pack('>BBHHH',16,2,0x5002,35,35))
for i in range(35):
    angle=-math.tau*.85*i/30;curve.extend(struct.pack('>3hbB',0,round(32767*math.sin(angle/2)),0,round(127*math.cos(angle/2)),i))
curve=bytes(curve);words=list(struct.unpack(f'>{len(curve)//4}I',curve));child=[];spinstart=m.crc('ucb_spin_vfx_start');spinstop=m.crc('ucb_spin_vfx_stop')
for block in b:
    if block[0]==0x16:block=[0x16,len(words)+2]+words
    elif block[0]==0:block=[0,4,key,key]
    elif block[0]==14:
        props=[];group=None
        for k,t,v in m.property_entries(block):
            if t==0x1000c:group=k
            if group==m.crc('ucb_helix_child_timeout'):continue
            v=[start if x==spinstart else stop if x==spinstop else x for x in v]
            if group==0xe16f3a56 and k in (0x5e0393bd,0xf465b2b5):v=fs(1.17)
            props.append((k,t,v))
        block=m.node_properties(props)
    child.append(block)
oldch=channel_records(p[9]);oldclips=m.table(p[13]);p[9],p[13]=m.merge_channels(p[9],p[13],[(key,0,curve)]);nc=channel_records(p[9]);assert all(streamed_clip(v,oldch)==streamed_clip(m.table(p[13])[k],nc) for k,v in oldclips.items())
# A brief localized air flash, soft outside the core; no screen overlay.
texkey=m.crc('ucb_suction_release_flash');oldtex=m.table(gp[0]);head=bytearray(oldtex[0xb458a502][:128]);struct.pack_into('>I',head,44,texkey);pixels=[]
for y in range(128):
    for x in range(128):
        r=math.hypot(2*x/127-1,2*y/127-1);a=round(255*max(0,1-r*r)**2.8);pixels.append((242,250,255,a))
tile=bytearray(16384)
for y in range(32):
    for x in range(32):
        v=encode_block([pixels[(4*y+j)*128+4*x+i] for j in range(4) for i in range(4)]);off=tiled_offset(x,y,32,4);tile[off:off+16]=bytes(v[i^1] for i in range(16))
bank(gp,0,m.vaps_rows(gp[0])+[(texkey,4,bytes(head)+tile)]);newglobal=m.package(gr,gp)
assert all(m.table(entries(newglobal)[0])[k]==v for k,v in oldtex.items())
ins={m.crc(f'ucb_suction_in_{i}') for i in range(6)};outs={m.crc(f'ucb_suction_out_{i}') for i in range(6)};nodes=[];seen=set()
for nk,f,v in m.vaps_rows(p[14]):
    if nk==root:
        rh,rb=m.node_parts(v);out=[]
        for block in rb:
            if block[0]==0x14:block=[0x14,block[1]+1,block[2]+1]+block[3:]+[key]
            elif block[0]==14:
                props=[];group=None;template=[]
                for k,t,pv in m.property_entries(block):
                    if t==0x1000c:group=k
                    if group==m.crc('ucb_suction_out_0'):template.append((k,t,list(pv)))
                    if group in ins|outs:
                        seen.add(group);outward=group in outs
                        if k==0x462ce4f5:
                            pv=list(pv);pv[1]=fs(.15 if not outward else .28)[0]
                        else:pv={0x3de73088:fs(.25 if not outward else .29),0x0f26fef6:fs(5.5 if not outward else 10),0x118a27c7:fs(.16 if not outward else .50),0x9c822a32:fs(.20 if not outward else .67),0x5a6ce323:[0x18ffffff if not outward else 0xc0ffffff],0xc365b299:[0x48ffffff if not outward else 0xe0ffffff],0xb462820f:[0x30ffffff if not outward else 0x80ffffff]}.get(k,pv)
                    props.append((k,t,pv))
                assert template
                flash={0x462ce4f5:fs(0,.54,0,0,0,0,1),0x9d762289:[1],0xe7965460:fs(60),0x3de73088:fs(.17),0x0f26fef6:fs(0),0x297c98f1:fs(0),0x7cb5a078:fs(0,0,0),0xd7943d68:fs(0,0,0),0x7a76b57b:fs(0,0,0),0x118a27c7:fs(1.45),0x9c822a32:fs(1.95),0x5a6ce323:[0xffffffff],0xc365b299:[0xdfffffff],0xb462820f:[0x40ffffff],0x2a0617ac:[0x00ffffff],0x82660d72:[texkey]}
                props.extend((m.crc('ucb_suction_core_flash') if t==0x1000c else k,t,flash.get(k,pv)) for k,t,pv in template)
                for i,event in enumerate((start,stop)):
                    props.extend([(m.crc(f'ucb_suction_ribbon_forward_{i}'),0x1000c,[m.EVENT_GROUP]),(0x939b68a0,0x201000c,[event]),(0x8541406c,0x201000c,[event]),(0x557c4b4d,0x201000c,[key])])
                block=m.node_properties(props)
            out.append(block)
        v=m.node_record(rh,out)
    nodes.append((nk,f,v))
assert seen==ins|outs;bank(p,14,nodes+[(key,0,m.node_record(h,child))]);newcb=m.package(raw,p);chk=entries(newcb)
assert all(chk[k]==v for k,v in entries(raw).items() if k not in (3,4,9,13,14));assert all(m.table(chk[14])[k]==v for k,v in n.items() if k!=root);assert all(m.table(chk[4])[k]==v for k,v in m.table(entries(raw)[4]).items())
(O/'g_cb.xbx').write_bytes(newcb);(O/'global.xbx').write_bytes(newglobal)
def sha(v):return hashlib.sha256(v).hexdigest()
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(newcb),old_global_sha=sha(gr),new_global_sha=sha(newglobal),ground_ribbons=6,flash_lifetime=.17,spin_mesh_unchanged=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
