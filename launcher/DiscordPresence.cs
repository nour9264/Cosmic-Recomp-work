using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

namespace CosmicRecompi {
    // Desktop IPC only: no bot, account credentials, OAuth token or network service.
    internal sealed class DiscordPresence : IDisposable {
        internal const string ApplicationId="1568421826894500000";
        readonly Process game;readonly string status,log,pipePrefix;readonly long started;
        readonly ManualResetEvent stop=new ManualResetEvent(false);
        readonly object gate=new object();NamedPipeClientStream pipe;readonly Thread worker;
        static readonly Dictionary<string,string[]> Levels=new Dictionary<string,string[]> {
            {"l_romd",new[]{"The Catacombs","catacombs"}},
            {"l_pari",new[]{"Eiffel Tower","eiffel_tower"}},
            {"l_rush",new[]{"Devil's Tower","devils_tower"}},
            {"l_chin",new[]{"The Great Wall","great_wall"}},
            {"l_tokn",new[]{"Tokyo Nights","tokyo_nights"}},
            {"l_mili",new[]{"The Amazon","amazon"}},
            {"l_romn",new[]{"The Colosseum","colosseum"}},
            {"l_tokd",new[]{"The Final Battle","final_battle"}}
        };
        internal DiscordPresence(Process process,string statusFile,string diagnosticLog,string ipcPrefix="discord-ipc-") {
            game=process;status=statusFile;log=diagnosticLog;pipePrefix=ipcPrefix;
            started=new DateTimeOffset(process.StartTime.ToUniversalTime()).ToUnixTimeSeconds();
            worker=new Thread(Run);worker.IsBackground=true;worker.Name="Cosmic Discord Presence";worker.Start();
        }
        internal static Dictionary<string,object> Activity(string level,long start) {
            string[] info;bool playing=Levels.TryGetValue(level??"",out info);
            var art=new Dictionary<string,object>{{"large_image","game_cover"},{"large_text","Cosmic Recomp (Fan-made PC port)"}};
            if(playing){art.Add("small_image",info[1]);art.Add("small_text",info[0]);}
            return new Dictionary<string,object>{{"type",0},{"details",playing?"Playing: "+info[0]:"Menus / Loading"},
                {"state","Ben 10: Ultimate Alien - Cosmic Destruction"},
                {"timestamps",new Dictionary<string,object>{{"start",start}}},
                {"assets",art}};
        }
        string Level() {try{return File.Exists(status)?File.ReadAllText(status).Trim():"menus";}catch(IOException){return "menus";}}
        void Note(string message) {try{File.AppendAllText(log,DateTime.UtcNow.ToString("o")+" Discord presence: "+message+Environment.NewLine);}catch(IOException){} }
        void Write(int opcode,byte[] data) {
            byte[] header=new byte[8];Buffer.BlockCopy(BitConverter.GetBytes(opcode),0,header,0,4);Buffer.BlockCopy(BitConverter.GetBytes(data.Length),0,header,4,4);
            // Async operations and finite deadlines prevent a stalled Discord client from hanging shutdown.
            WriteBytes(header);WriteBytes(data);
        }
        void Complete(System.Threading.Tasks.Task operation,int timeout) {
            var clock=Stopwatch.StartNew();
            while(!operation.Wait(50)) {
                if(stop.WaitOne(0) || clock.ElapsedMilliseconds>=timeout)throw new IOException("Discord IPC stopped or timed out");
            }
        }
        void WriteBytes(byte[] data) {
            // Task owns its completion handle. Disposing an APM wait handle
            // before a pending pipe completion can crash the completion thread.
            Complete(pipe.WriteAsync(data,0,data.Length),2000);
        }
        byte[] ReadBytes(int count) {
            byte[] bytes=new byte[count];int at=0;
            while(at<count) {
                var pending=pipe.ReadAsync(bytes,at,count-at);Complete(pending,3000);
                int n=pending.Result;if(n==0)throw new IOException("Discord disconnected");at+=n;
            }return bytes;
        }
        Dictionary<string,object> ReadFrame() {
            for(int frames=0;frames<16;frames++) {
                byte[] header=ReadBytes(8);int opcode=BitConverter.ToInt32(header,0),size=BitConverter.ToInt32(header,4);
                if(size<0 || size>65536)throw new IOException("Invalid IPC frame length");
                byte[] data=ReadBytes(size);
                if(opcode==3){Write(4,data);continue;}
                if(opcode!=1)throw new IOException("Discord closed the IPC session");
                return new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(Encoding.UTF8.GetString(data));
            }throw new IOException("Too many IPC control frames");
        }
        void Send(object activity) {
            string nonce=Guid.NewGuid().ToString("N");
            var command=new Dictionary<string,object>{{"cmd","SET_ACTIVITY"},{"nonce",nonce},
                {"args",new Dictionary<string,object>{{"pid",game.Id},{"activity",activity}}}};
            Write(1,Encoding.UTF8.GetBytes(new JavaScriptSerializer().Serialize(command)));
            for(int i=0;i<16;i++) {
                var reply=ReadFrame();object value;
                if(reply.TryGetValue("evt",out value) && (string)value=="ERROR")throw new IOException("Discord rejected activity: "+new JavaScriptSerializer().Serialize(reply["data"]));
                if(reply.TryGetValue("nonce",out value) && (string)value==nonce)return;
            }throw new IOException("Discord activity response missing");
        }
        void Run() {
            bool reportedUnavailable=false;
            while(!stop.WaitOne(0)) {
                try {
                    NamedPipeClientStream connected=null;
                    for(int i=0;i<10 && !stop.WaitOne(0);i++) {
                        var candidate=new NamedPipeClientStream(".",pipePrefix+i,PipeDirection.InOut,PipeOptions.Asynchronous);
                        try{candidate.Connect(75);connected=candidate;break;}catch(TimeoutException){candidate.Dispose();}catch(IOException){candidate.Dispose();}
                    }
                    if(connected==null)throw new IOException("Desktop Discord is not available");
                    lock(gate){pipe=connected;}
                    if(stop.WaitOne(0))break;
                    Write(0,Encoding.UTF8.GetBytes("{\"v\":1,\"client_id\":\""+ApplicationId+"\"}"));
                    var ready=ReadFrame();object evt;
                    if(!ready.TryGetValue("evt",out evt) || (string)evt!="READY")throw new IOException("Discord handshake rejected");
                    Note("connected");reportedUnavailable=false;string previous=null;DateTime refreshed=DateTime.MinValue;
                    while(!stop.WaitOne(0)) {
                        string level=Level();
                        if(level!=previous || (DateTime.UtcNow-refreshed).TotalSeconds>=15) {
                            bool changed=level!=previous;Send(Activity(level,started));previous=level;refreshed=DateTime.UtcNow;if(changed)Note("activity acknowledged: "+level);
                        }
                        if(stop.WaitOne(2000))break;
                    }
                } catch(Exception error) {
                    if(!stop.WaitOne(0) && !reportedUnavailable){Note(error.Message);reportedUnavailable=true;}
                } finally {lock(gate){if(pipe!=null){pipe.Dispose();pipe=null;}}}
                if(stop.WaitOne(10000))break;
            }
        }
        public void Dispose() {
            stop.Set();lock(gate){if(pipe!=null)pipe.Dispose();}
            worker.Join(500); // Worker is background-only; never delay game exit.
        }
    }
}
