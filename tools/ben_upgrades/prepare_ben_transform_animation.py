"""Port the locally owned VA Ben transformation to CD's existing skeleton."""
import hashlib, json, math, struct, sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, animation_time_range, streamed_clip, merge_streams

H = WORK;APP=APP_ROOT
G=APP/'installation/game/global'
source=vilgax_dump()/'global/a_plyr.xbx'
baseline=H/'transformation-animation-backups/20261124-223509/before/installation/game'
raw=(baseline/'global/a_plyr.xbx').read_bytes();p=entries(raw);s=entries(source.read_bytes())
oldclips=m.table(p[13]);sc=m.table(s[13]);oldch=channel_records(p[9]);sch=channel_records(s[9])
va=sc[0xf1e4d5e3];idle=oldclips[0x785f6c3e]
assert va[:64].split(b'\0')[0]==b'transform_01'
assert animation_time_range(va,sch)==(0,6400)
ids=m.bone_ids(idle);vaids=m.bone_ids(va)
assert set(ids)==set(vaids)-{167,168} and len(ids)==62
def indexes(c,i):
    return struct.unpack_from('>3I',c,216+12*i)
def qvalues(r):
    return [(t*160,(-x/32767,-y/32767,-z/32767,w/127))
        for x,y,z,w,t in struct.iter_unpack('>3hbB',r[8:])]
def normal(q):
    d=math.sqrt(sum(v*v for v in q));return tuple(v/d for v in q)
def qmul(a,b):
    x,y,z,w=a;u,v,t,s=b
    return normal((w*u+x*s+y*t-z*v,w*v-x*t+y*s+z*u,w*t+x*v-y*u+z*s,w*s-x*u-y*v-z*t))
def xyz(r):return list(struct.iter_unpack('>4f',r[8:]))
vroot=indexes(va,vaids.index(0));vbody=indexes(va,vaids.index(31))
rootloc=sch[vroot[0]];rootq=qvalues(sch[vroot[1]]);bodyq=qvalues(sch[vbody[1]])
assert len(rootq)==len(bodyq)==41 and [t for t,_ in rootq]==[t for t,_ in bodyq]
assert all(abs(x)<1e-6 for _,*pos in xyz(sch[vbody[0]]) for x in pos)
# VA's root contains its pelvis transform; CD leaves the game root neutral
# and places the composed motion on the body (tag 31).
packed=bytearray(struct.pack('>BBHHH',16,2,0x5002,len(rootq),len(rootq)))
last=None
for (time,a),(_,b) in zip(rootq,bodyq):
    q=qmul(normal(a),normal(b))
    if last and sum(x*y for x,y in zip(last,q))<0:q=tuple(-v for v in q)
    last=q
    packed.extend(struct.pack('>3hbB',*(max(-32767,min(32767,round(-v*32767))) for v in q[:3]),
        max(-127,min(127,round(q[3]*127))),int(time/160)))
newclip=bytearray(idle);name='cosmic_ben_transform_01';key=m.crc(name)
assert key not in oldclips and len(newclip)==216+12*len(ids)
newclip[:64]=name.encode().ljust(64,b'\0')
struct.pack_into('>2f',newclip,64,0,6400)
# Omit VA-specific audio/flag command. CD's original transformation owns
# its own flash, sound, actor switch and engine state.
struct.pack_into('>I',newclip,80,0xffffffff)
channelrows=m.vaps_rows(p[9]);tagged=[(k,f,b,('old',i)) for i,(k,f,b) in enumerate(channelrows)]
added={};patches={}
def use_raw(label,data):
    if label not in added:
        idx=len(added);added[label]=idx
        tagged.append((m.crc(name+'_'+str(label)),0,data,('new',idx)))
    return ('new',added[label])
def inv(q):return (-q[0],-q[1],-q[2],q[3])
def skeleton(path):
    b=m.table(entries(path.read_bytes())[12])[0xbbe3c047]
    rows=[struct.unpack_from('>10fI',b,12+44*i) for i in range(struct.unpack_from('>H',b)[0])]
    tags=[r[-1]&0xffff for r in rows]
    return {tag:(None if r[-1]>>24==255 else tags[r[-1]>>24],normal((-r[0],-r[1],-r[2],r[3])),r[4:7]) for tag,r in zip(tags,rows)}
vs=skeleton(source.parent.parent/'l_anur/l_anur.xbx')
cs=skeleton(G.parent/'l_mili/l_mili.xbx')
def world(skel,local):
    out={}
    for tag,(parent,_,_) in skel.items():
        out[tag]=qmul(out[parent],local[tag]) if parent is not None else local[tag]
    return out
vb=world(vs,{t:r[1] for t,r in vs.items()})
cb=world(cs,{t:r[1] for t,r in cs.items()})
def sample_q(data,t):
    keys=qvalues(data)
    return normal(min(keys,key=lambda v:abs(v[0]-t))[1])
rotation_tracks={t:[] for t in ids}
for tick in range(0,6401,160):
    local={t:sample_q(sch[indexes(va,vaids.index(t))[1]],tick) for t in vs}
    posed=world(vs,local);desired={0:(0,0,0,1)}
    for t in cs:
        if t==0:continue
        desired[t]=qmul(qmul(posed[t],inv(vb[t])),cb[t])
    for t in ids:
        parent=cs[t][0];q=qmul(inv(desired[parent]),desired[t]) if parent is not None else desired[t]
        track=rotation_tracks[t]
        if track and sum(a*b for a,b in zip(q,track[-1]))<0:q=tuple(-x for x in q)
        track.append(q)
def encode_rot(track):
    b=bytearray(struct.pack('>BBHHH',16,2,0x5002,len(track),len(track)))
    for i,q in enumerate(track):
        b.extend(struct.pack('>3hbB',*(round(-x*32767) for x in q[:3]),round(q[3]*127),i))
    return bytes(b)
def bind_translation(t):
    return struct.pack('>BBHHH4f',1,4,0x5001,1,1,0,*cs[t][2])
for i,tag in enumerate(ids):
    if tag==0:
        chosen=[('old',j) for j in indexes(idle,i)]
    elif tag==31:
        chosen=[use_raw('body_translation',rootloc),use_raw('body_rotation_v2',encode_rot(rotation_tracks[tag])),
            use_raw('body_scale',sch[vbody[2]])]
    else:
        si=indexes(va,vaids.index(tag))
        chosen=[use_raw('pos_'+str(tag),bind_translation(tag)),use_raw('rot_'+str(tag),encode_rot(rotation_tracks[tag])),
            use_raw(si[2],sch[si[2]])]
    for axis,value in enumerate(chosen):patches[216+12*i+4*axis]=value
buckets=max(1,len(tagged)//4);tagged.sort(key=lambda row:(row[0]%buckets,row[0],row[3]))
positions={t:i for i,(_,_,_,t) in enumerate(tagged)}
p[9]=m.build_vaps(9,struct.unpack_from('>H',p[9],12)[0],[(k,f,b) for k,f,b,_ in tagged])
newrows=[]
for k,flags,c in m.vaps_rows(p[13]):
    c=bytearray(c)
    for at in [80]+list(range(216,len(c),4)):
        ix=struct.unpack_from('>I',c,at)[0]
        if ix!=0xffffffff:struct.pack_into('>I',c,at,positions[('old',ix)])
    newrows.append((k,flags,bytes(c)))
for at,val in patches.items():struct.pack_into('>I',newclip,at,positions[val] if val else 0xffffffff)
newrows.append((key,0,bytes(newclip)))
p[13]=m.build_vaps(13,struct.unpack_from('>H',p[13],12)[0],m.bucket_sorted(newrows))
new=m.package(raw,p)
check=entries(new);newch=channel_records(check[9]);clips=m.table(check[13])
assert len(clips)==len(oldclips)+1
assert all(streamed_clip(c,oldch)==streamed_clip(clips[k],newch) for k,c in oldclips.items())
assert animation_time_range(clips[key],newch)==(0,6400)
assert m.bone_ids(clips[key])==ids
out=H/'ben-transform-animation-retarget';out.mkdir(exist_ok=True)
(out/'a_plyr.xbx').write_bytes(new)
sha=lambda b:hashlib.sha256(b).hexdigest()
report={'clip':name,'key':hex(key),'seconds':6400/4800,'source':sha(source.read_bytes()),
    'before':sha(raw),'after':sha(new),'stock_clips_preserved':len(oldclips),'streams':[]}
# Existing streamed archives are already installed and contain all stock
# player clips. Append just this new clip; the next bridge launch can also
# regenerate it from a_plyr.xbx.
for level in G.parent.glob('l_*'):
    for path in level.glob('a_*_s.xbx'):
        before=(baseline/path.relative_to(G.parent)).read_bytes();old=entries(before,True)
        assert key not in old
        result,detail=merge_streams(before,[(name,new)])
        after=entries(result)
        assert set(after)-set(old)=={key} and all(after[k]==v for k,v in old.items())
        dest=out/'streams'/path.relative_to(G.parent);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(result)
        report['streams'].append({'path':str(path.relative_to(G.parent)),'before':sha(before),'after':sha(result)})
(out/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
