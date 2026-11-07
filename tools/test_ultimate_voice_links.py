"""Verify script wrapping, descriptor isolation and successful-transition gating."""
import os
import struct
import subprocess
from pathlib import Path
from prepare_all_aliens_candidate import records,crc,encode
from ultimate_voice_program import resolver,EVENTS,SOUNDS,OBSERVED
from prepare_hero_time_candidate import authored,TARGET,PHASE
from test_all_aliens_script import VM

root=Path(__file__).resolve().parents[1];out=root/'build/diagnostics/ultimate-voices-v2';out.mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(out),TMP=str(out))
driver=out/'Driver.cs';driver.write_text('''using System;using System.IO;using CosmicRecompi;
class Driver {static int Main(string[] a){byte[] b=File.ReadAllBytes(a[1]);
byte[] result=a[0]=="voice"?AllAliensPatch.VoiceResolver(b):a[0]=="sounds"?UltimateVoiceLinks.Sounds(b):AllAliensPatch.Transform("globals.ds",b);
File.WriteAllBytes(a[2],result);return 0;}}''')
exe=out/'check.exe';csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
sources=['NativeBridge.cs','InstalledGame.cs','IsoImage.cs','GameMenuPatch.cs','AllAliensPatch.cs','SaveReset.cs','UltimateVoicePatch.cs','UltimateVoiceLinks.cs']
cmd=[str(csc),'/nologo','/main:Driver','/out:'+str(exe),'/reference:System.Windows.Forms.dll',
     '/define:COSMIC_NATIVE_SETTINGS;COSMIC_ALIEN_STREAMS;COSMIC_HERO_TIME;COSMIC_PRELOAD_ALIENS;COSMIC_ULTIMATE_VOICES',str(driver)]
for name,resource in [('AllAliensProgram.bin','CosmicAllAliens.bin'),('HeroTimeProgram.bin','CosmicHeroTime.bin'),('UltimateVoiceResolver.bin','CosmicUltimateVoiceResolver.bin')]:
    cmd.append('/resource:'+str(root/'build/gpu-diagnostic-release'/name)+','+resource)
subprocess.run(cmd+[str(root/'launcher'/s) for s in sources],check=True)
candidate=out/'candidate.bin'
for p in (root/'originals').glob('*/scripts/vo_*.ds'):
    if p.parent.parent.name=='l_titl':continue
    subprocess.run([str(exe),'voice',str(p),str(candidate)],check=True)
    before=records(p.read_bytes());after=records(candidate.read_bytes())
    assert len(after)==len(before)+1
    assert [(crc('CosmicOriginalUltimateVoiceResolver') if h==0xe8c0396d else h,a,c) for h,a,c in before]==after[:-1]
    assert after[-1]==resolver()[0]
p=root/'originals/global/scripts/sounds.ddf'
subprocess.run([str(exe),'sounds',str(p),str(candidate)],check=True)
original=p.read_text();updated=candidate.read_text();import re
forms=['bigchill','echoecho','humongousaur','swampfire','spidermonkey']
for i,form in enumerate(forms):
    pattern=r'(<sound name="ult_'+form+r'_name_callout_01" id=")([0-9]+)(" bank="voice")'
    expected=re.search(pattern,original);actual=re.search(pattern,updated)
    assert actual.group(2)==str(216+i)
    updated=re.sub(pattern,lambda m: m.group(1)+expected.group(2)+m.group(3),updated)
assert updated==original,'Unrelated sound definitions changed'
subprocess.run([str(exe),'globals',str(root/'originals/global/scripts/globals.ds'),str(candidate)],check=True)
rows={h:c for h,a,c in records(candidate.read_bytes())}
for h in [0xd322606e,0xd12b0644,0x29a1fb23]:assert struct.pack('>I',crc('CosmicHeroObserveVoice')) in rows[h]

vm=VM([1,2,3,4]);vm.functions={h:(a,c) for h,a,c in authored(ultimate_voices=True)}
for h in vm.functions:vm.globals[h]=h
played=[];vm.globals[crc('player')]={crc('playvo'):lambda *args:played.append(args[1])}
vm.globals[crc('overlay')][crc('cosmic_hero_active')]=lambda *_:None
vm.globals[crc('overlay')][crc('cosmic_hero_delta')]=lambda *_:0
for form,event in EVENTS.items():
    for observed in [False,True]:
        played.clear();vm.globals[crc(PHASE)]=1;vm.globals[crc(TARGET)]=form
        vm.globals[crc('gCurrentCharacter')]=17;vm.globals[crc(OBSERVED)]=observed
        vm.run('CosmicHeroAdvance');assert not played
        vm.globals[crc('gCurrentCharacter')]=form;vm.globals[0x597a958a]=True
        vm.run('CosmicHeroAdvance');assert not played
        vm.globals[0x597a958a]=False;vm.globals[0xc16ef1c4]=False
        vm.run('CosmicHeroAdvance');vm.run('CosmicHeroAdvance')
        assert played==([] if observed else [event])
vm.functions={h:(a,c) for h,a,c in resolver()};seen=[]
vm.globals[crc('CosmicOriginalUltimateVoiceResolver')]=lambda *args:seen.append(args) or 123
for form,event in EVENTS.items():assert vm.run(0xe8c0396d,[event,77])==crc(SOUNDS[form])
assert vm.run(0xe8c0396d,[987654,77])==123 and seen==[(987654,77)]
print('Passed: eight original resolvers preserved, five descriptor IDs isolated, observed-call hooks, successful completion gating, duplicate suppression and original resolver fallback arguments.')
