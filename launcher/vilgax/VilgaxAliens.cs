using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;

namespace CosmicRecompi {
    // Aliens imported from Vilgax Attacks: installed only by the Vilgax Attacks
    // aliens bridge (CosmicVilgaxBridge.exe), built with --vilgax.
    internal static partial class AllAliensPatch {
        // Aliens imported from Vilgax Attacks (tools/prepare_vilgax_import.py).
        // Each installation/vilgax/<name> bundle holds the form's package,
        // attack table, data records and registration scripts.
        internal sealed class ImportedForm {public string Folder,Name;public int Id;}
        // Only the first N forms: an earlier install had fewer imported aliens.
        static int ImportedLimit=int.MaxValue;
        internal static List<ImportedForm> ImportedForms(string installation) {
            var forms=new List<ImportedForm>();
            string root=Path.Combine(installation,"vilgax");
            if(!Directory.Exists(root))return forms;
            foreach(string folder in Directory.GetDirectories(root)) {
                string ids=Path.Combine(folder,"form-ids.txt");
                if(!File.Exists(ids))continue;
                string[] fields=File.ReadAllText(ids).Trim().Split(' ');
                int id;
                if(fields.Length!=2 || !int.TryParse(fields[1],out id) || id<20 || id>23)
                    throw new InvalidDataException("Unexpected imported form: "+folder);
                forms.Add(new ImportedForm{Folder=folder,Name=fields[0],Id=id});
            }
            forms.Sort((a,b)=>a.Id.CompareTo(b.Id));
            if(ImportedLimit<forms.Count)forms.RemoveRange(ImportedLimit,forms.Count-ImportedLimit);
            return forms;
        }
        // Records in a data file after its signature: 24-byte header (key first,
        // size last) followed by the record.
        static List<byte[]> DataRecords(byte[] b,int start) {
            var rows=new List<byte[]>();int p=start;
            while(p<b.Length) {
                if(p>b.Length-24)throw new InvalidDataException("Truncated data record.");
                int size=checked((int)Read(b,p+20));
                if(size<0 || size>b.Length-p-24)throw new InvalidDataException("Invalid data record.");
                rows.Add(Prefix(Skip(b,p),24+size));p+=24+size;
            }
            return rows;
        }
        static byte[] Skip(byte[] b,int n){var r=new byte[b.Length-n];Buffer.BlockCopy(b,n,r,0,r.Length);return r;}
        // Adds each imported form's records to a data file, replacing any earlier
        // copy of them. Other edits to the file (Albedo swaps Way Big's models in
        // char.ddf) are kept as they are.
        internal static void EnsureImportedRecords(string game) {
            var forms=ImportedForms(Path.GetDirectoryName(game));
            if(forms.Count==0)return;
            foreach(var file in new[]{new[]{"char.ddf","character-records.bin"},new[]{"player.ddf","player-records.bin"},new[]{"xbx.ddf","xbx-records.bin"}}) {
                string path=Path.Combine(game,"global","scripts",file[0]),backup=path+".cosmic-original";
                byte[] current=File.ReadAllBytes(path);
                if(Read(current,0)!=0x1badbabe)throw new InvalidDataException("Unexpected "+file[0]);
                var added=new List<byte[]>();var keys=new HashSet<uint>();
                foreach(var form in forms)foreach(var row in DataRecords(File.ReadAllBytes(Path.Combine(form.Folder,file[1])),0)){added.Add(row);keys.Add(Read(row,0));}
                using(var updated=new MemoryStream()) {
                    updated.Write(current,0,4);
                    foreach(var row in DataRecords(current,4))if(!keys.Contains(Read(row,0)))updated.Write(row,0,row.Length);
                    foreach(var row in added)updated.Write(row,0,row.Length);
                    byte[] result=updated.ToArray();
                    if(Hash(current)==Hash(result))continue;
                    if(!File.Exists(backup))File.WriteAllBytes(backup,current);
                    File.WriteAllBytes(path+".cosmic-new",result);
                    File.Replace(path+".cosmic-new",path,null);
                }
            }
            EnsureImportedSoundBanks(game,forms);
        }
        // Registers the FMOD project an imported form carries in its package
        // (section 24, named by prjid in sounds.txt) in sndbnk.ddf, next to
        // Four Arms' project. An unregistered project crashes the level load.
        static void EnsureImportedSoundBanks(string game,List<ImportedForm> forms) {
            string path=Path.Combine(game,"global","scripts","sndbnk.ddf"),backup=path+".cosmic-original";
            string original=Encoding.UTF8.GetString(File.ReadAllBytes(File.Exists(backup)?backup:path));
            const string bankAnchor="\t<sfxbank file=\"fourarm\" ";
            const string groupAnchor="  <sfxeventgroups name=\"fourarm\">";
            int bank=original.IndexOf(bankAnchor,StringComparison.Ordinal),group=original.IndexOf(groupAnchor,StringComparison.Ordinal);
            if(bank<0 || group<0 || original.IndexOf(bankAnchor,bank+1,StringComparison.Ordinal)>=0)
                throw new InvalidDataException("Unexpected sound bank list.");
            int bankEnd=original.IndexOf('\n',bank)+1,groupEnd=original.IndexOf("</sfxeventgroups>",group,StringComparison.Ordinal);
            groupEnd=original.IndexOf('\n',groupEnd)+1;
            string bankLine=original.Substring(bank,bankEnd-bank),groupBlock=original.Substring(group,groupEnd-group);
            var banks=new StringBuilder();var groups=new StringBuilder();
            foreach(var form in forms) {
                string sounds=Path.Combine(form.Folder,"sounds.txt");
                if(!File.Exists(sounds))continue;
                var projects=new HashSet<string>();
                foreach(string line in File.ReadAllLines(sounds)) {
                    int at=line.IndexOf("prjid=\"",StringComparison.Ordinal);
                    if(at>=0)projects.Add(line.Substring(at+7,line.IndexOf('"',at+7)-at-7));
                }
                foreach(string project in projects) {
                    if(project.Length==0 || project.Length>16 || original.Contains("\""+project+"\""))
                        throw new InvalidDataException("Unexpected imported sound project.");
                    banks.Append(bankLine.Replace("\"fourarm\"","\""+project+"\""));
                    groups.Append(groupBlock.Replace("\"fourarm\"","\""+project+"\""));
                }
            }
            string updated=original.Substring(0,bankEnd)+banks+original.Substring(bankEnd,groupEnd-bankEnd)+groups+original.Substring(groupEnd);
            byte[] result=Encoding.UTF8.GetBytes(updated),current=File.ReadAllBytes(path);
            if(Hash(current)==Hash(result))return;
            if(!File.Exists(backup))File.WriteAllBytes(backup,current);
            File.WriteAllBytes(path+".cosmic-new",result);
            File.Replace(path+".cosmic-new",path,null);
        }
        static byte[] Prefix(byte[] b,int n){var r=new byte[n];Buffer.BlockCopy(b,0,r,0,n);return r;}
        // A re-imported form only changes its own registration scripts.
        static bool EarlierImport(byte[] current,byte[] updated,List<ImportedForm> forms) {
            if(forms.Count==0)return false;
            List<Record> installed,expected;
            try{installed=Parse(current);expected=Parse(updated);}catch(InvalidDataException){return false;}
            var imported=new HashSet<uint>();
            foreach(var form in forms)foreach(var row in Parse(File.ReadAllBytes(Path.Combine(form.Folder,"forms.bin"))))imported.Add(row.Id);
            var rows=new Dictionary<uint,Record>();
            foreach(var row in expected)if(!imported.Contains(row.Id))rows[row.Id]=row;
            int matched=0;
            foreach(var row in installed) {
                if(imported.Contains(row.Id))continue;
                Record match;
                if(!rows.TryGetValue(row.Id,out match) || match.Args!=row.Args || Hash(match.Code)!=Hash(row.Code))return false;
                matched++;
            }
            return matched==rows.Count;
        }
    }
}
