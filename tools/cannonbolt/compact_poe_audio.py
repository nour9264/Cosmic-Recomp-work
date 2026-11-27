"""Reinstall a size-bounded private POE bank: filtered, native-rate PCM."""
import hashlib,json,struct,sys,wave,math,re
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
H = WORK; I=APP_ROOT/'installation'; O=H/'compact-audio'; O.mkdir(exist_ok=True)
R=H/'remaining-candidate'; F=H/'meteor-audio-fix'; original=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes()
assert original==(I/'game/global/g_ucb.xbx').read_bytes() and 24 not in entries(original)
trial=(R/'g_ucb.xbx').read_bytes(); bank=entries(trial)[24]; rows=m.vaps_rows(bank)
old=rows[1][2][32:]; count,hsize,_=struct.unpack_from('<3I',old,4);assert count==29 and hsize==80*count
template=(I/'vilgax/ultimatecannonbolt/callout.fsb').read_bytes()
slots={6:'spin_cycle',7:'spin_cycle',8:'backspin_burnout',9:'backspin_burnout',14:'meteor_candidate',15:'suction_blast'}
audio={}
for name in set(slots.values()):
    with wave.open(str(F/(name+'.wav')),'rb') as w:
        assert w.getframerate()==48000 and w.getsampwidth()==2 and w.getnchannels()==1
        n=w.getnframes(); x=struct.unpack(f'<{n}h',w.readframes(n))
    # Previous pass was low-passed below Nyquist. Average 6 samples per
    # output frame for efficient 8 kHz PCM, avoiding a large model package.
    y=[round(sum(x[j:j+6])/len(x[j:j+6])) for j in range(0,n,6)]
    audio[name]=struct.pack(f'<{len(y)}h',*y)
headers=bytearray();data=bytearray()
for j in range(count):
    h=bytearray(template[48:128]); h[2:32]=old[48+j*80+2:48+j*80+32]
    pcm=audio[slots[j]] if j in slots else bytes(32)
    pcm+=bytes((-len(pcm))%32)
    struct.pack_into('<4I',h,32,len(pcm)//2,len(pcm),0,0)
    struct.pack_into('<I',h,52,8000)
    assert struct.unpack_from('<I',h,48)[0]==0x131
    headers.extend(h);data.extend(pcm)
head=bytearray(template[:48]); struct.pack_into('<3I',head,4,count,len(headers),len(data)); fsb=bytes(head+headers+data)
wrapper=bytearray(rows[1][2][:32]);struct.pack_into('>I',wrapper,4,len(fsb)); rows[1]=(rows[1][0],rows[1][1],bytes(wrapper)+fsb)
parts=entries(original);parts[24]=m.build_vaps(24,struct.unpack_from('>H',bank,12)[0],rows);package=m.package(original,parts)
assert len(package)<=len(trial), (len(package),len(trial))
assert all(entries(package)[k]==v for k,v in entries(original).items())
assert m.vaps_rows(entries(package)[24])[1][2][32:]==fsb
ddf=(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes();assert ddf==(I/'game/global/scripts/atk_ucb.ddf').read_bytes()
d=bytearray(ddf); candidate=(R/'atk_ucb.ddf').read_bytes();changed=0
for at in range(4,len(d),224):
    assert d[at:at+4]==candidate[at:at+4]
    if d[at+152:at+156]!=candidate[at+152:at+156]:d[at+152:at+156]=candidate[at+152:at+156];changed+=1
assert changed==12
(O/'g_ucb.xbx').write_bytes(package);(O/'atk_ucb.ddf').write_bytes(d);(O/'ucbpova.fsb').write_bytes(fsb);(O/'sounds.txt').write_bytes((R/'sounds.txt').read_bytes())
report=dict(original_sha=hashlib.sha256(original).hexdigest(),attack_sha=hashlib.sha256(ddf).hexdigest(),package_bytes=len(package),previous_working_size=len(trial),pcm_rate=8000,bank_bytes=len(fsb),routes=changed,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
