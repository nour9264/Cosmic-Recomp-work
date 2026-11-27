"""Build-local POE animation prototypes and PS2 audio extraction."""
import hashlib,json,math,struct,sys,wave
from pathlib import Path
from mathutils import Quaternion,Vector
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range

H = WORK
I=APP_ROOT/'installation'
O=H/'remaining-candidate'; O.mkdir(exist_ok=True)
src=(H/'99_95.stream1.bin').read_bytes()
catalog=json.loads((H/'cannonbolt-clip-catalog.json').read_text())
raw=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes()
ddf=(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
assert raw==(I/'game/global/g_cb.xbx').read_bytes()
assert ddf==(I/'game/global/scripts/atk_ucb.ddf').read_bytes()
parts=entries(raw); oldrows=m.vaps_rows(parts[9]); oldclips=m.vaps_rows(parts[13]); channels=list(oldrows)
oldch=channel_records(parts[9]); clips=m.table(parts[13]); donor=clips[0xef7b4b93]
idx=struct.unpack_from('>135I',donor,216)
assert m.bone_ids(donor)[44]==0xc1
def first_q(c):
    x,y,z,w,_=struct.unpack_from('>3hbB',c,8)
    return Quaternion((w/127,x/32767,y/32767,z/32767)).normalized().conjugated()
root=first_q(oldch[idx[1]]); base=first_q(oldch[idx[133]])
basis=Quaternion(Vector((1,0,0)),-math.pi/2)
def source_rotation(r):
    n=r['sample_count']; f=r['stream_pointers']; qs=[]
    assert f[7]-f[6]==4*n
    for (word,) in struct.iter_unpack('<I',src[f[6]:f[7]]):
        omit=word&3; v=[(((word>>s)&1023)-512)/(512*math.sqrt(2)) for s in (2,12,22)]
        v.insert(omit,math.sqrt(max(0,1-sum(x*x for x in v))))
        assert abs(v[omit])+.003>=max(map(abs,v))
        q=Quaternion((v[3],*v[:3])).normalized()
        if qs and q.dot(qs[-1])<0:q.negate()
        qs.append(q)
    out=[]
    for q in qs:
        d=basis@(q@qs[0].inverted())@basis.inverted()
        pose=(root.inverted()@d@root@base).conjugated().normalized()
        if out and pose.dot(out[-1])<0:pose.negate()
        out.append(pose)
    return out

new=[]; routes={}; reports=[]
for ci,slug,route in [(0,'backspin_burnout',0xe19178df),(2,'meteor_bolt',0xc9fb4de3),(3,'suction_blast',0x055ebd1f)]:
    r=catalog[ci]; n=r['sample_count']; f=r['stream_pointers']; name='cosmic_poe_ucb_'+slug; key=m.crc(name)
    assert key not in clips
    c=bytearray(donor); c[:64]=name.encode().ljust(64,b'\0'); struct.pack_into('>2f',c,64,0,(n-1)*160); struct.pack_into('>I',c,80,0xffffffff)
    rotations=None; positions=None
    if ci==2:
        # Original frame records end in a vertical translation vector. Its scale
        # is retargeted to the native powerflop's measured vertical excursion.
        pointers=struct.unpack_from(f'<{n}I',src,f[8]); ends=list(pointers[1:])+[f[8]]
        vals=[struct.unpack_from('<3f',src,e-12) for e in ends]
        assert all(math.isfinite(x) for v in vals for x in v)
        assert max(abs(v[0])+abs(v[1]) for v in vals)<.01
        heights=[v[2]-vals[0][2] for v in vals]; peak=max(heights); assert peak>10
        native=oldch[struct.unpack_from('>I',clips[route],216)[0]]
        h=[v[2] for v in struct.iter_unpack('>4f',native[8:])]; scale=(max(h)-h[0])/peak
        start=Vector(struct.unpack_from('>3f',oldch[idx[132]],12)); up=root.inverted()@Vector((0,1,0))
        positions=[start+up*(v*scale) for v in heights]
        method='source vertical trajectory, scaled to native powerflop height'
    else:
        rotations=source_rotation(r); method='source ball rotation, native ball pose'
    for j,index in enumerate(idx):
        orig=oldch[index]; kind,stride,tag,_,_=struct.unpack_from('>BBHHH',orig)
        if j==133 and rotations is not None:
            payload=bytearray(struct.pack('>BBHHH',16,2,0x5002,n,n))
            for frame,q in enumerate(rotations):
                xyz=[round(v*32767) for v in (q.x,q.y,q.z)]; w=round(q.w*127)
                payload.extend(struct.pack('>3hbB',*xyz,w,frame))
                dq=Quaternion((w/127,*(v/32767 for v in xyz))).normalized()
                assert abs(q.dot(dq))>.9998
        elif j==132 and positions is not None:
            payload=bytearray(struct.pack('>BBHHH',1,4,0x5001,n,n))
            for frame,p in enumerate(positions):payload.extend(struct.pack('>4f',frame*160,*p))
        else:
            payload=bytearray(struct.pack('>BBHHH',kind,stride,tag,2,2)); a=bytearray(orig[8:8+stride*4]); b=bytearray(a)
            if kind==16:a[-1]=0;b[-1]=n-1
            else:struct.pack_into('>f',a,0,0);struct.pack_into('>f',b,0,(n-1)*160)
            payload.extend(a+b)
        struct.pack_into('>I',c,216+4*j,len(channels));channels.append((m.crc(f'{name}_{j}'),0,bytes(payload)))
    new.append((key,0,bytes(c)));routes[route]=key;reports.append(dict(move=r['move'],frames=n,method=method,key=hex(key)))
buckets=max(1,len(channels)//4);order=sorted(range(len(channels)),key=lambda i:(channels[i][0]%buckets,channels[i][0],i));remap={a:b for b,a in enumerate(order)}
updated=[]
for k,fl,c in oldclips+new:
    c=bytearray(c)
    for offset in [80]+list(range(216,len(c),4)):
        j=struct.unpack_from('>I',c,offset)[0]
        if j!=0xffffffff:struct.pack_into('>I',c,offset,remap[j])
    updated.append((k,fl,bytes(c)))
parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],[channels[i] for i in order])
parts[13]=m.build_vaps(13,struct.unpack_from('>H',parts[13],12)[0],m.bucket_sorted(updated))
result=m.package(raw,parts); check=entries(result); nch=channel_records(check[9]); nc=m.table(check[13])
for k,fl,c in oldclips:assert streamed_clip(c,oldch)==streamed_clip(nc[k],nch)
for k,v in entries(raw).items():
    if k not in (9,13):assert check[k]==v
for r in reports:assert animation_time_range(nc[int(r['key'],16)],nch)==(0,(r['frames']-1)*160)
d=bytearray(ddf); counts={k:0 for k in routes}
for p in range(4,len(d),224):
    k=struct.unpack_from('>I',d,p+32)[0]
    if k in routes:struct.pack_into('>I',d,p+32,routes[k]);counts[k]+=1
assert set(counts.values())=={3}
(O/'g_cb.xbx').write_bytes(result);(O/'atk_ucb.ddf').write_bytes(d)

# PS2 ADPCM waves at sector-aligned end of compressed asset streams.
pss=(H/'99_95.pss').read_bytes(); audio_base=(508+sum(struct.unpack_from('<2I',pss,140))+2047)&~2047
sound_names={'spin_cycle':'atkHHH.wav','backspin_burnout':'CB_LLH.wav','suction_blast':'atkSH.wav','meteor_candidate':'CB_JS_thud_louder.wav','roll':'CB_roll.wav','roll_start':'CB_roll_start.wav','roll_stop':'CB_roll_stop.wav'}
audio=[]
for label,nm in sound_names.items():
    at=src.find(nm.encode()+b'\0'); assert at>=0 and src.find(nm.encode()+b'\0',at+1)<0
    start=at-44; assert src[start:start+4]==b'RIFF'; end=start+8+struct.unpack_from('<I',src,start+4)[0]
    fmt=src.find(b'fmt ',at,end); fact=src.find(b'fact',fmt,end); st=src.find(b'strm',fact,end)
    form,chan,rate=struct.unpack_from('<HHI',src,fmt+8); count=struct.unpack_from('<I',src,fact+8)[0];off,size=struct.unpack_from('<II',src,st+8)
    assert form==0x600 and chan==1 and size%16==0 and audio_base+off+size<=len(pss)
    data=pss[audio_base+off:audio_base+off+size]; samples=[]; h1=h2=0; coeff=[(0,0),(60,0),(115,-52),(98,-55),(122,-60)]
    for p in range(0,len(data),16):
        frame=data[p:p+16]; pred=frame[0]>>4; shift=frame[0]&15
        assert pred<5 and shift<=12 and frame[1]<=7
        a,b=coeff[pred]
        for byte in frame[2:]:
            for nib in (byte&15,byte>>4):
                signed=nib if nib<8 else nib-16; v=((signed<<12)>>shift)+((h1*a+h2*b+32)>>6); v=max(-32768,min(32767,v));samples.append(v);h2,h1=h1,v
    assert abs(len(samples)-count)<56 and max(map(abs,samples))>100
    samples=samples[:count]
    with wave.open(str(O/(label+'.wav')),'wb') as w:w.setparams((1,2,rate,len(samples),'NONE','not compressed'));w.writeframes(struct.pack(f'<{len(samples)}h',*samples))
    audio.append(dict(label=label,source=nm,rate=rate,samples=len(samples)))
report=dict(animations=reports,original_clips_preserved=len(oldclips),audio=audio,sha256_asset=hashlib.sha256(raw).hexdigest(),sha256_attack=hashlib.sha256(ddf).hexdigest(),gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
