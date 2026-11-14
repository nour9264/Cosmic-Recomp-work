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
  // Descriptors for imported aliens' name callouts (UltimateVoicePatch slots 221+).
  internal static byte[] Sounds(byte[] original,string game){return Sounds(original,game,true);}
  // effects=false gives an install from before imported sound effects existed.
  static byte[] Sounds(byte[] original,string game,bool effects){return Sounds(original,game,effects,int.MaxValue);}
  // limit: how many imported aliens to include (an earlier install had fewer).
  static byte[] Sounds(byte[] original,string game,bool effects,int limit) {
   byte[] updated=Sounds(original);
#if COSMIC_VILGAX_ALIENS
   string text=Encoding.UTF8.GetString(updated);int slot=221;var lines=new StringBuilder();var attackLines=new StringBuilder();
   int taken=0;
   foreach(var form in AllAliensPatch.ImportedForms(Path.GetDirectoryName(game))) {
    if(taken++>=limit)break;
    string path=Path.Combine(form.Folder,"callout.txt");
    if(File.Exists(path)) {
     string name=File.ReadAllText(path).Trim();
     if(!Regex.IsMatch(name,"^[a-z0-9_]+$") || text.Contains("<sound name=\""+name+"\""))throw new InvalidDataException("Unexpected imported callout name.");
     lines.Append("<sound name=\""+name+"\" id=\""+slot+++"\" bank=\"voice\" isloop=\"no\" falloffstart=\"-1.0\" falloffend=\"-1.0\" volume=\"1.0\" />\r\n");
    }
    // Sound effects in the form's own FMOD project (package section 24).
    string sounds=Path.Combine(form.Folder,"sounds.txt");
    if(!effects || !File.Exists(sounds))continue;
    foreach(string line in File.ReadAllLines(sounds)) {
     if(line.Length==0)continue;
     var match=Regex.Match(line,"^<sound name=\"([a-z0-9_]+)\" id=\"[0-9]+\" swpgroupid=\"0\" prjid=\"[a-z0-9_]+\"/>$");
     if(!match.Success || text.Contains("<sound name=\""+match.Groups[1].Value+"\""))throw new InvalidDataException("Unexpected imported sound.");
     // The enclosing <group> sets a sound's mixer group and project lookup:
     // effects belong in "sfxattack" with Four Arms' (a descriptor inside
     // "dialog" is treated as a voice line and crashes when played).
     attackLines.Append(line+"\r\n");
    }
   }
   if(attackLines.Length>0) {
    var attackAnchor=new Regex("<sound name=\"spinning_crusher\"[^>]*/>\r?\n");
    if(attackAnchor.Matches(text).Count!=1)throw new InvalidDataException("Missing attack sound anchor.");
    text=attackAnchor.Replace(text,m=>m.Value+attackLines.ToString());
    updated=Encoding.UTF8.GetBytes(text);
   }
   if(lines.Length>0) {
    var anchor=new Regex("<sound name=\"ult_spidermonkey_name_callout_01\"[^>]*/>\r?\n");
    if(anchor.Matches(text).Count!=1)throw new InvalidDataException("Missing callout anchor.");
    text=anchor.Replace(text,m=>m.Value+lines.ToString());
    updated=Encoding.UTF8.GetBytes(text);
   }
#endif
   return updated;
  }
  internal static void Ensure(string game) {
   var updates=new Dictionary<string,byte[]>();var originals=new Dictionary<string,byte[]>();
   var pins=new Dictionary<string,string>(Pins);pins.Add("global/scripts/sounds.ddf","83d51bc335c69a74c5f44c85f16bedfa1e4c301b9911c03d7f2be0b6feabef6b");
   foreach(var entry in pins) {
    string path=Path.Combine(game,entry.Key.Replace('/',Path.DirectorySeparatorChar)),backup=path+".cosmic-voice-original";
    byte[] original=File.ReadAllBytes(File.Exists(backup)?backup:path);
    if(UltimateVoicePatch.Hash(original)!=entry.Value)throw new IOException("Unsupported original voice links: "+entry.Key);
    bool sounds=entry.Key.EndsWith("sounds.ddf");
    byte[] updated=sounds?Sounds(original,game):AllAliensPatch.VoiceResolver(original);
    string current=UltimateVoicePatch.Hash(File.ReadAllBytes(path));
    if(current==UltimateVoicePatch.Hash(updated))continue;
    bool earlier=false;
#if COSMIC_VILGAX_ALIENS
    if(sounds)for(int k=1;k<AllAliensPatch.ImportedForms(Path.GetDirectoryName(game)).Count && !earlier;k++)
     earlier=current==UltimateVoicePatch.Hash(Sounds(original,game,true,k));
#endif
    if(current!=entry.Value && !earlier && !(sounds && (current==UltimateVoicePatch.Hash(Sounds(original)) ||
       current==UltimateVoicePatch.Hash(Sounds(original,game,false)))))throw new IOException("Unknown voice-link edit: "+entry.Key);
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
