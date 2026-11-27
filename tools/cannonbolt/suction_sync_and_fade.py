"""Match side intake to animated spike transforms, stretch audio, fade the release."""
import math,struct,sys,hashlib,json
from pathlib import Path
import numpy as np
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'suction-sync-fade';O.mkdir(exist_ok=True)
raw=(G/'g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(raw);u=(G/'g_ucb.xbx').read_bytes();assert u==(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes();up=entries(u)
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(a,s,rows):a[s]=m.build_vaps(s,struct.unpack_from('>H',a[s],12)[0],rows)
side=m.crc('ucb_suction_side_ribbons');root=m.effect_root('cannonbolt');start=m.crc('ucb_suction_vfx_start');flash=m.crc('ucb_suction_core_flash');flashstop=m.crc('ucb_suction_flash_fade_stop');ch=channel_records(p[9]);clips=m.table(p[13]);c=clips[0x754d9887]
def get(j):return ch[struct.unpack_from('>I',c,216+j*4)[0]]
def qmat(q):
    x,y,z,w=np.array(q,dtype=float)/np.linalg.norm(q);return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def readq(v):return [np.array((-x/32767,-y/32767,-z/32767,w/127)) for x,y,z,w,t in struct.iter_unpack('>3hbB',v[8:])]
def readp(v):return [np.array((x,y,z)) for t,x,y,z in struct.iter_unpack('>4f',v[8:])]
sk=m.table(p[12])[0x8b21e1f6];bind=[struct.unpack_from('>10f',sk,12+44*i) for i in (0,44)];bp0,bp1=bind
rb0=qmat([-x for x in bp0[:3]]+[bp0[3]]);rb1=qmat([-x for x in bp1[:3]]+[bp1[3]]);bindR=rb0@rb1;bindT=np.array(bp0[4:7])+rb0@np.array(bp1[4:7]);tipmid=np.array((0,.835,-.006));localmid=bindR.T@(tipmid-bindT);localaxis=bindR.T@np.array((1.,0,0))
q0,q1=readq(get(1)),readq(get(133));t0,t1=readp(get(0)),readp(get(132));assert len(q1)==len(t1)==61
points=[];quats=[]
for i in range(50):
    r0=qmat(q0[0]);r1=qmat(q1[i]);r=r0@r1;center=t0[0]+r0@t1[i]+r@localmid;axis=r@localaxis;axis/=np.linalg.norm(axis)
    # shortest quaternion from local +X to actual animated spike axis
    q=np.array((0.,-axis[2],axis[1],1+axis[0]));q/=np.linalg.norm(q);points.append((i*160,*center));quats.append(q)
assert all(abs(q[3])>.95 for q in quats)
print('tip midpoint first/last',points[0],points[-1]);track=[0x15,4+10*len(points),0x050ad001,(len(points)<<16)|len(points)]
for time,x,y,z in points:track.extend(fs(time)+[0]*6+fs(x,y,z))
curve=bytearray(struct.pack('>BBHHH',16,2,0x5002,len(quats),len(quats)))
for i,q in enumerate(quats):curve.extend(struct.pack('>3hbB',*(round(-v*32767) for v in q[:3]),round(q[3]*127),i))
curve=bytes(curve);bank(p,9,[(k,f,curve if k==side else v) for k,f,v in m.vaps_rows(p[9])]);nc=channel_records(p[9]);assert all(streamed_clip(v,ch)==streamed_clip(v,nc) for v in clips.values())
# Re-center the cone mesh at its actual spike midpoint; narrow throat meets
# the exported model's x=+/-1.145 spike tip rather than inside the cap.
rows=[]
for k,f,v in m.vaps_rows(p[4]):
    if k==side:
        at,vb,ib=m.mesh_buffers(v,xbox=True);q=bytearray(v)
        for i in range(0,len(vb),20):
            x,y,z,t,_=struct.unpack_from('>5f',vb,i);x=math.copysign(2.43-(2.43-1.145)*t,x);struct.pack_into('>3f',q,at+i,x,y-.82,z)
        v=bytes(q);assert m.mesh_buffers(v,xbox=True)[2]==ib
    rows.append((k,f,v))
bank(p,4,rows)
n=m.table(p[14]);nodes=[]
for k,f,v in m.vaps_rows(p[14]):
    if k in (root,side):
        h,b=m.node_parts(v);out=[]
        if k==side:h[19:26]=fs(3.0,-2.5,-.6,-.6,2.5,.6,.6)
        for block in b:
            if k==side and block[0]==0x15:block=track
            elif k==side and block[0]==0x16:words=list(struct.unpack(f'>{len(curve)//4}I',curve));block=[0x16,len(words)+2]+words
            elif k==root and block[0]==14:
                pp=[];group=None
                for pk,pt,pv in m.property_entries(block):
                    if pt==0x1000c:group=pk
                    if group==flash:pv={0xf7be9018:[flashstop],0x3de73088:fs(.64),0x9d762289:[1],0x118a27c7:fs(7.5),0x9c822a32:fs(8.0),0x5a6ce323:[0xffffffff],0xc365b299:[0xc4ffffff],0xb462820f:[0x35ffffff],0x2a0617ac:[0x00ffffff]}.get(pk,pv)
                    pp.append((pk,pt,pv))
                pp.extend([(m.crc('ucb_suction_flash_fade_timer'),0x1000c,[0x6ad0de1a]),(0x8ddaf3ee,0x201000c,[0]),(0x8541406c,0x201000c,[start]),(0x865f80c0,0x101000c,fs(2.31)),(0xd058515c,0x201000c,[flashstop])]);block=m.node_properties(pp)
            out.append(block)
        v=m.node_record(h,out)
    nodes.append((k,f,v))
bank(p,14,nodes);newcb=m.package(raw,p);check=entries(newcb);assert all(check[k]==v for k,v in entries(raw).items() if k not in (4,9,14));assert all(m.table(check[14])[k]==v for k,v in n.items() if k not in(root,side))
# Smoothly resample only the charge section, without repeating an impact.
# Keep the original final 0.32 seconds byte-for-byte and exactly 2s total.
br=m.vaps_rows(up[24]);fev=bytearray(br[0][2][32:]);f=br[1][2][32:];count,hs,ds=struct.unpack_from('<3I',f,4);headers=bytearray();data=bytearray();off=48+hs
for j in range(count):
    hdr=bytearray(f[48+j*80:48+(j+1)*80]);nn,size=struct.unpack_from('<2I',hdr,32);pcm=f[off:off+size];off+=size
    if j==15:
        assert nn==11840 and struct.unpack_from('<I',hdr,52)[0]==8000;x=np.array(struct.unpack(f'>{nn}h',pcm[:nn*2]),dtype=float);cut=9280;target=16000-(nn-cut);y=np.interp(np.linspace(0,cut-1,target),np.arange(cut),x[:cut]);y=np.concatenate((np.rint(y),x[cut:]));assert len(y)==16000 and np.array_equal(y[-(nn-cut):],x[cut:]);pcm=struct.pack('>16000h',*y.astype(int));pcm+=bytes((-len(pcm))%2048);struct.pack_into('<2I',hdr,32,len(y),len(pcm))
    headers.extend(hdr);data.extend(pcm)
assert off==len(f);fh=bytearray(f[:48]);struct.pack_into('<3I',fh,4,count,len(headers),len(data));fsb=bytes(fh+headers+data);marker=struct.pack('<I',8)+b'ucbpova\0';pos=fev.find(marker);hits=0
while pos>=0:
    a=pos+len(marker)
    if fev[:pos].endswith(b'.wav\0') and struct.unpack_from('<I',fev,a)[0]==15:struct.pack_into('<I',fev,a+4,2000);hits+=1
    pos=fev.find(marker,a)
assert hits;wrapper=bytearray(br[1][2][:32]);struct.pack_into('>I',wrapper,4,len(fsb));br[0]=(br[0][0],br[0][1],br[0][2][:32]+fev);br[1]=(br[1][0],br[1][1],bytes(wrapper)+fsb);bank(up,24,br);newu=m.package(u,up);assert all(entries(newu)[k]==v for k,v in entries(u).items() if k!=24)
(O/'g_cb.xbx').write_bytes(newcb);(O/'g_ucb.xbx').write_bytes(newu)
sha=lambda b:hashlib.sha256(b).hexdigest();report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(newcb),old_ucb_sha=sha(u),new_ucb_sha=sha(newu),spike_alignment_frames=len(points),audio_seconds=2.,flash_fade_seconds=.64,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
