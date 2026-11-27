"""Raise CD's weighted Ultimatrix head along the wrist's outward axis."""
import sys,struct,hashlib,json
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
H = WORK; G=APP_ROOT/'installation/game'; dest=H/'ben-core-raised';dest.mkdir(exist_ok=True)
path=G/'global/a_plyr.xbx';raw=path.read_bytes();p=entries(raw);old=dict(p);rows=m.vaps_rows(p[9]);clips=m.table(p[13]);channels=channel_records(p[9]);key=m.crc('cosmic_ben_transform_01');clip=clips[key]
ids=m.bone_ids(clip);index=struct.unpack_from('>I',clip,216+12*ids.index(194))[0];base=struct.unpack_from('>4f',channels[index],8)[1:]
# In CD tag 194 actually owns the visible wrist mesh; the imported VA
# longitudinal slide does not raise it. Local +Y points away from the forearm.
samples=[(0,0),(1600,0),(1760,.004),(1920,.013),(2080,.023),(2240,.029),(2400,.032),(5120,.032),(5440,.022),(5600,0),(6400,0)]
track=struct.pack('>BBHHH',1,4,0x5001,len(samples),len(samples))+b''.join(struct.pack('>4f',t,base[0],base[1]+d,base[2]) for t,d in samples)
# Dedicated track from previous core install: no other clip may use it.
assert sum(struct.unpack_from('>I',c,a)[0]==index for c in clips.values() for a in range(216,len(c),4))==1
k,f,_=rows[index];rows[index]=(k,f,track);p[9]=m.build_vaps(9,struct.unpack_from('>H',p[9],12)[0],rows)
after=m.package(raw,p);q=entries(after);cc=channel_records(q[9]);assert all(q[k]==v for k,v in old.items() if k!=9)
assert all(streamed_clip(c,channels)==streamed_clip(c,cc) for k,c in clips.items() if k!=key)
(dest/'a_plyr.xbx').write_bytes(after);(dest/'manifest.json').write_text(json.dumps({'before':hashlib.sha256(raw).hexdigest(),'after':hashlib.sha256(after).hexdigest(),'key':key,'lift':.032}))
print('Prepared raised head: native wrist-local +Y, 0.032 units, original press timing.')
