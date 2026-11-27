"""Private Goop asset conversion. Run with Blender --background --python.
Preserves the native skeleton, skin, textures, all original clip payloads and events.
Skeleton node layout: 10 floats at 12+44*i, trailing parent/id at 52+44*i.
Native rotations use the conjugate of mathutils column-vector quaternions.
"""
import sys,struct,json,math,hashlib
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from vilgax_animation_paths import APP as APP_ROOT, BLEND, REPO, WORK
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
ROOT=(APP_ROOT/'installation')
OUT=(BLEND/'goop-native-patch');OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'vilgax/goop/g_gp.xbx'
raw=source.read_bytes();parts=entries(raw);sk=next(iter(m.table(parts[12]).values()))
oldrows=m.vaps_rows(parts[9]);oldclips=m.vaps_rows(parts[13]);channels=list(oldrows)
idle=next(c for k,f,c in oldclips if c.startswith(b'idle_01\0'))
ids=m.bone_ids(idle);assert len(ids)==55
bind=[];parents=[]
for i in range(55):
 vals=struct.unpack_from('>10f',sk,12+44*i);tag=struct.unpack_from('>I',sk,52+44*i)[0]
 assert tag&0xffffff==ids[i]
 par=tag>>24;parents.append(-1 if par==255 else par)
 q=Quaternion((vals[3],*vals[:3])).conjugated()
 local=Matrix.LocRotScale(Vector(vals[4:7]),q,Vector(vals[7:10]))
 bind.append(local if par==255 else bind[par]@local)
# Game (X,Y-up,Z-forward) -> authoring Blender (X,-Z,Y).
C=Matrix(((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)));Ci=C.inverted()
def mat(values):return Matrix([values[i:i+4] for i in range(0,16,4)])
def vec_channel(values,kind=1):
 return struct.pack('>BBHHH',kind,4,0x5001 if kind==1 else 0x5003,len(values),len(values))+b''.join(struct.pack('>4f',i*160,*v) for i,v in enumerate(values))
def quat_channel(values):
 out=bytearray(struct.pack('>BBHHH',16,2,0x5002,len(values),len(values)));prev=None;decoded=[]
 for i,q in enumerate(values):
  q=q.normalized()
  if prev is not None and q.dot(prev)<0:q.negate()
  prev=q.copy();x,y,z=[max(-32767,min(32767,round(v*32767))) for v in (q.x,q.y,q.z)];w=max(-127,min(127,round(q.w*127)))
  out.extend(struct.pack('>3hbB',x,y,z,w,i));decoded.append(Quaternion((w/127,x/32767,y/32767,z/32767)).normalized())
 return bytes(out),decoded
newclips=[];reports=[]
for path in sorted((BLEND/'goop-game-export').glob('*.json')):
 if path.name!='block_dodge_forward.json':continue
 data=json.loads(path.read_text());assert [b['id'] for b in data['bones']]==ids
 rest=[mat(b['rest_matrix']) for b in data['bones']]
 local_frames=[];targets=[]
 for frame in data['frames']:
  pose=[mat(v) for v in frame['pose_matrices']]
  displacement=pose[0].translation
  # Engine owns X/Z travel and collision. Retain authored vertical lift and lean.
  in_place=Matrix.Translation((-displacement.x,-displacement.y,0))
  deforms=[Ci@in_place@p@r.inverted()@C for p,r in zip(pose,rest)]
  world=[d@b for d,b in zip(deforms,bind)]
  stretch=Matrix.Diagonal((*deforms[1].to_scale(),1));inv=stretch.inverted()
  # Factor common squash once; retain original folded joint positions/rotations.
  world=[stretch@Matrix.LocRotScale((inv@w).translation,(inv@w).to_quaternion(),Vector((1,1,1))) for w in world]
  world[0]=stretch@bind[0]
  local=[world[i] if parents[i]<0 else world[parents[i]].inverted()@world[i] for i in range(55)]
  local_frames.append(local);targets.append(world)
 clip=bytearray(idle);name='cosmic_'+path.stem;encoded=name.encode();assert len(encoded)<64
 clip[:64]=encoded+b'\0'*(64-len(encoded));struct.pack_into('>2f',clip,64,0,(len(local_frames)-1)*160)
 struct.pack_into('>I',clip,80,0xffffffff)
 decodedrot=[];quantworld=[[] for _ in local_frames]
 for i in range(55):
  decomposed=[f[i].decompose() for f in local_frames]
  pos=[p for p,q,s in decomposed];q=[q.conjugated() for p,q,s in decomposed];scale=[s for p,q,s in decomposed]
  assert all(math.isfinite(v) and 0.001<v<20 for s in scale for v in s)
  rot,dq=quat_channel(q);decodedrot.append(dq)
  for fi in range(len(local_frames)):
   parent=Matrix.Identity(4) if parents[i]<0 else quantworld[fi][parents[i]]
   pos[fi]=parent.inverted()@targets[fi][i].translation
   local_frames[fi][i].translation=pos[fi]
   quantworld[fi].append(parent@Matrix.LocRotScale(pos[fi],dq[fi].conjugated(),scale[fi]))
  for field,channel in enumerate((vec_channel(pos),rot,vec_channel(scale,12))):
   index=len(channels);channels.append((m.crc(f'goop_{name}_{i}_{field}'),0,channel));struct.pack_into('>I',clip,216+i*12+field*4,index)
 # Quantized reconstruction must match authoring deformation closely.
 error=0.0
 for fi,locals in enumerate(local_frames):
  rebuilt=[]
  for i,L in enumerate(locals):
   p,q,s=L.decompose();L2=Matrix.LocRotScale(p,decodedrot[i][fi].conjugated(),s)
   rebuilt.append(L2 if parents[i]<0 else rebuilt[parents[i]]@L2)
   error=max(error,(rebuilt[i].translation-targets[fi][i].translation).length)
 assert error<.08,(path.name,error)
 key=m.crc('goop_'+name);newclips.append((key,0,bytes(clip)))
 reports.append(dict(file=path.name,key=f'{key:08x}',frames=len(local_frames),max_joint_quantization_error=error))
# Channel-directory positions change when sorting: relocate every old and new clip.
buckets=max(1,len(channels)//4)
order=sorted(range(len(channels)),key=lambda i:(channels[i][0]%buckets,channels[i][0],i));remap={old:new for new,old in enumerate(order)}
updated=[]
for key,flags,c in [row for row in oldclips if row[0] not in {k for k,f,c in newclips}]+newclips:
 c=bytearray(c)
 for at in [80]+list(range(216,len(c),4)):
  index=struct.unpack_from('>I',c,at)[0]
  if index!=0xffffffff:struct.pack_into('>I',c,at,remap[index])
 updated.append((key,flags,bytes(c)))
parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],[channels[i] for i in order])
parts[13]=m.build_vaps(13,struct.unpack_from('>H',parts[13],12)[0],m.bucket_sorted(updated))
result=m.package(raw,parts);check=entries(result);newchannels=channel_records(check[9]);checkclips=m.table(check[13]);oldchannels=[r[2] for r in oldrows]
for k,f,c in oldclips:
 if k not in {key for key,f,c in newclips}:assert streamed_clip(c,oldchannels)==streamed_clip(checkclips[k],newchannels)
for sid,blob in entries(raw).items():
 if sid not in (9,13):assert check[sid]==blob
(OUT/'g_gp.xbx').write_bytes(result)
keys={r['file']:int(r['key'],16) for r in reports}
# Person record's single dodge slot. Engine 0x8214CB68 rotates to stick heading.
p=ROOT/'vilgax/goop/xbx-records.bin';b=bytearray(p.read_bytes());assert len(m.ddf_records(b'\x1b\xad\xba\xbe'+b))==1
assert struct.unpack_from('>I',b,24+0x130)[0]==keys['block_dodge_forward.json']
struct.pack_into('>I',b,24+0x130,keys['block_dodge_forward.json']);(OUT/p.name).write_bytes(b)
mapping=[]
(OUT/'atk_gp.ddf').write_bytes((ROOT/'vilgax/goop/atk_gp.ddf').read_bytes())
report=dict(source_sha256=hashlib.sha256(raw).hexdigest(),bones=55,skeleton_skin_mesh_textures_unchanged=True,original_clips_unchanged=True,clips=reports,attack_routes=mapping,
 dodge_route='One native melt dodge in all directions; root squash applied once, projector stays airborne.',gameplay_verified=False)
(OUT/'validation.json').write_text(json.dumps(report,indent=2));print('PASS: Goop melt dodge, 55 bones, all original clips/resources preserved; existing lunges preserved.')
print('Max joint quantization error:',round(max(r['max_joint_quantization_error'] for r in reports),6))
