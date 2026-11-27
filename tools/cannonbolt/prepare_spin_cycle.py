"""Animation-only prototype: POE ball rotation on inherited native CB ball pose."""
import hashlib
import json
import math
import struct
from pathlib import Path
from mathutils import Quaternion, Vector
import sys
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, streamed_clip, animation_time_range

HERE = WORK
INSTALL = APP_ROOT/'installation'
OUT = HERE / 'spin-cycle-candidate'
OUT.mkdir(exist_ok=True)
source = (HERE / '99_95.stream1.bin').read_bytes()
at = 0xdf020
assert source[at:at+10] == b'atk_hhh_b\0'
fields = struct.unpack_from('<12I', source, at+0x50)
n = fields[1]
assert n == 83 and fields[7]-fields[6] == 4*n
times = struct.unpack_from('<83f', source, fields[2])
assert max(abs(t-i/(n-1)) for i,t in enumerate(times)) < 0.0001
qs = []
for (word,) in struct.iter_unpack('<I', source[fields[6]:fields[7]]):
    omitted = word & 3
    v = [(((word >> shift)&1023)-512)/(512*math.sqrt(2)) for shift in (2,12,22)]
    v.insert(omitted, math.sqrt(max(0,1-sum(x*x for x in v))))
    assert abs(v[omitted])+0.003 >= max(map(abs,v))
    q = Quaternion((v[3],*v[:3])).normalized()
    if qs and q.dot(qs[-1]) < 0: q.negate()
    qs.append(q)
assert abs(qs[0].dot(qs[-1])) > .999

asset = Path('vilgax/cannonbolt/g_cb.xbx')
attack = Path('vilgax/ultimatecannonbolt/atk_ucb.ddf')
raw = (INSTALL/asset).read_bytes()
ddf = (INSTALL/attack).read_bytes()
assert raw == (INSTALL/'game/global/g_cb.xbx').read_bytes()
assert ddf == (INSTALL/'game/global/scripts/atk_ucb.ddf').read_bytes()
parts = entries(raw)
oldrows = m.vaps_rows(parts[9]); oldclips = m.vaps_rows(parts[13]); channels = list(oldrows)
donor = m.table(parts[13])[0xef7b4b93]
assert donor.startswith(b'burnout_run_01\0') and len(m.bone_ids(donor)) == 45
assert m.bone_ids(donor)[44] == 0xc1
sk = next(iter(m.table(parts[12]).values()))
assert struct.unpack_from('>I',sk,52+44*44)[0] == 0xc1
oldchannels = channel_records(parts[9])
idx = struct.unpack_from('>135I',donor,216)
def first_q(channel):
    assert channel[:4] == b'\x10\x02\x50\x02'
    x,y,z,w,_ = struct.unpack_from('>3hbB',channel,8)
    return Quaternion((w/127,x/32767,y/32767,z/32767)).normalized().conjugated()

root = first_q(oldchannels[idx[1]])
base = first_q(oldchannels[idx[44*3+1]])
assert max(abs(x) for x in struct.unpack_from('>3f',oldchannels[idx[5]],12)) < .001
assert min(struct.unpack_from('>3f',oldchannels[idx[44*3+2]],12)) > .9
basis = Quaternion(Vector((1,0,0)), -math.pi/2)
spin = []
for q in qs:
    delta = basis @ (q @ qs[0].inverted()) @ basis.inverted()
    pose = (root.inverted() @ delta @ root @ base).conjugated().normalized()
    if spin and pose.dot(spin[-1]) < 0: pose.negate()
    spin.append(pose)

name = b'cosmic_poe_ucb_spin_cycle'
key = m.crc(name.decode())
assert key not in m.table(parts[13])
clip = bytearray(donor)
clip[:64] = name.ljust(64,b'\0')
struct.pack_into('>2f',clip,64,0,(n-1)*160)
struct.pack_into('>I',clip,80,0xffffffff)
quant_error = 0.0
for i,index in enumerate(idx):
    original = oldchannels[index]
    kind,stride,tag,_,_ = struct.unpack_from('>BBHHH',original)
    if i == 44*3+1:
        payload = bytearray(struct.pack('>BBHHH',16,2,0x5002,n,n))
        for frame,q in enumerate(spin):
            xyz = [round(v*32767) for v in (q.x,q.y,q.z)]
            w = round(q.w*127)
            payload.extend(struct.pack('>3hbB',*xyz,w,frame))
            quantized = Quaternion((w/127,*(v/32767 for v in xyz))).normalized()
            quant_error = max(quant_error, 2*math.acos(min(1,abs(q.dot(quantized)))))
    else:
        # Hold the donor's native ball posture; don't add movement or gameplay events.
        payload = bytearray(struct.pack('>BBHHH',kind,stride,tag,2,2))
        first = bytearray(original[8:8+stride*4]); last = bytearray(first)
        if kind == 16:
            first[-1] = 0; last[-1] = n-1
        else:
            assert kind in (1,12)
            struct.pack_into('>f',first,0,0); struct.pack_into('>f',last,0,(n-1)*160)
        payload.extend(first+last)
    struct.pack_into('>I',clip,216+4*i,len(channels))
    channels.append((m.crc(f'{name.decode()}_{i}'),0,bytes(payload)))
assert quant_error < .03
buckets = max(1,len(channels)//4)
order = sorted(range(len(channels)),key=lambda i:(channels[i][0]%buckets,channels[i][0],i))
remap = {old:new for new,old in enumerate(order)}
updated = []
for k,flags,c in oldclips+[(key,0,bytes(clip))]:
    c = bytearray(c)
    for pos in [80]+list(range(216,len(c),4)):
        index = struct.unpack_from('>I',c,pos)[0]
        if index != 0xffffffff: struct.pack_into('>I',c,pos,remap[index])
    updated.append((k,flags,bytes(c)))
parts[9] = m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],[channels[i] for i in order])
parts[13] = m.build_vaps(13,struct.unpack_from('>H',parts[13],12)[0],m.bucket_sorted(updated))
result = m.package(raw,parts)
check = entries(result); newchannels = channel_records(check[9]); newclips = m.table(check[13])
for k,f,c in oldclips: assert streamed_clip(c,oldchannels) == streamed_clip(newclips[k],newchannels)
for sid,blob in entries(raw).items():
    if sid not in (9,13): assert check[sid] == blob
assert animation_time_range(newclips[key],newchannels) == (0,(n-1)*160)
assert len(ddf) == 6500
newddf = bytearray(ddf); routes = []
for pos in range(4,len(ddf),224):
    if struct.unpack_from('>I',ddf,pos+32)[0] == 0xef7b4b93:
        struct.pack_into('>I',newddf,pos+32,key); routes.append(pos+32)
assert len(routes) == 3
assert all(a==b or any(p<=i<p+4 for p in routes) for i,(a,b) in enumerate(zip(ddf,newddf)))
(OUT/asset.name).write_bytes(result)
(OUT/attack.name).write_bytes(newddf)
report = dict(key=hex(key), source='atk_hhh_b',frames=n,duration_seconds=(n-1)/30,
    original_clips_preserved=len(oldclips), max_rotation_error_rad=quant_error,
    routes=routes, source_rotation_only=True, other_bone_tracks_transferred=False,
    gameplay_verified=False, original_asset_sha256=hashlib.sha256(raw).hexdigest(),
    original_attack_sha256=hashlib.sha256(ddf).hexdigest())
(OUT/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
