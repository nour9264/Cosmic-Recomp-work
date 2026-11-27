import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
import pathlib,struct,subprocess,wave
H=WORK
v=vilgax_dump()/'global'
d=(v/'snd_xbx/core.fsb').read_bytes()
n,hs,ds=struct.unpack_from('<3I',d,4);at=48;off=48+hs
for i in range(n):
    size=struct.unpack_from('<H',d,at)[0];name=d[at+2:at+32].split(b'\0')[0]
    samples,length=struct.unpack_from('<2I',d,at+32)
    if name==b'omni_select_07.wav':
        rate=struct.unpack_from('<I',d,at+52)[0];payload=d[off:off+length];break
    at+=size;off+=length
else:raise ValueError('Missing original selection sound')
assert rate==22050 and length%2048==0
out=H/'ben-transform-animation-retarget'
fmt=struct.pack('<HHIIHHHHIIIIIIIBBH',0x166,1,rate,rate*2,2048,16,34,1,4,samples,2048,0,samples,0,0,0,4,length//2048)
assert len(fmt)==52
body=b'WAVEfmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',length)+payload
src=out/'omni-select.xma';src.write_bytes(b'RIFF'+struct.pack('<I',len(body))+body)
ff=vilgax_dump()
dst=out/'ben-transform-select.wav'
subprocess.run([str(ff),'-v','error','-n','-i',str(src),'-c:a','pcm_s16le',str(dst)],check=True)
with wave.open(str(dst)) as w:
    assert w.getnframes()>0
    print('Original VA omni_select:',w.getnframes()/w.getframerate(),'seconds')
