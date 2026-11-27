"""Boost only the working Bounce Ball impacts; preserve their timing."""
import hashlib,json,struct,sys
from pathlib import Path
import numpy as np
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries

H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'ultimate-bounce-ball-v12-louder';O.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest();prev=json.loads((H/'ultimate-bounce-ball-v11-sound/validation.json').read_text());raw=(G/'g_ucb.xbx').read_bytes();assert sha(raw)==prev['new_sha'] and raw==(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes()
p=entries(raw);rows=m.vaps_rows(p[24]);fev=bytearray(rows[0][2][32:]);f=bytearray(rows[1][2][32:]);count,hs,ds=struct.unpack_from('<3I',f,4);assert count==29 and hs==80*count
name=b'four_seismic_upper_aoe\0';a=fev.index(name)+len(name)+16;vol=struct.unpack_from('<f',fev,a)[0];assert .89<vol<.90 and fev[a+20]==1;struct.pack_into('<f',fev,a,1.0)
at=48+hs+sum(struct.unpack_from('<I',f,48+j*80+36)[0] for j in range(11));n,size,_,_,mode,rate=struct.unpack_from('<6I',f,48+11*80+32);assert (mode,rate)==(0x131,8000) and n*2<=size
x=np.frombuffer(f[at:at+2*n],dtype='>i2').astype(float);out=x.copy();rms=lambda s:float(np.sqrt(np.mean(s*s)));stats=[]
for i,t in enumerate(prev['contact_seconds']):
    begin=round(t*rate);end=min(n,begin+round(.4*rate));v=x[begin:end];before=rms(v);lo,hi=1.,6.
    target=before*1.27
    for _ in range(24):
        gain=(lo+hi)/2;y=32100*np.tanh(gain*v/32100)
        if rms(y)<target:lo=gain
        else:hi=gain
    y=32100*np.tanh(hi*v/32100);out[begin:end]=y;stats.append(dict(contact=i+1,old_rms=before,new_rms=rms(y),effective_gain_db=float(20*np.log10(rms(y)/before/vol))))
assert np.max(np.abs(out))<32767;f[at:at+2*n]=np.rint(out).astype('>i2').tobytes()
assert f[:at]==rows[1][2][32:32+at] and f[at+2*n:]==rows[1][2][32+at+2*n:]
oldfev=rows[0][2][32:];assert fev[:a]==oldfev[:a] and fev[a+4:]==oldfev[a+4:]
rows[0]=(rows[0][0],rows[0][1],rows[0][2][:32]+fev);rows[1]=(rows[1][0],rows[1][1],rows[1][2][:32]+f);p[24]=m.build_vaps(24,struct.unpack_from('>H',p[24],12)[0],rows);new=m.package(raw,p)
assert len(new)==len(raw) and all(entries(new)[k]==v for k,v in entries(raw).items() if k!=24)
(O/'g_ucb.xbx').write_bytes(new);report=dict(old_sha=sha(raw),new_sha=sha(new),impacts=stats,timing_unchanged=True,peak=float(np.max(np.abs(out))),gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
