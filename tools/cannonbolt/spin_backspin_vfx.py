"""Private UCB wind funnel and backspin debris, plus half-second Spin extension."""
import hashlib,json,math,struct,sys
from pathlib import Path
from mathutils import Quaternion
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
H = WORK;I=APP_ROOT/'installation';O=H/'spin-backspin-vfx';O.mkdir(exist_ok=True)
cb=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();ucb=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes();ddf=(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
assert cb==(I/'game/global/g_cb.xbx').read_bytes() and ucb==(I/'game/global/g_ucb.xbx').read_bytes() and ddf==(I/'game/global/scripts/atk_ucb.ddf').read_bytes()
parts=entries(cb);nodes=m.table(parts[14]);root=m.effect_root('cannonbolt');donor=nodes[0xf69eafe4];dh,db=m.node_parts(donor)
props=next(m.property_entries(b) for b in db if b[0]==0xe); groups=[]
for e in props:
    if e[1]==0x1000c:groups.append([])
    groups[-1].append(e)
assert len(groups)==3
def fw(x):return struct.unpack('>I',struct.pack('>f',x))[0]
def ev(move):return (m.crc('ucb_'+move+'_vfx_start'),m.crc('ucb_'+move+'_vfx_stop'))
newnodes=[]
def emitter(move,label,group,height,edits):
    key=m.crc('ucb_'+move+'_'+label);assert key not in nodes
    h=list(dh);h[0]=key;h[7:14]=[0,fw(height),0,0,0,0,fw(1)]
    start,stop=ev(move);p=[]
    for i,(k,t,v) in enumerate(groups[group]):
        v=list(v)
        if i==0:k=m.crc('ucb_'+move+'_'+label+'_particles')
        if k==0x8541406c:v=[start]
        elif k==0xf7be9018:v=[stop]
        elif k in edits:v=edits[k]
        p.append((k,t,v))
    node=m.node_record(h,[[0x08,3,root],m.node_properties(p)]);newnodes.append((key,0,node));return key
def floats(*v):return [fw(x) for x in v]
# Three stacked wind layers, rising and widening. Reuse original transparent
# dust sprite and additive blending, with alternating rotation and drift.
for i,(height,radius,size,spin) in enumerate(((.22,.65,.50,240),(1.05,1.10,.75,-280),(2.0,1.65,1.05,330))):
    emitter('spin',f'wind_{i}',2,height,{0x9d762289:[28],0xe7965460:floats(40),0x3de73088:floats(.7),0xf26fef6:floats(1.1),0x297c98f1:floats(spin),0x7cb5a078:floats(radius,.12,radius),0xd7943d68:floats(.8,.20,.8),0x7a76b57b:floats(0,1.1,0),0x118a27c7:floats(size),0x9c822a32:floats(size),0x5a6ce323:[0x60d9eaff],0xc365b299:[0x90e9f5ff],0xb462820f:[0x40d9eaff],0x2a0617ac:[0x00ffffff]})
# Original rock sprites, kicked up low with gravity. Dust hovers near the
# ground; each node has exclusive Ultimate start/stop events.
for i in (0,1):
    emitter('backspin',f'rock_{i}',i,.18,{0x9d762289:[20],0xe7965460:floats(24),0x3de73088:floats(.7),0xf26fef6:floats(5),0x297c98f1:floats(-190 if i==0 else 220),0x7cb5a078:floats(.95,.1,.95),0xd7943d68:floats(2.2,1.3,2.2),0x7a76b57b:floats(0,-8,0),0x118a27c7:floats(.28),0x9c822a32:floats(.28)})
emitter('backspin','ground_dust',2,.08,{0x9d762289:[24],0xe7965460:floats(35),0x7cb5a078:floats(1.15,.08,1.15),0xd7943d68:floats(1.4,.12,1.4),0x7a76b57b:floats(0,.4,0),0x118a27c7:floats(.55),0x9c822a32:floats(.55)})
# Add the new nodes to the inherited weapon root; ordinary event IDs remain
# untouched. New attack records fire both original and new event? Only the
# new visual event is selected, so existing shockwave must also hear it.
nr=m.vaps_rows(parts[14]); rh,rb=m.node_parts(nodes[root]);more=[k for k,_,_ in newnodes];newrb=[]
for b in rb:
    if b[0]==0x14:b=[0x14,3+b[2]+len(more),b[2]+len(more)]+b[3:]+more
    newrb.append(b)
# Clone each original damage/shockwave node for the new event, retaining its
# exact collision properties. This avoids changing normal CB's attack.
for move,slot in [('spin',0xcaf9c3c5),('backspin',0x239a66f0)]:
    oldkey=m.crc(f'cannonbolt_special_{slot:08x}_shockwave'); original=nodes[oldkey]; key=m.crc('ucb_'+move+'_shockwave');oldstart,oldstop=m.effect_events('cannonbolt',slot);start,stop=ev(move)
    h,b=m.node_parts(original);h[0]=key
    for block in b:
        if block[0]==0xe:
            p=m.property_entries(block);block[:]=m.node_properties([(k,t,[start if x==oldstart else stop if x==oldstop else x for x in v]) for k,t,v in p])
    newnodes.append((key,0,m.node_record(h,b)));q=next(b for b in newrb if b[0]==0x14);q.append(key);q[1]+=1;q[2]+=1
for i,(k,f,v) in enumerate(nr):
    if k==root:nr[i]=(k,f,m.node_record(rh,newrb))
nr+=newnodes;parts[14]=m.build_vaps(14,struct.unpack_from('>H',parts[14],12)[0],m.bucket_sorted(nr))
# Extend Spin's unique native animation by 15 keyframe intervals.
cr=m.vaps_rows(parts[13]);clips=m.table(parts[13]);rows=m.vaps_rows(parts[9]);oldch=channel_records(parts[9]);key=0xdb46cb2;clip=clips[key];indices=struct.unpack_from('>135I',clip,216);assert len(set(indices))==135
for j,ix in enumerate(indices):
    assert sum(struct.unpack_from('>I',v,a)[0]==ix for v in clips.values() for a in range(216,len(v),4))==1
    p=bytearray(oldch[ix]);kind,stride,tag,n,_=struct.unpack_from('>BBHHH',p)
    if j==133:
        assert n==83 and kind==16;qs=[]
        for x,y,z,w,f in struct.iter_unpack('>3hbB',p[8:]):qs.append(Quaternion((w/127,x/32767,y/32767,z/32767)).normalized())
        p=bytearray(struct.pack('>BBHHH',16,2,0x5002,98,98));prev=None
        for i in range(98):
            at=i*82/97;a=int(at);q=qs[a].slerp(qs[min(a+1,82)],at-a).normalized()
            if prev is not None and q.dot(prev)<0:q.negate()
            prev=q.copy();p.extend(struct.pack('>3hbB',*(round(v*32767) for v in(q.x,q.y,q.z)),round(q.w*127),i))
    else:
        assert n==2
        if kind==16:p[-1]=97
        else:struct.pack_into('>f',p,8+stride*4,97*160)
    rows[ix]=(rows[ix][0],rows[ix][1],bytes(p))
for i,(k,f,v) in enumerate(cr):
    if k==key:
        c=bytearray(v);struct.pack_into('>2f',c,64,0,97*160);cr[i]=(k,f,bytes(c))
parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],rows);parts[13]=m.build_vaps(13,struct.unpack_from('>H',parts[13],12)[0],cr);newcb=m.package(cb,parts);check=entries(newcb);nch=channel_records(check[9]);nc=m.table(check[13]);assert animation_time_range(nc[key],nch)==(0,97*160)
assert all(streamed_clip(v,oldch)==streamed_clip(nc[k],nch) for k,v in clips.items() if k!=key)
assert all(m.table(check[14])[k]==v for k,v in nodes.items() if k!=root)
(O/'g_cb.xbx').write_bytes(newcb)
d=bytearray(ddf);count=0
for at in range(4,len(d),224):
    slot=struct.unpack_from('>I',d,at+160)[0]
    if slot in (0xcaf9c3c5,0x239a66f0):struct.pack_into('>2I',d,at+144,*ev('spin' if slot==0xcaf9c3c5 else 'backspin'));count+=1
assert count==6;(O/'atk_ucb.ddf').write_bytes(d)
# Extend the already-approved BE PCM by a half-second overlap-add of the
# middle of the original spinning texture; keep all other samples exact.
up=entries(ucb);bank=up[24];br=m.vaps_rows(bank);fev=bytearray(br[0][2][32:]);f=br[1][2][32:];n,hs,ds=struct.unpack_from('<3I',f,4);assert n==29 and hs==80*n
headers=bytearray();data=bytearray();off=48+hs
for j in range(n):
    h=bytearray(f[48+j*80:48+(j+1)*80]);samples,size=struct.unpack_from('<2I',h,32);pcm=f[off:off+size];off+=size
    if j in (6,7):
        x=list(struct.unpack(f'>{samples}h',pcm[:samples*2]));start=samples//2;overlap=160;insert=x[start:start+4000+overlap];assert len(insert)==4160
        prefix=x[:start];suffix=x[start:];blend=[round(insert[-overlap+i]*(1-i/overlap)+suffix[i]*(i/overlap)) for i in range(overlap)];y=prefix+insert[:-overlap]+blend+suffix[overlap:];assert len(y)==samples+4000
        pcm=struct.pack(f'>{len(y)}h',*y);pcm+=bytes((-len(pcm))%2048);struct.pack_into('<2I',h,32,len(y),len(pcm))
    headers.extend(h);data.extend(pcm)
assert off==len(f);head=bytearray(f[:48]);struct.pack_into('<3I',head,4,n,len(headers),len(data));fsb=bytes(head+headers+data)
marker=struct.pack('<I',8)+b'ucbpova\0';pos=fev.find(marker);hits=0
while pos>=0:
    a=pos+len(marker)
    if fev[:pos].endswith(b'.wav\0') and struct.unpack_from('<I',fev,a)[0] in (6,7):
        ms=struct.unpack_from('<I',fev,a+4)[0];struct.pack_into('<I',fev,a+4,ms+500);hits+=1
    pos=fev.find(marker,a)
assert hits>=1
w=bytearray(br[1][2][:32]);struct.pack_into('>I',w,4,len(fsb));br[0]=(br[0][0],br[0][1],br[0][2][:32]+fev);br[1]=(br[1][0],br[1][1],bytes(w)+fsb);up[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],br);newu=m.package(ucb,up)
assert len(newu)<=(H/'remaining-candidate/g_ucb.xbx').stat().st_size and all(entries(newu)[k]==v for k,v in entries(ucb).items() if k!=24)
(O/'g_ucb.xbx').write_bytes(newu)
report=dict(old_cb=hashlib.sha256(cb).hexdigest(),old_ucb=hashlib.sha256(ucb).hexdigest(),old_attack=hashlib.sha256(ddf).hexdigest(),new_visual_nodes=len(newnodes),spin_frames=98,spin_audio_extension_ms=500,attack_rows=count,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
