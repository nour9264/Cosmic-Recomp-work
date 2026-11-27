"""Bake approved Blender v8 normal-form chest taps into native local packages."""
import sys,struct,json,hashlib,math
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion,Vector
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
R=REPO; G=APP_ROOT/'installation/game'; OUT=WORK/'ultimate-chest-tap-native';OUT.mkdir(parents=True,exist_ok=True)
C=Matrix(((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)));Ci=C.inverted()
bpy.ops.wm.open_mainfile(filepath=str(WORK/'ultimate-chest-tap-review-v8/Ultimate-Transformation-Review.blend'))
report=[]
for label,code in [('Humungousaur','hm'),('Swampfire','sf'),('Echo Echo','ec'),('Big Chill','bc'),('Spider Monkey','sm'),('Cannonbolt','cb'),('Way Big','wayb')]:
    scene=next(s for s in bpy.data.scenes if s.name.endswith('| '+label));bpy.context.window.scene=scene
    rig=next(o for o in scene.objects if o.type=='ARMATURE');source=G/('l_tokd/g_wayb.xbx' if code=='wayb' else f'global/g_{code}.xbx');raw=source.read_bytes();p=entries(raw)
    sk=m.table(entries((G/'l_tokd/l_tokd.xbx').read_bytes())[12])[0x64ea483a] if code=='wayb' else next(iter(m.table(p[12]).values()))
    rows=m.vaps_rows(p[9]);oldrows=list(rows);oldclips=m.vaps_rows(p[13]);channels=channel_records(p[9]);idle=next(c for k,f,c in oldclips if c.startswith(b'idle_01\0'))
    ids=m.bone_ids(idle);bones={b.bone.get('game_bone_id'):b for b in rig.pose.bones};assert set(ids)==set(bones)
    bind=[];parents=[];tags=[]
    for i in range(struct.unpack_from('>H',sk)[0]):
        r=struct.unpack_from('>10fI',sk,12+44*i);tag=r[-1]&0xffffff;par=r[-1]>>24;tags.append(tag);parents.append(par)
        local=Matrix.LocRotScale(Vector(r[4:7]),Quaternion((r[3],-r[0],-r[1],-r[2])).normalized(),Vector(r[7:10]));bind.append(local if par==255 else bind[par]@local)
    assert tags==ids
    frames=[]
    # Switch at the end of the approved contact hold, not the recovery.
    for f in range(1,26):
        scene.frame_set(f);bpy.context.view_layer.update()
        world=[Ci@bones[t].matrix@bones[t].bone.matrix_local.inverted()@C@bind[i] for i,t in enumerate(tags)]
        local=[world[i] if par==255 else world[par].inverted_safe()@world[i] for i,par in enumerate(parents)]
        frames.append([v.decompose() for v in local])
    name='cosmic_ultimate_chest_tap_'+code;key=m.crc(name);assert all(k!=key for k,_,_ in oldclips)
    clip=bytearray(idle);clip[:64]=name.encode().ljust(64,b'\0');struct.pack_into('>2f',clip,64,0,3840);struct.pack_into('>I',clip,80,0xffffffff)
    for i,t in enumerate(tags):
        # Preserve the native root and non-arm visibility/scale except for the
        # approved pose. Native transformed matrices are sampled at 30 Hz.
        pos=[f[i][0] for f in frames];rot=[f[i][1].conjugated().normalized() for f in frames];scale=[f[i][2] for f in frames]
        if code=='cb' and t==193:scale=[Vector((0,0,0)) for _ in frames]
        tracks=[]
        for kind,vals in [(1,pos),(16,rot),(12,scale)]:
            if kind==16:
                b=bytearray(struct.pack('>BBHHH',16,2,0x5002,len(vals),len(vals)));prev=None
                for f,q in enumerate(vals):
                    if prev is not None and prev.dot(q)<0:q.negate()
                    prev=q.copy();b.extend(struct.pack('>3hbB',*(max(-32767,min(32767,round(x*32767))) for x in (q.x,q.y,q.z)),max(-127,min(127,round(q.w*127))),f))
            else:b=bytearray(struct.pack('>BBHHH',kind,4,0x5001 if kind==1 else 0x5003,len(vals),len(vals))+b''.join(struct.pack('>4f',f*160,*v) for f,v in enumerate(vals)))
            tracks.append(bytes(b))
        for j,b in enumerate(tracks):
            ix=len(rows);rows.append((m.crc(name+f'_{t}_{j}'),0,b));struct.pack_into('>I',clip,216+i*12+j*4,ix)
    order=sorted(range(len(rows)),key=lambda i:(rows[i][0]%max(1,len(rows)//4),rows[i][0],i));remap={i:j for j,i in enumerate(order)}
    updated=[]
    for k,flags,c in oldclips+[(key,0,bytes(clip))]:
        c=bytearray(c)
        for at in [80]+list(range(216,len(c),4)):
            ix=struct.unpack_from('>I',c,at)[0]
            if ix!=0xffffffff:struct.pack_into('>I',c,at,remap[ix])
        updated.append((k,flags,bytes(c)))
    p[9]=m.build_vaps(9,struct.unpack_from('>H',p[9],12)[0],[rows[i] for i in order]);p[13]=m.build_vaps(13,struct.unpack_from('>H',p[13],12)[0],m.bucket_sorted(updated))
    result=m.package(raw,p);decoded=entries(result);cc=channel_records(decoded[9]);clips=m.table(decoded[13]);assert all(streamed_clip(c,channels)==streamed_clip(clips[k],cc) for k,_,c in oldclips)
    assert all(decoded[k]==v for k,v in entries(raw).items() if k not in (9,13));assert animation_time_range(clips[key],cc)==(0,3840)
    dest=OUT/source.name;dest.write_bytes(result);report.append(dict(code=code,source=str(source.relative_to(G)),key=key,seconds=.8,before=hashlib.sha256(raw).hexdigest(),after=hashlib.sha256(result).hexdigest()))
    print(label,hex(key),len(tags),'bones; stock clips preserved',flush=True)
(OUT/'manifest.json').write_text(json.dumps(report,indent=2))
