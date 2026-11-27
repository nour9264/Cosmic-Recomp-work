"""Retiming fix for Jetray travel clips; preserve the approved single-direction dodge."""
import sys,struct,math,json,hashlib,datetime
from pathlib import Path
from mathutils import Quaternion
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from vilgax_animation_paths import APP as APP_ROOT, BLEND, REPO, WORK
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
root=(APP_ROOT/'installation')
p=root/'vilgax/jetray/g_jr.xbx';raw=p.read_bytes();sections=entries(raw)
rows=m.vaps_rows(sections[9]);clips=m.vaps_rows(sections[13]);oldchannels=[r[2] for r in rows]
targets={k for k,f,c in clips if c[:64].split(b'\0')[0] in [b'cosmic_lunge_left',b'cosmic_lunge_right',b'cosmic_lunge_dive']};assert len(targets)==3
used={struct.unpack_from('>I',c,a)[0] for k,f,c in clips if k not in targets for a in [80]+list(range(216,len(c),4))}
changed=set();result=[]
for k,flags,c in clips:
 if k not in targets:result.append((k,flags,c));continue
 c=bytearray(c);assert animation_time_range(c,oldchannels)==(0.0,4480.0),'Already retimed or unexpected source'
 for at in range(216,len(c),4):
  idx=struct.unpack_from('>I',c,at)[0];assert idx not in used and idx not in changed
  key,flag,channel=rows[idx];kind=channel[0];count=struct.unpack_from('>H',channel,4)[0];assert count==29
  out=bytearray(channel[:8]);struct.pack_into('>2H',out,4,11,11)
  # Authoring frames 1..17 contain launch/flight/contact. Recovery is owned
  # by the original impact/recovery clips following this travel state.
  for f in range(11):
   source=f*16/10;lo=int(source);hi=min(lo+1,28);u=source-lo
   if kind==16:
    def readq(i):
     x,y,z,w,t=struct.unpack_from('>3hbB',channel,8+i*8);return Quaternion((w/127,x/32767,y/32767,z/32767)).normalized()
    q=readq(lo).slerp(readq(hi),u)
    out.extend(struct.pack('>3hbB',*[max(-32767,min(32767,round(v*32767))) for v in (q.x,q.y,q.z)],max(-127,min(127,round(q.w*127))),f))
   else:
    assert kind in (1,12)
    a=struct.unpack_from('>4f',channel,8+lo*16)[1:];b=struct.unpack_from('>4f',channel,8+hi*16)[1:]
    out.extend(struct.pack('>4f',f*160,*[x+(y-x)*u for x,y in zip(a,b)]))
  rows[idx]=(key,flag,bytes(out));changed.add(idx)
 struct.pack_into('>2f',c,64,0,1600);result.append((k,flags,bytes(c)))
sections[9]=m.build_vaps(9,struct.unpack_from('>H',sections[9],12)[0],rows)
sections[13]=m.build_vaps(13,struct.unpack_from('>H',sections[13],12)[0],result)
new=m.package(raw,sections);decoded=entries(new);nc=channel_records(decoded[9]);nd=m.table(decoded[13])
for k,f,c in clips:
 if k in targets:assert animation_time_range(nd[k],nc)==(0.0,1600.0)
 else:assert streamed_clip(c,oldchannels)==streamed_clip(nd[k],nc)
for key,value in entries(raw).items():
 if key not in (9,13):assert decoded[key]==value
backup=(BLEND/'jetray-native-patch')/('speed-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest();manifest=[]
for target in [p,root/'game/global/g_jr.xbx']:
 old=target.read_bytes();assert old==raw,'Active package differs'
 saved=backup/target.relative_to(root);saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(old)
 manifest.append({'path':target.relative_to(root).as_posix(),'before':sha(old),'after':sha(new)})
for target in [p,root/'game/global/g_jr.xbx']:
 tmp=target.with_name(target.name+'.jetray-new');tmp.write_bytes(new);tmp.replace(target);assert target.read_bytes()==new
(backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
(BLEND/'jetray-native-patch'/'lunge-speed-validation.json').write_text(json.dumps(dict(duration_before=4480/4800,duration_after=1600/4800,clips=3,unchanged_other_clips=True,unchanged_dodge=True,gameplay_verified=False,backup=str(backup)),indent=2))
print('Installed: 3 lunges now 0.333s (native travel timing), down from 0.933s; recovery tail removed. Dodge and every other clip unchanged. Restart game through launcher to refresh streams.')
