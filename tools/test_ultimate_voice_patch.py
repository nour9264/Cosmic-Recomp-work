"""Independent FSB4 preservation oracle against locally owned input only."""
from pathlib import Path
import os
import struct
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'build/diagnostics/ultimate-voices';out.mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(out),TMP=str(out))
driver=out/'Driver.cs'
driver.write_text('''using System;using System.IO;using CosmicRecompi;
class Driver {
 static byte[] Read(string root,string level){return File.ReadAllBytes(Path.Combine(root,level,"vo","vo_eng.xbx"));}
 static int Main(string[] args){
  byte[][] donors={Read(args[0],"l_chin"),Read(args[0],"l_mili"),Read(args[0],"l_romd"),Read(args[0],"l_pari"),Read(args[0],"l_rush")};
  byte[] original=Read(args[0],args[1]);byte[] updated=UltimateVoicePatch.Merge(original,donors);
  if(UltimateVoicePatch.Hash(updated)!=UltimateVoicePatch.Hash(UltimateVoicePatch.Merge(updated,donors)))return 1;
  try{UltimateVoicePatch.Merge(new byte[48],donors);return 2;}catch(InvalidDataException){}
  File.WriteAllBytes(args[2],updated);return 0;
 }
}''')
exe=out/'check.exe'
csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
subprocess.run([str(csc),'/nologo','/out:'+str(exe),str(driver),str(root/'launcher/UltimateVoicePatch.cs')],check=True)

def samples(blob):
    magic,count,headers,data=struct.unpack_from('<4sIII',blob)
    assert magic==b'FSB4' and 48+headers+data==len(blob)
    cursor=48;offset=48+headers;result=[]
    for _ in range(count):
        size=struct.unpack_from('<H',blob,cursor)[0]
        name=blob[cursor+2:cursor+32].rstrip(b'\0')
        packed=struct.unpack_from('<I',blob,cursor+36)[0]
        result.append((name,blob[cursor:cursor+size],blob[offset:offset+packed]))
        cursor+=size;offset+=packed
    assert offset==len(blob) and cursor<=48+headers
    return result

expected={}
for level in ['l_chin','l_mili','l_romd','l_pari','l_rush']:
    for item in samples((root/'originals'/level/'vo/vo_eng.xbx').read_bytes()):
        if item[0].startswith(b'ult_') and b'name_callout' in item[0]:expected[item[0]]=item
assert len(expected)==5
candidate=out/'candidate.fsb'
for level in ['global','l_chin','l_mili','l_pari','l_romd','l_romn','l_rush','l_tokd','l_tokn']:
    original=(root/'originals'/level/'vo/vo_eng.xbx').read_bytes()
    subprocess.run([str(exe),str(root/'originals'),level,str(candidate)],check=True)
    old=samples(original);new=samples(candidate.read_bytes())
    assert new[:len(old)]==old, 'An existing index, header or audio payload changed'
    calls={s[0]:s for s in new if s[0] in expected}
    assert calls==expected and len(new)==221
    for i,name in enumerate([b'ult_bigchill_',b'ult_echoecho_',b'ult_humongousaur_',b'ult_swampfire_',b'ult_spidermonkey_']):
        assert new[216+i][0].startswith(name) and new[216+i]==expected[new[216+i][0]]
    print(level+': existing indices/headers/audio preserved; exactly five Ultimate callouts; idempotence passed.')
print('No game launched. FMOD lookup and audible playback still require gameplay testing.')
