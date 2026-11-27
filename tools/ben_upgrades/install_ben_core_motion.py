"""Apply only VA wrist-device translation channels to the installed retargeted clip."""
import datetime, hashlib, json, struct, sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, streamed_clip

H = WORK; APP=APP_ROOT; G=APP/'installation/game/global'
source=vilgax_dump()/'global/a_plyr.xbx'
target=G/'a_plyr.xbx'; raw=target.read_bytes(); p=entries(raw); old=dict(p); q=entries(source.read_bytes())
key=m.crc('cosmic_ben_transform_01'); donor=m.table(q[13])[0xf1e4d5e3]; clips=m.table(p[13]); clip=clips[key]
assert clip.startswith(b'cosmic_ben_transform_01\0') and donor.startswith(b'transform_01\0')
channels=channel_records(p[9]); va=channel_records(q[9]); rows=m.vaps_rows(p[9]); ids=m.bone_ids(clip); dids=m.bone_ids(donor)
changed={}; report={}
for tag in (194,206):
    at=216+12*ids.index(tag); i=struct.unpack_from('>I',clip,at)[0]; j=struct.unpack_from('>I',donor,216+12*dids.index(tag))[0]
    src=va[j]; dst=channels[i]
    assert src[0]==dst[0]==1 and len(src)==8+8*16 and len(dst)==24
    base=struct.unpack_from('>4f',dst,8)[1:]; samples=list(struct.iter_unpack('>4f',src[8:])); initial=samples[0][1:]
    # The local parent axes match between titles, but CD's closed device
    # has slightly different bind translation. Preserve CD's zero position.
    values=[(t,*(b+x-a for b,x,a in zip(base,pos,initial))) for t,*pos in samples]
    data=src[:8]+b''.join(struct.pack('>4f',*v) for v in values)
    changed[at]=len(rows); rows.append((m.crc('cosmic_ben_core_translation_'+str(tag)),0,data));report[str(tag)]=values
order=sorted(range(len(rows)),key=lambda i:(rows[i][0]%max(1,len(rows)//4),rows[i][0],i)); remap={i:j for j,i in enumerate(order)}
p[9]=m.build_vaps(9,struct.unpack_from('>H',p[9],12)[0],[rows[i] for i in order]); result=[]
for k,flags,c in m.vaps_rows(p[13]):
    c=bytearray(c)
    for at in [80]+list(range(216,len(c),4)):
        i=struct.unpack_from('>I',c,at)[0]
        if k==key and at in changed:i=changed[at]
        if i!=0xffffffff:struct.pack_into('>I',c,at,remap[i])
    result.append((k,flags,bytes(c)))
p[13]=m.build_vaps(13,struct.unpack_from('>H',p[13],12)[0],result); new=m.package(raw,p); check=entries(new); cc=channel_records(check[9]); nc=m.table(check[13])
assert set(nc)==set(clips) and all(check[k]==v for k,v in old.items() if k not in (9,13))
assert all(streamed_clip(c,channels)==streamed_clip(nc[k],cc) for k,c in clips.items() if k!=key)
for at in [80]+list(range(216,len(clip),4)):
    if at in changed:continue
    a=struct.unpack_from('>I',clip,at)[0]; b=struct.unpack_from('>I',nc[key],at)[0]
    assert (a==b==0xffffffff) or channels[a]==cc[b]
before_clip=streamed_clip(clip,channels); after_clip=streamed_clip(nc[key],cc)
changes={target:(raw,new)}
for level in G.parent.glob('l_*'):
    for path in level.glob('a_*_s.xbx'):
        original=path.read_bytes(); records=entries(original,True)
        if key not in records:continue
        assert records[key]==before_clip, str(path)
        records[key]=after_clip
        data=m.package(original,records)
        assert entries(data)==records
        changes[path]=(original,data)
assert len(changes)>1
backup=H/'ben-core-motion-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S'); backup.mkdir(parents=True)
for path,(prior,after) in changes.items():
    dest=backup/'before'/path.relative_to(APP); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(prior); assert dest.read_bytes()==prior
done=[]
try:
    for path,(prior,after) in changes.items():
        assert path.read_bytes()==prior
        tmp=path.with_name(path.name+'.core-new'); assert not tmp.exists(); tmp.write_bytes(after); tmp.replace(path); done.append(path); assert path.read_bytes()==after
except BaseException:
    for path in reversed(done):
        tmp=path.with_name(path.name+'.core-restore'); tmp.write_bytes(changes[path][0]); tmp.replace(path)
    raise
sha=lambda b:hashlib.sha256(b).hexdigest()
(backup/'validation.json').write_text(json.dumps({'tracks':report,'files':{str(p.relative_to(APP)):{'before':sha(a),'after':sha(b)} for p,(a,b) in changes.items()},'gameplay_verified':False},indent=2))
print('Installed original VA core motion on tags 194 and 206:',len(changes),'packages. Backup:',backup)
