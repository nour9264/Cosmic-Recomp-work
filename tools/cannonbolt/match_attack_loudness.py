"""Increase clean attack SFX loudness without changing timing or bank layout."""
import hashlib,json,struct,sys
from pathlib import Path
import numpy as np
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
H = WORK;I=APP_ROOT/'installation';O=H/'matched-attack-loudness';O.mkdir(exist_ok=True)
raw=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes();assert raw==(I/'game/global/g_ucb.xbx').read_bytes()
assert raw==(H/'clean-synced-audio/g_ucb.xbx').read_bytes()
parts=entries(raw);bank=parts[24];rows=m.vaps_rows(bank);old=rows[1][2][32:];count,hs,ds=struct.unpack_from('<3I',old,4);assert count==29 and hs==80*count
fsb=bytearray(old);at=48+hs;stats=[]
for j in range(count):
    n,size,_,_,mode,rate=struct.unpack_from('<6I',old,48+j*80+32);assert mode==0x131 and rate==8000 and size%2048==0 and n*2<=size
    if j in (6,7,8,9,14,15):
        x=np.frombuffer(old[at:at+2*n],dtype='>i2').astype(np.float64);rms=lambda a:float(np.sqrt(np.mean(a*a)));before=rms(x)
        # Gain rides the signal envelope rather than saturating individual
        # samples. Clamp by a lookahead peak envelope, retaining clean peaks.
        env=np.sqrt(np.convolve(x*x,np.ones(161)/161,mode='same'))
        peak=np.maximum.reduce([np.roll(np.abs(x),k) for k in range(-32,33)])
        gain=np.minimum(3.1,15500/np.maximum(env,1000));gain=np.minimum(gain,30900/np.maximum(peak,1))
        gain=np.convolve(gain,np.ones(17)/17,mode='same');y=x*gain
        y*=min(1,30800/max(np.max(np.abs(y)),1));y=np.rint(y).astype(np.int16)
        assert np.max(np.abs(y.astype(np.int32)))<=30800
        fsb[at:at+2*n]=y.astype('>i2').tobytes();stats.append(dict(slot=j,boost_db=round(20*np.log10(rms(y.astype(float))/before),2),rms=round(rms(y.astype(float))),peak=int(np.max(np.abs(y.astype(np.int32))))))
    at+=size
assert at==len(old) and old[:48+hs]==fsb[:48+hs]
rows[1]=(rows[1][0],rows[1][1],rows[1][2][:32]+fsb);parts[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],rows);result=m.package(raw,parts)
assert len(result)==len(raw) and all(entries(result)[k]==v for k,v in entries(raw).items() if k!=24)
assert m.vaps_rows(entries(result)[24])[0]==m.vaps_rows(bank)[0]
(O/'g_ucb.xbx').write_bytes(result);report=dict(old_sha=hashlib.sha256(raw).hexdigest(),samples=stats,timing_unchanged=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
