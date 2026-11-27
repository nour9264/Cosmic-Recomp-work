"""Convert both approved Cannonbolt Blender previews and install locally.

The normal and Ultimate forms use separate dodge and long-attack routes.
Travel is owned by the game's target/dodge controller; the clips retain the
approved body and ball articulation (including scale switches) and vertical arc.
"""
import datetime
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, streamed_clip, animation_time_range
from prepare_all_aliens_candidate import records, encode

ROOT = (APP_ROOT/'installation').resolve()
G = ROOT / 'game/global'
U = ROOT / 'vilgax/ultimatecannonbolt'
N = ROOT / 'vilgax/cannonbolt'
OUT = (WORK/'cannonbolt-approved-actions-native').resolve()
SIG = bytes.fromhex('1badbabe')
SHA = lambda b: hashlib.sha256(b).hexdigest()
ORDER = (0, 3, 4, 9, 12, 13, 14, 22, 24)
C = Matrix(((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)))
CI = C.inverted()

raw = (G/'g_cb.xbx').read_bytes()
assert raw == (N/'g_cb.xbx').read_bytes()
parts = entries(raw)
old = dict(parts)
oldchannels = channel_records(parts[9])
channelrows = m.vaps_rows(parts[9])
cliprows = m.vaps_rows(parts[13])
clips = dict((k,v) for k,_,v in cliprows)
byname = {v[:64].split(b'\0')[0].decode():k for k,v in clips.items()}
idle = clips[byname['idle_01']]
ids = m.bone_ids(idle)
assert len(ids) == 45
sk = m.table(parts[12])[0x8b21e1f6]
bind, parents = [], []
for i in range(45):
    v = struct.unpack_from('>10f', sk, 12+44*i)
    tag = struct.unpack_from('>I', sk, 52+44*i)[0]
    assert tag & 0xffffff == ids[i]
    parent = -1 if tag>>24 == 255 else tag>>24
    parents.append(parent)
    local = Matrix.LocRotScale(Vector(v[4:7]),Quaternion((v[3],*v[:3])).conjugated(),Vector(v[7:]))
    bind.append(local if parent<0 else bind[parent]@local)

def extract(scene_name, frames):
    scene = bpy.data.scenes[scene_name]
    bpy.context.window.scene = scene
    rig = next(o for o in scene.objects if o.type=='ARMATURE')
    bones = sorted(rig.pose.bones, key=lambda b:b.bone['game_bone_index'])
    assert [b.bone['game_bone_id'] for b in bones] == ids
    assert scene.frame_end == frames and scene.render.fps==30
    rests = [b.bone.matrix_local.inverted()@C@v for b,v in zip(bones,bind)]
    result = []
    scene.frame_set(1)
    baseline = rig.location.z
    for frame in range(1,frames+1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        # Export the actual evaluated Blender deformation (not an approximation
        # to the animation). Keep only the vertical part of object motion.
        lift = Matrix.Translation((0,rig.location.z-baseline,0))
        world = [lift@CI@b.matrix@rest for b,rest in zip(bones,rests)]
        row=[]
        for i,w in enumerate(world):
            local = w if parents[i]<0 else world[parents[i]].inverted()@w
            p,q,s = local.decompose()
            # Native body/ball visibility uses scale 0. Blender stored a small
            # epsilon to allow inverse matrices while authoring. Restore zero
            # only for those two native visibility bones, never children.
            if i in (1,44) and max(s)<.001:
                s=Vector((0,0,0))
            assert all(math.isfinite(x) for x in (*p,*q,*s))
            assert max(abs(x) for x in p)<5 and max(abs(x) for x in s)<2.5, (scene_name,frame,i,p,s)
            if i not in (1,44):
                assert min(s)>.95 and max(s)<1.05,(scene_name,frame,i,tuple(s))
            row.append((p,q.normalized(),s))
        assert max(row[1][2])>.1 or max(row[44][2])>.1, (scene_name,frame)
        result.append(row)
    print('Extracted',scene_name,len(result),'frames; vertical range',round(min(x[0][0].y for x in result),3),round(max(x[0][0].y for x in result),3),flush=True)
    return result

actions = {
    'dodge':extract('01 | Forward Dodge Roll',30),
    'ram':extract('02 | Long Attack - Rolling Ram',50),
    'aerial':extract('03 | Long Attack - Aerial Cannonball',43),
}
bpy.ops.wm.open_mainfile(filepath=str((WORK/'Cannonbolt-Dodge-and-Long-Attacks.blend').resolve()))
actions.update({
    'normal_dodge':extract('01 | Normal - Quick Roll Hop',24),
    'bowling':extract('02 | Normal - Bowling Strike',43),
    'body_slam':extract('03 | Normal - Jumping Body Slam',40),
})

def vec_channel(values,kind):
    return struct.pack('>BBHHH',kind,4,0x5001 if kind==1 else 0x5003,len(values),len(values))+b''.join(struct.pack('>4f',i*160,*v) for i,v in enumerate(values))

def quat_channel(values):
    out=bytearray(struct.pack('>BBHHH',16,2,0x5002,len(values),len(values)))
    previous=None
    for i,rotation in enumerate(values):
        q=rotation.conjugated().normalized()
        if previous is not None and q.dot(previous)<0:q.negate()
        previous=q.copy()
        out.extend(struct.pack('>3hbB',*(max(-32767,min(32767,round(v*32767))) for v in (q.x,q.y,q.z)),max(-127,min(127,round(q.w*127))),i))
    return bytes(out)

newchannels = {}
def addchannel(data,name):
    # Deduplicate newly authored tracks; original directory rows are retained.
    if data not in newchannels:
        newchannels[data]=len(channelrows)
        channelrows.append((m.crc(name),0,data))
    return newchannels[data]

def event_track(donor, frames, impact_at=None):
    i=struct.unpack_from('>I',donor,80)[0]
    if i==0xffffffff:return None
    raw=oldchannels[i]
    n,mcount=struct.unpack_from('>HH',raw,4)
    assert n==mcount and 8+n*36==len(raw)
    begin,end=animation_time_range(donor,oldchannels)
    length=(frames-1)*160
    # Preserve all native event flag/payload words, changing only the time.
    # Map the donor's contact (first nonzero hit event) onto the authored
    # strike/landing, without reversing the original sequence.
    times=[struct.unpack_from('>f',raw,8+36*j)[0] for j in range(n)]
    if impact_at is not None:
        hit_index=next((j for j in range(n) if struct.unpack_from('>I',raw,8+36*j+16)[0] in (0x100000,0x80000)),None)
    else:hit_index=None
    def retime(t):
        if hit_index is None:
            return (t-begin)/(end-begin)*length
        pivot=times[hit_index];target=impact_at*160
        if t<=pivot:return (t-begin)/max(1,pivot-begin)*target
        return target+(t-pivot)/max(1,end-pivot)*(length-target)
    out=bytearray(raw)
    for j,t in enumerate(times):
        struct.pack_into('>f',out,8+j*36,max(1,min(length-1,retime(t))))
    return bytes(out)

appended=[]
def addclip(name, action, start, end, donor_name=None, impact_at=None):
    key=m.crc(name)
    assert key not in clips and all(k!=key for k,_,_ in appended)
    frames=actions[action][start-1:end]
    assert 2<=len(frames)<=255
    clip=bytearray(idle);encoded=name.encode();assert len(encoded)<64
    clip[:64]=encoded.ljust(64,b'\0')
    struct.pack_into('>2f',clip,64,0,(len(frames)-1)*160)
    event=event_track(clips[byname[donor_name]],len(frames),impact_at) if donor_name else None
    struct.pack_into('>I',clip,80,addchannel(event,name+'_event') if event else 0xffffffff)
    for i in range(45):
        p,q,s=zip(*(f[i] for f in frames))
        for field,channel in enumerate((vec_channel(p,1),quat_channel(q),vec_channel(s,12))):
            idx=addchannel(channel,f'{name}_{i}_{field}')
            struct.pack_into('>I',clip,216+(3*i+field)*4,idx)
    appended.append((key,0,bytes(clip)))
    return key

dodge=addclip('cosmic_ucb_dodge_forward','dodge',1,30)
ram_travel=addclip('cosmic_ucb_ram_travel','ram',1,28)
ram_recovery=addclip('cosmic_ucb_ram_recovery','ram',38,50)
aerial_travel=addclip('cosmic_ucb_aerial_travel','aerial',1,25)
aerial_recovery=addclip('cosmic_ucb_aerial_recovery','aerial',35,43)
normal_dodge=addclip('cosmic_cb_dodge_forward','normal_dodge',1,24)
bowling_travel=addclip('cosmic_cb_bowling_travel','bowling',1,21)
bowling_recovery=addclip('cosmic_cb_bowling_recovery','bowling',34,43)
slam_travel=addclip('cosmic_cb_slam_travel','body_slam',1,26)
slam_recovery=addclip('cosmic_cb_slam_recovery','body_slam',32,40)

# Exactly the four native FAR attack rows (normal and finisher variants).
# Counterattacks and attacks against downed targets are separate and unchanged.
routes=[]
def attack_patch(code, bundle, variants):
    attack_old=(G/'scripts'/f'atk_{code}.ddf').read_bytes()
    assert attack_old==(bundle/f'atk_{code}.ddf').read_bytes()
    attack_new=bytearray(attack_old)
    changed=0
    for at in range(4,len(attack_old),224):
        row=list(struct.unpack_from('>56I',attack_old,at))
        if row[4] not in (0xc0077403,0x70017403,0x100c7403,0x20047403):continue
        assert row[7]==byname['run_01'] and row[40]==0x47c02d3b
        donor=clips[row[8]][:64].split(b'\0')[0].decode()
        forward=row[4] in (0xc0077403,0x70017403)
        name,start,end,hit,travel,recovery=variants[int(not forward)]
        has_recovery=bool(row[9])
        final=end if has_recovery else len(actions[name])
        row[7]=travel
        row[8]=addclip(f'cosmic_{code}_{name}_hit_{row[0]:08x}',name,start,final,donor,hit)
        if has_recovery:row[9]=recovery
        struct.pack_into('>56I',attack_new,at,*row)
        routes.append({'form':code,'id':hex(row[0]),'attack':name,'legacy_hit':donor,'travel':hex(row[7]),'strike':hex(row[8]),'recovery':hex(row[9])})
        changed+=1
    assert changed==4
    for at in range(4,len(attack_old),224):
        assert attack_old[at:at+28]==attack_new[at:at+28] and attack_old[at+40:at+224]==attack_new[at+40:at+224]
    return bytes(attack_new)

attack_ultimate=attack_patch('ucb',U,[('ram',28,38,5,ram_travel,ram_recovery),('aerial',25,35,2,aerial_travel,aerial_recovery)])
attack_normal=attack_patch('cb',N,[('bowling',21,34,2,bowling_travel,bowling_recovery),('body_slam',26,32,2,slam_travel,slam_recovery)])
assert len(routes)==8 and all(sum(x['attack']==name for x in routes)==2 for name in ('ram','aerial','bowling','body_slam'))

# Reindex after the channel-directory sort and prove every original clip is
# byte-equivalent in streamed form, including all existing special attacks.
buckets=max(1,len(channelrows)//4)
order=sorted(range(len(channelrows)),key=lambda i:(channelrows[i][0]%buckets,channelrows[i][0],i))
remap={old:new for new,old in enumerate(order)}
outclips=[]
for k,flag,blob in cliprows+appended:
    data=bytearray(blob)
    for at in [80]+list(range(216,len(data),4)):
        index=struct.unpack_from('>I',data,at)[0]
        if index!=0xffffffff:struct.pack_into('>I',data,at,remap[index])
    outclips.append((k,flag,bytes(data)))
parts[9]=m.build_vaps(9,struct.unpack_from('>H',old[9],12)[0],[channelrows[i] for i in order])
parts[13]=m.build_vaps(13,struct.unpack_from('>H',old[13],12)[0],m.bucket_sorted(outclips))
newbank=m.package(raw,parts,ORDER)
check=entries(newbank);newch=channel_records(check[9]);newclips=m.table(check[13])
assert all(check[k]==v for k,v in old.items() if k not in (9,13))
assert all(streamed_clip(v,oldchannels)==streamed_clip(newclips[k],newch) for k,v in clips.items())
for key,_,_ in appended:
    assert m.bone_ids(newclips[key])==ids
    assert animation_time_range(newclips[key],newch)[0]==0
    streamed_clip(newclips[key],newch)

# UCB formerly reused the normal Cannonbolt person record. Clone it under a
# new key and give the original record its separate normal dodge.
person_key=0x94c8a236;new_person=m.crc('cosmic_ultimatecannonbolt_person')
person_records=m.ddf_records(SIG+(N/'xbx-records.bin').read_bytes())
header,body=person_records[person_key]
assert len(person_records)==1 and len(body)==1684 and struct.unpack_from('>I',body,0x130)[0]==0
person=bytearray(header+body)
struct.pack_into('>I',person,0,new_person)
struct.pack_into('>I',person,24+0x130,dodge)
normal_person=bytearray(header+body)
struct.pack_into('>I',normal_person,24+0x130,normal_dodge)
assert not (U/'xbx-records.bin').read_bytes()
xbx_old=(G/'scripts/xbx.ddf').read_bytes()
all_person_records=m.ddf_records(xbx_old)
assert all_person_records[person_key]==(header,body) and new_person not in all_person_records
assert xbx_old.count(header+body)==1
xbx_new=xbx_old.replace(header+body,bytes(normal_person),1)+person
new_person_records=m.ddf_records(xbx_new)
assert len(new_person_records)==len(all_person_records)+1
assert all(new_person_records[k]==v for k,v in all_person_records.items() if k!=person_key)
assert struct.unpack_from('>I',new_person_records[person_key][1],0x130)[0]==normal_dodge
assert struct.unpack_from('>I',new_person_records[new_person][1],0x130)[0]==dodge

form_id=m.crc('Cosmic_ultimatecannonbolt_init')
def forms_patch(blob):
    rows=records(blob);result=[];changed=0
    assert encode(rows)==blob
    for key,args,code in rows:
        if key==form_id:
            newcode=m.replace_arguments(code,{person_key:new_person})
            assert newcode!=code and len(newcode)==len(code)
            assert sum(a!=b for a,b in zip(struct.iter_unpack('>I',code),struct.iter_unpack('>I',newcode)))==1
            code=newcode;changed+=1
        result.append((key,args,code))
    assert changed==1
    return encode(result)

form_old=(U/'forms.bin').read_bytes();form_new=forms_patch(form_old)
# Installed imported init functions reside in gld_xbx.ds, not globals.ds.
gld_old=(G/'scripts/gld_xbx.ds').read_bytes();gld_new=forms_patch(gld_old)
changes={G/'g_cb.xbx':newbank,N/'g_cb.xbx':newbank,
         G/'scripts/atk_ucb.ddf':attack_ultimate,U/'atk_ucb.ddf':attack_ultimate,
         G/'scripts/atk_cb.ddf':attack_normal,N/'atk_cb.ddf':attack_normal,
         N/'xbx-records.bin':bytes(normal_person),
         U/'xbx-records.bin':bytes(person),G/'scripts/xbx.ddf':bytes(xbx_new),
         U/'forms.bin':form_new,G/'scripts/gld_xbx.ds':gld_new}
ucb_model=(G/'g_ucb.xbx').read_bytes()
backup=OUT/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True)
manifest=[]
for path,data in changes.items():
    assert path.is_file() and path.is_relative_to(ROOT)
    relative=path.relative_to(ROOT);dst=backup/'before'/relative;dst.parent.mkdir(parents=True,exist_ok=True)
    original=path.read_bytes();dst.write_bytes(original)
    dst=backup/'after'/relative;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
    manifest.append({'file':str(relative),'before':SHA(original),'after':SHA(data)})
report={'files':manifest,'clips':len(appended),'approved_actions':6,'routes':routes,'person':hex(new_person),
        'dodge':{'normal':hex(normal_dodge),'ultimate':hex(dodge)},'original_animation_payloads_preserved':True,'gameplay_verified':False}
(backup/'validation.json').write_text(json.dumps(report,indent=2))
if '--install' in sys.argv:
    for path,data in changes.items():
        assert SHA(path.read_bytes())==next(x['before'] for x in manifest if x['file']==str(path.relative_to(ROOT)))
    for path,data in changes.items():
        staged=path.with_name(path.name+'.ucb-actions-new');staged.write_bytes(data);staged.replace(path)
        assert path.read_bytes()==data
    assert (G/'g_ucb.xbx').read_bytes()==ucb_model
    print('INSTALLED:',len(changes),'files; both forms; backup',backup,flush=True)
else:
    print('VALIDATED CANDIDATE:',backup,flush=True)
print(json.dumps(report,indent=2),flush=True)
