using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
namespace CosmicRecompi {
 internal static class UltimateVoiceLinks {
  static readonly Dictionary<string,string> Pins=new Dictionary<string,string>{{"l_chin/scripts/vo_chin.ds","1d2aac44a13669072ea2094abc2071399ace500957520632183775bb2b330ecd"},{"l_mili/scripts/vo_mili.ds","66892c113583cc4b3eed852029c41ef419a0b93f0a365e06d52636fe7ca2b055"},{"l_pari/scripts/vo_pari.ds","1c8b95f6f97037c3408bcbdad95419d4f6f0a6344e128ec7af9756eeee01ec20"},{"l_romd/scripts/vo_romd.ds","456a4e6963a4bb67af0dcdf754d0872133a22849013785e6723535afc236b1d9"},{"l_romn/scripts/vo_romn.ds","c368625d46e44d98183aeb5cca03f0e683c3b001b63cbbb49cd8e0594d93f07b"},{"l_rush/scripts/vo_rush.ds","be92d4ab8fbaae30b9bf55865a03d14cb1279ca725964150b16f828a08974b7e"},{"l_tokd/scripts/vo_tokd.ds","17d629227869af4160c95061ff4e1dbb06a45a80006575f673b4188b19503456"},{"l_tokn/scripts/vo_tokn.ds","89478a2cae882cfe642a7d73030cf3404bb04bf25c11efce20219e7ddc3f87c8"}};
  internal static byte[] Sounds(byte[] original) {
   string text=Encoding.UTF8.GetString(original);
   string[] forms={"bigchill","echoecho","humongousaur","swampfire","spidermonkey"};
   for(int i=0;i<forms.Length;i++) {
    string pattern="(<sound name=\"ult_"+forms[i]+"_name_callout_01\" id=\")([0-9]+)(\" bank=\"voice\")";
    var regex=new Regex(pattern);if(regex.Matches(text).Count!=1)throw new InvalidDataException("Missing/duplicate callout descriptor.");
    int slot=216+i;text=regex.Replace(text,m=>m.Groups[1].Value+slot+m.Groups[3].Value);
   }
   return Encoding.UTF8.GetBytes(text);
  }
  internal static void Ensure(string game) {
   var updates=new Dictionary<string,byte[]>();var originals=new Dictionary<string,byte[]>();
   var pins=new Dictionary<string,string>(Pins);pins.Add("global/scripts/sounds.ddf","83d51bc335c69a74c5f44c85f16bedfa1e4c301b9911c03d7f2be0b6feabef6b");
   foreach(var entry in pins) {
    string path=Path.Combine(game,entry.Key.Replace('/',Path.DirectorySeparatorChar)),backup=path+".cosmic-voice-original";
    byte[] original=File.ReadAllBytes(File.Exists(backup)?backup:path);
    if(UltimateVoicePatch.Hash(original)!=entry.Value)throw new IOException("Unsupported original voice links: "+entry.Key);
    byte[] updated=entry.Key.EndsWith("sounds.ddf")?Sounds(original):AllAliensPatch.VoiceResolver(original);
    string current=UltimateVoicePatch.Hash(File.ReadAllBytes(path));
    if(current==UltimateVoicePatch.Hash(updated))continue;
    if(current!=entry.Value)throw new IOException("Unknown voice-link edit: "+entry.Key);
    originals.Add(path,original);updates.Add(path,updated);
   }
   foreach(var entry in updates) {
    string path=entry.Key,backup=path+".cosmic-voice-original",temp=path+".cosmic-voice-new";
    if(!File.Exists(backup))File.WriteAllBytes(backup,originals[path]);
    File.WriteAllBytes(temp,entry.Value);File.Replace(temp,path,null);
   }
  }
 }
}
