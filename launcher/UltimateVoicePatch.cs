using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace CosmicRecompi {
    // Local ISO resources only. Append missing name callouts; never replace a
    // sample, reorder existing subsounds, re-encode audio or add playback events.
    internal static class UltimateVoicePatch {
        static readonly string[] Prefixes={"ult_bigchill_name_callout_","ult_echoecho_name_callout_",
            "ult_humongousaur_name_callout_","ult_swampfire_name_callout_","ult_spidermonkey_name_callout_"};
        static readonly Dictionary<string,string> Originals=new Dictionary<string,string> {
            {"global","42cdd4c886e4a0cc56206f20ad9a9a0080e89d5babbb2bc0721cde086862cc4b"},
            {"l_chin","19bf511afdd82219e4be10e1c2735870f0f1f68ceaf53193eab9cfac005b3b68"},
            {"l_mili","8e3230afdb35cc0da0f7979d6295127e9f3192bca5e77677372dfb9d870ead6f"},
            {"l_pari","50e74e005279e7a334fc85c09952e594d0685cc6d13905ab812d18403ab3cc32"},
            {"l_romd","f8ee9e2888b3da2a3873c559c147d07b427e94e83834a63f8039036d42bba8f5"},
            {"l_romn","37b24609914995e179e39f6cffcf4aa5c57ea7b309759eaea7e915738c4ce54b"},
            {"l_rush","7be743e733f711b827c2ab74b7c278f92b5630bc5c42c84ad17e87e947dcd796"},
            {"l_tokd","87ccefd9a01dd4bc115aa88093d0ddda83186c8f10266dc6d8ebfa47c34b5532"},
            {"l_tokn","701d309ff46dd201580a845abec86703cc348b744b2efb629d5b9cabf0156c1b"}
        };
        sealed class Sample { internal string Name; internal byte[] Header,Data; }
        static int Word(byte[] b,int p) { return checked((int)BitConverter.ToUInt32(b,p)); }
        static void Put(byte[] b,int p,int n) { Buffer.BlockCopy(BitConverter.GetBytes(n),0,b,p,4); }
        static byte[] Slice(byte[] b,int p,int n) { var r=new byte[n];Buffer.BlockCopy(b,p,r,0,n);return r; }
        internal static string Hash(byte[] b) { using(var s=SHA256.Create())return BitConverter.ToString(s.ComputeHash(b)).Replace("-","").ToLowerInvariant(); }
        static List<Sample> Parse(byte[] b) {
            if(b.Length<48 || Encoding.ASCII.GetString(b,0,4)!="FSB4" || Word(b,16)!=0x40000 || Word(b,20)!=0x40)
                throw new InvalidDataException("Unsupported voice bank format.");
            int count=Word(b,4),headers=Word(b,8),data=Word(b,12);
            if(count>10000 || (long)48+headers+data!=b.Length)throw new InvalidDataException("Invalid voice bank bounds.");
            int at=48,offset=48+headers;var result=new List<Sample>();
            for(int i=0;i<count;i++) {
                if(at+80>48+headers)throw new InvalidDataException("Truncated voice header.");
                int size=BitConverter.ToUInt16(b,at),packed=Word(b,at+36);
                if(size<80 || size>48+headers-at || packed>b.Length-offset || packed%2048!=0)
                    throw new InvalidDataException("Invalid voice sample bounds/alignment.");
                string name=Encoding.ASCII.GetString(b,at+2,30).TrimEnd('\0');
                // Original banks have truncated-name collisions. Preserve them
                // in place; uniqueness is required only for our five donors.
                result.Add(new Sample{Name=name,Header=Slice(b,at,size),Data=Slice(b,offset,packed)});
                at+=size;offset+=packed;
            }
            if(offset!=b.Length || at>48+headers || 48+headers-at>=32 || (48+headers)%32!=0)throw new InvalidDataException("Invalid voice bank padding.");
            for(int i=at;i<48+headers;i++)if(b[i]!=0)throw new InvalidDataException("Nonzero voice bank padding.");
            return result;
        }
        internal static byte[] Merge(byte[] original,byte[][] donors) {
            var samples=Parse(original);var selected=new List<Sample>();
            for(int i=0;i<Prefixes.Length;i++) {
                Sample found=null;
                foreach(var sample in Parse(donors[i]))if(sample.Name.StartsWith(Prefixes[i],StringComparison.Ordinal)) {
                    if(found!=null)throw new InvalidDataException("Ambiguous Ultimate callout.");found=sample;
                }
                if(found==null)throw new InvalidDataException("Missing Ultimate callout.");selected.Add(found);
            }
            if(samples.Count==221) {
                for(int i=0;i<5;i++)if(samples[216+i].Name!=selected[i].Name || Hash(samples[216+i].Data)!=Hash(selected[i].Data))
                    throw new InvalidDataException("Unexpected fixed callout slots.");
                return original;
            }
            if(samples.Count>216)throw new InvalidDataException("Unsupported original sample count.");
            while(samples.Count<216) {
                byte[] header=(byte[])selected[0].Header.Clone();Array.Clear(header,2,30);
                byte[] name=Encoding.ASCII.GetBytes("cosmic_voice_padding_"+samples.Count);
                Buffer.BlockCopy(name,0,header,2,name.Length);
                samples.Add(new Sample{Name=Encoding.ASCII.GetString(name),Header=header,Data=selected[0].Data});
            }
            samples.AddRange(selected);int headers=0,data=0;
            foreach(var sample in samples){headers=checked(headers+sample.Header.Length);data=checked(data+sample.Data.Length);}
            headers=checked((48+headers+31)/32*32-48);var output=new byte[checked(48+headers+data)];
            Buffer.BlockCopy(original,0,output,0,48);Put(output,4,samples.Count);Put(output,8,headers);Put(output,12,data);
            int h=48,d=48+headers;
            foreach(var sample in samples){Buffer.BlockCopy(sample.Header,0,output,h,sample.Header.Length);h+=sample.Header.Length;
                Buffer.BlockCopy(sample.Data,0,output,d,sample.Data.Length);d+=sample.Data.Length;}
            Parse(output);return output;
        }
        static byte[] Legacy(byte[] original,byte[][] donors) {
            var samples=Parse(original);var names=new HashSet<string>();foreach(var s in samples)names.Add(s.Name);
            for(int i=0;i<5;i++)foreach(var s in Parse(donors[i]))if(s.Name.StartsWith(Prefixes[i],StringComparison.Ordinal) && names.Add(s.Name))samples.Add(s);
            int headers=0,data=0;foreach(var s in samples){headers+=s.Header.Length;data+=s.Data.Length;}
            headers=(48+headers+31)/32*32-48;byte[] output=new byte[48+headers+data];Buffer.BlockCopy(original,0,output,0,48);
            Put(output,4,samples.Count);Put(output,8,headers);Put(output,12,data);int h=48,d=48+headers;
            foreach(var s in samples){Buffer.BlockCopy(s.Header,0,output,h,s.Header.Length);h+=s.Header.Length;Buffer.BlockCopy(s.Data,0,output,d,s.Data.Length);d+=s.Data.Length;}
            return output;
        }
        internal static void Ensure(string game) {
            var originals=new Dictionary<string,byte[]>();var paths=new Dictionary<string,string>();
            // Validate every input before making any change. A backup is the
            // immutable source for idempotent upgrades and manual rollback.
            foreach(var pair in Originals) {
                string path=Path.Combine(game,pair.Key,"vo","vo_eng.xbx"),backup=path+".cosmic-voice-original";
                byte[] bytes=File.ReadAllBytes(File.Exists(backup)?backup:path);
                if(Hash(bytes)!=pair.Value)throw new IOException("Unsupported or modified original voice bank: "+pair.Key);
                originals.Add(pair.Key,bytes);paths.Add(pair.Key,path);
            }
            var donors=new byte[][]{originals["l_chin"],originals["l_mili"],originals["l_romd"],originals["l_pari"],originals["l_rush"]};
            var updates=new Dictionary<string,byte[]>();
            foreach(var pair in originals) {
                byte[] updated=Merge(pair.Value,donors);string path=paths[pair.Key];string current=Hash(File.ReadAllBytes(path));
                if(current==Hash(updated))continue;
                if(current!=Hash(pair.Value) && current!=Hash(Legacy(pair.Value,donors)))throw new IOException("Another patch modified the voice bank: "+pair.Key);
                updates.Add(pair.Key,updated);
            }
            foreach(var pair in updates) {
                string path=paths[pair.Key],backup=path+".cosmic-voice-original",temp=path+".cosmic-voice-new";
                if(!File.Exists(backup))File.WriteAllBytes(backup,originals[pair.Key]);
                File.WriteAllBytes(temp,pair.Value);File.Replace(temp,path,null);
            }
        }
    }
}
