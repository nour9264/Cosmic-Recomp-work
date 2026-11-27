"""Meteor ball lead-in, elevated steerable arc, and original FSB identity."""
import hashlib,json,math,struct,sys,wave
from pathlib import Path
from mathutils import Quaternion,Vector
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
H = WORK; I=APP_ROOT/'installation'; O=H/'meteor-air-control'; O.mkdir(exist_ok=True)
cb=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes(); ucb=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes(); ddf=(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
assert cb==(I/'game/global/g_cb.xbx').read_bytes() and ucb==(I/'game/global/g_ucb.xbx').read_bytes() and ddf==(I/'game/global/scripts/atk_ucb.ddf').read_bytes()
parts=entries(cb);rows=m.vaps_rows(parts[9]);oldch=channel_records(parts[9]);cliprows=m.vaps_rows(parts[13]);clips=m.table(parts[13]);key=0xd8baecc8;c=cliprows[next(i for i,(k,_,_) in enumerate(cliprows) if k==key)][2]
indexes=struct.unpack_from('>135I',c,216)
assert len(set(indexes))==135 and all(sum(struct.unpack_from('>I',v,i)[0]==ix for v in clips.values() for i in range(216,len(v),4))==1 for ix in indexes)
qbytes=oldch[indexes[1]];x,y,z,w,_=struct.unpack_from('>3hbB',qbytes,8);root=Quaternion((w/127,x/32767,y/32767,z/32767)).normalized().conjugated();up=root.inverted()@Vector((0,1,0))
start=Vector(struct.unpack_from('>3f',oldch[indexes[132]],12));n=45
# Smooth rise, brief targeting window, fast accelerating landing and settle.
points=[(0,0),(3,0),(6,.13),(10,.44),(15,.78),(19,.96),(22,1),(27,.98),(30,.93),(31,.85),(32,.70),(33,.46),(34,.24),(35,0),(36,.025),(38,0),(44,0)]
def height(i):
    for (a,x),(b,y) in zip(points,points[1:]):
        if a<=i<=b:return x+(y-x)*(i-a)/(b-a)
    raise ValueError(i)
for j,ix in enumerate(indexes):
    old=oldch[ix];kind,stride,tag,count,_=struct.unpack_from('>BBHHH',old)
    if j==132:
        p=bytearray(struct.pack('>BBHHH',1,4,0x5001,n,n))
        for i in range(n):p.extend(struct.pack('>4f',160*i,*(start+up*7.2*height(i))))
    else:
        assert count==2;p=bytearray(old)
        if kind==16:p[8+2*stride*4-1]=n-1
        else:struct.pack_into('>f',p,8+stride*4,(n-1)*160)
    rows[ix]=(rows[ix][0],rows[ix][1],bytes(p))
newclips=[]
for k,f,v in cliprows:
    if k==key:
        v=bytearray(v);struct.pack_into('>2f',v,64,0,(n-1)*160);v=bytes(v)
    newclips.append((k,f,v))
parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],rows);parts[13]=m.build_vaps(13,struct.unpack_from('>H',parts[13],12)[0],newclips)
newcb=m.package(cb,parts);check=entries(newcb);nc=m.table(check[13]);ch=channel_records(check[9]);assert animation_time_range(nc[key],ch)==(0,7040)
assert all(streamed_clip(v,oldch)==streamed_clip(nc[k],ch) for k,v in clips.items() if k!=key)
(O/'g_cb.xbx').write_bytes(newcb)
d=bytearray(ddf); count=0
for at in range(4,len(d),224):
    if struct.unpack_from('>I',d,at+160)[0]!=0xba93374a:continue
    assert struct.unpack_from('>I',d,at+32)[0]==key
    struct.pack_into('>3I',d,at+28,0x81d27700,key,0x6f97ed2d)
    # Actor moves on ground while the ball pose is lifted. This keeps the
    # projected ground position steerable; native damage remains intact.
    struct.pack_into('>f',d,at+52,1.6);struct.pack_into('>f',d,at+64,3.0);struct.pack_into('>I',d,at+100,0x41eb4);count+=1
assert count==3;(O/'atk_ucb.ddf').write_bytes(d)
# Reuse the first (audible but noisy) project's exact FSB identity/header,
# unlike the later silent trials that copied the transformation bank header.
first=(H/'remaining-candidate/g_ucb.xbx').read_bytes();bank=entries(first)[24];br=m.vaps_rows(bank);f=br[1][2][32:];num,hs,ds=struct.unpack_from('<3I',f,4);assert num==29 and hs==80*num
sourcecb=entries(cb)[24];stockfsb=m.vaps_rows(sourcecb)[1][2][32:]
assert f[16:48]==stockfsb[16:48]
clean=(H/'specials-refined/g_ucb.xbx').read_bytes();cleanfsb=m.vaps_rows(entries(clean)[24])[1][2][32:]
assert cleanfsb[:4]==b'FSB4'
fsb=bytearray(cleanfsb);fsb[16:48]=f[16:48]
assert fsb[16:48]==stockfsb[16:48]
wrapper=bytearray(br[1][2][:32]);struct.pack_into('>I',wrapper,4,len(fsb));br[1]=(br[1][0],br[1][1],bytes(wrapper)+fsb)
uparts=entries(ucb);assert 24 not in uparts;uparts[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],br);newu=m.package(ucb,uparts)
assert len(newu)<=len(first) and all(entries(newu)[k]==v for k,v in entries(ucb).items())
(O/'g_ucb.xbx').write_bytes(newu)
result=dict(old_cb=hashlib.sha256(cb).hexdigest(),old_ucb=hashlib.sha256(ucb).hexdigest(),old_attack=hashlib.sha256(ddf).hexdigest(),meteor_frames=n,meteor_height=7.2,steer_speed=1.6,original_fsb_identity=True,package_bytes=len(newu),gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
