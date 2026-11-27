"""Match the working Meteor one-shot playback mode for the bounce event."""
import hashlib,json,struct,sys
from pathlib import Path
import numpy as np
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries

H = WORK;I=APP_ROOT/'installation';G=I/'game/global';U=I/'vilgax/ultimatecannonbolt';O=H/'ultimate-bounce-ball-v11-sound';O.mkdir(exist_ok=True)
sha=lambda x:hashlib.sha256(x).hexdigest();r=json.loads((H/'ultimate-bounce-ball-v9-sync/validation.json').read_text());v10=json.loads((H/'ultimate-bounce-ball-v10-stop/validation.json').read_text())
raw=(G/'g_ucb.xbx').read_bytes();assert sha(raw)==r['new_model_sha'] and raw==(U/'g_ucb.xbx').read_bytes()
assert sha((G/'g_cb.xbx').read_bytes())==v10['new_cb_sha'] and sha((G/'scripts/atk_ucb.ddf').read_bytes())==v10['new_ucb_sha']
parts=entries(raw);bank=parts[24];rows=m.vaps_rows(bank);fev=bytearray(rows[0][2][32:]);fsb=bytearray(rows[1][2][32:]);count,hs,ds=struct.unpack_from('<3I',fsb,4);assert count==29 and hs==80*count and len(fsb)==48+hs+ds

# Existing event 15 is audible; event 16 is dispatched but silent. Comparing
# their serialized settings identifies the event playback mode (1 vs 4).
# Preserve the distinct event GUID, name, wave reference 9 and name length.
names=[b'four_seismic_upper\0',b'four_seismic_upper_aoe\0',b'four_spinning_crusher_aoe\0'];a=[fev.index(n) for n in names];s=[p+len(n)+16 for p,n in zip(a,names)]
one=fev[s[0]:a[1]-4];aoe=fev[s[1]:a[2]-4]
assert len(one)==len(aoe)==217
assert [(i,x,y) for i,(x,y) in enumerate(zip(one,aoe)) if x!=y]==[(20,1,4),(136,15,9),(216,24,27)]
fev[s[1]+20]=one[20]
# The sound definition has its own sample-playback mode as well. Copy the
# metadata of the audible source, not the wave index or timing.
dn=[b'/ucbpova/four_seismic_upper\0',b'/ucbpova/four_aoe\0'];dp=[fev.index(n)+len(n) for n in dn]
assert struct.unpack_from('<4I',fev,dp[0])==(1,1,0,100) and struct.unpack_from('<4I',fev,dp[1])==(0,1,0,100)
struct.pack_into('<I',fev,dp[1],1)

# Decode the actual staged impact PCM; it is already the same big-endian
# signed mono 8kHz format as the working attack samples. Increase each
# transient's loudness without moving it or introducing clipping. Retain
# exactly the current sample count, bank offsets and size.
at=48+hs;payloads=[];meta=[]
for j in range(count):
    n,size,_,_,mode,rate=struct.unpack_from('<6I',fsb,48+j*80+32);assert (mode,rate)==(0x131,8000) and n*2<=size and size%2048==0
    payloads.append(at);meta.append((n,size));at+=size
assert at==len(fsb)
n,size=meta[11];at=payloads[11];x=np.frombuffer(fsb[at:at+2*n],dtype='>i2').astype(float);assert n>20000 and np.max(np.abs(x))>15000
original=x.copy();peak=lambda v:float(np.max(np.abs(v)));rms=lambda v:float(np.sqrt(np.mean(v*v)))
for i,t in enumerate(r['contact_seconds']):
    begin=round(t*8000);end=min(n,begin+round(.40*8000));v=x[begin:end];before=rms(v);assert before>1000
    # A short soft compressor, same established gain technique as the audible
    # Meteor/Spin/Suction samples. Silence and exact impact offsets unchanged.
    target=14000+i*1000;lo,hi=1.,8.
    for _ in range(20):
        gain=(lo+hi)/2;y=30900*np.tanh(gain*v/30900)
        if rms(y)<target:lo=gain
        else:hi=gain
    x[begin:end]=30900*np.tanh(hi*v/30900)
y=np.rint(x).astype('>i2');assert peak(x)<32767
fsb[at:at+2*n]=y.tobytes()
assert all(fsb[p:p+sz]==rows[1][2][32+p:32+p+sz] for j,(p,(_,sz)) in enumerate(zip(payloads,meta)) if j!=11)
assert fsb[:48+hs]==rows[1][2][32:32+48+hs]
rows[0]=(rows[0][0],rows[0][1],rows[0][2][:32]+fev);rows[1]=(rows[1][0],rows[1][1],rows[1][2][:32]+fsb);parts[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],rows);new=m.package(raw,parts)
assert len(new)==len(raw) and all(entries(new)[k]==v for k,v in entries(raw).items() if k!=24)
(O/'g_ucb.xbx').write_bytes(new)
report=dict(old_sha=sha(raw),new_sha=sha(new),event=16,event_playback_mode=1,sound_definition_mode=1,sample=11,pcm='signed big-endian mono 8000Hz',contact_seconds=r['contact_seconds'],peak_before=peak(original),peak_after=peak(x),rms_before=rms(original),rms_after=rms(x),other_attacks_unchanged=True,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
