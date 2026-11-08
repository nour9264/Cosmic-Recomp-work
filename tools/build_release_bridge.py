"""Build the corrected settings/animation bridge, or the legacy exclusion profile."""
import argparse,os,subprocess
from pathlib import Path
from prepare_all_aliens_candidate import ROOT,authored,encode

parser=argparse.ArgumentParser();parser.add_argument('--rath-disabled',action='store_true');parser.add_argument('--hero-time',action='store_true');parser.add_argument('--gpu-diagnostics',action='store_true');parser.add_argument('--performance-alpha5',action='store_true');parser.add_argument('--ultimate-voices',action='store_true');parser.add_argument('--discord-presence',action='store_true')
parser.add_argument('--four-arms',action='store_true',help='Build the optional Four Arms launcher bridge')
parser.add_argument('--output-dir',type=Path)
args=parser.parse_args()
assert not args.performance_alpha5 or (args.hero_time and args.gpu_diagnostics),'Alpha 5 requires explicit --hero-time --gpu-diagnostics'
assert not (args.rath_disabled and args.hero_time)
# The current contributor default must include the released authored features.
# Keep --hero-time accepted for existing reproducible release commands.
if not args.rath_disabled:args.hero_time=True
assert not args.discord_presence or args.hero_time,'Discord presence requires the API 7 Hero Time bridge'
assert not args.ultimate_voices or args.hero_time,'Ultimate voices require Hero Time'
assert not args.gpu_diagnostics or args.hero_time,'GPU diagnostics require the matching Hero Time API 7 profile'
assert not (args.four_arms and args.rath_disabled),'Four Arms requires the standard roster'
out=args.output_dir.resolve() if args.output_dir else ROOT/('build/four-arms-release-bridge' if args.four_arms else 'build/gpu-diagnostic-release' if args.gpu_diagnostics else 'build/rath-disabled-release' if args.rath_disabled else 'build/hero-time-release' if args.hero_time else 'build/settings-release')
out.mkdir(parents=True,exist_ok=True)
program=out/'AllAliensProgram.bin';program.write_bytes(encode(authored(disable_rath=args.rath_disabled,preload_resources=args.hero_time,four_arms_probe=args.four_arms)))
hero_arguments=[]
if args.hero_time:
    from prepare_hero_time_candidate import authored as hero_authored
    hero=out/'HeroTimeProgram.bin';hero.write_bytes(encode(hero_authored(ultimate_voices=args.ultimate_voices,discord_presence=args.discord_presence)))
    hero_arguments=['/resource:'+str(hero)+',CosmicHeroTime.bin']
    if args.ultimate_voices:
        from ultimate_voice_program import resolver
        voice=out/'UltimateVoiceResolver.bin';voice.write_bytes(encode(resolver()))
        hero_arguments.append('/resource:'+str(voice)+',CosmicUltimateVoiceResolver.bin')
os.environ.update(TEMP=str(ROOT/'data/temp'),TMP=str(ROOT/'data/temp'))
csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
sources=[str(ROOT/'launcher'/('four-arms' if args.four_arms and n in ('NativeBridge.cs','GameMenuPatch.cs','AllAliensPatch.cs') else '')/n)
         for n in ['NativeBridge.cs','InstalledGame.cs','IsoImage.cs','GameMenuPatch.cs','AllAliensPatch.cs','SaveReset.cs']]
if args.ultimate_voices:sources.extend(str(ROOT/'launcher'/n) for n in ['UltimateVoicePatch.cs','UltimateVoiceLinks.cs'])
if args.discord_presence:sources.extend(str(ROOT/'launcher'/n) for n in ['DiscordPresence.cs','DiscordPresencePatch.cs'])
subprocess.run([str(csc),'/nologo','/optimize+','/target:winexe','/platform:x64',
 '/define:'+('COSMIC_DISABLE_RATH' if args.rath_disabled else 'COSMIC_NATIVE_SETTINGS;COSMIC_ALIEN_STREAMS'+(';COSMIC_HERO_TIME;COSMIC_PRELOAD_ALIENS' if args.hero_time else '')+(';COSMIC_GPU_DIAGNOSTICS' if args.gpu_diagnostics else '')+(';COSMIC_PERFORMANCE_ALPHA5' if args.performance_alpha5 else '')+(';COSMIC_ULTIMATE_VOICES' if args.ultimate_voices else '')+(';COSMIC_DISCORD_PRESENCE' if args.discord_presence else '')),'/win32manifest:'+str(ROOT/'launcher/windows.manifest'),
 *(['/reference:System.Web.Extensions.dll'] if args.discord_presence else []),
 '/reference:System.Windows.Forms.dll','/resource:'+str(program)+',CosmicAllAliens.bin',
 *hero_arguments,'/out:'+str(out/'CosmicBridge.exe'),*sources],check=True)
print('Legacy exclusion bridge built.' if args.rath_disabled else 'Corrected animation/settings bridge built; matching API 7 runtime required.')
