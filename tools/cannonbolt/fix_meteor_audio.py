"""Revise only Meteor Bolt's ball trajectory and all four private attack sounds."""
import hashlib,json,math,struct,sys,wave
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
H = WORK; I=APP_ROOT/'installation'; O=H/'meteor-audio-fix'; O.mkdir(exist_ok=True)
prev=H/'remaining-candidate'
cb=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes(); ucb=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes()
assert cb==(I/'game/global/g_cb.xbx').read_bytes() and ucb==(I/'game/global/g_ucb.xbx').read_bytes()
parts=entries(cb); rows=m.vaps_rows(parts[9]); oldch=channel_records(parts[9]); clips=m.table(parts[13]); key=0xd8baecc8; clip=clips[key]
idx=struct.unpack_from('>I',clip,216+132*4)[0]; channel=oldch[idx]; values=list(struct.iter_unpack('>4f',channel[8:]));assert len(values)==36
assert sum(struct.unpack_from('>I',c,i)[0]==idx for c in clips.values() for i in range(216,len(c),4))==1
start=values[0][1:]; peak=max(values,key=lambda v:v[2]); direction=[a-b for a,b in zip(peak[1:],start)]; length=math.sqrt(sum(v*v for v in direction)); unit=[v/length for v in direction]
# A moderate 2.8-unit lift, short apex, accelerating four-frame slam, settle.
# Keep the actual clip length and the gameplay-controlled root unchanged.
points=[(0,0),(3,0),(5,.13),(9,.48),(13,.83),(16,1),(18,1),(20,.96),(21,.87),(22,.69),(23,.39),(24,0),(25,.035),(27,0),(35,0)]
def height(i):
    for (a,x),(b,y) in zip(points,points[1:]):
        if a<=i<=b:return x+(y-x)*(i-a)/(b-a)
    raise ValueError(i)
payload=bytearray(channel[:8]); altitude=2.8
for i in range(36):payload.extend(struct.pack('>4f',160*i,*(a+u*altitude*height(i) for a,u in zip(start,unit))))
assert len(payload)==len(channel)
rows[idx]=(rows[idx][0],rows[idx][1],bytes(payload)); parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],rows)
newcb=m.package(cb,parts); checked=entries(newcb); nch=channel_records(checked[9])
for k,c in clips.items():
    if k!=key:assert streamed_clip(c,oldch)==streamed_clip(m.table(checked[13])[k],nch)
assert animation_time_range(clip,nch)==(0,5600)
for k,v in entries(cb).items():
    if k!=9:assert checked[k]==v
(O/'g_cb.xbx').write_bytes(newcb)

# Resample the decoded PS2 effects to the same 48 kHz signed mono PCM
# used by the known-working transformation voices. Low-pass the original
# low-rate assets before interpolation and avoid clipping or hard edges.
uparts=entries(ucb); bank=uparts[24]; br=m.vaps_rows(bank); f=br[1][2][32:]; template=(I/'vilgax/ultimatecannonbolt/callout.fsb').read_bytes()
count,hsize,dsize=struct.unpack_from('<3I',f,4); assert count==29 and hsize==count*80
slots={6:'spin_cycle',7:'spin_cycle',8:'backspin_burnout',9:'backspin_burnout',14:'meteor_candidate',15:'suction_blast'}
converted={}
for name in sorted(set(slots.values())):
    with wave.open(str(prev/(name+'.wav')),'rb') as w:
        rate=w.getframerate(); n=w.getnframes(); x=list(struct.unpack(f'<{n}h',w.readframes(n)))
    # Two-pass low-pass, zero-phase. Reduce the low-rate ADPCM harshness
    # without changing the original playback duration or pitch.
    alpha=1-math.exp(-2*math.pi*min(2200,rate*.28)/rate)
    for backward in (False,True):
        if backward:x.reverse()
        y=x[0]
        for j,v in enumerate(x):y+=alpha*(v-y);x[j]=y
        if backward:x.reverse()
    mean=sum(x)/len(x); x=[v-mean for v in x]; gain=min(1.4,24000/max(1,max(map(abs,x))))
    outn=round(n*48000/rate); out=[]; fade=480
    for j in range(outn):
        at=j*rate/48000; k=min(n-1,int(at)); frac=at-k; v=x[k]*(1-frac)+x[min(k+1,n-1)]*frac
        edge=min(1,j/fade,(outn-1-j)/fade); out.append(round(v*gain*max(0,edge)))
    assert max(map(abs,out))<=24001
    pcm=struct.pack(f'<{outn}h',*out); converted[name]=(outn,pcm)
    with wave.open(str(O/(name+'.wav')),'wb') as w:w.setparams((1,2,48000,outn,'NONE','not compressed'));w.writeframes(pcm)
headers=bytearray(); data=bytearray()
for j in range(count):
    old=f[48+j*80:48+(j+1)*80]; h=bytearray(template[48:128]); h[2:32]=old[2:32]
    n,pcm=converted[slots[j]] if j in slots else (1024,bytes(2048))
    # Include padding in the sample count, so the PCM loader's byte and
    # frame counts agree exactly; the silence is at most 21 ms.
    pcm+=bytes((-len(pcm))%2048); frames=len(pcm)//2
    struct.pack_into('<4I',h,32,frames,len(pcm),0,0)
    assert struct.unpack_from('<II',h,48)==(0x131,48000)
    headers.extend(h);data.extend(pcm)
head=bytearray(template[:48]);struct.pack_into('<3I',head,4,count,len(headers),len(data)); newfsb=bytes(head+headers+data)
wrapper=bytearray(br[1][2][:32]);struct.pack_into('>I',wrapper,4,len(newfsb)); br[1]=(br[1][0],br[1][1],bytes(wrapper)+newfsb)
uparts[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],br); newucb=m.package(ucb,uparts)
for k,v in entries(ucb).items():
    if k!=24:assert entries(newucb)[k]==v
assert m.vaps_rows(entries(newucb)[24])[1][2][32:]==newfsb
(O/'g_ucb.xbx').write_bytes(newucb);(O/'ucbpova.fsb').write_bytes(newfsb)
report=dict(old_cb=hashlib.sha256(cb).hexdigest(),old_ucb=hashlib.sha256(ucb).hexdigest(),height=altitude,slam_frame=24,all_other_clips_preserved=True,audio_rate=48000,attack_sounds=list(converted),gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
