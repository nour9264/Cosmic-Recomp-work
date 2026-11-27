"""Boost the verified big-endian attack PCM and strengthen Meteor contact."""
import hashlib,json,math,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
H = WORK; I=APP_ROOT/'installation'; O=H/'louder-weighted-impact'; O.mkdir(exist_ok=True)
cb=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes(); ucb=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes()
assert cb==(I/'game/global/g_cb.xbx').read_bytes() and ucb==(I/'game/global/g_ucb.xbx').read_bytes()
parts=entries(cb);rows=m.vaps_rows(parts[9]);oldch=channel_records(parts[9]);clips=m.table(parts[13]);key=0xd8baecc8;c=clips[key]
def ci(j):return struct.unpack_from('>I',c,216+j*4)[0]
def setchannel(idx,p):
    assert sum(struct.unpack_from('>I',v,i)[0]==idx for v in clips.values() for i in range(216,len(v),4))==1
    rows[idx]=(rows[idx][0],rows[idx][1],bytes(p))
idx=ci(132);old=oldch[idx];s=list(struct.iter_unpack('>4f',old[8:]));assert len(s)==45
start=s[0][1:];apex=s[22][1:];p=bytearray(old)
factors={30:1,31:.98,32:.89,33:.68,34:.40,35:0,36:0,37:.028,38:.012,39:0}
for i,f in factors.items():struct.pack_into('>4f',p,8+i*16,i*160,*(a+(b-a)*f for a,b in zip(start,apex)))
setchannel(idx,p)
idx=ci(134);old=oldch[idx];s=list(struct.iter_unpack('>4f',old[8:]));assert len(s)==45
axis=min(range(3),key=lambda j:s[35][j+1]/s[0][j+1]);base=s[0][1:];p=bytearray(old)
for i,vert in {34:1.10,35:.65,36:.79,37:1.12,38:1.04,39:1}.items():
    side=math.sqrt(1/vert);struct.pack_into('>4f',p,8+i*16,i*160,*(v*(vert if j==axis else side) for j,v in enumerate(base)))
setchannel(idx,p);parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],rows);newcb=m.package(cb,parts);check=entries(newcb);nch=channel_records(check[9]);nc=m.table(check[13]);assert all(streamed_clip(v,oldch)==streamed_clip(nc[k],nch) for k,v in clips.items() if k!=key)
(O/'g_cb.xbx').write_bytes(newcb)
# Preserve the successful SFX byte order and native project GUID/header.
# Soft saturation raises average loudness without hard clipping peaks.
parts=entries(ucb);bank=parts[24];r=m.vaps_rows(bank);old=r[1][2][32:];count,hs,ds=struct.unpack_from('<3I',old,4);assert count==29 and hs==80*count
fsb=bytearray(old);at=48+hs;stats=[]
for j in range(count):
    n,size=struct.unpack_from('<2I',old,48+j*80+32);assert n*2<=size and size%2048==0
    if j in (6,7,8,9,14,15):
        x=struct.unpack(f'>{n}h',old[at:at+2*n]);rms=lambda v:math.sqrt(sum(a*a for a in v)/len(v));before=rms(x)
        target=15000 if j==14 else 13500;lo,hi=1.,8.
        for _ in range(20):
            gain=(lo+hi)/2;y=[31500*math.tanh(gain*v/31500) for v in x]
            if rms(y)<target:lo=gain
            else:hi=gain
        y=[round(31500*math.tanh(hi*v/31500)) for v in x];assert max(map(abs,y))<32767
        fsb[at:at+2*n]=struct.pack(f'>{n}h',*y);stats.append(dict(slot=j,boost_db=round(20*math.log10(rms(y)/before),1),peak=max(map(abs,y))))
    at+=size
assert at==len(old) and fsb[:48+hs]==old[:48+hs]
r[1]=(r[1][0],r[1][1],r[1][2][:32]+fsb);parts[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],r);newu=m.package(ucb,parts);assert len(newu)==len(ucb) and all(entries(newu)[k]==v for k,v in entries(ucb).items() if k!=24)
(O/'g_ucb.xbx').write_bytes(newu)
report=dict(old_cb=hashlib.sha256(cb).hexdigest(),old_ucb=hashlib.sha256(ucb).hexdigest(),audio=stats,impact_squash=.65,animation_speed_unchanged=True,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
