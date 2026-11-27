"""Revise UCB locomotion/ball poses and restore retail FSB sample alignment."""
import hashlib,json,math,struct,sys,wave
from pathlib import Path
from mathutils import Quaternion,Vector
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
H = WORK; I=APP_ROOT/'installation'; O=H/'specials-refined'; O.mkdir(exist_ok=True)
keys={'backspin':0x2d806255,'suction':0x754d9887,'meteor':0xd8baecc8}
cb=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes(); ucb=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes(); ddf=(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
assert cb==(I/'game/global/g_cb.xbx').read_bytes() and ucb==(I/'game/global/g_ucb.xbx').read_bytes() and ddf==(I/'game/global/scripts/atk_ucb.ddf').read_bytes()
parts=entries(cb); rows=m.vaps_rows(parts[9]); oldch=channel_records(parts[9]); clips=m.table(parts[13]); report=[]
def getidx(c,j):return struct.unpack_from('>I',c,216+j*4)[0]
def pose_q(c):
    x,y,z,w,_=struct.unpack_from('>3hbB',c,8);return Quaternion((w/127,x/32767,y/32767,z/32767)).normalized().conjugated()
def revise(c,j,payload):
    idx=getidx(c,j);assert sum(getidx(v,i)==idx for v in clips.values() for i in range((len(v)-216)//4))==1
    k,f,_=rows[idx];rows[idx]=(k,f,bytes(payload))
def curve(points,i):
    for (a,u),(b,v) in zip(points,points[1:]):
        if a<=i<=b:return u+(v-u)*(i-a)/(b-a)
    raise ValueError(i)
for kind,key in keys.items():
    c=clips[key]; _,end=animation_time_range(c,oldch);n=int(end/160)+1
    root=pose_q(oldch[getidx(c,1)]); ball=pose_q(oldch[getidx(c,133)])
    start=Vector(struct.unpack_from('>3f',oldch[getidx(c,132)],12)); up=root.inverted()@Vector((0,1,0))
    if kind=='meteor':
        # Raise to 4.7 game units, accelerate down and stop at the floor.
        h=[(0,0),(3,0),(6,.16),(10,.58),(13,.87),(16,1),(19,1),(20,.95),(21,.82),(22,.59),(23,.32),(24,0),(26,0),(35,0)]; angle=None
    elif kind=='suction':
        # Curl already comes from the native ball pose. Sink progressively,
        # spin around vertical, then release upward just before the finish.
        h=[(0,0),(5,-.03),(14,-.12),(29,-.22),(35,-.22),(38,.13),(41,0),(45,0)]
        angle=[(0,0),(5,.08),(14,.6),(29,2.1),(35,2.7),(39,3),(45,3)]; axis=Vector((0,1,0))
    else:
        # Counter-roll about the lateral axis, not a forward locomotion clip.
        h=[(0,0),(57,0)];angle=[(0,0),(6,.1),(17,.65),(40,2.6),(51,3),(57,3)];axis=Vector((-1,0,0))
    pos=bytearray(struct.pack('>BBHHH',1,4,0x5001,n,n))
    for i in range(n):pos.extend(struct.pack('>4f',i*160,*(start+up*curve(h,i)*(4.7 if kind=='meteor' else 1))))
    revise(c,132,pos)
    if angle:
        rot=bytearray(struct.pack('>BBHHH',16,2,0x5002,n,n));prev=None
        for i in range(n):
            delta=Quaternion(axis,2*math.pi*curve(angle,i)); q=(root.inverted()@delta@root@ball).conjugated().normalized()
            if prev is not None and q.dot(prev)<0:q.negate()
            prev=q.copy();rot.extend(struct.pack('>3hbB',*(round(v*32767) for v in (q.x,q.y,q.z)),round(q.w*127),i))
        revise(c,133,rot)
    report.append(dict(move=kind,frames=n))
parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],rows); newcb=m.package(cb,parts); check=entries(newcb); nch=channel_records(check[9]); nc=m.table(check[13])
assert all(streamed_clip(c,oldch)==streamed_clip(nc[k],nch) for k,c in clips.items() if k not in keys.values())
assert all(check[k]==v for k,v in entries(cb).items() if k!=9)
(O/'g_cb.xbx').write_bytes(newcb)
# Explicit user mapping: Circle=544... (Suction), Triangle=239... (Backspin).
d=bytearray(ddf); routes={0x549d5666:('suction','ucb_poe_suction'),0x239a66f0:('backspin','ucb_poe_backspin')}; counts={k:0 for k in routes}
for at in range(4,len(d),224):
    slot=struct.unpack_from('>I',d,at+160)[0]
    if slot not in routes:continue
    move,sound=routes[slot];struct.pack_into('>I',d,at+32,keys[move]);struct.pack_into('>I',d,at+152,m.crc(sound))
    struct.pack_into('>f',d,at+13*4,0);struct.pack_into('>f',d,at+16*4,0);struct.pack_into('>f',d,at+19*4,0);struct.pack_into('>I',d,at+25*4,0x41e3c);counts[slot]+=1
assert set(counts.values())=={3}
(O/'atk_ucb.ddf').write_bytes(d)
# The retail voice parser explicitly requires every PCM subsound to be
# 2048-byte aligned. Restore that layout without increasing the package
# beyond the original small trial which displayed the character correctly.
uparts=entries(ucb); bank=uparts[24]; r=m.vaps_rows(bank); old=r[1][2][32:]; count,hs,_=struct.unpack_from('<3I',old,4);assert count==29 and hs==80*count
v=(I/'vilgax/ultimatecannonbolt/callout.fsb').read_bytes();slots={6:'spin_cycle',7:'spin_cycle',8:'backspin_burnout',9:'backspin_burnout',14:'meteor_candidate',15:'suction_blast'}
pcm={}
for name in set(slots.values()):
    with wave.open(str(H/'meteor-audio-fix'/ (name+'.wav')),'rb') as w:
        assert w.getframerate()==48000; n=w.getnframes();x=struct.unpack(f'<{n}h',w.readframes(n))
    y=[round(sum(x[j:j+6])/len(x[j:j+6])) for j in range(0,n,6)]
    pcm[name]=struct.pack(f'<{len(y)}h',*y)
heads=bytearray();data=bytearray()
for j in range(count):
    h=bytearray(v[48:128]);h[2:32]=old[48+j*80+2:48+j*80+32];p=pcm[slots[j]] if j in slots else bytes(32);n=len(p)//2
    p+=bytes((-len(p))%2048);struct.pack_into('<6I',h,32,n,len(p),0,0,0x131,8000);heads.extend(h);data.extend(p)
head=bytearray(v[:48]);struct.pack_into('<3I',head,4,count,len(heads),len(data));fsb=bytes(head+heads+data)
assert all(struct.unpack_from('<I',heads,j*80+36)[0]%2048==0 for j in range(count))
wrapper=bytearray(r[1][2][:32]);struct.pack_into('>I',wrapper,4,len(fsb));r[1]=(r[1][0],r[1][1],bytes(wrapper)+fsb)
uparts[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],r);newu=m.package(ucb,uparts)
assert len(newu)<=(H/'remaining-candidate/g_ucb.xbx').stat().st_size
assert all(entries(newu)[k]==val for k,val in entries(ucb).items() if k!=24)
(O/'g_ucb.xbx').write_bytes(newu)
result=dict(animations=report,source_audio='POE decoded and filtered',audio_alignment=2048,package_size=len(newu),original_cb_sha=hashlib.sha256(cb).hexdigest(),original_ucb_sha=hashlib.sha256(ucb).hexdigest(),original_attack_sha=hashlib.sha256(ddf).hexdigest(),gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
