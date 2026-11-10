using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace CosmicRecompi {
    // Transform only the user's verified scripts. No original bytecode is bundled.
    internal static class GameMenuPatch {
        const string FrontendHash = "dfe41cb728d90d93fb685a5d19e1664bb08bbebc9056ef23e25e997a00eafabb";
        const string EnglishHash = "fd1571d2b528a1710a73f5af4b0a8e916b6e0623db1916f615975bdc10e08365";
        static uint Read(byte[] bytes, int offset) {
            if (offset < 0 || offset > bytes.Length - 4) throw new InvalidDataException("Truncated game script.");
            return ((uint)bytes[offset] << 24) | ((uint)bytes[offset+1] << 16) | ((uint)bytes[offset+2] << 8) | bytes[offset+3];
        }
        static void Write(byte[] bytes, int offset, uint value) {
            bytes[offset]=(byte)(value>>24); bytes[offset+1]=(byte)(value>>16); bytes[offset+2]=(byte)(value>>8); bytes[offset+3]=(byte)value;
        }
        static void Append(Stream stream, uint value) {
            byte[] bytes=new byte[4]; Write(bytes,0,value); stream.Write(bytes,0,4);
        }
        static string Hash(byte[] bytes) {
            using (SHA256 sha=SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }
        static uint Crc(string text) {
            uint crc=0xffffffff;
            foreach (byte value in Encoding.ASCII.GetBytes(text.ToLowerInvariant())) {
                crc^=value;
                for(int bit=0;bit<8;bit++) crc=(crc>>1)^((crc&1)!=0 ? 0xedb88320U : 0);
            }
            return crc^0xffffffff;
        }
        static List<int> Tokens(byte[] code) {
            List<int> positions=new List<int>(); int cursor=0;
            while(cursor<code.Length) {
                positions.Add(cursor); int kind=(int)(Read(code,cursor)&255),size=4;
                if(kind==3 || kind==5 || kind==7 || kind==8 || kind==0x17 || kind==0x19 || kind==0x20) size=8;
                else if(kind==4) {
                    int end=Array.IndexOf(code,(byte)0,cursor+4);
                    if(end<0) throw new InvalidDataException("Unterminated script string.");
                    size=((end+1-cursor+3)/4)*4;
                } else if(kind!=1 && kind!=2 && kind!=0x0f && kind!=0x10 && kind!=0x11 && kind!=0x13 && kind!=0x14 && kind!=0x15 && kind!=0x1f && kind!=0x21)
                    throw new InvalidDataException("Unsupported menu token.");
                cursor=checked(cursor+size);
                if(cursor>code.Length) throw new InvalidDataException("Invalid menu token size.");
            }
            return positions;
        }
        static byte[] InsertRow(byte[] code,string label,string callback,int expectedCount) {
            List<int> positions=Tokens(code),calls=new List<int>();
            foreach(int p in positions)
                if((Read(code,p)&255)==7 && Read(code,p+4)==Crc("Menu_AddOption"))calls.Add(p);
            if(calls.Count!=expectedCount)throw new InvalidDataException("Unexpected original menu structure.");
            int begin=calls[calls.Count-1]-32,end=begin+48;
            byte[] row=new byte[48];Buffer.BlockCopy(code,begin,row,0,48);
            Write(row,12,Crc(label));Write(row,24,Crc(callback));
            byte[] moved=(byte[])code.Clone();
            foreach(int p in positions) {
                uint word=Read(code,p);
                if((word&255)==0x1f && (word>>16)>end/4)Write(moved,p,word+(12U<<16));
            }
            byte[] result=new byte[code.Length+48];
            Buffer.BlockCopy(moved,0,result,0,end);Buffer.BlockCopy(row,0,result,end,48);
            Buffer.BlockCopy(moved,end,result,end+48,code.Length-end);
            HashSet<int> boundaries=new HashSet<int>(Tokens(result));boundaries.Add(result.Length);
            foreach(int p in Tokens(result)) {
                uint word=Read(result,p);
                if((word&255)==0x1f && !boundaries.Contains(checked((int)(word>>16)*4)))throw new InvalidDataException("Invalid relocated menu branch.");
            }
            return result;
        }
        static void Wrapper(Stream stream,string name,string native) {
            Append(stream,Crc(name));Append(stream,1);Append(stream,native=="cosmic_video_options" ? 19U : 9U);
            foreach(uint word in new uint[] {0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),0x00000217,Crc(native),0x01050020,1})Append(stream,word);
            if(native=="cosmic_video_options")foreach(uint word in new uint[] {0x00000507,Crc("overlay"),0x00000607,Crc("CosmicRestoreOptions"),0x00000207,Crc("overlay"),0x00000217,Crc("pushfunction"),0x02050020,1})Append(stream,word);
            Append(stream,0x21);
        }
        static byte[] LegacyFrontend(byte[] original,bool previousQuitBinding=false) {
            if(Hash(original)!=FrontendHash)throw new InvalidDataException("Unsupported original frontend script.");
            if(Read(original,0)!=0x1badbabe || Read(original,4)!=103)throw new InvalidDataException("Unsupported frontend header.");
            using(MemoryStream output=new MemoryStream()) {
                Append(output,0x1badbabe);Append(output,
#if COSMIC_NATIVE_SETTINGS
                    109
#else
                    107
#endif
                    );int cursor=8,patched=0;byte[] quit=null;uint quitArguments=0;
                for(int i=0;i<103;i++) {
                    uint identity=Read(original,cursor),arguments=Read(original,cursor+4);
                    int size=checked((int)Read(original,cursor+8)*4);
                    byte[] code=new byte[size];Buffer.BlockCopy(original,cursor+12,code,0,size);
                    if(identity==Crc("QuitGame")){quit=(byte[])code.Clone();quitArguments=arguments;}
                    if(identity==Crc("pausemenu_enter")){int anchors=0;foreach(int p in Tokens(code))if((Read(code,p)&255)==3 && Read(code,p+4)==0x3f066666){Write(code,p+4,0x3f166666);anchors++;}if(anchors!=1)throw new InvalidDataException("Unexpected pause list anchor.");code=InsertRow(code,"cosmic_quit_to_launcher_label","CosmicQuitToLauncher",5);patched++;}
                    if(identity==0xb4db5294){code=InsertRow(code,"cosmic_video_label","CosmicVideoOptions",3);patched++;}
                    Append(output,identity);Append(output,arguments);Append(output,(uint)(code.Length/4));output.Write(code,0,code.Length);
                    cursor=checked(cursor+12+size);
                }
                if(cursor!=original.Length || patched!=2)throw new InvalidDataException("Invalid original menu boundaries.");
                if(quit==null)throw new InvalidDataException("Original confirmation missing.");
#if COSMIC_NATIVE_SETTINGS
                byte[] wipe=(byte[])quit.Clone();int wipeCallback=0,wipeQuestion=0;
                foreach(int p in Tokens(wipe)) {
                    if((Read(wipe,p)&255)==7 && Read(wipe,p+4)==0xd4abb75d){Write(wipe,p+4,Crc("CosmicWipeConfirmed"));wipeCallback++;}
                    if((Read(wipe,p)&255)==5 && Read(wipe,p+4)==0x78ea141f){Write(wipe,p+4,Crc("cosmic_wipe_question"));wipeQuestion++;}
                }
                if(wipeCallback!=1 || wipeQuestion!=1)throw new InvalidDataException("Unsupported reset confirmation.");
                using(var prompt=new MemoryStream()) {
                    foreach(uint word in new uint[]{0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),0x00000217,Crc("cosmic_wipe_prompt"),0x01050020,1})Append(prompt,word);
                    prompt.Write(wipe,0,wipe.Length);
                    Function(output,"CosmicWipeProgress",quitArguments,prompt.ToArray());
                }
                Wrapper(output,"CosmicWipeConfirmed","cosmic_wipe_progress");
#endif
                int replacements=0;
                // The English YES row calls 0xe66c2a6e. Older builds replaced NO.
                uint quitCallback=previousQuitBinding?0xd4abb75dU:0xe66c2a6eU;
                foreach(int p in Tokens(quit))if((Read(quit,p)&255)==7 && Read(quit,p+4)==quitCallback){Write(quit,p+4,Crc("CosmicExitToLauncher"));replacements++;}
                if(replacements!=1)throw new InvalidDataException("Unexpected confirmation layout.");
                Append(output,Crc("CosmicQuitToLauncher"));Append(output,quitArguments);Append(output,(uint)(quit.Length/4));output.Write(quit,0,quit.Length);
                Wrapper(output,"CosmicExitToLauncher","cosmic_quit_to_launcher");
                Wrapper(output,"CosmicVideoOptions","cosmic_video_options");
                uint[] restore={0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),0x00000217,Crc("popfunction"),0x01050020,1,0x00000207,0x8610f32e,0x00000502,0x00050219,0x84fe6ee3,0x00000503,0,0x00050219,0xa393d2fb,0x00010502,0x00000207,Crc("MenuStack_ShowCurrentMenu"),0x01050220,1,0x21};
                Append(output,Crc("CosmicRestoreOptions"));Append(output,1);Append(output,(uint)restore.Length);foreach(uint word in restore)Append(output,word);
                return output.ToArray();
            }
        }
        static readonly string[][] VideoChoices = {
            new string[]{"cosmic_resolution_720", "1280 X 720 (NATIVE)", "cosmic_set_720"},
            new string[]{"cosmic_resolution_1080", "1920 X 1080", "cosmic_set_1080"},
            new string[]{"cosmic_resolution_1440", "2560 X 1440", "cosmic_set_1440"},
            new string[]{"cosmic_resolution_4k", "3840 X 2160", "cosmic_set_4k"},
            new string[]{"cosmic_fps_30", "30 FPS", "cosmic_set_30"},
            new string[]{"cosmic_fps_60", "60 FPS", "cosmic_set_60"},
            new string[]{"cosmic_fps_unlimited", "UNLIMITED", "cosmic_set_unlimited"}
#if COSMIC_NATIVE_SETTINGS
            ,new string[]{"cosmic_overlay_on_label", "ON", "cosmic_overlay_on"}
            ,new string[]{"cosmic_overlay_off_label", "OFF", "cosmic_overlay_off"}
            ,new string[]{"cosmic_windowed_label", "WINDOWED", "cosmic_windowed"}
            ,new string[]{"cosmic_borderless_label", "BORDERLESS FULLSCREEN", "cosmic_borderless"}
            ,new string[]{"cosmic_exclusive_label", "EXCLUSIVE FULLSCREEN", "cosmic_exclusive"}
            ,new string[]{"cosmic_icons_xbox_label", "XBOX", "cosmic_icons_xbox"}
            ,new string[]{"cosmic_icons_playstation_label", "PLAYSTATION", "cosmic_icons_playstation"}
            ,new string[]{"cosmic_icons_keyboard_label", "KEYBOARD", "cosmic_icons_keyboard"}
            ,new string[]{"cosmic_fps_120", "120 FPS", "cosmic_set_120"}
            ,new string[]{"cosmic_graphics_default_label", "ORIGINAL", "cosmic_graphics_default"}
            ,new string[]{"cosmic_graphics_low_label", "LOW", "cosmic_graphics_low"}
            ,new string[]{"cosmic_graphics_medium_label", "MEDIUM", "cosmic_graphics_medium"}
            ,new string[]{"cosmic_graphics_high_label", "HIGH", "cosmic_graphics_high"}
            ,new string[]{"cosmic_graphics_scale_original_label","ORIGINAL","cosmic_graphics_scale_original"}
            ,new string[]{"cosmic_graphics_scale_1_label","NATIVE (1X)","cosmic_graphics_scale_1"}
            ,new string[]{"cosmic_graphics_scale_2_label","2X","cosmic_graphics_scale_2"}
            ,new string[]{"cosmic_graphics_aa_original_label","ORIGINAL","cosmic_graphics_aa_original"}
            ,new string[]{"cosmic_graphics_aa_off_label","OFF","cosmic_graphics_aa_off"}
            ,new string[]{"cosmic_graphics_aa_fxaa_label","FXAA","cosmic_graphics_aa_fxaa"}
            ,new string[]{"cosmic_graphics_aa_extreme_label","FXAA EXTREME","cosmic_graphics_aa_extreme"}
            ,new string[]{"cosmic_graphics_filter_original_label","ORIGINAL","cosmic_graphics_filter_original"}
            ,new string[]{"cosmic_graphics_filter_2_label","2X","cosmic_graphics_filter_2"}
            ,new string[]{"cosmic_graphics_filter_4_label","4X","cosmic_graphics_filter_4"}
            ,new string[]{"cosmic_graphics_filter_8_label","8X","cosmic_graphics_filter_8"}
            ,new string[]{"cosmic_graphics_filter_16_label","16X","cosmic_graphics_filter_16"}
#endif
        };
        static void Function(Stream output,string name,uint arguments,byte[] code) {
            Append(output,Crc(name));Append(output,arguments);Append(output,(uint)(code.Length/4));output.Write(code,0,code.Length);
        }
        static byte[] NativeMenu(byte[] template,string menu,string title,string[][] rows) {
            // Preserve the original Options menu's VM registers, repeat-input,
            // intro animation and cancel callback. Only authored rows differ.
            using(MemoryStream code=new MemoryStream()) {
                byte[] header=new byte[37*4];Buffer.BlockCopy(template,0,header,0,header.Length);
                Write(header,12*4,Crc(title));
                foreach(int p in Tokens(header))if((Read(header,p)&255)==7 || (Read(header,p)&255)==8)
                    if(Read(header,p+4)==0x8610f32e)Write(header,p+4,Crc(menu));
                code.Write(header,0,header.Length);
                foreach(string[] row in rows)if(row!=null)foreach(uint word in new uint[]{
                    0x00000607,Crc(menu),0x00000705,Crc(row[0]),0x00000801,
                    0x00000907,Crc(row[2]),0x00000a01,0x00000307,Crc("Menu_AddOption"),0x05060320,1})Append(code,word);
                foreach(uint word in new uint[]{0x00000607,Crc(menu),0x00000307,Crc("MenuStack_Push"),0x01060320,1,0x21})Append(code,word);
                return code.ToArray();
            }
        }
        static void NativeGraphicsChoices(Stream output,byte[] template,bool textRows,bool sharpening,bool screenBloom) {
            string[] keys=sharpening && textRows?(screenBloom?new[]{"scale","aa","filter","sharpen","bloom"}:new[]{"scale","aa","filter","sharpen"}):new[]{"scale","aa","filter"};
            int[] offsets={20,23,27,32,36,40};
            byte[] empty=NativeMenu(template,"cosmic_graphics_menu","cosmic_graphics_label",new string[0][]);
            var words=new List<uint>();
            for(int i=0;i<keys.Length;i++) {
                string key=keys[i];
                if(textRows) {
                    words.AddRange(new uint[]{
                        0x00000507,Crc("overlay"),0x00010517,Crc("cosmic_index_"+key),0x01050120,1,
                        0x00000705,Crc("cosmic_graphics_value_"+offsets[i])});
                    for(int j=offsets[i]+1;j<offsets[i+1];j++) {
                        uint next=(uint)(37+words.Count+6);
                        words.AddRange(new uint[]{
                            0x00000403,BitConverter.ToUInt32(BitConverter.GetBytes((float)(j-offsets[i])),0),
                            0x02040110,(next<<16)|0x021f,
                            0x00000705,Crc("cosmic_graphics_value_"+j)});
                    }
                    words.AddRange(new uint[]{
                        0x00000607,Crc("cosmic_graphics_menu"),0x00000801,
                        0x00000907,Crc("cosmic_change_"+key),0x00000a01,
                        0x00000307,Crc("Menu_AddOption"),0x05060320,1});
                    continue;
                }
                words.AddRange(new uint[]{
                    0x00000807,Crc("cosmic_graphics_menu"),0x00000905,Crc("cosmic_"+key+"_label"),
                    0x00000a03,0x3f800000,0x00000b07,Crc("cosmic_change_"+key),
                    0x00001e07,0xa6c36cbb,0x04081e20,3,
                    // Resolve the option just created by the stock Extras row builder.
                    0x000c0817,0x90274abc,0x000d0817,0xd035fa87,0x0e0c0d18,
                    0x00000507,Crc("overlay"),0x00010517,Crc("cosmic_index_"+key),0x01050120,1,
                    0x00001705,Crc(VideoChoices[offsets[i]][0]),
                    0x00001905,Crc(VideoChoices[offsets[i]+1][0])});
                for(int j=offsets[i]+1;j<offsets[i+1];j++) {
                    uint next=(uint)(37+words.Count+8);
                    words.AddRange(new uint[]{
                        0x00000403,BitConverter.ToUInt32(BitConverter.GetBytes((float)(j-offsets[i])),0),
                        0x02040110,(next<<16)|0x021f,
                        0x00001705,Crc(VideoChoices[j][0]),
                        0x00001905,Crc(VideoChoices[j+1<offsets[i+1]?j+1:offsets[i]][0])});
                }
                words.AddRange(new uint[]{
                    0x00160e17,0xc5bf6581,0x00181617,0x76971fb1,0x02161820,0x10,
                    0x00160e17,0x2470ad3b,0x00171906,0x00181617,0x76971fb1,0x02161820,0x10});
            }
            using(var code=new MemoryStream()) {
                code.Write(empty,0,37*4);
                foreach(uint word in words)Append(code,word);
                code.Write(empty,37*4,empty.Length-37*4);
                Function(output,"CosmicGraphicsOptions",1,code.ToArray());
            }
            foreach(string key in keys)using(var callback=new MemoryStream()) {
                foreach(uint word in new uint[]{
                    0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),0x00000217,Crc("cosmic_cycle_"+key),0x01050020,1,
                    0x00000207,Crc("MenuStack_Pop"),0x00050220,1,
                    0x00010502,0x00000207,Crc("CosmicGraphicsOptions"),0x01050220,1,0x21})Append(callback,word);
                Function(output,"cosmic_change_"+key,1,callback.ToArray());
            }
        }
        static void NativeGraphics(Stream output,byte[] template,bool previousSlider) {
            string[] keys={"scale","aa","filter"};
            uint[] steps={0x3f000000,0x3eaaaaab,0x3e800000};
            byte[] empty=NativeMenu(template,"cosmic_graphics_menu","cosmic_graphics_label",new string[0][]);
            using(var code=new MemoryStream()) {
                code.Write(empty,0,37*4);
                for(int i=0;i<keys.Length;i++) {
                    string key=keys[i];
                    foreach(uint word in new uint[]{
                        0x00000807,Crc("cosmic_graphics_menu"),0x00000905,Crc("cosmic_"+key+"_label"),
                        0x00000507,Crc("overlay"),previousSlider?0x00000517U:0x00010517U,Crc("cosmic_read_"+key),previousSlider?0x00050120U:0x01050120U,1,
                        0x000a0106,0x00000b03,steps[i],0x00000c07,Crc("cosmic_change_"+key),
                        0x00000507,Crc("Menu_AddSliderOption"),0x05080520,2})Append(code,word);
                }
                code.Write(empty,37*4,empty.Length-37*4);
                Function(output,"CosmicGraphicsOptions",1,code.ToArray());
            }
            foreach(string key in keys)using(var callback=new MemoryStream()) {
                foreach(uint word in new uint[]{
                    0x00000507,Crc("overlay"),0x00060106,0x00000207,Crc("overlay"),
                    0x00000217,Crc("cosmic_write_"+key),0x02050020,1,0x21})Append(callback,word);
                Function(output,"cosmic_change_"+key,1,callback.ToArray());
            }
        }
        static byte[] NativeMenuFrontend(byte[] original,bool previousQuitBinding=false,bool buttonIcons=true,bool fps120=true,bool graphics=true,bool customGraphics=true,bool flatGraphics=true,bool previousOverlay=false,bool previousSlider=false,bool namedChoices=true,bool textRows=true,bool sharpening=true,bool screenBloom=true) {
            byte[] legacy=LegacyFrontend(original,previousQuitBinding),template=null;
            int cursor=8;
            for(int i=0;i<103;i++) {
                int bytes=checked((int)Read(original,cursor+8)*4);
                if(Read(original,cursor)==0xb4db5294){template=new byte[bytes];Buffer.BlockCopy(original,cursor+12,template,0,bytes);}
                cursor+=12+bytes;
            }
            if(template==null)throw new InvalidDataException("Original Options menu missing.");
            using(MemoryStream output=new MemoryStream()) {
                Append(output,0x1badbabe);Append(output,Read(legacy,4)+(uint)(VideoChoices.Length+2
#if COSMIC_NATIVE_SETTINGS
                    +2+(buttonIcons?1:-3)-(fps120?0:1)+(graphics?1:-4)-(graphics && customGraphics?(flatGraphics?(previousOverlay?16:13)-(sharpening && namedChoices && textRows && !previousOverlay?(screenBloom?2:1):0):1):12)
#endif
                    ));cursor=8;
                for(int i=0;i<Read(legacy,4);i++) {
                    uint identity=Read(legacy,cursor);int bytes=checked((int)Read(legacy,cursor+8)*4);
                    if(identity==Crc("CosmicVideoOptions"))Function(output,"CosmicVideoOptions",1,NativeMenu(template,"cosmic_video_menu","cosmic_video_label",new string[][] {
                        new string[]{"cosmic_resolution_label","OUTPUT RESOLUTION","CosmicResolutionOptions"},
                        new string[]{"cosmic_frame_limit_label","FRAME LIMIT","CosmicFrameOptions"}
#if COSMIC_NATIVE_SETTINGS
                        ,new string[]{"cosmic_overlay_label","SHOW FPS","CosmicOverlayOptions"}
                        ,new string[]{"cosmic_display_label","DISPLAY MODE","CosmicDisplayOptions"}
                        ,buttonIcons?new string[]{"cosmic_button_icons_label","BUTTON ICONS","CosmicButtonIconOptions"}:null
                        ,graphics?new string[]{"cosmic_graphics_label","GRAPHICS QUALITY","CosmicGraphicsOptions"}:null
#endif
                        }));
                    else output.Write(legacy,cursor,12+bytes);
                    cursor+=12+bytes;
                }
                Function(output,"CosmicResolutionOptions",1,NativeMenu(template,"cosmic_resolution_menu","cosmic_resolution_label",new string[][] {VideoChoices[0],VideoChoices[1],VideoChoices[2],VideoChoices[3]}));
                Function(output,"CosmicFrameOptions",1,NativeMenu(template,"cosmic_frame_menu","cosmic_frame_limit_label",new string[][] {VideoChoices[4],VideoChoices[5],
#if COSMIC_NATIVE_SETTINGS
                    fps120?VideoChoices[15]:null,
#endif
                    VideoChoices[6]}));
#if COSMIC_NATIVE_SETTINGS
                Function(output,"CosmicOverlayOptions",1,NativeMenu(template,"cosmic_overlay_menu","cosmic_overlay_label",new string[][] {VideoChoices[7],VideoChoices[8]}));
                Function(output,"CosmicDisplayOptions",1,NativeMenu(template,"cosmic_display_menu","cosmic_display_label",new string[][] {VideoChoices[9],VideoChoices[10],VideoChoices[11]}));
                if(buttonIcons)Function(output,"CosmicButtonIconOptions",1,NativeMenu(template,"cosmic_button_icon_menu","cosmic_button_icons_label",new string[][] {VideoChoices[12],VideoChoices[13],VideoChoices[14]}));
                if(graphics && customGraphics && flatGraphics) {
                    if(previousOverlay) {
                        using(var callback=new MemoryStream()) {
                            foreach(uint word in new uint[]{
                                0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),0x00000217,Crc("cosmic_open_graphics"),0x01050020,1,
                                0x00000207,Crc("cosmic_video_menu"),0x00000502,0x00050219,0x84fe6ee3,
                                0x00000503,0,0x00050219,0xa393d2fb,
                                0x00010502,0x00000207,Crc("MenuStack_ShowCurrentMenu"),0x01050220,1,0x21})Append(callback,word);
                            Function(output,"CosmicGraphicsOptions",1,callback.ToArray());
                        }
                    } else if(namedChoices)NativeGraphicsChoices(output,template,textRows,sharpening,screenBloom);
                    else NativeGraphics(output,template,previousSlider);
                } else if(graphics && customGraphics) {
                    Function(output,"CosmicGraphicsOptions",1,NativeMenu(template,"cosmic_graphics_menu","cosmic_graphics_label",new string[][] {
                        new string[]{"cosmic_scale_label","INTERNAL RESOLUTION","CosmicGraphicsScale"},
                        new string[]{"cosmic_aa_label","ANTI-ALIASING","CosmicGraphicsAA"},
                        new string[]{"cosmic_filter_label","TEXTURE FILTERING","CosmicGraphicsFilter"}}));
                    Function(output,"CosmicGraphicsScale",1,NativeMenu(template,"cosmic_scale_menu","cosmic_scale_label",new string[][] {VideoChoices[20],VideoChoices[21],VideoChoices[22]}));
                    Function(output,"CosmicGraphicsAA",1,NativeMenu(template,"cosmic_aa_menu","cosmic_aa_label",new string[][] {VideoChoices[23],VideoChoices[24],VideoChoices[25],VideoChoices[26]}));
                    Function(output,"CosmicGraphicsFilter",1,NativeMenu(template,"cosmic_filter_menu","cosmic_filter_label",new string[][] {VideoChoices[27],VideoChoices[28],VideoChoices[29],VideoChoices[30],VideoChoices[31]}));
                } else if(graphics)Function(output,"CosmicGraphicsOptions",1,NativeMenu(template,"cosmic_graphics_menu","cosmic_graphics_label",new string[][] {VideoChoices[16],VideoChoices[17],VideoChoices[18],VideoChoices[19]}));
#endif
                foreach(string[] choice in VideoChoices) {
                    int choiceIndex=Array.IndexOf(VideoChoices,choice);
                    if((choiceIndex>=20 && (!graphics || !customGraphics || flatGraphics)) ||
                       (choiceIndex>=16 && choiceIndex<20 && graphics && customGraphics))continue;
                    if(!fps120 && choice[2]=="cosmic_set_120")continue;
                    if(!graphics && choice[2].StartsWith("cosmic_graphics_",StringComparison.Ordinal))continue;
                    if(!buttonIcons && choice[2].StartsWith("cosmic_icons_",StringComparison.Ordinal))continue;
                    using(MemoryStream callback=new MemoryStream()) {
                        foreach(uint word in new uint[]{0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),0x00000217,Crc(choice[2]),0x01050020,1})Append(callback,word);
#if COSMIC_NATIVE_SETTINGS
                        // Selecting a row hides the original menu before its
                        // callback runs. A setting has no child menu to push;
                        // reset its completed action and show the current one.

                        string owner=choiceIndex<4?"cosmic_resolution_menu":(choiceIndex<7 || choice[2]=="cosmic_set_120")?"cosmic_frame_menu":choiceIndex<9?"cosmic_overlay_menu":choiceIndex<12?"cosmic_display_menu":choiceIndex<16?"cosmic_button_icon_menu":choiceIndex<20?"cosmic_graphics_menu":choiceIndex<23?"cosmic_scale_menu":choiceIndex<27?"cosmic_aa_menu":"cosmic_filter_menu";
                        foreach(uint word in new uint[]{0x00000207,Crc(owner),0x00000502,0x00050219,0x84fe6ee3,
                            0x00000503,0,0x00050219,0xa393d2fb})Append(callback,word);
                        foreach(uint word in new uint[]{0x00010502,0x00000207,Crc("MenuStack_ShowCurrentMenu"),0x01050220,1})Append(callback,word);
#endif
                        Append(callback,0x21);
                        Function(output,choice[2]+"_row",1,callback.ToArray());
                    }
                }
                // Menu callbacks point at script wrappers; the native names are
                // invoked through the overlay's registered native methods.
                byte[] result=output.ToArray();
                cursor=8;
                for(int i=0;i<Read(result,4);i++) {
                    int bytes=checked((int)Read(result,cursor+8)*4);byte[] code=new byte[bytes];Buffer.BlockCopy(result,cursor+12,code,0,bytes);
                    uint identity=Read(result,cursor);
                    if(identity==Crc("CosmicResolutionOptions") || identity==Crc("CosmicFrameOptions")
#if COSMIC_NATIVE_SETTINGS
                        || identity==Crc("CosmicOverlayOptions") || identity==Crc("CosmicDisplayOptions") || identity==Crc("CosmicButtonIconOptions") || (!(graphics && customGraphics && flatGraphics && !previousOverlay) && identity==Crc("CosmicGraphicsOptions"))
                        || identity==Crc("CosmicGraphicsScale") || identity==Crc("CosmicGraphicsAA") || identity==Crc("CosmicGraphicsFilter")
#endif
                        )
                        foreach(int p in Tokens(code))if((Read(code,p)&255)==7)
                            foreach(string[] choice in VideoChoices)if(Read(code,p+4)==Crc(choice[2]))Write(result,cursor+12+p+4,Crc(choice[2]+"_row"));
                    cursor+=12+bytes;
                }
                return result;
            }
        }
        public static byte[] Frontend(byte[] original) {
            return Frontend(original,false);
        }
        static byte[] Frontend(byte[] original,bool previousQuitBinding,bool albedoHud=true,bool buttonIcons=true,bool fps120=true,bool graphics=true,bool customGraphics=true,bool flatGraphics=true,bool previousOverlay=false,bool previousSlider=false,bool namedChoices=true,bool textRows=true,bool sharpening=true,bool screenBloom=true) {
            byte[] menus=AllAliensPatch.Frontend(RathFrontend(original,previousQuitBinding,buttonIcons,fps120,graphics,customGraphics,flatGraphics,previousOverlay,previousSlider,namedChoices,textRows,sharpening,screenBloom));
#if COSMIC_HERO_TIME
            return HeroTimeFrontend(original,menus,albedoHud);
#else
            return menus;
#endif
        }
#if COSMIC_HERO_TIME
        static byte[] HeroTimeFrontend(byte[] original,byte[] menus,bool albedoHud) {
            byte[] template=null;int cursor=8;
            for(int i=0;i<Read(original,4);i++) {
                int bytes=checked((int)Read(original,cursor+8)*4);
                if(Read(original,cursor)==0xb4db5294){template=new byte[bytes];Buffer.BlockCopy(original,cursor+12,template,0,bytes);}
                cursor+=12+bytes;
            }
            if(template==null)throw new InvalidDataException("Original Extras menu template missing.");
            using(var output=new MemoryStream()) {
                Append(output,0x1badbabe);Append(output,Read(menus,4)+(albedoHud?4U:3U));cursor=8;int renamed=0;
                for(int i=0;i<Read(menus,4);i++) {
                    int bytes=checked((int)Read(menus,cursor+8)*4);
                    uint identity=Read(menus,cursor);
                    if(identity==Crc("GameplayMenu_Enter")){identity=Crc("CosmicStandardGameplay");renamed++;}
                    Append(output,identity);output.Write(menus,cursor+4,8+bytes);cursor+=12+bytes;
                }
                if(renamed!=1)throw new InvalidDataException("Original Gameplay entry missing.");
                Function(output,"GameplayMenu_Enter",1,NativeMenu(template,"cosmic_gameplay_root","cosmic_gameplay_label",new string[][] {
                    new string[]{"cosmic_standard_label","STANDARD","CosmicStandardGameplay"},
                    new string[]{"cosmic_extras_label","EXTRAS","CosmicGameplayExtras"}}));
                byte[] empty=NativeMenu(template,"cosmic_extras_menu","cosmic_extras_label",new string[0][]);
                using(var extras=new MemoryStream()) {
                    extras.Write(empty,0,37*4);
                    var rows=new List<string[]> {
                        new string[]{"cosmic_all_aliens_label","cosmic_all_aliens_enabled","CosmicToggleAllAliens"},
                        new string[]{"cosmic_hero_label","cosmic_hero_enabled","CosmicToggleHeroTime"}};
                    if(albedoHud)rows.Add(new string[]{"cosmic_albedo_hud_label","cosmic_albedo_hud_enabled","CosmicToggleAlbedoHud"});
                    foreach(string[] row in rows) {
                        foreach(uint word in new uint[]{
                            0x00000807,Crc("cosmic_extras_menu"),0x00000905,Crc(row[0]),
                            0x00001d07,Crc("overlay"),0x00281d06,0x001e1d17,Crc(row[1]),0x01281e20,1,
                            0x00000203,0x3f800000,0x0a020110,0x00000b07,Crc(row[2]),
                            0x00280806,0x00290906,0x002a0a06,0x002b0b06,
                            0x00001e07,0xa6c36cbb,0x04281e20,3})Append(extras,word);
                    }
                    extras.Write(empty,37*4,empty.Length-37*4);
                    Function(output,"CosmicGameplayExtras",1,extras.ToArray());
                }
                using(var callback=new MemoryStream()) {
                    foreach(uint word in new uint[]{0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),
                        0x00000217,Crc("cosmic_toggle_hero_time"),0x01050020,1,0x21})Append(callback,word);
                    Function(output,"CosmicToggleHeroTime",1,callback.ToArray());
                }
                if(albedoHud)Wrapper(output,"CosmicToggleAlbedoHud","cosmic_toggle_albedo_hud");
                return output.ToArray();
            }
        }
#endif
        static byte[] RathFrontend(byte[] original,bool previousQuitBinding=false,bool buttonIcons=true,bool fps120=true,bool graphics=true,bool customGraphics=true,bool flatGraphics=true,bool previousOverlay=false,bool previousSlider=false,bool namedChoices=true,bool textRows=true,bool sharpening=true,bool screenBloom=true) {
            byte[] menus=NativeMenuFrontend(original,previousQuitBinding,buttonIcons,fps120,graphics,customGraphics,flatGraphics,previousOverlay,previousSlider,namedChoices,textRows,sharpening,screenBloom);
#if COSMIC_NATIVE_SETTINGS
            // Preserve normal progression and the original cheat. All Aliens
            // selects Rath through its temporary pages without changing saves.
            return menus;
#else
            using(MemoryStream output=new MemoryStream()) {
                Append(output,Read(menus,0));Append(output,Read(menus,4));int cursor=8,patched=0;
                for(int i=0;i<Read(menus,4);i++) {
                    uint identity=Read(menus,cursor),arguments=Read(menus,cursor+4);
                    int bytes=checked((int)Read(menus,cursor+8)*4);
                    byte[] code=new byte[bytes];Buffer.BlockCopy(menus,cursor+12,code,0,bytes);
                    if(identity==Crc("MainMenuText_Enter")) {
                        // The original Xbox "primus" branch sets
                        // postMission.unlocked[9] = true. Apply just that flag
                        // after loading a profile, before roster selection.
                        // Nil guards retain the original flow on invalid data.
                        uint[] prefix={0x00000107,Crc("postMission"),0x000a011f,
                            0x00020117,Crc("unlocked"),0x000a021f,
                            0x00000303,0x41100000,0x00010402,0x0403021a};
#if COSMIC_DISABLE_RATH
                        // Public test policy: keep Rath locked while his
                        // transformation resource failure is investigated.
                        prefix[8]=0x00000402;
#endif
                        var decoded=Tokens(code);var boundaries=new HashSet<int>(decoded);boundaries.Add(code.Length);
                        foreach(int p in decoded) {
                            uint word=Read(code,p);
                            if((word&255)==0x1f) {
                                if(!boundaries.Contains(checked((int)(word>>16)*4)))throw new InvalidDataException("Invalid main-menu branch.");
                                Write(code,p,word+((uint)prefix.Length<<16));
                            }
                        }
                        using(MemoryStream extended=new MemoryStream()) {
                            foreach(uint word in prefix)Append(extended,word);
                            extended.Write(code,0,code.Length);code=extended.ToArray();
                        }
                        patched++;
                    }
                    Append(output,identity);Append(output,arguments);Append(output,(uint)(code.Length/4));output.Write(code,0,code.Length);cursor+=12+bytes;
                }
                if(patched!=1 || cursor!=menus.Length)throw new InvalidDataException("Expected main-menu unlock point missing.");
                return output.ToArray();
            }
#endif
        }
        static byte[] LegacyEnglish(byte[] original) {
            if(Hash(original)!=EnglishHash)throw new InvalidDataException("Unsupported original English text table.");
            using(MemoryStream output=new MemoryStream()) {
                output.Write(original,0,original.Length);
                foreach(string[] row in new string[][] {new string[] {"cosmic_quit_to_launcher_label","QUIT TO LAUNCHER"},new string[] {"cosmic_video_label","VIDEO"}}) {
                    byte[] text=Encoding.ASCII.GetBytes(row[1]+"\0");Append(output,Crc(row[0]));Append(output,(uint)text.Length);output.Write(text,0,text.Length);
                }
                return output.ToArray();
            }
        }
        public static byte[] English(byte[] original) {
            return AllAliensPatch.English(NativeEnglish(original));
        }
        static byte[] NativeEnglish(byte[] original,bool albedoHud=true,bool previewLabel=false,bool buttonIcons=true,bool fps120=true,bool graphics=true,bool customGraphics=true,bool flatGraphics=true,bool textRows=true,bool sharpening=true,bool screenBloom=true) {
            using(MemoryStream output=new MemoryStream()) {
                byte[] legacy=LegacyEnglish(original);output.Write(legacy,0,legacy.Length);
                var rows=new List<string[]>(VideoChoices);
                if(graphics && customGraphics) {
                    rows.RemoveRange(16,4);
                    if(flatGraphics && textRows)for(int i=20;i<32;i++) {
                        string label=i<23?"INTERNAL RESOLUTION":i<27?"ANTI-ALIASING":"TEXTURE FILTERING";
                        rows.Add(new string[]{"cosmic_graphics_value_"+i,label+"  -  "+VideoChoices[i][1]});
                    }
                    if(flatGraphics && textRows && sharpening) {
                        string[] strengths={"ORIGINAL","LOW","MEDIUM","HIGH"};
                        for(int i=0;i<strengths.Length;i++)
                            rows.Add(new string[]{"cosmic_graphics_value_"+(32+i),"SHARPENING  -  "+strengths[i]});
                        if(screenBloom)for(int i=0;i<strengths.Length;i++)
                            rows.Add(new string[]{"cosmic_graphics_value_"+(36+i),"SCREEN BLOOM  -  "+strengths[i]});
                    }
                    rows.Add(new string[]{"cosmic_scale_label","INTERNAL RESOLUTION"});
                    rows.Add(new string[]{"cosmic_aa_label","ANTI-ALIASING"});
                    rows.Add(new string[]{"cosmic_filter_label","TEXTURE FILTERING"});
                } else if(graphics)rows.RemoveRange(20,12);
                if(!graphics)rows.RemoveAll(row=>row[0].StartsWith("cosmic_graphics_",StringComparison.Ordinal));
                if(graphics)rows.Add(new string[]{"cosmic_graphics_label",customGraphics && flatGraphics?"GRAPHICS":"GRAPHICS QUALITY"});
                if(!fps120)rows.RemoveAll(row=>row[0]=="cosmic_fps_120");
                if(!buttonIcons)rows.RemoveAll(row=>row[0].StartsWith("cosmic_icons_",StringComparison.Ordinal));
                if(buttonIcons)rows.Add(new string[]{"cosmic_button_icons_label","BUTTON ICONS"});
                rows.Add(new string[]{"cosmic_resolution_label",
#if COSMIC_NATIVE_SETTINGS
                    "OUTPUT RESOLUTION"
#else
                    "RESOLUTION (RESTART REQUIRED)"
#endif
                    });
                rows.Add(new string[]{"cosmic_frame_limit_label","FRAME LIMIT"});
#if COSMIC_HERO_TIME
                rows.Add(new string[]{"cosmic_gameplay_label","GAMEPLAY"});
                rows.Add(new string[]{"cosmic_standard_label","STANDARD"});
                rows.Add(new string[]{"cosmic_extras_label","EXTRAS"});
                rows.Add(new string[]{"cosmic_hero_label","HERO TIME (L3)"});
                if(albedoHud)rows.Add(new string[]{"cosmic_albedo_hud_label",previewLabel?"ALBEDO HUD PREVIEW":"PLAY AS ALBEDO"});
#endif
#if COSMIC_NATIVE_SETTINGS
                rows.Add(new string[]{"cosmic_overlay_label","SHOW FPS"});
                rows.Add(new string[]{"cosmic_display_label","DISPLAY MODE"});
                rows.Add(new string[]{"cosmic_wipe_label","WIPE DATA"});
                rows.Add(new string[]{"cosmic_wipe_question","RESET PROGRESS? BACKUP KEPT. RETURNING TO LAUNCHER."});
#endif
                foreach(string[] row in rows) {
                    byte[] text=Encoding.ASCII.GetBytes(row[1]+"\0");Append(output,Crc(row[0]));Append(output,(uint)text.Length);output.Write(text,0,text.Length);
                }
                return output.ToArray();
            }
        }
        static HashSet<uint> TextKeys(byte[] bytes) {
            if(bytes.Length<4 || bytes.Length>16*1024*1024 || Read(bytes,0)!=0x1badbabe)throw new InvalidDataException("Invalid translation table header or size.");
            var keys=new HashSet<uint>();int cursor=4;
            while(cursor<bytes.Length) {
                uint key=Read(bytes,cursor),length=Read(bytes,cursor+4);
                if(length==0 || length>bytes.Length-cursor-8 || !keys.Add(key))throw new InvalidDataException("Truncated or duplicate translation entry.");
                int count=checked((int)length);
                if(bytes[cursor+8+count-1]!=0)throw new InvalidDataException("Translation text is not terminated.");
                cursor=checked(cursor+8+count);
            }
            if(cursor!=bytes.Length)throw new InvalidDataException("Invalid translation table boundary.");
            return keys;
        }
        public static byte[] MergeTranslation(byte[] original,byte[] translation) {
            byte[] authored=English(original); // Also verifies the supported original hash.
            if(!TextKeys(original).SetEquals(TextKeys(translation)))throw new InvalidDataException("The translation must contain exactly the supported game's text IDs.");
            using(var result=new MemoryStream()) {
                result.Write(translation,0,translation.Length);
                result.Write(authored,original.Length,authored.Length-original.Length);
                byte[] merged=result.ToArray();TextKeys(merged);return merged;
            }
        }
        public static void InstallTranslation(string gameFolder,string storedPatch,byte[] translation) {
            byte[] previous=File.Exists(storedPatch)?File.ReadAllBytes(storedPatch):null;
            Ensure(gameFolder,previous);
            string english=Path.Combine(gameFolder,"global","scripts","xbx_us.txt");
            byte[] original=File.ReadAllBytes(english+".cosmic-original");
            MergeTranslation(original,translation); // Validate before committing the source patch.
            Directory.CreateDirectory(Path.GetDirectoryName(storedPatch));
            string patchTemp=storedPatch+".new";
            File.WriteAllBytes(patchTemp,translation);
            // One canonical atomic commit. Generated text is rebuilt from this
            // source at every launch, including after an interrupted apply.
            if(previous==null)File.Move(patchTemp,storedPatch);else File.Replace(patchTemp,storedPatch,null);
            Ensure(gameFolder,translation);
        }
        static bool IsAuthoredTranslation(byte[] original,byte[] current) {
            try {
                byte[] previous=NativeEnglish(original,false);
                byte[] preview=NativeEnglish(original,true,true);
                byte[] priorIcons=NativeEnglish(original,true,false,false,false,false);
                byte[] priorRate=NativeEnglish(original,true,false,true,false,false);
                byte[] priorGraphics=NativeEnglish(original,true,false,true,true,false);
                byte[] priorSharpening=NativeEnglish(original,true,false,true,true,true,true,true,true,true,false);
                byte[] priorText=NativeEnglish(original,true,false,true,true,true,true,true,true,false);
                byte[] priorNamed=NativeEnglish(original,true,false,true,true,true,true,true,false);
                byte[] priorCustom=NativeEnglish(original,true,false,true,true,true,true,false);
                byte[] priorPreset=NativeEnglish(original,true,false,true,true,true,false);
                foreach(byte[] authored in new byte[][]{English(original),NativeEnglish(original),AllAliensPatch.English(priorSharpening),priorSharpening,AllAliensPatch.English(priorText),priorText,AllAliensPatch.English(priorNamed),priorNamed,AllAliensPatch.English(priorCustom),priorCustom,AllAliensPatch.English(priorPreset),priorPreset,AllAliensPatch.English(priorGraphics),priorGraphics,AllAliensPatch.English(priorRate),priorRate,AllAliensPatch.English(priorIcons),priorIcons,
                    AllAliensPatch.English(previous),previous,AllAliensPatch.English(preview),preview}) {
                    int suffix=authored.Length-original.Length;
                    if(current.Length<suffix+4 || !TextKeys(authored).SetEquals(TextKeys(current)))continue;
                    bool matches=true;
                    for(int i=0;i<suffix;i++)if(authored[original.Length+i]!=current[current.Length-suffix+i]){matches=false;break;}
                    if(matches)return true;
                }
                return false;
            }catch(InvalidDataException){return false;}
        }
        static byte[] PreviewVideoPage(byte[] menus) {
            using(var output=new MemoryStream()) {
                output.Write(menus,0,8);
                int cursor=8, replacements=0;
                for(int i=0;i<Read(menus,4);i++) {
                    int bytes=checked((int)Read(menus,cursor+8)*4);
                    if(Read(menus,cursor)==Crc("CosmicVideoOptions")) {
                        using(var callback=new MemoryStream()) {
                            foreach(uint word in new uint[]{
                                0x00000507,Crc("overlay"),0x00000207,Crc("overlay"),
                                0x00000217,Crc("cosmic_preview_video"),0x01050020,1,
                                0x00000207,0x8610f32e,0x00000502,0x00050219,0x84fe6ee3,
                                0x00000503,0,0x00050219,0xa393d2fb,
                                0x00010502,0x00000207,Crc("MenuStack_ShowCurrentMenu"),0x01050220,1,0x21})Append(callback,word);
                            Function(output,"CosmicVideoOptions",1,callback.ToArray());
                        }
                        replacements++;
                    } else output.Write(menus,cursor,12+bytes);
                    cursor+=12+bytes;
                }
                if(replacements!=1 || cursor!=menus.Length)throw new InvalidDataException("Options preview entry mismatch.");
                return output.ToArray();
            }
        }
        static void EnsurePauseHighlight(string scripts) {
            const string originalHash="59d49d773e53ba9f2c2e94ae0a31f31843638211dcb7ea51aeb6856465f77d47";
            string path=Path.Combine(scripts,"menu.ds"),backup=path+".cosmic-original";
            byte[] current=File.ReadAllBytes(path);
            bool backedUp=File.Exists(backup);
            byte[] original=backedUp?File.ReadAllBytes(backup):current;
            if(Hash(original)!=originalHash)throw new InvalidDataException("Unsupported original menu script.");
            byte[] aligned=AllAliensPatch.AlignPauseHighlight(original);
            byte[] updated=AllAliensPatch.GuardCheatBackdropCleanup(aligned);
            string currentHash=Hash(current);
            if(currentHash==Hash(updated))return;
            if(currentHash!=originalHash && currentHash!=Hash(aligned))throw new IOException("Another version modified menu.ds.");
            if(!backedUp)File.WriteAllBytes(backup,original);
            string temporary=path+".cosmic-new";
            File.WriteAllBytes(temporary,updated);
            File.Replace(temporary,path,null);
        }

        public static void Ensure(string gameFolder,byte[] translation=null) {
            string scripts=Path.Combine(gameFolder,"global","scripts");
            string frontend=Path.Combine(scripts,"frontend.ds"),english=Path.Combine(scripts,"xbx_us.txt");
            string frontendBackup=frontend+".cosmic-original",englishBackup=english+".cosmic-original";
            byte[] original=File.ReadAllBytes(File.Exists(frontendBackup)?frontendBackup:frontend);
            byte[] originalEnglish=File.ReadAllBytes(File.Exists(englishBackup)?englishBackup:english);
            byte[] updated=Frontend(original),updatedEnglish=translation==null?English(originalEnglish):MergeTranslation(originalEnglish,translation);
            byte[] videoPreview=PreviewVideoPage(updated);
#if COSMIC_HERO_TIME && COSMIC_NATIVE_SETTINGS
            byte[] previousSettingsPreview=AllAliensPatch.SettingsPreview(original,videoPreview);
            byte[] gameplayPreview=AllAliensPatch.StyledGameplayPreview(original,previousSettingsPreview);
            byte[] soundPreview=AllAliensPatch.StyledSoundPreview(gameplayPreview);
            byte[] preview=AllAliensPatch.StyledOptionsHub(soundPreview);
            byte[] previousSoundPreview=AllAliensPatch.StyledSoundPreview(gameplayPreview,true);
            byte[] previousStyledPreview=AllAliensPatch.StyledGameplayPreview(original,previousSettingsPreview,1);
            byte[] crashedStyledPreview=AllAliensPatch.StyledGameplayPreview(original,previousSettingsPreview,2);
            byte[] numericVibrationPreview=AllAliensPatch.StyledGameplayPreview(original,previousSettingsPreview,3);
            byte[] oldVibrationPreview=AllAliensPatch.StyledGameplayPreview(original,previousSettingsPreview,4);
#else
            byte[] previousSettingsPreview=videoPreview,preview=videoPreview,gameplayPreview=videoPreview,soundPreview=videoPreview,previousSoundPreview=videoPreview,previousStyledPreview=videoPreview,crashedStyledPreview=videoPreview,numericVibrationPreview=videoPreview,oldVibrationPreview=videoPreview;
#endif
            byte[] previousAlignedPreview=AllAliensPatch.AlignPauseMenu(preview,true);
            byte[] previousAlignedStock=AllAliensPatch.AlignPauseMenu(Frontend(original),true);
            byte[] unsyncedPreview=previousAlignedPreview,unsyncedStock=previousAlignedStock;
            byte[] alignedPreview=AllAliensPatch.AlignPauseMenu(preview);
            byte[] alignedStock=AllAliensPatch.AlignPauseMenu(Frontend(original));
#if COSMIC_NATIVE_SETTINGS
            previousAlignedPreview=AllAliensPatch.SyncLauncherGameplay(previousAlignedPreview);
            previousAlignedStock=AllAliensPatch.SyncLauncherGameplay(previousAlignedStock);
            alignedPreview=AllAliensPatch.SyncLauncherGameplay(alignedPreview);
            alignedStock=AllAliensPatch.SyncLauncherGameplay(alignedStock);
#endif
            byte[] cheatPreview=AllAliensPatch.PreserveCheatBackdropOnRefresh(alignedPreview);
            byte[] cheatStock=AllAliensPatch.PreserveCheatBackdropOnRefresh(alignedStock);
#if COSMIC_HERO_TIME && COSMIC_NATIVE_SETTINGS
            updated=cheatPreview;
#else
            updated=cheatStock;
#endif
            byte[] current=File.ReadAllBytes(frontend),currentEnglish=File.ReadAllBytes(english);
            string expected=Hash(updated),expectedEnglish=Hash(updatedEnglish),currentHash=Hash(current);
            if(currentHash==expected && Hash(currentEnglish)==expectedEnglish) { EnsurePauseHighlight(scripts);return; }
            if((currentHash!=expected && currentHash!=Hash(cheatPreview) && currentHash!=Hash(cheatStock) &&
                currentHash!=Hash(AllAliensPatch.LegacyCinematicVoiceVolume(cheatPreview)) &&
                currentHash!=Hash(AllAliensPatch.LegacyCinematicVoiceVolume(cheatStock)) && currentHash!=Hash(preview) && currentHash!=Hash(alignedPreview) && currentHash!=Hash(alignedStock) && currentHash!=Hash(previousAlignedPreview) && currentHash!=Hash(previousAlignedStock) && currentHash!=Hash(unsyncedPreview) && currentHash!=Hash(unsyncedStock) && currentHash!=Hash(videoPreview) && currentHash!=Hash(previousSettingsPreview) && currentHash!=Hash(gameplayPreview) && currentHash!=Hash(soundPreview) && currentHash!=Hash(previousSoundPreview) && currentHash!=Hash(previousStyledPreview) && currentHash!=Hash(crashedStyledPreview) && currentHash!=Hash(numericVibrationPreview) && currentHash!=Hash(oldVibrationPreview) && currentHash!=Hash(Frontend(original)) && currentHash!=FrontendHash &&
                currentHash!=Hash(LegacyFrontend(original)) && currentHash!=Hash(NativeMenuFrontend(original)) &&
                currentHash!=Hash(RathFrontend(original)) &&
                currentHash!=Hash(LegacyFrontend(original,true)) && currentHash!=Hash(NativeMenuFrontend(original,true)) &&
                currentHash!=Hash(RathFrontend(original,true)) && currentHash!=Hash(Frontend(original,true)) &&
                currentHash!=Hash(Frontend(original,false,true,true,true,true,true,true,false,false,true,true,true,false)) && currentHash!=Hash(Frontend(original,true,true,true,true,true,true,true,false,false,true,true,true,false)) &&
                currentHash!=Hash(Frontend(original,false,true,true,true,true,true,true,false,false,true,true,false)) && currentHash!=Hash(Frontend(original,true,true,true,true,true,true,true,false,false,true,true,false)) &&
                currentHash!=Hash(Frontend(original,false,true,true,true,true,true,true,false,false,true,false)) && currentHash!=Hash(Frontend(original,true,true,true,true,true,true,true,false,false,true,false)) &&
                currentHash!=Hash(Frontend(original,false,true,true,true,true,true,true,false,false,false)) && currentHash!=Hash(Frontend(original,true,true,true,true,true,true,true,false,false,false)) &&
                currentHash!=Hash(Frontend(original,false,true,true,true,true,true,true,false,true,false)) && currentHash!=Hash(Frontend(original,true,true,true,true,true,true,true,false,true,false)) &&
                currentHash!=Hash(Frontend(original,false,true,true,true,true,true,true,true)) && currentHash!=Hash(Frontend(original,true,true,true,true,true,true,true,true)) &&
                currentHash!=Hash(Frontend(original,false,true,true,true,true,true,false)) && currentHash!=Hash(Frontend(original,true,true,true,true,true,true,false)) &&
                currentHash!=Hash(Frontend(original,false,true,true,true,true,false)) && currentHash!=Hash(Frontend(original,true,true,true,true,true,false)) &&
                currentHash!=Hash(Frontend(original,false,true,true,true,false)) && currentHash!=Hash(Frontend(original,true,true,true,true,false)) &&
                currentHash!=Hash(Frontend(original,false,true,true,false,false)) && currentHash!=Hash(Frontend(original,true,true,true,false,false)) &&
                currentHash!=Hash(Frontend(original,false,true,false,false,false)) && currentHash!=Hash(Frontend(original,true,true,false,false,false)) &&
                currentHash!=Hash(Frontend(original,false,false)) && currentHash!=Hash(Frontend(original,true,false))) ||
               (Hash(currentEnglish)!=EnglishHash && Hash(currentEnglish)!=Hash(LegacyEnglish(originalEnglish)) && !IsAuthoredTranslation(originalEnglish,currentEnglish)))
                throw new IOException("The game's menu files were modified by another version. Import your ISO into a new folder; your saves are preserved separately.");
            EnsurePauseHighlight(scripts);
            if(!File.Exists(frontendBackup))File.WriteAllBytes(frontendBackup,original);
            if(!File.Exists(englishBackup))File.WriteAllBytes(englishBackup,originalEnglish);
            string first=frontend+".cosmic-new",second=english+".cosmic-new";
            File.WriteAllBytes(first,updated);File.WriteAllBytes(second,updatedEnglish);
            try {
                File.Replace(first,frontend,null);File.Replace(second,english,null);
            } catch {
                // Restore only these launcher-owned changes, never saves or other assets.
                File.WriteAllBytes(frontend,original);File.WriteAllBytes(english,originalEnglish);
                throw;
            }
        }
    }
}
