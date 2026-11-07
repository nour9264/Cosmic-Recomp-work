"""Cross-check bridge mission hooks with the independent Python relocator."""
from pathlib import Path
import os,struct,subprocess
from prepare_all_aliens_candidate import records,relocate,hook

root=Path(__file__).resolve().parents[1];out=root/'build/diagnostics/discord';out.mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(out),TMP=str(out))
driver=out/'HookCheck.cs';driver.write_text('''using System;using System.IO;using System.Reflection;
class HookCheck{static int Main(string[] a){var assembly=Assembly.LoadFrom(a[0]);
var method=assembly.GetType("CosmicRecompi.AllAliensPatch").GetMethod("PresenceMission",BindingFlags.Static|BindingFlags.NonPublic);
File.WriteAllBytes(a[3],(byte[])method.Invoke(null,new object[]{File.ReadAllBytes(a[1]),a[2]}));return 0;}}''')
exe=out/'hook-check.exe';csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
subprocess.run([str(csc),'/nologo','/out:'+str(exe),str(driver)],check=True)
bridge=root/'build/gpu-diagnostic-release/CosmicBridge.exe';output=out/'hook-candidate.bin'
for level in ['l_romd','l_pari','l_rush','l_chin','l_tokn','l_mili','l_romn','l_tokd']:
    original=root/'originals'/level/'scripts'/(level+'.ds');before=records(original.read_bytes())
    subprocess.run([str(exe),str(bridge),str(original),level,str(output)],check=True)
    after=records(output.read_bytes());expected=[(h,a,relocate(c,{0:hook('CosmicPresence_'+level)}) if i==0 else c) for i,(h,a,c) in enumerate(before)]
    assert after==expected,(level,'Mission body or unrelated function changed')
print('Eight mission-entry hooks match the independent relocator; unrelated functions preserved.')
