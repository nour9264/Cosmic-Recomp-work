"""Restore native head-slot flags and put UCB emitters on the receiving node."""
import hashlib,json,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
H = WORK;I=APP_ROOT/'installation';O=H/'vfx-dispatch-fixed';O.mkdir(exist_ok=True)
raw=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();assert raw==(I/'game/global/g_cb.xbx').read_bytes();parts=entries(raw)
rows=m.vaps_rows(parts[9]);clips=m.vaps_rows(parts[13]);oldch=channel_records(parts[9]);new=[];targets={0xdb46cb2,0x2d806255};changed=[]
def fw(x):return struct.unpack('>I',struct.pack('>f',x))[0]
# Native clip word 20 indexes the animation flag stream. HEAD_START 0x1000
# is the slot-4 mask tested by sub_82148DF0, before it dispatches word36.
for k,f,v in clips:
    if k in targets:
        assert struct.unpack_from('>I',v,80)[0]==0xffffffff
        begin,end=animation_time_range(v,oldch);seq=[[fw(begin+1),0,0,0,m.HEAD_START,0,0,0,0],[fw(end),0,0,0,m.HEAD_STOP,0,0,0,0]]
        q=bytearray(v);struct.pack_into('>I',q,80,len(rows));rows.append((m.crc(f'ucb_{k:08x}_vfx_flags'),0,m.flag_channel(seq)));v=bytes(q);changed.append((hex(k),begin,end))
    new.append((k,f,v))
assert len(changed)==2
buckets=max(1,len(rows)//4);order=sorted(range(len(rows)),key=lambda i:(rows[i][0]%buckets,rows[i][0],i));remap={a:b for b,a in enumerate(order)};reindexed=[]
for k,f,v in new:
    c=bytearray(v)
    for at in [80]+list(range(216,len(c),4)):
        ix=struct.unpack_from('>I',c,at)[0]
        if ix!=0xffffffff:struct.pack_into('>I',c,at,remap[ix])
    reindexed.append((k,f,bytes(c)))
parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],[rows[i] for i in order]);parts[13]=m.build_vaps(13,struct.unpack_from('>H',parts[13],12)[0],reindexed)
# The attack event is nonrecursive; directly attach the six particle
# components to the weapon root, which receives it. Retain their local
# height offsets via the component's native 7-float transform property.
nodes=m.vaps_rows(parts[14]);nd=m.table(parts[14]);root=m.effect_root('cannonbolt');rh,rb=m.node_parts(nd[root]);keys={m.crc('ucb_'+move+'_'+label) for move,label in [('spin','wind_0'),('spin','wind_1'),('spin','wind_2'),('backspin','rock_0'),('backspin','rock_1'),('backspin','ground_dust')]}
rootprops=next(m.property_entries(b) for b in rb if b[0]==0xe);initial=len(rootprops)
for k in sorted(keys):
    h,b=m.node_parts(nd[k]);pp=next(m.property_entries(z) for z in b if z[0]==0xe)
    for prop,t,val in pp:
        if prop==0x462ce4f5:assert len(val)==7;val=list(h[7:14])
        rootprops.append((prop,t,val))
assert len(rootprops)>initial
out=[]
for k,f,v in nodes:
    if k in keys:continue
    if k==root:
        b=[]
        for z in rb:
            if z[0]==0x14:
                children=[i for i in z[3:] if i not in keys];z=[0x14,3+len(children),len(children)]+children
            elif z[0]==0xe:z=m.node_properties(rootprops)
            b.append(z)
        v=m.node_record(rh,b)
    out.append((k,f,v))
parts[14]=m.build_vaps(14,struct.unpack_from('>H',parts[14],12)[0],m.bucket_sorted(out));result=m.package(raw,parts);check=entries(result);nc=m.table(check[13]);ch=channel_records(check[9]);oc=m.table(entries(raw)[13])
for k,v in oc.items():
    if k not in targets:assert streamed_clip(v,oldch)==streamed_clip(nc[k],ch)
    else:
        assert animation_time_range(v,oldch)==animation_time_range(nc[k],ch)
        i=struct.unpack_from('>I',nc[k],80)[0];assert [f[4] for f in m.flag_frames(ch[i])]==[m.HEAD_START,m.HEAD_STOP]
assert all(m.table(check[14])[k]==v for k,v in nd.items() if k!=root and k not in keys)
(O/'g_cb.xbx').write_bytes(result);report=dict(old_sha=hashlib.sha256(raw).hexdigest(),flag_clips=changed,root_particle_groups=6,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
