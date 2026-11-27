"""Extend suction charge by 15 frames; remove mouth puffs; add expanding release ring."""
import math,struct,sys,hashlib,json
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'suction-extended-release';O.mkdir(exist_ok=True)
raw=(G/'g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(raw);u=(G/'g_ucb.xbx').read_bytes();assert u==(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes();up=entries(u)
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(a,s,rows):a[s]=m.build_vaps(s,struct.unpack_from('>H',a[s],12)[0],rows)
root=m.effect_root('cannonbolt');side=m.crc('ucb_suction_side_ribbons');ground=m.crc('ucb_suction_ground_ribbons');ring=m.crc('ucb_suction_release_ring');start=m.crc('ucb_suction_vfx_start');blast=m.crc('ucb_suction_release');ringstop=m.crc('ucb_suction_ring_stop')
oldch=channel_records(p[9]);clips=m.table(p[13]);key=0x754d9887;c=clips[key];assert animation_time_range(c,oldch)==(0,7200);ix=struct.unpack_from('>135I',c,216);assert len(set(ix))==135
rows=m.vaps_rows(p[9]);end=9600
for i,idx in enumerate(ix):
    v=bytearray(rows[idx][2]);kind,stride,tag,n,_=struct.unpack_from('>BBHHH',v)
    if n==46:
        if kind==1:
            data=list(struct.iter_unpack('>4f',v[8:]));buf=bytearray(struct.pack('>BBHHH',kind,stride,tag,61,61))
            for j in range(61):
                at=j*35/50 if j<=50 else j-15;a=int(at);b=min(45,a+1);t=at-a;buf.extend(struct.pack('>4f',j*160,*(data[a][k]*(1-t)+data[b][k]*t for k in (1,2,3))))
        else:
            assert kind==16;data=list(struct.iter_unpack('>3hbB',v[8:]));buf=bytearray(struct.pack('>BBHHH',kind,stride,tag,61,61))
            for j in range(61):
                at=j*35/50 if j<=50 else j-15;a=int(at);b=min(45,a+1);t=at-a;qa=[data[a][k]/(127 if k==3 else 32767) for k in range(4)];qb=[data[b][k]/(127 if k==3 else 32767) for k in range(4)];dot=sum(x*y for x,y in zip(qa,qb));qb=[-x for x in qb] if dot<0 else qb;q=[x*(1-t)+y*t for x,y in zip(qa,qb)];norm=math.sqrt(sum(x*x for x in q));buf.extend(struct.pack('>3hbB',*(round(max(-1,min(1,x/norm))*32767) for x in q[:3]),round(max(-1,min(1,q[3]/norm))*127),j))
        v=buf
    else:
        assert n==2
        if kind==16:v[-1]=60
        else:struct.pack_into('>f',v,8+stride*4,end)
    rows[idx]=(rows[idx][0],rows[idx][1],bytes(v))
fi=struct.unpack_from('>I',c,80)[0];flags=m.flag_frames(oldch[fi]);flags[-1][0]=fs(end-160)[0];rows[fi]=(rows[fi][0],rows[fi][1],m.flag_channel(flags))
cr=[]
for k,f,v in m.vaps_rows(p[13]):
    if k==key:q=bytearray(v);struct.pack_into('>2f',q,64,0,end);v=bytes(q)
    cr.append((k,f,v))
bank(p,13,cr)
# Extend the ground rotation and side child tracks with the same charge timing.
curves={}
for key_,count in ((ground,50),(side,2)):
    v=bytearray(struct.pack('>BBHHH',16,2,0x5002,count,count))
    for j in range(count):
        frame=j if key_==ground else j*49;angle=-math.tau*.85*frame/30 if key_==ground else 0
        v.extend(struct.pack('>3hbB',0,round(32767*math.sin(angle/2)),0,round(127*math.cos(angle/2)),frame))
    curves[key_]=bytes(v)
bank(p,9,[(k,f,curves.get(k,v)) for k,f,v in rows]);nc=channel_records(p[9]);assert animation_time_range(m.table(p[13])[key],nc)==(0,end);assert all(streamed_clip(v,oldch)==streamed_clip(m.table(p[13])[k],nc) for k,v in clips.items() if k!=key)
# Build a transparent 3D annulus, expanding from the ball at release.
verts=[];indices=[];colors=[]
for j in range(49):
    a=math.tau*j/48
    for i in range(5):
        t=i/4;r=.74+.26*t;verts.append((r*math.cos(a),.10,r*math.sin(a),j/12,t));alpha=round(190*math.sin(math.pi*t)**.65);colors.append(bytes((alpha,230,242,255)))
for j in range(48):
    for i in range(4):
        a=j*5+i;b=a+5;c=a+1;d=b+1;indices.extend((a,b,c,b,d,c,c,b,a,c,d,b))
vb=b''.join(struct.pack('>5f',*v) for v in verts);ib=struct.pack(f'>{len(indices)}H',*indices);donor=m.table(p[4])[ground];at,_,_=m.mesh_buffers(donor,xbox=True);head=bytearray(donor[:at]);meta=struct.unpack_from('<I',head,28)[0];ia=(at+len(vb)+31)&~31
struct.pack_into('>I',head,4,len(verts));struct.pack_into('>I',head,16,len(indices));struct.pack_into('<I',head,20,meta+ia-376);struct.pack_into('>I',head,384,(len(indices)<<16)|(struct.unpack_from('>I',head,384)[0]&0xffff));mesh=bytes(head)+vb+bytes(ia-at-len(vb))+ib;assert m.mesh_buffers(mesh,xbox=True)==(at,vb,ib)
col=bytearray(m.table(p[3])[ground][:32]);struct.pack_into('>I',col,8,ring);bank(p,4,m.bucket_sorted(m.vaps_rows(p[4])+[(ring,at//32,mesh)]));bank(p,3,m.bucket_sorted(m.vaps_rows(p[3])+[(ring,1,bytes(col)+b''.join(colors))]))
n=m.table(p[14]);h,b=m.node_parts(n[ground]);h[0]=ring;h[19:26]=fs(4.5,-4.3,0,-4.3,4.3,.3,4.3);child=[];pullstop=m.crc('ucb_suction_pull_stop')
# Scale track matches the native Chromastone effect format.
scale=[0x19,24,0x0d0a5003,0x00020002]+fs(0)+[0]*6+fs(.95,1,.95)+fs(1248)+[0]*6+fs(3.9,1,3.9)
for block in b:
    if block[0]==0x16:continue
    if block[0]==0:block=[0,4,ring,ring]
    if block[0]==14:
        pp=[];group=None
        for k,t,v in m.property_entries(block):
            if t==0x1000c:group=k
            v=[blast if x==start else ringstop if x==pullstop else x for x in v]
            if group==0xe16f3a56 and k in (0x5e0393bd,0xf465b2b5):v=fs(.29)
            pp.append((k,t,v))
        block=m.node_properties(pp)
    child.append(block)
child.insert(0,scale)
sidegroups={m.crc(f'ucb_suction_side_{s}') for s in (-1,1)};timers={m.crc('ucb_suction_'+k) for k in ('pull_end','release','burst_end','cleanup')};nodes=[]
for k,f,v in m.vaps_rows(p[14]):
    if k in (root,side,ground):
        nh,bl=m.node_parts(v);out=[]
        for block in bl:
            if k==root and block[0]==0x14:block=[0x14,block[1]+1,block[2]+1]+block[3:]+[ring]
            elif k in curves and block[0]==0x16:words=list(struct.unpack(f'>{len(curves[k])//4}I',curves[k]));block=[0x16,len(words)+2]+words
            elif k==side and block[0]==0x15:
                block=list(block)
                for i in range(4,len(block),10):block[i]=fs(struct.unpack('>f',struct.pack('>I',block[i]))[0]*50/35)[0]
            elif block[0]==14:
                pp=[];group=None
                for pk,pt,pv in m.property_entries(block):
                    if pt==0x1000c:group=pk
                    if k==side and group in sidegroups:continue # remove mouth smoke entirely
                    if k==root and group in timers and pk==0x865f80c0:pv=fs(struct.unpack('>f',struct.pack('>I',pv[0]))[0]+.5)
                    if k in (side,ground) and group==0xe16f3a56 and pk in (0x5e0393bd,0xf465b2b5):pv=fs(1.67)
                    if k==root and group==m.crc('ucb_suction_core_flash'):pv={0x118a27c7:fs(2.55),0x9c822a32:fs(3.0),0x3de73088:fs(.20)}.get(pk,pv)
                    pp.append((pk,pt,pv))
                if k==root:
                    for i,event in enumerate((blast,ringstop)):pp.extend([(m.crc(f'ucb_suction_ring_forward_{i}'),0x1000c,[m.EVENT_GROUP]),(0x939b68a0,0x201000c,[event]),(0x8541406c,0x201000c,[event]),(0x557c4b4d,0x201000c,[ring])])
                    pp.extend([(m.crc('ucb_suction_ring_timer'),0x1000c,[0x6ad0de1a]),(0x8ddaf3ee,0x201000c,[0]),(0x8541406c,0x201000c,[start]),(0x865f80c0,0x101000c,fs(1.96)),(0xd058515c,0x201000c,[ringstop])])
                block=m.node_properties(pp)
            out.append(block)
        v=m.node_record(nh,out)
    nodes.append((k,f,v))
bank(p,14,m.bucket_sorted(nodes+[(ring,0,m.node_record(h,child))]));newcb=m.package(raw,p)
# Preserve original PCM release; overlap-add half a second of charge audio
# in the middle of the existing 8kHz BE mono sample (slot 15).
br=m.vaps_rows(up[24]);fev=bytearray(br[0][2][32:]);f=br[1][2][32:];count,hs,ds=struct.unpack_from('<3I',f,4);assert count==29 and hs==80*count;headers=bytearray();data=bytearray();off=48+hs
for j in range(count):
    hdr=bytearray(f[48+j*80:48+(j+1)*80]);n,size=struct.unpack_from('<2I',hdr,32);pcm=f[off:off+size];off+=size
    if j==15:
        assert struct.unpack_from('<I',hdr,52)[0]==8000;x=list(struct.unpack(f'>{n}h',pcm[:n*2]));pos=5600;overlap=160;insert=x[1440:1440+4320];assert len(insert)==4320
        pre=x[:pos];tail=x[pos:];intro=[round(pre[-overlap+i]*(1-i/overlap)+insert[i]*i/overlap) for i in range(overlap)];outro=[round(insert[-overlap+i]*(1-i/overlap)+tail[i]*i/overlap) for i in range(overlap)];y=pre[:-overlap]+intro+insert[overlap:-overlap]+outro+tail[overlap:];assert len(y)==n+4000
        pcm=struct.pack(f'>{len(y)}h',*y);pcm+=bytes((-len(pcm))%2048);struct.pack_into('<2I',hdr,32,len(y),len(pcm))
    headers.extend(hdr);data.extend(pcm)
assert off==len(f);fh=bytearray(f[:48]);struct.pack_into('<3I',fh,4,count,len(headers),len(data));fsb=bytes(fh+headers+data);marker=struct.pack('<I',8)+b'ucbpova\0';pos=fev.find(marker);hits=0
while pos>=0:
    a=pos+len(marker)
    if fev[:pos].endswith(b'.wav\0') and struct.unpack_from('<I',fev,a)[0]==15:struct.pack_into('<I',fev,a+4,struct.unpack_from('<I',fev,a+4)[0]+500);hits+=1
    pos=fev.find(marker,a)
assert hits>=1;wrapper=bytearray(br[1][2][:32]);struct.pack_into('>I',wrapper,4,len(fsb));br[0]=(br[0][0],br[0][1],br[0][2][:32]+fev);br[1]=(br[1][0],br[1][1],bytes(wrapper)+fsb);bank(up,24,br);newu=m.package(u,up);assert all(entries(newu)[k]==v for k,v in entries(u).items() if k!=24)
(O/'g_cb.xbx').write_bytes(newcb);(O/'g_ucb.xbx').write_bytes(newu)
def sha(v):return hashlib.sha256(v).hexdigest()
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(newcb),old_ucb_sha=sha(u),new_ucb_sha=sha(newu),duration_seconds=2.0,audio_extension_ms=500,release_seconds=50/30,mouth_smoke_removed=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
