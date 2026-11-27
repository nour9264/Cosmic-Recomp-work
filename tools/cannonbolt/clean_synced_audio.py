"""Clean source PCM, align effect durations and update FEV waveform metadata."""
import hashlib,json,math,struct,sys,wave
from pathlib import Path
import numpy as np
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
H = WORK;I=APP_ROOT/'installation';O=H/'clean-synced-audio';O.mkdir(exist_ok=True)
raw=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes();assert raw==(I/'game/global/g_ucb.xbx').read_bytes()
parts=entries(raw);bank=parts[24];rows=m.vaps_rows(bank);fev=bytearray(rows[0][2][32:]);old=rows[1][2][32:];count,hs,ds=struct.unpack_from('<3I',old,4);assert count==29 and hs==80*count
rate=8000
def load(name):
    with wave.open(str(H/'remaining-candidate'/(name+'.wav')),'rb') as w:
        assert w.getnchannels()==1 and w.getsampwidth()==2
        sr=w.getframerate();x=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)
    # Work on the original decoded signal, not the previously saturated bank.
    x-=np.mean(x);freq=np.fft.rfftfreq(len(x),1/sr)
    mask=(1-np.exp(-(freq/75)**4))*np.exp(-(freq/2550)**6)
    x=np.fft.irfft(np.fft.rfft(x)*mask,n=len(x));return np.interp(np.arange(round(len(x)*rate/sr))*sr/rate,np.arange(len(x)),x)
def stretch(x,seconds):
    # Waveform-similarity overlap/add keeps original pitch during shortening.
    target=round(seconds*rate); win=320;hop=160;out=np.zeros(target+win);weights=np.zeros_like(out);window=np.hanning(win);ratio=(len(x)-win)/max(1,target-win)
    for dst in range(0,target,hop):
        center=min(max(0,round(dst*ratio)),max(0,len(x)-win));lo=max(0,center-80);hi=min(len(x)-win,center+80)
        if dst and hi>lo:
            ref=out[dst:dst+hop]/np.maximum(weights[dst:dst+hop],1e-8)
            def score(k):
                a=x[k:k+hop];return np.dot(ref,a)/(np.linalg.norm(a)*np.linalg.norm(ref)+1e-8)
            center=max(range(lo,hi+1,4),key=score)
        block=x[center:center+win];out[dst:dst+win]+=block*window;weights[dst:dst+win]+=window
    return (out/np.maximum(weights,1e-8))[:target]
def master(x,target=9500):
    # Smooth RMS compressor and conservative peak headroom: no waveshaping.
    x=x.copy();n=len(x);sq=np.convolve(x*x,np.ones(161)/161,mode='same');env=np.sqrt(np.maximum(sq,1));gain=np.minimum(3.5,(target/np.maximum(env,900))**.65);x*=gain
    mx=np.max(np.abs(x));x*=min(1,29000/max(mx,1));fade=min(80,n//2);x[:fade]*=np.linspace(0,1,fade);x[-fade:]*=np.linspace(1,0,fade)
    return np.rint(x).astype(np.int16)
spin=master(stretch(load('spin_cycle'),2.12));back=master(stretch(load('backspin_burnout'),1.90));suction=master(stretch(load('suction_blast'),1.48))
# Main Meteor clip reaches ground at frame 35/30. Put the actual extracted
# thud at that point; quiet original roll-start audio makes the lead audible.
meteor=np.zeros(round(1.68*rate));intro=load('roll_start');meteor[:len(intro)]=intro*.6;thud=load('meteor_candidate');at=round(1.12*rate);meteor[at:at+len(thud)]+=thud;meteor=master(meteor,10500)
audio={6:spin,7:spin,8:back,9:back,14:meteor,15:suction};headers=bytearray();data=bytearray();stats=[];lengths={}
for j in range(count):
    h=bytearray(old[48+j*80:48+(j+1)*80]);n,size=struct.unpack_from('<2I',h,32)
    if j in audio:
        x=audio[j];n=len(x);pcm=x.astype('>i2').tobytes();pcm+=bytes((-len(pcm))%2048)
        struct.pack_into('<4I',h,32,n,len(pcm),0,0);stats.append(dict(slot=j,seconds=round(n/rate,3),peak=int(np.max(np.abs(x.astype(np.int32))),),rms=round(float(np.sqrt(np.mean(x.astype(float)**2))))))
    else:pcm=bytes(size)
    lengths[j]=round(1000*n/rate);headers.extend(h);data.extend(pcm)
head=bytearray(old[:48]);struct.pack_into('<3I',head,4,count,len(headers),len(data));fsb=bytes(head+headers+data)
marker=struct.pack('<I',8)+b'ucbpova\0';assert fev[40:48]==fsb[24:32];pos=fev.find(marker);changed=[]
while pos>=0:
    a=pos+len(marker)
    if fev[:pos].endswith(b'.wav\0'):
        slot,ms=struct.unpack_from('<II',fev,a)
        if slot in audio:struct.pack_into('<I',fev,a+4,lengths[slot]);changed.append((slot,ms,lengths[slot]))
    pos=fev.find(marker,a)
assert {7,8,14,15}<=set(x[0] for x in changed)
wrapper=bytearray(rows[1][2][:32]);struct.pack_into('>I',wrapper,4,len(fsb));rows[0]=(rows[0][0],rows[0][1],rows[0][2][:32]+fev);rows[1]=(rows[1][0],rows[1][1],bytes(wrapper)+fsb)
parts[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],rows);result=m.package(raw,parts)
assert len(result)<=(H/'remaining-candidate/g_ucb.xbx').stat().st_size and all(entries(result)[k]==v for k,v in entries(raw).items() if k!=24)
(O/'g_ucb.xbx').write_bytes(result)
report=dict(old_sha=hashlib.sha256(raw).hexdigest(),samples=stats,fev_duration_updates=changed,meteor_impact_seconds=1.12,package_bytes=len(result),animations_unchanged=True,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
