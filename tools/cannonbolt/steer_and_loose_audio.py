"""Stationary rolling direction/steering plus independent loose FMOD bank."""
import hashlib,json,math,struct,sys
from pathlib import Path
from mathutils import Quaternion,Vector
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
H = WORK; I=APP_ROOT/'installation'; O=H/'steer-loose-audio'; O.mkdir(exist_ok=True)
cb=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes(); ucb=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes(); ddf=(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
assert cb==(I/'game/global/g_cb.xbx').read_bytes() and ucb==(I/'game/global/g_ucb.xbx').read_bytes() and ddf==(I/'game/global/scripts/atk_ucb.ddf').read_bytes()
parts=entries(cb);rows=m.vaps_rows(parts[9]); ch=channel_records(parts[9]);clips=m.table(parts[13]); key=0x754d9887;c=clips[key]
def idx(j):return struct.unpack_from('>I',c,216+j*4)[0]
def q0(j):
    x,y,z,w,_=struct.unpack_from('>3hbB',ch[idx(j)],8);return Quaternion((w/127,x/32767,y/32767,z/32767)).normalized().conjugated()
root=q0(1);ball=q0(133); n=46; irot=idx(133)
assert sum(struct.unpack_from('>I',v,i)[0]==irot for v in clips.values() for i in range(216,len(v),4))==1
knots=[(0,0),(5,.08),(14,.6),(29,2.1),(35,2.7),(39,3),(45,3)]
def turn(i):
    for (a,x),(b,y) in zip(knots,knots[1:]):
        if a<=i<=b:return x+(y-x)*(i-a)/(b-a)
    raise ValueError(i)
payload=bytearray(struct.pack('>BBHHH',16,2,0x5002,n,n));prev=None
for i in range(n):
    # Positive X in the game basis rolls toward +Z. The character remains
    # in place while the ball rolls forward; the sinking position is preserved.
    d=Quaternion(Vector((1,0,0)),2*math.pi*turn(i));q=(root.inverted()@d@root@ball).conjugated().normalized()
    if prev is not None and q.dot(prev)<0:q.negate()
    prev=q.copy();payload.extend(struct.pack('>3hbB',*(round(v*32767) for v in (q.x,q.y,q.z)),round(q.w*127),i))
assert len(payload)==len(ch[irot]); rows[irot]=(rows[irot][0],rows[irot][1],bytes(payload));parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],rows)
newcb=m.package(cb,parts); check=entries(newcb); nch=channel_records(check[9]); nc=m.table(check[13]);assert all(streamed_clip(v,ch)==streamed_clip(nc[k],nch) for k,v in clips.items() if k!=key)
assert all(check[k]==v for k,v in entries(cb).items() if k!=9)
(O/'g_cb.xbx').write_bytes(newcb)
d=bytearray(ddf);changed=0
for at in range(4,len(d),224):
    if struct.unpack_from('>I',d,at+160)[0]!=0x239a66f0:continue
    assert struct.unpack_from('>I',d,at+32)[0]==0x2d806255 and struct.unpack_from('>f',d,at+52)[0]==0
    struct.pack_into('>f',d,at+64,3.0);struct.pack_into('>I',d,at+100,0x41ebc);changed+=1
assert changed==3;(O/'atk_ucb.ddf').write_bytes(d)
# Restore the original character resource, so the high-quality 48 kHz
# independent project cannot exceed the character package's memory budget.
original=(H/'remaining-candidate/pre-install/vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes();assert 24 not in entries(original)
assert all(entries(ucb)[k]==v for k,v in entries(original).items());(O/'g_ucb.xbx').write_bytes(original)
bank=m.vaps_rows(entries(ucb)[24]);fev=bank[0][2][32:];assert fev[:4]==b'FEV1' and b'ucbpova' in fev
fsb=(H/'meteor-audio-fix/ucbpova.fsb').read_bytes();assert fsb[:4]==b'FSB4'
count,hs,ds=struct.unpack_from('<3I',fsb,4);assert count==29 and hs==80*count and 48+hs+ds==len(fsb)
for j in range(count):
    n,size,_,_,mode,rate=struct.unpack_from('<6I',fsb,48+j*80+32);assert size==n*2 and size%2048==0 and mode==0x131 and rate==48000
(O/'ucbpova.fev').write_bytes(fev);(O/'ucbpova.fsb').write_bytes(fsb)
r=dict(old_cb=hashlib.sha256(cb).hexdigest(),old_ucb=hashlib.sha256(ucb).hexdigest(),old_attack=hashlib.sha256(ddf).hexdigest(),steer_rows=changed,suction_forward_roll=True,source_audio='POE 48 kHz PCM',loose_project=True,original_model_package_restored=True,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
