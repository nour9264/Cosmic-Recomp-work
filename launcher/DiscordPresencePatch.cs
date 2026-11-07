using System;using System.Collections.Generic;using System.IO;using System.Security.Cryptography;
namespace CosmicRecompi {
 internal static class DiscordPresencePatch {
  static readonly Dictionary<string,string> Pins=new Dictionary<string,string>{{"l_chin","f34ffa64adaf717784a457cfc6fa0a1ca78aae3d796996fd78618e6629c0b13c"},{"l_mili","12ad247753404e94e1535d0054a72a8b95baa988e68f320c7dd9f643bb514c3c"},{"l_pari","f1fdd86c41d82c884bb84d989a0c6580c88b659250c584d489c921a05f002497"},{"l_romd","0f5febeb2afed6e2923f46dd6933eba925bffc5c04267248e96683811ee4330c"},{"l_romn","5d442901b88c2457785419702ed7cebab26152a9eaf179356b275a5eec0259a0"},{"l_rush","ee834f6a9af2d73ad4f6276e6b3aadfb2cd99e2bceb1304b51c0ee21c042c30f"},{"l_tokd","5f5663c708f6d00cb258573abdd8ae2dcefaff793c35c9d6ac414c067c6c76ea"},{"l_tokn","ebd8b02f9c75cabac01004cbc7e26922ff6c42d1d412a8ede3e0d66d81c8b65c"}};
  internal static readonly Dictionary<string,uint> Entries=new Dictionary<string,uint>{{"l_chin",0x82b91484},{"l_mili",0x284ebed7},{"l_pari",0x395d02db},{"l_romd",0xa0fa8a70},{"l_romn",0x35d400ee},{"l_rush",0x33f05470},{"l_tokd",0x42d95fd7},{"l_tokn",0xd7f7d549}};
  static string Hash(byte[] bytes){using(var s=SHA256.Create())return BitConverter.ToString(s.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();}
  internal static void Ensure(string game) {
   var updated=new Dictionary<string,byte[]>();var originals=new Dictionary<string,byte[]>();
   foreach(var pair in Pins) {
    string path=Path.Combine(game,pair.Key,"scripts",pair.Key+".ds"),backup=path+".cosmic-discord-original";
    byte[] original=File.ReadAllBytes(File.Exists(backup)?backup:path);
    if(Hash(original)!=pair.Value)throw new IOException("Unsupported original mission script: "+pair.Key);
    byte[] target=AllAliensPatch.PresenceMission(original,pair.Key);string current=Hash(File.ReadAllBytes(path));
    if(current==Hash(target))continue;
    if(current!=pair.Value)throw new IOException("Unknown mission-script edit: "+pair.Key);
    originals.Add(path,original);updated.Add(path,target);
   }
   foreach(var pair in updated){string backup=pair.Key+".cosmic-discord-original",temp=pair.Key+".cosmic-discord-new";
    if(!File.Exists(backup))File.WriteAllBytes(backup,originals[pair.Key]);File.WriteAllBytes(temp,pair.Value);File.Replace(temp,pair.Key,null);}
  }
 }
}
