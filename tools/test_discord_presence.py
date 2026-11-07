"""Exercise actual desktop IPC code against a private pipe, never real Discord."""
import os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'build/diagnostics/discord';out.mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(out),TMP=str(out))
driver=out/'Driver.cs';driver.write_text(r'''
using System;using System.IO;using System.IO.Pipes;using System.Text;using System.Threading;using System.Diagnostics;
using System.Collections.Generic;using System.Web.Script.Serialization;using CosmicRecompi;
class Driver {
 static JavaScriptSerializer json=new JavaScriptSerializer();
 static byte[] Read(Stream s,int count){byte[] b=new byte[count];int at=0;while(at<count){int n=s.Read(b,at,count-at);if(n==0)throw new Exception("EOF");at+=n;}return b;}
 static Dictionary<string,object> Frame(Stream s,int expected){byte[] h=Read(s,8);if(BitConverter.ToInt32(h,0)!=expected)throw new Exception("opcode");return json.Deserialize<Dictionary<string,object>>(Encoding.UTF8.GetString(Read(s,BitConverter.ToInt32(h,4))));}
 static void Send(Stream s,int op,object value){byte[] data=Encoding.UTF8.GetBytes(json.Serialize(value));byte[] head=new byte[8];Buffer.BlockCopy(BitConverter.GetBytes(op),0,head,0,4);Buffer.BlockCopy(BitConverter.GetBytes(data.Length),0,head,4,4);
  foreach(byte b in head)s.WriteByte(b);s.Write(data,0,data.Length);s.Flush();}
 static void Require(bool condition){if(!condition)throw new Exception("Assertion failed");}
 static int Main(string[] args){
  if(args.Length==2 && args[1]=="map"){
   var mapping=new Dictionary<string,object>();foreach(string level in new[]{"l_romd","l_pari","l_rush","l_chin","l_tokn","l_mili","l_romn","l_tokd"})mapping[level]=DiscordPresence.Activity(level,123);
   Console.WriteLine(json.Serialize(mapping));return 0;
  }
  string prefix="cosmic-presence-test-"+Guid.NewGuid().ToString("N")+"-",status=Path.Combine(args[0],"status.txt"),log=Path.Combine(args[0],"ipc.log");File.WriteAllText(status,"menus");
  Exception failure=null;var done=new ManualResetEvent(false);long firstStart=0;
  using(var server=new NamedPipeServerStream(prefix+"0",PipeDirection.InOut,1,PipeTransmissionMode.Byte,PipeOptions.None,4096,4096)){
   var thread=new Thread(()=>{try{
    server.WaitForConnection();Console.WriteLine("server connected");var hello=Frame(server,0);Console.WriteLine("server handshake read");Require((string)hello["client_id"]==DiscordPresence.ApplicationId);
    Console.WriteLine("server sending ping");Send(server,3,new Dictionary<string,object>{{"probe",1}});Send(server,1,new Dictionary<string,object>{{"evt","READY"}});Console.WriteLine("server ready written");Frame(server,4);Console.WriteLine("server pong received");
    for(int i=0;i<2;i++){
     Console.WriteLine("server awaiting activity");var cmd=Frame(server,1);Console.WriteLine("server got activity");Require((string)cmd["cmd"]=="SET_ACTIVITY");var a=(Dictionary<string,object>)cmd["args"];
     Require(Convert.ToInt32(a["pid"])==Process.GetCurrentProcess().Id);var activity=(Dictionary<string,object>)a["activity"];
     long start=Convert.ToInt64(((Dictionary<string,object>)activity["timestamps"])["start"]);
     var art=(Dictionary<string,object>)activity["assets"];Require((string)art["large_image"]=="game_cover");
     if(i==0)Require(!art.ContainsKey("small_image"));else Require((string)art["small_image"]=="catacombs" && (string)art["small_text"]=="The Catacombs");
     if(i==0){firstStart=start;Require((string)activity["details"]=="Menus / Loading");}
     else Require(start==firstStart && (string)activity["details"]=="Playing: The Catacombs");
     Send(server,1,new Dictionary<string,object>{{"cmd","SET_ACTIVITY"},{"nonce",cmd["nonce"]},{"evt",null},{"data",new object()}});
     if(i==0)File.WriteAllText(status,"l_romd");
    }
   }catch(Exception e){failure=e;}finally{done.Set();}});thread.IsBackground=true;thread.Start();
   using(var client=new DiscordPresence(Process.GetCurrentProcess(),status,log,prefix)){
    Require(done.WaitOne(15000));if(failure!=null)throw failure;
   }
  }
  var timer=Stopwatch.StartNew();using(var offline=new DiscordPresence(Process.GetCurrentProcess(),status,log,prefix+"absent")){Thread.Sleep(100);}Require(timer.ElapsedMilliseconds<2000);
  Require((string)DiscordPresence.Activity("unknown",123)["details"]=="Menus / Loading");
  Console.WriteLine("Passed: handshake/client ID, fragmented frames, ping/pong, activity acknowledgements, level update, stable session timestamp, cover asset, absent-Discord shutdown. Real Discord was not contacted.");return 0;
 }
}
''')
exe=out/'check.exe';csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
subprocess.run([str(csc),'/nologo','/reference:System.Web.Extensions.dll','/out:'+str(exe),str(driver),str(root/'launcher/DiscordPresence.cs')],check=True)
import json
manifest=root/'build/discord-art/levels/manifest.json'
if manifest.exists():
    mapping=json.loads(subprocess.check_output([str(exe),str(out),'map'],text=True))
    for level in json.loads(manifest.read_text())['levels']:
        activity=mapping[level['game_folder']]
        assert activity['assets']['small_image']==level['asset_key']
        assert activity['assets']['small_text']==level['name']
        assert activity['details']=='Playing: '+level['name']
        assert activity['assets']['large_image']=='game_cover' and activity['timestamps']['start']==123
    print('All eight Rich Presence image/name mappings match the independently extracted game-data manifest.')
subprocess.run([str(exe),str(out)],check=True,timeout=25)
