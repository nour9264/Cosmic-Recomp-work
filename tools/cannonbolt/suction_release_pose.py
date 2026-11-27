"""Append the native Cannonbolt superball unroll/release pose to the POE attack."""
import sys,struct,hashlib,json
from pathlib import Path
import numpy as np
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
H = WORK;I=APP_ROOT/'installation';O=H/'suction-release-pose';O.mkdir(exist_ok=True)
raw=(I/'game/global/g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();assert hashlib.sha256(raw).hexdigest()=='b9780292b573ba923c96e55098c091583bb62d5f99d8fae56ba7e437d350cb04';p=entries(raw);old=entries(raw);rows=m.vaps_rows(p[9]);ch=channel_records(p[9]);clips=m.table(p[13]);key=0x754d9887;donor=0x055ebd1f;c=clips[key];src=clips[donor];assert m.bone_ids(c)==m.bone_ids(src)
idx=struct.unpack_from('>135I',c,216);ix=struct.unpack_from('>135I',src,216);assert len(set(idx))==135
def samples(v):
    kind,stride,tag,n,_=struct.unpack_from('>BBHHH',v)
    if kind==16:
        data=[(t*160,np.array((x/32767,y/32767,z/32767,w/127))) for x,y,z,w,t in struct.iter_unpack('>3hbB',v[8:])]
        data=[(t,q/np.linalg.norm(q)) for t,q in data]
    else:data=[(t,np.array((x,y,z))) for t,x,y,z in struct.iter_unpack('>4f',v[8:])]
    assert len(data)==n
    return kind,stride,tag,data
def sample(data,t,q):
    if t<=data[0][0]:return data[0][1].copy()
    for (a,x),(b,y) in zip(data,data[1:]):
        if t<=b:
            if b==a:return y.copy()
            f=(t-a)/(b-a);y=-y if q and np.dot(x,y)<0 else y;r=x*(1-f)+y*f;return r/np.linalg.norm(r) if q else r
    return data[-1][1].copy()
# The source game switches from the ball to the body at 10399 ticks.
# Keep the entire charge and release, then play its native release recovery.
switch=54;frames=82;source_start=10400
for j,i in enumerate(idx):
    assert sum(struct.unpack_from('>I',v,o)[0]==i for v in clips.values() for o in range(216,len(v),4))==1
    kind,stride,tag,a=samples(ch[i]);sk,ss,st,b=samples(ch[ix[j]]);assert (kind,stride,tag)==(sk,ss,st);data=[]
    for frame in range(frames):
        if frame<switch:val=sample(a,frame*160,kind==16)
        else:
            val=sample(b,source_start+(frame-switch)*160,kind==16)
            if j==0:
                # The stock animation has a big jump; keep this release grounded.
                base=sample(a,(switch-1)*160,False);val=np.array((base[0],base[1]+max(0,min(.30,(val[1]-.45)*.20)),base[2]))
            if j==5:val=np.ones(3)
            if j==134:val=np.ones(3)*.0001
        if kind==16 and data and np.dot(data[-1],val)<0:val=-val
        data.append(val)
    v=bytearray(struct.pack('>BBHHH',kind,stride,tag,frames,frames))
    for f,x in enumerate(data):
        if kind==16:v.extend(struct.pack('>3hbB',*(round(a*32767) for a in x[:3]),round(x[3]*127),f))
        else:v.extend(struct.pack('>4f',f*160,*x))
    rows[i]=(rows[i][0],rows[i][1],bytes(v))
p[9]=m.build_vaps(9,struct.unpack_from('>H',p[9],12)[0],rows);cr=[]
for k,f,v in m.vaps_rows(p[13]):
    if k==key:q=bytearray(v);struct.pack_into('>2f',q,64,0,(frames-1)*160);v=bytes(q)
    cr.append((k,f,v))
p[13]=m.build_vaps(13,struct.unpack_from('>H',p[13],12)[0],cr);new=m.package(raw,p);check=entries(new);nc=channel_records(check[9]);assert all(streamed_clip(v,ch)==streamed_clip(m.table(check[13])[k],nc) for k,v in clips.items() if k!=key);assert all(check[k]==v for k,v in old.items() if k not in (9,13));assert struct.unpack_from('>I',m.table(check[13])[key],80)[0]==struct.unpack_from('>I',c,80)[0]
(O/'g_cb.xbx').write_bytes(new);report=dict(old_cb_sha=hashlib.sha256(raw).hexdigest(),new_cb_sha=hashlib.sha256(new).hexdigest(),release_frame=switch,total_frames=frames,stock_recovery_source='superball_01',gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
