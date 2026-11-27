"""Weighted Meteor impact and isolated Xbox event PCM endian trial."""
import hashlib,json,struct,sys
from pathlib import Path
from mathutils import Quaternion,Vector
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
H = WORK; I=APP_ROOT/'installation'; O=H/'meteor-fast-slam-audio-endian'; O.mkdir(exist_ok=True)
cb=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes(); ucb=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes()
assert cb==(I/'game/global/g_cb.xbx').read_bytes() and ucb==(I/'game/global/g_ucb.xbx').read_bytes()
parts=entries(cb);rows=m.vaps_rows(parts[9]);oldch=channel_records(parts[9]);clips=m.table(parts[13]);key=0xd8baecc8;c=clips[key];idx=struct.unpack_from('>I',c,216+132*4)[0]
assert sum(struct.unpack_from('>I',v,i)[0]==idx for v in clips.values() for i in range(216,len(v),4))==1
old=oldch[idx]; samples=list(struct.iter_unpack('>4f',old[8:]));assert len(samples)==45
start=samples[0][1:];apex=samples[22][1:];p=bytearray(old)
# Preserve timing, accelerate into contact, then give the ball a small
# weighted recoil. No global animation-speed adjustment.
factors={28:.98,29:.98,30:1,31:.96,32:.84,33:.63,34:.34,35:0,36:0,37:.018,38:.012,39:0}
for i,f in factors.items():struct.pack_into('>4f',p,8+i*16,i*160,*(a+(b-a)*f for a,b in zip(start,apex)))
rows[idx]=(rows[idx][0],rows[idx][1],bytes(p))
def q0(j):
    x,y,z,w,_=struct.unpack_from('>3hbB',oldch[struct.unpack_from('>I',c,216+j*4)[0]],8)
    return Quaternion((w/127,x/32767,y/32767,z/32767)).normalized().conjugated()
vertical=(q0(1)@q0(133)).inverted()@Vector((0,1,0));axis=max(range(3),key=lambda k:abs(vertical[k]))
scaleidx=struct.unpack_from('>I',c,216+134*4)[0]
assert sum(struct.unpack_from('>I',v,i)[0]==scaleidx for v in clips.values() for i in range(216,len(v),4))==1
base=struct.unpack_from('>3f',oldch[scaleidx],12); sp=bytearray(struct.pack('>BBHHH',12,4,0x5003,45,45))
deform={34:1.06,35:.80,36:.88,37:1.06,38:1.025}
for i in range(45):
    vert=deform.get(i,1);side=(1/vert)**.5
    sp.extend(struct.pack('>4f',160*i,*(v*(vert if j==axis else side) for j,v in enumerate(base))))
rows[scaleidx]=(rows[scaleidx][0],rows[scaleidx][1],bytes(sp))
parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],rows);newcb=m.package(cb,parts);check=entries(newcb);newch=channel_records(check[9]);nc=m.table(check[13]);assert all(streamed_clip(v,oldch)==streamed_clip(nc[k],newch) for k,v in clips.items() if k!=key)
(O/'g_cb.xbx').write_bytes(newcb)
# Keep FEV and FSB identity, offsets, sample lengths, PCM header and size
# identical. Only swap each 16-bit sample for the Xbox SFX PCM path.
parts=entries(ucb);bank=parts[24];r=m.vaps_rows(bank);old=r[1][2][32:];count,hs,ds=struct.unpack_from('<3I',old,4);assert count==29 and hs==80*count and len(old)==48+hs+ds
fsb=bytearray(old);start=48+hs;at=start
for j in range(count):
    n,size,_,_,mode,rate=struct.unpack_from('<6I',old,48+j*80+32);assert mode==0x131 and size%2048==0 and n*2<=size
    data=old[at:at+size];swap=bytearray(size);swap[::2]=data[1::2];swap[1::2]=data[::2];fsb[at:at+size]=swap;at+=size
assert at==len(old) and fsb[:start]==old[:start]
r[1]=(r[1][0],r[1][1],r[1][2][:32]+fsb);parts[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],r);newu=m.package(ucb,parts);assert len(newu)==len(ucb) and all(entries(newu)[k]==v for k,v in entries(ucb).items() if k!=24)
(O/'g_ucb.xbx').write_bytes(newu)
report=dict(old_cb=hashlib.sha256(cb).hexdigest(),old_ucb=hashlib.sha256(ucb).hexdigest(),slam_frames=5,contact_squash=.8,animation_speed_unchanged=True,pcm_byte_order='big-endian trial',package_bytes=len(newu),gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
