using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;

namespace CosmicRecompi {
    // Source for the authored program: tools/prepare_all_aliens_candidate.py.
    // Original instructions are read only from hash-verified user files.
    internal static class AllAliensPatch {
        static uint Read(byte[] b,int p) {
            if(p<0 || p>b.Length-4)throw new InvalidDataException("Truncated All Aliens script.");
            return ((uint)b[p]<<24)|((uint)b[p+1]<<16)|((uint)b[p+2]<<8)|b[p+3];
        }
        static uint Crc(string name) {
            uint c=0xffffffff;
            foreach(byte b in Encoding.ASCII.GetBytes(name.ToLowerInvariant())) {
                c^=b;for(int i=0;i<8;i++)c=(c>>1)^((c&1)!=0?0xedb88320U:0);
            }
            return c^0xffffffff;
        }
        static string Hash(byte[] b) {
            using(var s=SHA256.Create())return BitConverter.ToString(s.ComputeHash(b)).Replace("-","").ToLowerInvariant();
        }
        static void Word(Stream s,uint v){s.WriteByte((byte)(v>>24));s.WriteByte((byte)(v>>16));s.WriteByte((byte)(v>>8));s.WriteByte((byte)v);}
        static byte[] Bytes(IEnumerable<uint> words){using(var s=new MemoryStream()){foreach(uint w in words)Word(s,w);return s.ToArray();}}
        sealed class Record {public uint Id,Args;public byte[] Code;}
        static List<Record> Parse(byte[] b,bool preserveDuplicateIds=false) {
            if(Read(b,0)!=0x1badbabe)throw new InvalidDataException("Invalid script signature.");
            var rows=new List<Record>();int p=8;uint count=Read(b,4);
            if(count>4096)throw new InvalidDataException("Unexpected script record count.");
            var ids=new HashSet<uint>();
            for(int i=0;i<count;i++) {
                var row=new Record {Id=Read(b,p),Args=Read(b,p+4)};
                int n=checked((int)Read(b,p+8)*4);p+=12;
                if(n>b.Length-p || (!ids.Add(row.Id) && !preserveDuplicateIds))throw new InvalidDataException("Invalid script record.");
                row.Code=new byte[n];Buffer.BlockCopy(b,p,row.Code,0,n);p+=n;rows.Add(row);
            }
            if(p!=b.Length)throw new InvalidDataException("Trailing script bytes.");return rows;
        }
        static byte[] Pack(List<Record> rows) {
            using(var s=new MemoryStream()) {
                Word(s,0x1badbabe);Word(s,(uint)rows.Count);
                foreach(var r in rows){Word(s,r.Id);Word(s,r.Args);Word(s,(uint)(r.Code.Length/4));s.Write(r.Code,0,r.Code.Length);}
                return s.ToArray();
            }
        }
        static List<int> Tokens(byte[] b) {
            var positions=new List<int>();int p=0;
            while(p<b.Length) {
                positions.Add(p/4);uint kind=Read(b,p)&255;int size=4;
                if(kind==3 || kind==5 || kind==7 || kind==8 || kind==0x17 || kind==0x19 || kind==0x20)size=8;
                else if(kind==4) {
                    int end=Array.IndexOf(b,(byte)0,p+4);
                    if(end<0)throw new InvalidDataException("Unterminated script literal.");
                    size=((end+1-p+3)/4)*4;
                }else if(kind<1 || kind>0x22)throw new InvalidDataException("Unexpected script opcode.");
                p=checked(p+size);if(p>b.Length)throw new InvalidDataException("Truncated script token.");
            }
            return positions;
        }
        sealed class Fixup {public int Position,Target,Shift;public bool Local;}
        sealed class Injection {
            public List<uint> Words=new List<uint>();public List<Fixup> Fixups=new List<Fixup>();
            public void Add(params uint[] words){Words.AddRange(words);}
            public void Branch(int reg,int target,bool local=false) {
                Fixups.Add(new Fixup{Position=Words.Count,Target=target,Shift=16,Local=local});Words.Add((uint)(reg<<8)|0x1f);
            }
            public void Jump(int target,bool local=false) {
                Fixups.Add(new Fixup{Position=Words.Count,Target=target,Shift=8,Local=local});Words.Add(0x1d);
            }
        }
        static Injection Hook(params string[] names) {
            var i=new Injection();
            foreach(string name in names)i.Add(0x00001b07,Crc(name),0x00281b20,3);
            return i;
        }
        static byte[] Relocate(byte[] code,Dictionary<int,Injection> insertions) {
            var positions=Tokens(code);var boundaries=new HashSet<int>(positions);boundaries.Add(code.Length/4);
            foreach(int p in insertions.Keys)if(!boundaries.Contains(p))throw new InvalidDataException("Hook inside script token.");
            Func<int,int> map=delegate(int p){int q=p;foreach(var i in insertions)if(i.Key<p)q+=i.Value.Words.Count;return q;};
            var output=new List<uint>();
            for(int i=0;i<positions.Count;i++) {
                int p=positions[i],next=i+1<positions.Count?positions[i+1]:code.Length/4;
                Injection added;
                if(insertions.TryGetValue(p,out added)) {
                    uint[] words=added.Words.ToArray();int start=output.Count;
                    foreach(var f in added.Fixups)words[f.Position]|=(uint)(f.Local?start+f.Target:map(f.Target))<<f.Shift;
                    output.AddRange(words);
                }
                uint value=Read(code,p*4),kind=value&255;
                if(kind==0x1d || kind==0x1e || kind==0x1f) {
                    int shift=kind==0x1d?8:16,target=(int)(value>>shift);
                    if(!boundaries.Contains(target))throw new InvalidDataException("Invalid original branch.");
                    value=(value&((1U<<shift)-1))|((uint)map(target)<<shift);
                }
                output.Add(value);for(int k=p+1;k<next;k++)output.Add(Read(code,k*4));
            }
            byte[] result=Bytes(output);var targets=new HashSet<int>(Tokens(result));targets.Add(result.Length/4);
            foreach(int p in Tokens(result)) {
                uint value=Read(result,p*4),kind=value&255;
                if((kind==0x1d || kind==0x1e || kind==0x1f) && !targets.Contains((int)(value>>(kind==0x1d?8:16))))
                    throw new InvalidDataException("Invalid relocated branch.");
            }
            return result;
        }
        static Injection EmptySlotGuard(int nextIteration) {
            var i=new Injection();
            i.Add(0x00002d07,Crc("gFormHotKey"),0x1f1d2d18,0x00201f17,Crc("formID"));
            // Present form -> original HUD path. Empty form -> original blank
            // portrait routine, then skip all gFormData[nil] reads.
            i.Branch(32,7,true);i.Jump(15,true);
            i.Add(0x00281806,0x00291d06,0x00001b07,Crc("CosmicEmptyAlienIcon"),0x02281b20,31);
            i.Jump(nextIteration);
            i.Fixups[1].Target=i.Words.Count;
            return i;
        }
        public static byte[] Frontend(byte[] original) {
            var rows=Parse(original);int patched=0;
            foreach(var r in rows)if(r.Id==Crc("GameplayMenu_Enter")) {
                if(r.Code.Length!=241*4)throw new InvalidDataException("Unexpected Gameplay menu.");
                var i=new Injection();
#if !COSMIC_HERO_TIME
                i.Add(
                    0x00000807,0x0fc54df4,0x00000905,Crc("cosmic_all_aliens_label"),
                    0x00001d07,Crc("overlay"),0x00281d06,0x001e1d17,Crc("cosmic_all_aliens_enabled"),0x01281e20,1,
                    0x00000203,0x3f800000,0x0a020110,
                    0x00000b07,Crc("CosmicToggleAllAliens"),
                    0x00280806,0x00290906,0x002a0a06,0x002b0b06,
                    0x00001e07,0xa6c36cbb,0x04281e20,3);
#endif
#if COSMIC_NATIVE_SETTINGS
                i.Add(0x00000807,0x0fc54df4,0x00000905,Crc("cosmic_wipe_label"),
                    0x00000a01,0x00000b07,Crc("CosmicWipeProgress"),0x00000c01,
                    0x00000207,Crc("Menu_AddOption"),0x05080220,3);
#endif
                r.Code=Relocate(r.Code,new Dictionary<int,Injection>{{96,i}});patched++;
            }
            if(patched!=1)throw new InvalidDataException("Gameplay menu missing.");
            foreach(var r in rows)if(r.Id==Crc("pausemenu_enter"))
                r.Code=Relocate(r.Code,new Dictionary<int,Injection>{{0,Hook("CosmicAlienRestore")}});
#if COSMIC_NATIVE_SETTINGS
            int inputPatched=0;
            foreach(var r in rows)if(r.Id==0x3b77a27e) {
                // Original Gameplay's pre-input handler consumes A to confirm
                // the whole settings screen. Let the standard option handler
                // receive A only on our fourth row. Keep B and every original
                // checkbox's confirmation/cancel behavior untouched.
                if(r.Args!=2 || r.Code.Length!=106*4)throw new InvalidDataException("Unexpected Gameplay input handler.");
                var guard=new Injection();
                guard.Add(0x001e0017,0x74a09b28,0x00001f03,
#if COSMIC_HERO_TIME
                    0x40400000,
#else
                    0x40800000,
#endif
                    0x201f1e10);
                guard.Branch(32,11,true);
                guard.Add(0x00220117,0xe585980f);
                guard.Branch(34,11,true);
                guard.Add(0x00002102,0x00002122);
                r.Code=Relocate(r.Code,new Dictionary<int,Injection>{{0,guard}});inputPatched++;
            }
            if(inputPatched!=1)throw new InvalidDataException("Gameplay input handler missing.");
#endif
            rows.Add(new Record{Id=Crc("CosmicToggleAllAliens"),Args=1,Code=Bytes(new uint[]{
                0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),0x00000217,Crc("cosmic_toggle_all_aliens"),0x01050020,1,0x21})});
            return Pack(rows);
        }
        internal static byte[] SettingsPreview(byte[] original,byte[] preview) {
            var stock=Parse(original);
            var rows=Parse(preview);
            var gameplay=stock.Find(r=>r.Id==Crc("GameplayMenu_Enter"));
            var target=rows.Find(r=>r.Id==Crc("GameplayMenu_Enter"));
            var input=rows.Find(r=>r.Id==0x3b77a27e);
            var sound=rows.Find(r=>r.Id==Crc("SoundMenu_Enter"));
            if(gameplay==null || target==null || input==null || sound==null ||
               gameplay.Code.Length!=241*4 || Read(gameplay.Code,123*4)!=0x00000507 ||
               Read(gameplay.Code,124*4)!=0x77f62458 ||
               Read(input.Code,0)!=0x001e0017 || Read(input.Code,12)!=0x40400000 ||
               Read(sound.Code,0)!=0x00000803 || Read(sound.Code,4)!=0x3f000000)
                throw new InvalidDataException("Unexpected original settings layout.");

            // Keep the original camera, vibration and menu callbacks. Put the
            // extra toggles and the confirmed reset after those stock rows.
            var additions=new Injection();
            foreach(string[] row in new[]{
                new[]{"cosmic_all_aliens_label","cosmic_all_aliens_enabled","CosmicToggleAllAliens"},
                new[]{"cosmic_hero_label","cosmic_hero_enabled","CosmicToggleHeroTime"},
                new[]{"cosmic_albedo_hud_label","cosmic_albedo_hud_enabled","CosmicToggleAlbedoHud"}}) {
                additions.Add(0x00000807,0x0fc54df4,0x00000905,Crc(row[0]),
                    0x00001d07,Crc("overlay"),0x00281d06,0x001e1d17,Crc(row[1]),0x01281e20,1,
                    0x00000203,0x3f800000,0x0a020110,0x00000b07,Crc(row[2]),
                    0x00280806,0x00290906,0x002a0a06,0x002b0b06,
                    0x00001e07,0xa6c36cbb,0x04281e20,3);
            }
            additions.Add(0x00000807,0x0fc54df4,0x00000905,Crc("cosmic_wipe_label"),
                0x00000a01,0x00000b07,Crc("CosmicWipeProgress"),0x00000c01,
                0x00000207,Crc("Menu_AddOption"),0x05080220,3);
            target.Code=Relocate(gameplay.Code,new Dictionary<int,Injection>{{123,additions}});
            // Raise the first row to leave space for the combined list.
            Buffer.BlockCopy(Bytes(new uint[]{0x3f266666}),0,target.Code,12*4,4);

            // The existing Confirm guard compares the selection with a fixed
            // Wipe Data index. Here Wipe Data is always the last menu option,
            // including when the original platform check omits Vibration.
            var lastRow=new Injection();
            lastRow.Add(0x001f0017,0x90274abc,0x00002003,0x3f800000,0x1f201f0b);
            input.Code=Relocate(input.Code,new Dictionary<int,Injection>{{4,lastRow}});

            // Keep the stock sound rows, live mixer callbacks, and cancel
            // snapshot. Move the three-row group lower within the panel.
            Buffer.BlockCopy(Bytes(new uint[]{0x3ee66666}),0,sound.Code,4,4);
            return Pack(rows);
        }

        internal static byte[] StyledGameplayPreview(byte[] original,byte[] preview,int legacy=0) {
            var stock=Parse(original);
            var rows=Parse(preview);
            var source=stock.Find(r=>r.Id==Crc("GameplayMenu_Enter"));
            var entry=rows.Find(r=>r.Id==Crc("GameplayMenu_Enter"));
            var video=rows.Find(r=>r.Id==Crc("CosmicVideoOptions"));
            var vibration=stock.Find(r=>r.Id==0xa096ad03);
            if(source==null || source.Code.Length!=241*4 || entry==null ||
               video==null || Read(video.Code,7*4)!=1 || vibration==null ||
               vibration.Code.Length!=41*4 || Read(vibration.Code,22*4)!=0x00010502)
                throw new InvalidDataException("Unexpected Gameplay preview callbacks.");

            string[] names={"pitch","yaw","vibration"};
            int[] getters={58,79,108};
            int[] ends={68,89,116};
            uint[] preferences={0x89299dc9,0x502823d8,0xbfb146c9};
            uint[] setters={0x000e859d,0x11c12fdd,Crc("CosmicPreviewVibration")};
            bool previous=legacy==1;
            var tick=new Injection();
            if(!previous)PreviewNative(tick,"cosmic_gameplay_begin_tick",0);
            for(int i=0;i<names.Length;i++) {
                // A nonnegative result is the new setting. Use the stock
                // callback and acknowledge only after the callback returns.
                PreviewNative(tick,"cosmic_gameplay_"+names[i]+"_value",2,legacy);
                tick.Add(0x00000403,0xbf800000,0x03040211);
                int noChange=tick.Fixups.Count;
                tick.Branch(3,0,true);
                // Stock checkboxes pass VM booleans. The bridge returns a numeric command.
                if(legacy==0 || (legacy==4 && i==2))tick.Add(0x00000403,0x3f800000,0x08040210);
                else tick.Add(0x00080206);
                tick.Add(0x00000207,setters[i],0x01080220,1);
                PreviewCapture(tick,source.Code,getters[i],ends[i],names[i],legacy==0?preferences[i]:0,legacy==4 && i==2);
                tick.Fixups[noChange].Target=tick.Words.Count;
            }
            PreviewNative(tick,"cosmic_gameplay_finish",2,legacy);
            tick.Add(0x00000403,0x3f800000,0x03040210);
            int stay=tick.Fixups.Count;
            tick.Branch(3,0,true);
            PreviewNative(tick,"popfunction",0);
            if(!previous)for(int i=8;i<video.Code.Length/4-1;i++)tick.Add(Read(video.Code,i*4));
            tick.Fixups[stay].Target=tick.Words.Count;
            tick.Add(0x21);
            foreach(var fix in tick.Fixups)tick.Words[fix.Position]|=(uint)fix.Target<<fix.Shift;

            var open=new Injection();
            for(int i=0;i<names.Length;i++)PreviewCapture(open,source.Code,getters[i],ends[i],names[i],legacy==0?preferences[i]:0,legacy==4 && i==2);
            foreach(var fix in open.Fixups)open.Words[fix.Position]|=(uint)fix.Target<<fix.Shift;
            PreviewNative(open,"cosmic_gameplay_open",0);
            // Legacy preview restored Options before pushing the update callback.
            if(previous)for(int i=8;i<video.Code.Length/4-1;i++)open.Add(Read(video.Code,i*4));
            open.Add(0x00000507,Crc("overlay"),0x00000607,Crc("CosmicGameplayTick"),
                0x00000207,Crc("overlay"),0x00000217,Crc("pushfunction"),0x02050020,1,0x21);
            entry.Code=Bytes(open.Words);
            rows.Add(new Record{Id=Crc("CosmicGameplayTick"),Args=2,Code=Bytes(tick.Words)});
            var volumeIndependent=new List<uint>();
            // The trailing stock code animates a checkbox in the original
            // menu. The first part owns the actual rumble preference.
            for(int i=0;i<22;i++)volumeIndependent.Add(Read(vibration.Code,i*4));
            volumeIndependent.Add(0x21);
            rows.Add(new Record{Id=setters[2],Args=1,Code=Bytes(volumeIndependent)});
            return Pack(rows);
        }
        static void PreviewNative(Injection script,string name,uint result,int legacy=0) {
            script.Add(0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),
                (legacy==2?0:result<<16)|0x00000217,Crc(name),0x01050220-(result==0?0x200u:0u),
                legacy==1 || result==0?1:result);
        }
        static void PreviewCapture(Injection script,byte[] source,int begin,int end,string name,uint preference,bool legacyVibration) {
            if(preference!=0)script.Add(0x00000507,0xe545a0c5,0x00020517,preference);
            else for(int i=begin;i<end;i++)script.Add(Read(source,i*4));
            if(preference!=0 || legacyVibration)script.Add(0x00010402,0x03040210);
            else script.Add(0x00000403,0x3f800000,0x03040210);
            int off=script.Fixups.Count;
            script.Branch(3,0,true);
            PreviewNative(script,"cosmic_gameplay_"+name+"_on",0);
            int done=script.Fixups.Count;
            script.Jump(0,true);
            script.Fixups[off].Target=script.Words.Count;
            PreviewNative(script,"cosmic_gameplay_"+name+"_off",0);
            script.Fixups[done].Target=script.Words.Count;
        }

        internal static byte[] StyledSoundPreview(byte[] preview,bool previous=false) {
            var rows=Parse(preview);
            var entry=rows.Find(r=>r.Id==Crc("SoundMenu_Enter"));
            var video=rows.Find(r=>r.Id==Crc("CosmicVideoOptions"));
            if(entry==null || entry.Code.Length!=188*4 || video==null || Read(video.Code,7*4)!=1)
                throw new InvalidDataException("Unexpected Sound preview callbacks.");

            string[] names={"music","sfx","voice"};
            uint[] preferences={0x3faa0027,0x2d16f1ee,0x1fdf5f40};
            uint[] setters={0xa3db69e6,0xcdfa48f8,0x252f93da};
            var open=new Injection();
            var tick=new Injection();
            PreviewNative(tick,"cosmic_sound_begin_tick",0);
            for(int i=0;i<names.Length;i++) {
                string capture="cosmic_sound_"+names[i]+"_read";
                SoundPreviewCapture(open,preferences[i],capture,previous);
                PreviewNative(tick,"cosmic_sound_"+names[i]+"_value",2);
                tick.Add(0x00000403,0xbf800000,0x03040211);
                int unchanged=tick.Fixups.Count;
                tick.Branch(3,0,true);
                tick.Add(0x00080206,0x00000207,setters[i],0x01080220,1);
                SoundPreviewCapture(tick,preferences[i],capture,previous);
                tick.Fixups[unchanged].Target=tick.Words.Count;
            }
            PreviewNative(tick,"cosmic_sound_finish",2);
            tick.Add(0x00000403,0x3f800000,0x03040210);
            int stay=tick.Fixups.Count;
            tick.Branch(3,0,true);
            PreviewNative(tick,"popfunction",0);
            for(int i=8;i<video.Code.Length/4-1;i++)tick.Add(Read(video.Code,i*4));
            tick.Fixups[stay].Target=tick.Words.Count;
            tick.Add(0x21);
            foreach(var fix in tick.Fixups)tick.Words[fix.Position]|=(uint)fix.Target<<fix.Shift;

            PreviewNative(open,"cosmic_sound_open",0);
            open.Add(0x00000507,Crc("overlay"),0x00000607,Crc("CosmicSoundTick"),
                0x00000207,Crc("overlay"),0x00000217,Crc("pushfunction"),0x02050020,1,0x21);
            entry.Code=Bytes(open.Words);
            rows.Add(new Record{Id=Crc("CosmicSoundTick"),Args=2,Code=Bytes(tick.Words)});
            return Pack(rows);
        }
        // Recognize menus written by the previous local audio preview.
        internal static byte[] LegacyCinematicVoiceVolume(byte[] frontend) {
            var rows=Parse(frontend);
            // Observe the same saved Voice value applied by the stock mixer.
            foreach(uint id in new uint[]{0x87e6bef2,0x252f93da,0x9dcb4a3d}) {
                var row=rows.Find(r=>r.Id==id);
                if(row==null)throw new InvalidDataException("Missing voice volume handler.");
                int position=Tokens(row.Code).Find(i=>(Read(row.Code,i*4)&255)==0x17 &&
                    Read(row.Code,(i+1)*4)==0x88380a7c);
                if(position==0 || (Read(row.Code,(position+2)*4)&255)!=0x20)
                    throw new InvalidDataException("Unexpected voice volume call.");
                // Run after the mixer call and reuse its scratch registers.
                uint call=Read(row.Code,(position+2)*4);
                uint frame=(call>>16)&255, scratch=(call>>8)&255;
                var capture=new Injection();
                capture.Add((scratch<<8)|7,0xe545a0c5,
                    ((frame+1)<<16)|(scratch<<8)|0x17,0x1fdf5f40,
                    (frame<<8)|7,Crc("overlay"),(scratch<<8)|7,Crc("overlay"),
                    (scratch<<8)|0x17,Crc("cosmic_sound_voice_read"),
                    0x02000020|(frame<<16)|(scratch<<8),Read(row.Code,(position+3)*4));
                row.Code=Relocate(row.Code,new Dictionary<int,Injection>{{position+4,capture}});
            }
            return Pack(rows);
        }
        static void SoundPreviewCapture(Injection script,uint preference,string callback,bool previous) {
            script.Add(0x00000507,0xe545a0c5,0x00060517,preference,
                0x00000507,Crc("overlay"),previous?0x00000217u:0x00000517u,Crc(callback),0x02050020,1);
        }

        internal static byte[] StyledOptionsHub(byte[] preview) {
            var rows=Parse(preview);
            var entry=rows.Find(r=>r.Id==0xb4db5294);
            if(entry==null || entry.Args!=1 || Read(entry.Code,entry.Code.Length-4)!=0x21)
                throw new InvalidDataException("Unexpected Options entry.");

            var open=new Injection();
            // Identical predicate to the original Options Credits row.
            open.Add(0x00000307,0x56b55f63);
            open.Branch(3,0,true);
            PreviewNative(open,"cosmic_options_open_credits",0);
            open.Jump(0,true);
            open.Fixups[0].Target=open.Words.Count;
            PreviewNative(open,"cosmic_options_open",0);
            open.Fixups[1].Target=open.Words.Count;
            open.Add(0x00000507,Crc("overlay"),0x00000607,Crc("CosmicOptionsHubTick"),
                0x00000207,Crc("overlay"),0x00000217,Crc("pushfunction"),0x02050020,1);
            entry.Code=Relocate(entry.Code,new Dictionary<int,Injection>{{entry.Code.Length/4-1,open}});

            uint[] actions={Crc("GameplayMenu_Enter"),Crc("SoundMenu_Enter"),Crc("CosmicVideoOptions"),0x572245a7,Crc("MenuStack_Pop")};
            var tick=new Injection();
            PreviewNative(tick,"cosmic_options_poll",2);
            for(int i=0;i<actions.Length;i++) {
                tick.Add(0x00000403,BitConverter.ToUInt32(BitConverter.GetBytes((float)(i+1)),0),0x03040210);
                int next=tick.Fixups.Count;
                tick.Branch(3,0,true);
                if(i>=3)PreviewNative(tick,"popfunction",0);
                if(i<4) {
                    // Original menu callbacks expect the parent to be hidden before entering.
                    tick.Add(0x00000507,0x8610f32e,0x00000602,
                        0x00000207,Crc("Menu_Show"),0x02050220,1,
                        0x00010502,0x00000207,actions[i],0x01050220,1);
                } else tick.Add(0x00000207,actions[i],0x00050220,1);
                tick.Add(0x21);
                tick.Fixups[next].Target=tick.Words.Count;
            }
            tick.Add(0x21);
            foreach(var fix in tick.Fixups)tick.Words[fix.Position]|=(uint)fix.Target<<fix.Shift;
            rows.Add(new Record{Id=Crc("CosmicOptionsHubTick"),Args=2,Code=Bytes(tick.Words)});
            return Pack(rows);
        }

        // A distinct anchor identifies the compact Pause Menu in the shared menu script.
        const uint CompactPauseAnchor=0x3f0c0000; // .546875
        const uint CompactPausePitch=0x3d872b02; // .066

        // CheatEntered rebuilds the title menu after updating unlocks. Keep the
        // shared animated backdrop alive across its second stack pop.
        static readonly uint KeepCheatBackdrop=Crc("CosmicKeepCheatBackdrop");

        internal static byte[] PreserveCheatBackdropOnRefresh(byte[] frontend) {
            var rows=Parse(frontend);
            var cheat=rows.Find(r=>r.Id==Crc("CheatEntered"));
            if(cheat==null || cheat.Code.Length!=703*4 ||
                Read(cheat.Code,693*4)!=0x02be141f ||
                Read(cheat.Code,695*4)!=Crc("MenuStack_Pop") ||
                Read(cheat.Code,699*4)!=Crc("MainMenuText_Enter"))
                throw new InvalidDataException("Unexpected title cheat refresh.");
            var begin=new Injection();
            begin.Add(0x00001703,0x3f800000,0x00001708,KeepCheatBackdrop);
            var end=new Injection();
            end.Add(0x00001701,0x00001708,KeepCheatBackdrop);
            cheat.Code=Relocate(cheat.Code,new Dictionary<int,Injection>{{694,begin},{698,end}});
            return Pack(rows);
        }

        internal static byte[] GuardCheatBackdropCleanup(byte[] menu) {
            var rows=Parse(menu);
            var destroy=rows.Find(r=>r.Id==0xf4919bc5);
            if(destroy==null || Read(destroy.Code,100*4)!=Crc("MenuIntro_Destroy") ||
                Read(destroy.Code,104*4)!=0xd0cf7cb9)
                throw new InvalidDataException("Unexpected title backdrop cleanup.");
            var guard=new Injection();
            guard.Add(0x00000c07,KeepCheatBackdrop);
            guard.Branch(12,4,true);
            guard.Jump(103);
            destroy.Code=Relocate(destroy.Code,new Dictionary<int,Injection>{{99,guard}});
            return Pack(rows);
        }

        internal static byte[] AlignPauseHighlight(byte[] menu) {
            var rows=Parse(menu);
            // The stock routines position the glow on initial selection and on
            // subsequent selection changes using separate copies of the pitch.
            foreach(uint id in new uint[]{0x44c22a0d,0x7f9ba68e}) {
                var row=rows.Find(r=>r.Id==id);
                bool initial=id==0x44c22a0d;
                int pitch=initial?72:61;
                uint pitchLoad=initial?0x00000c03u:0x00001003u;
                uint anchorReg=initial?5u:6u;
                if(row==null || Read(row.Code,pitch*4)!=pitchLoad ||
                    Read(row.Code,(pitch+1)*4)!=0x3d99999a)
                    throw new InvalidDataException("Unexpected menu highlight position code.");
                var choose=new Injection();
                choose.Add(0x00002d03,CompactPauseAnchor,0x2e2d0010|(anchorReg<<8));
                choose.Branch(46,0,true);
                choose.Add(pitchLoad,CompactPausePitch);
                choose.Fixups[0].Target=choose.Words.Count;
                row.Code=Relocate(row.Code,new Dictionary<int,Injection>{{pitch+2,choose}});
            }
            return Pack(rows);
        }

        internal static byte[] AlignPauseMenu(byte[] frontend,bool previous=false) {
            const uint menuAnchorField=0xb87458ce, optionCountField=0x90274abc;
            const uint negativePitchAdjustment=0xbc1374bc; // -.009
            var rows=Parse(frontend);
            var pause=rows.Find(r=>r.Id==Crc("pausemenu_enter"));
            if(pause==null)throw new InvalidDataException("Pause menu missing.");
            int anchors=0,calls=0;
            var hooks=new Dictionary<int,Injection>();
            uint addOption=Crc("Menu_AddOption");
            foreach(int word in Tokens(pause.Code)) {
                uint op=Read(pause.Code,word*4);
                if((op&255)==3 && Read(pause.Code,(word+1)*4)==0x3f166666) {
                    Buffer.BlockCopy(Bytes(new uint[]{previous?0x3f10cccc:CompactPauseAnchor}),0,pause.Code,(word+1)*4,4);
                    anchors++;
                }
                if(previous || (op&255)!=7 || Read(pause.Code,(word+1)*4)!=addOption)continue;
                if(Read(pause.Code,(word+2)*4)!=0x050d0a20)
                    throw new InvalidDataException("Unexpected pause option call.");
                // Stock Menu_AddOption subtracts .075 times the row index.
                // Offset the anchor by .009 times the number of rows already added.
                // The live count also handles the optional Upgrade Forms row.
                var before=new Injection();
                before.Add(0x002d0d17,optionCountField,0x00002e03,negativePitchAdjustment,
                    0x2f2e2d0c,0x00003003,CompactPauseAnchor,0x312f300b,0x00310d19,menuAnchorField);
                hooks.Add(word,before);
                var after=new Injection();
                after.Add(0x00003003,CompactPauseAnchor,0x00300d19,menuAnchorField);
                hooks.Add(word+4,after);
                calls++;
            }
            if(anchors!=1 || (!previous && calls!=6))throw new InvalidDataException("Unexpected pause menu layout.");
            if(!previous)pause.Code=Relocate(pause.Code,hooks);
            return Pack(rows);
        }

        static readonly string[] StockGameplayNames={"pitch","yaw","vibration"};
        static readonly uint[] StockGameplayFields={0x89299dc9,0x502823d8,0xbfb146c9};
        static Injection LauncherGameplayOverrides() {
            var code=new Injection();
            // Settings initialization can run before the PC registry is ready.
            code.Add(0x00000507,Crc("overlay"));
            code.Branch(5,0,true);
            code.Add(0x00020517,Crc("cosmic_gameplay_pitch_preference"));
            code.Branch(2,0,true);
            for(int row=0;row<StockGameplayFields.Length;row++) {
                PreviewNative(code,"cosmic_gameplay_"+StockGameplayNames[row]+"_preference",2);
                code.Add(0x00000403,0xbf800000,0x03040211);
                int unset=code.Fixups.Count;
                code.Branch(3,0,true);
                code.Add(0x00000403,0x3f800000,0x08040210,
                    0x00000507,0xe545a0c5,0x00080519,StockGameplayFields[row]);
                code.Fixups[unset].Target=code.Words.Count;
            }
            code.Fixups[0].Target=code.Words.Count;
            code.Fixups[1].Target=code.Words.Count;
            return code;
        }
        internal static byte[] SyncLauncherGameplay(byte[] data,bool globals=false) {
            var rows=Parse(data);
            var load=rows.Find(r=>r.Id==(globals?0xa4a8ae6eu:0x87e6bef2u));
            int boundary=globals?69:75;
            if(load==null || Read(load.Code,boundary*4)!=(globals?0x00000307u:0x00000707u) ||
                Read(load.Code,(boundary+1)*4)!=0xd45e5cfe)
                throw new InvalidDataException("Unexpected stock gameplay settings initialization.");
            load.Code=Relocate(load.Code,new Dictionary<int,Injection>{{boundary,LauncherGameplayOverrides()}});
            if(!globals) {
                var confirm=rows.Find(r=>r.Id==0x3b77a27e);
                if(confirm==null)throw new InvalidDataException("Missing stock Gameplay confirmation.");
                int confirmAt=-1;
                foreach(int word in Tokens(confirm.Code))
                    if(Read(confirm.Code,word*4)==0x00000907 && Read(confirm.Code,(word+1)*4)==0x2712f51f &&
                       Read(confirm.Code,(word+3)*4)==0x98b5b218)confirmAt=word;
                if(confirmAt<0)throw new InvalidDataException("Unexpected stock Gameplay confirmation.");
                var save=new Injection();
                for(int row=0;row<StockGameplayFields.Length;row++)
                    PreviewCapture(save,load.Code,0,0,StockGameplayNames[row],StockGameplayFields[row],false);
                PreviewNative(save,"cosmic_gameplay_save_stock",0);
                confirm.Code=Relocate(confirm.Code,new Dictionary<int,Injection>{{confirmAt,save}});
            }
            return Pack(rows);
        }

        public static byte[] English(byte[] original) {
            using(var s=new MemoryStream()) {
                s.Write(original,0,original.Length);byte[] label=Encoding.ASCII.GetBytes("ALL ALIENS\0");
                Word(s,Crc("cosmic_all_aliens_label"));Word(s,(uint)label.Length);s.Write(label,0,label.Length);return s.ToArray();
            }
        }
#if COSMIC_ULTIMATE_VOICES
        internal static byte[] VoiceResolver(byte[] original) {
            var rows=Parse(original);int found=0;uint saved=Crc("CosmicOriginalUltimateVoiceResolver");
            foreach(var row in rows) {
                if(row.Id==saved)throw new InvalidDataException("Voice resolver already wrapped.");
                if(row.Id==0xe8c0396d){if(row.Args!=2)throw new InvalidDataException("Unexpected voice resolver arguments.");row.Id=saved;found++;}
            }
            if(found!=1)throw new InvalidDataException("Original voice resolver missing.");
            using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("CosmicUltimateVoiceResolver.bin")) {
                if(stream==null)throw new InvalidDataException("Voice resolver resource missing.");
                using(var memory=new MemoryStream()){stream.CopyTo(memory);rows.AddRange(Parse(memory.ToArray()));}
            }
            return Pack(rows);
        }
#endif
#if COSMIC_DISCORD_PRESENCE
        internal static byte[] PresenceMission(byte[] original,string level) {
            // The hash-pinned l_rush script contains an unrelated duplicate ID.
            // Preserve all records in order; still require our entry exactly once.
            var rows=Parse(original,true);uint entry=DiscordPresencePatch.Entries[level];int found=0;
            foreach(var row in rows)if(row.Id==entry) {
                if(row.Args!=1)throw new InvalidDataException("Unexpected mission entry arguments.");
                row.Code=Relocate(row.Code,new Dictionary<int,Injection>{{0,Hook("CosmicPresence_"+level)}});found++;
            }
            if(found!=1)throw new InvalidDataException("Mission entry missing.");return Pack(rows);
        }
#endif
        public static byte[] Transform(string file,byte[] original) {
#if COSMIC_HERO_TIME
            // Private candidate only. Compose at original VM boundaries before
            // the independently verified All Aliens relocation.
            if(file=="globals.ds") {
                var heroRows=Parse(original);int heroHooks=0;
                foreach(var row in heroRows) {
#if COSMIC_DISCORD_PRESENCE
                    if(row.Id==Crc("global_mission_unload"))row.Code=Relocate(row.Code,new Dictionary<int,Injection>{{0,Hook("CosmicPresence_menus")}});
#endif
#if COSMIC_ULTIMATE_VOICES
                    // Mark existing calls only when Hero Time owns the request.
                    if(row.Id==0xd322606e || row.Id==0xd12b0644 || row.Id==0x29a1fb23) {
                        int boundary=row.Id==0x29a1fb23?89:84;
                        if(Read(row.Code,(boundary-4)*4)!=0x00000617 || Read(row.Code,(boundary-3)*4)!=Crc("playvo") || Read(row.Code,(boundary-2)*4)!=0x04090020)
                            throw new InvalidDataException("Unexpected original Ultimate voice call.");
                        row.Code=Relocate(row.Code,new Dictionary<int,Injection>{{boundary,Hook("CosmicHeroObserveVoice")}});
                    }
#endif
                    if(row.Id==Crc("switch_form_update")){row.Code=Relocate(row.Code,new Dictionary<int,Injection>{{34,Hook("CosmicHeroUpdate","CosmicUltimateHudUpdate")}});heroHooks++;}
                    if(row.Id==Crc("destroy_form_switching")){row.Code=Relocate(row.Code,new Dictionary<int,Injection>{{0,Hook("CosmicUltimateHudReset","CosmicHeroUnload")}});heroHooks++;}
                    if(row.Id==0xaac6a726){row.Code=Relocate(row.Code,new Dictionary<int,Injection>{{87,Hook("CosmicHeroLoad")}});heroHooks++;}
                }
                if(heroHooks!=3)throw new InvalidDataException("Original Hero Time lifecycle missing.");
                using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("CosmicHeroTime.bin")) {
                    if(stream==null)throw new IOException("Private Hero Time program missing.");
                    using(var memory=new MemoryStream()){stream.CopyTo(memory);heroRows.AddRange(Parse(memory.ToArray()));}
                }
                original=Pack(heroRows);
            }
#endif
            var rows=Parse(original);int patched=0;
            if(file=="globals.ds") {
                foreach(var r in rows) {
                    if(r.Id==Crc("switch_form_update")){r.Code=Relocate(r.Code,new Dictionary<int,Injection>{{34,Hook("CosmicAlienUpdate")}});patched++;}
                    if(r.Id==Crc("destroy_form_switching")){r.Code=Relocate(r.Code,new Dictionary<int,Injection>{{0,Hook("CosmicAlienUnload")}});patched++;}
                    // Mission preload snapshots the four active hotkeys into
                    // another game-owned table. Keep temporary pages out of it.
                    if(r.Id==0xa67003d2){r.Code=Relocate(r.Code,new Dictionary<int,Injection>{{0,Hook("CosmicAlienRestore")}});patched++;}
#if COSMIC_PRELOAD_ALIENS
                    if(r.Id==0xaac6a726){r.Code=Relocate(r.Code,new Dictionary<int,Injection>{{87,Hook("CosmicAlienLoad")}});patched++;}
#endif
                }
                using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream("CosmicAllAliens.bin")) {
                    if(stream==null)throw new IOException("The launcher is missing its All Aliens program.");
                    using(var memory=new MemoryStream()){stream.CopyTo(memory);rows.AddRange(Parse(memory.ToArray()));}
                }
#if COSMIC_PRELOAD_ALIENS
                if(patched!=4)throw new InvalidDataException("Original form preload lifecycle missing.");
#else
                if(patched!=3)throw new InvalidDataException("Original form lifecycle missing.");
#endif
            }else if(file=="gld_xbx.ds") {
                foreach(var r in rows)if(r.Id==0x66960347) {
                    if(r.Code.Length!=230*4)throw new InvalidDataException("Unexpected form input handler.");
                    var hooks=new Dictionary<int,Injection>();
                    foreach(int p in new int[]{55,98,141,184}){
                        var i=new Injection();i.Branch(4,207);
#if COSMIC_DISABLE_RATH
                        // Also guard old profiles/cheats: Rath must not reach
                        // the native transform even if already in a saved slot.
                        i.Add(0x00000807,0xe1003dc4,0x000b0820,8,
                            0x00090817,Crc("Rath"),0x05090411);
                        i.Branch(5,207);
#endif
                        hooks.Add(p,i);
                    }
                    r.Code=Relocate(r.Code,hooks);patched++;
                }
                if(patched!=1)throw new InvalidDataException("Original form input missing.");
#if COSMIC_HERO_TIME
                foreach(var row in rows)if(row.Id==0x66960347) {
                    int tail=-1;
                    foreach(int token in Tokens(row.Code))if(Read(row.Code,token*4)==0x00030017 && Read(row.Code,token*4+4)==0xa95fe03f) {
                        if(tail!=-1)throw new InvalidDataException("Ambiguous form input tail.");tail=token;
                    }
                    if(tail<0)throw new InvalidDataException("Original input history update missing.");
                    var guard=new Injection();guard.Add(0x00001b07,Crc("cosmic_hero_phase"));
                    guard.Branch(27,7,true); // nil: ordinary game behavior
                    guard.Add(0x00001c03,0,0x1d1c1b10);
                    guard.Branch(29,tail); // owned cycle: preserve input history only
                    row.Code=Relocate(row.Code,new Dictionary<int,Injection>{{0,guard}});
                }
#endif
            }else if(file=="circdisp.ds") {
                byte[] blank=null;
                foreach(var r in rows)if(r.Id==0x8f436ad3) {
                    if(r.Code.Length!=769*4)throw new InvalidDataException("Unexpected form HUD.");
                    if(Read(r.Code,49*4)!=0x00181f06 || Read(r.Code,635*4)!=0x00181f06)
                        throw new InvalidDataException("Original HUD icon capture missing.");
                    using(var s=new MemoryStream()) {
                        Word(s,0x00180006);Word(s,0x001d0106);
                        // Original blank portrait creation/position/animation.
                        s.Write(r.Code,227*4,(340-227)*4);
                        // The original placeholder texture is Ben, not an
                        // empty portrait. Hide the whole unused item through
                        // the original SetAlpha routine; the normal HUD path
                        // restores alpha when this slot has a form again.
                        foreach(uint w in new uint[]{0x00301806,0x00003103,0,
                            0x00002d07,0x41871bc9,0x02302d20,31,0x21})Word(s,w);
                        blank=s.ToArray();
                    }
                    // Both guards reuse register 31. Capture the returned icon
                    // into register 24 first; otherwise the guard's hotkey
                    // lookup would become the icon argument to a95e2870.
                    r.Code=Relocate(r.Code,new Dictionary<int,Injection>{{50,EmptySlotGuard(340)},{636,EmptySlotGuard(758)}});patched++;
                }
                if(patched!=1)throw new InvalidDataException("Original form HUD missing.");
                rows.Add(new Record{Id=Crc("CosmicEmptyAlienIcon"),Args=2,Code=blank});
            }else throw new ArgumentException("Unsupported script file.");
            return Pack(rows);
        }
        public static void Ensure(string game) {
#if COSMIC_ALIEN_STREAMS
            AlienAnimationStreams.Ensure(game);
#endif
            string scripts=Path.Combine(game,"global","scripts");
            string[] names={"globals.ds","gld_xbx.ds","circdisp.ds"};
            string[] hashes={"5bf03a8d2ce2cd8c26176139cd57aea63a15af5e6405a6449e265375ea7103c2",
                "4c090a5b10488ddccd742adf25bc606d2a3cf3c94d5f5ae14f6df60948f09256",
                "2748e4bc8810f9af390f92999acdedbc7ee3b4d4dcbe833606f41c61b36bb576"};
            var replacements=new Dictionary<string,byte[]>();var originals=new Dictionary<string,byte[]>();
            for(int i=0;i<names.Length;i++) {
                string path=Path.Combine(scripts,names[i]),backup=path+".cosmic-original";
                byte[] original=File.ReadAllBytes(File.Exists(backup)?backup:path);
                if(Hash(original)!=hashes[i])throw new InvalidDataException("Unsupported original form script: "+names[i]);
                byte[] updated=Transform(names[i],original),current=File.ReadAllBytes(path);
                byte[] previous=updated;
#if COSMIC_NATIVE_SETTINGS
                if(names[i]=="globals.ds")updated=SyncLauncherGameplay(updated,true);
#endif
                if(Hash(current)==Hash(updated))continue;
                if(Hash(current)!=hashes[i] && Hash(current)!=Hash(previous)
#if COSMIC_ULTIMATE_VOICES
                    && !(names[i]=="globals.ds" && Hash(current)=="1c99d65b77ad414fc64fa2c890d458d0870753ec338258ecedf21bfbff00ca55")
#endif
#if COSMIC_DISCORD_PRESENCE
                    && !(names[i]=="globals.ds" && Hash(current)=="60490e513f99dd2ecdfaa27c02ef9c98ba0f8f3b0574e0d3436a9458bbc82e36")
                    && !(names[i]=="globals.ds" && Hash(current)=="e14dc88268fd637c156f532eecd58588131c30aa6732317145c05f6c486f2b4a")
#endif
                )throw new IOException("Another version modified "+names[i]+". Import into a fresh folder.");
                replacements[path]=updated;originals[path]=original;
            }
            foreach(var item in replacements) {
                string path=item.Key,backup=path+".cosmic-original",temporary=path+".cosmic-new";
                if(!File.Exists(backup))File.WriteAllBytes(backup,originals[path]);
                File.WriteAllBytes(temporary,item.Value);
                // Replace the directory entry: never modify a hard-linked ISO
                // extraction file in place. Interrupted installs are resumable.
                File.Replace(temporary,path,null);
            }
        }
    }

    // Private candidate. Existing clips keep priority; only user-owned records
    // are converted locally. No animation data is embedded in this program.
    internal static class AlienAnimationStreams {
        sealed class Entry {public uint Key;public byte[] Data;}
        static uint U(byte[] b,int p) {
            if(p<0||p>b.Length-4)throw new InvalidDataException("Truncated animation archive.");
            return ((uint)b[p]<<24)|((uint)b[p+1]<<16)|((uint)b[p+2]<<8)|b[p+3];
        }
        static int I(byte[] b,int p){return checked((int)U(b,p));}
        static void Put(byte[] b,int p,uint v){b[p]=(byte)(v>>24);b[p+1]=(byte)(v>>16);b[p+2]=(byte)(v>>8);b[p+3]=(byte)v;}
        static void Word(Stream s,uint v){byte[] b=new byte[4];Put(b,0,v);s.Write(b,0,4);}
        static List<Entry> Parse(byte[] b) {
            if(U(b,0)!=0x76617073||U(b,4)!=0x00010003)throw new InvalidDataException("Unsupported animation archive.");
            int n=I(b,36),at=checked(32+I(b,44)),data=I(b,28);
            if(n!=I(b,8)||I(b,48)!=12||n>100000||checked(at+n*12)>data||data>b.Length)
                throw new InvalidDataException("Invalid animation index.");
            var rows=new List<Entry>();
            for(int j=0;j<n;j++) {
                int p=checked(at+j*12),size=I(b,p+4),offset=checked(data+I(b,p+8));
                if(offset>b.Length-size)throw new InvalidDataException("Invalid animation record.");
                byte[] value=new byte[size];Buffer.BlockCopy(b,offset,value,0,size);
                rows.Add(new Entry{Key=U(b,p),Data=value});
            }
            return rows;
        }
        static float Float(byte[] b,int p){return BitConverter.ToSingle(BitConverter.GetBytes(U(b,p)),0);}
        static void PutFloat(byte[] b,int p,float value){Put(b,p,BitConverter.ToUInt32(BitConverter.GetBytes(value),0));}
        static void TimeRange(byte[] clip,List<Entry> channels,byte[] target) {
            // Match the game's resident initializer 0x8219ED50. Streamed loading
            // relocates channels but does not calculate these two fields.
            float first=10000000.0f,last=-10000000.0f;int bones=I(clip,72);
            if(bones<0 || checked(216+bones*12)>clip.Length)throw new InvalidDataException("Invalid timed animation bone count.");
            for(int at=216;at<216+bones*12;at+=4) {
                uint index=U(clip,at);if(index==0xffffffff)continue;
                if(index>=channels.Count)throw new InvalidDataException("Invalid timed animation channel.");
                byte[] ch=channels[(int)index].Data;
                if(ch.Length<8)throw new InvalidDataException("Truncated animation timing header.");
                int keys=(ch[4]<<8)|ch[5],stride=ch[1]*4;
                if(keys==0 || stride==0)throw new InvalidDataException("Invalid animation timing stride.");
                int a=ch[0]==16?15:8,b=checked(a+(keys-1)*stride);
                if(b>ch.Length-(ch[0]==16?1:4))throw new InvalidDataException("Animation timing outside channel.");
                float lo=ch[0]==16?ch[a]*160.0f:Float(ch,a),hi=ch[0]==16?ch[b]*160.0f:Float(ch,b);
                if(Single.IsNaN(lo)||Single.IsInfinity(lo)||Single.IsNaN(hi)||Single.IsInfinity(hi))throw new InvalidDataException("Non-finite animation time.");
                first=Math.Min(first,lo);last=Math.Max(last,hi);
            }
            PutFloat(target,64,first);PutFloat(target,68,last);
        }
        static byte[] ConvertClip(byte[] clip,List<Entry> channels,bool reconstructTiming) {
            int bones=I(clip,76);
            if(clip.Length!=checked(216+bones*12))throw new InvalidDataException("Unsupported resident animation layout.");
            using(var output=new MemoryStream()) {
                byte[] header=(byte[])clip.Clone();if(reconstructTiming)TimeRange(clip,channels,header);
                output.Write(header,0,header.Length);var offsets=new Dictionary<uint,uint>();
                for(int position=80;position<clip.Length;position=position==80?216:position+4) {
                    uint index=U(clip,position);if(index==0xffffffff)continue;
                    if(index>=channels.Count)throw new InvalidDataException("Invalid animation channel index.");
                    uint offset;
                    if(!offsets.TryGetValue(index,out offset)) {
                        output.Position=output.Length;while((output.Length&3)!=0)output.WriteByte(0);
                        offset=checked((uint)output.Length);offsets[index]=offset;
                        byte[] value=channels[(int)index].Data;output.Write(value,0,value.Length);
                    }
                    output.Position=position;Word(output,offset);
                }
                return output.ToArray();
            }
        }
        internal static byte[] Merge(byte[] original,IEnumerable<byte[]> archives,bool reconstructTiming=true) {
            if(U(original,20)!=13)throw new InvalidDataException("Expected a streamed animation bank.");
            var rows=new Dictionary<uint,byte[]>();
            foreach(var row in Parse(original))if(!rows.ContainsKey(row.Key))rows.Add(row.Key,row.Data);
            foreach(byte[] archive in archives) {
                byte[] clips=null,channelBank=null;
                foreach(var part in Parse(archive)){if(part.Key==13)clips=part.Data;if(part.Key==9)channelBank=part.Data;}
                if(clips==null)continue;if(channelBank==null)throw new InvalidDataException("Animation channels missing.");
                var channels=Parse(channelBank);
                foreach(var row in Parse(clips))if(!rows.ContainsKey(row.Key))rows.Add(row.Key,ConvertClip(row.Data,channels,reconstructTiming));
            }
            int alignment=1<<((original[12]<<8)|original[13]);
            if(alignment<16||alignment>65536)throw new InvalidDataException("Invalid animation alignment.");
            int count=rows.Count,buckets=(count+3)/4*4;var keys=new List<uint>(rows.Keys);
            keys.Sort(delegate(uint a,uint b){int c=(a%(uint)buckets).CompareTo(b%(uint)buckets);return c!=0?c:a.CompareTo(b);});
            using(var dictionary=new MemoryStream())using(var payload=new MemoryStream()) {
                byte[] header=new byte[32];Buffer.BlockCopy(original,32,header,0,32);
                Put(header,0,(uint)buckets);Put(header,4,(uint)count);Put(header,8,32);
                Put(header,12,(uint)(32+buckets*4));Put(header,16,12);dictionary.Write(header,0,32);
                int cursor=0;
                for(uint bucket=0;bucket<buckets;bucket++){while(cursor<count&&keys[cursor]%(uint)buckets<bucket)cursor++;Word(dictionary,(uint)cursor);}
                foreach(uint key in keys) {
                    while(payload.Length%alignment!=0)payload.WriteByte(0);
                    Word(dictionary,key);Word(dictionary,(uint)rows[key].Length);Word(dictionary,(uint)payload.Length);
                    payload.Write(rows[key],0,rows[key].Length);
                }
                int data=checked(((32+(int)dictionary.Length+alignment-1)/alignment)*alignment);
                byte[] result=new byte[checked(data+(int)payload.Length)];Buffer.BlockCopy(original,0,result,0,32);
                Put(result,8,(uint)count);Put(result,16,(uint)payload.Length);Put(result,28,(uint)data);
                Buffer.BlockCopy(dictionary.ToArray(),0,result,32,(int)dictionary.Length);
                Buffer.BlockCopy(payload.ToArray(),0,result,data,(int)payload.Length);Parse(result);return result;
            }
        }
        internal static void Ensure(string game) {
            string[] forms={"ad","af","bc","ec","hm","nr","ra","sf","sm","ts","wh"};
            var archives=new List<byte[]>();foreach(string form in forms)archives.Add(File.ReadAllBytes(Path.Combine(game,"global","g_"+form+".xbx")));
            var ordinaryArchives=new List<byte[]>(archives);
            // Scripted Ultimate transformations still use the same resource
            // lookup while All Aliens has replaced the current loadout.
            foreach(string form in new[]{"ubc","uec","uhm","usf","usm"})
                archives.Add(File.ReadAllBytes(Path.Combine(game,"global","g_"+form+".xbx")));
            var ultimateArchives=new List<byte[]>(archives);
            // Common player transitions live outside the g_* character banks.
            archives.Add(File.ReadAllBytes(Path.Combine(game,"global","a_plyr.xbx")));
            foreach(string level in Directory.GetDirectories(game,"l_*")) {
            // Camera/mission activation can request an NPC animation through the
            // same streamed-resource path as an additional player form. Include
            // this level's own resident clips too; never replace existing clips.
            var levelArchives=new List<byte[]>(archives);
            var previousLevelArchives=new List<byte[]>(ordinaryArchives);
            var previousUltimateLevelArchives=new List<byte[]>(ultimateArchives);
            string[] residents=Directory.GetFiles(level,"g_*.xbx");Array.Sort(residents,StringComparer.Ordinal);
            foreach(string resident in residents) {
                byte[] bytes=File.ReadAllBytes(resident);levelArchives.Add(bytes);previousLevelArchives.Add(bytes);previousUltimateLevelArchives.Add(bytes);
            }
            foreach(string path in Directory.GetFiles(level,"a_*_s.xbx")) {
                string backup=path+".cosmic-animation-original",temporary=path+".cosmic-animation-new";
                byte[] original=File.ReadAllBytes(File.Exists(backup)?backup:path),updated=Merge(original,levelArchives);
                byte[] current=File.ReadAllBytes(path);
                using(var hash=SHA256.Create())if(Convert.ToBase64String(hash.ComputeHash(current))==Convert.ToBase64String(hash.ComputeHash(updated)))continue;
                if(File.Exists(backup))using(var hash=SHA256.Create()) {
                    string currentHash=Convert.ToBase64String(hash.ComputeHash(current));
                    // A byte-identical output of our previous converter is a
                    // supported upgrade, not an arbitrary third-party edit.
                    if(currentHash!=Convert.ToBase64String(hash.ComputeHash(original)) &&
                       currentHash!=Convert.ToBase64String(hash.ComputeHash(Merge(original,ordinaryArchives,false))) &&
                       currentHash!=Convert.ToBase64String(hash.ComputeHash(Merge(original,previousLevelArchives))) &&
                       currentHash!=Convert.ToBase64String(hash.ComputeHash(Merge(original,previousUltimateLevelArchives))))
                        throw new IOException("Another patch modified the animation bank: "+Path.GetFileName(path));
                }
                if(!File.Exists(backup))File.WriteAllBytes(backup,original);
                File.WriteAllBytes(temporary,updated);File.Replace(temporary,path,null);
            }
            }
        }
    }
}
