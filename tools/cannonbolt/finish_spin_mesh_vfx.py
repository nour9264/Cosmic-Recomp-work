"""Widen the confirmed 3D wind, extend its quaternion track, and end on cue."""
import math,struct,sys,json,hashlib
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range

H = WORK;I=APP_ROOT/'installation';O=H/'spin-mesh-final-timing';O.mkdir(exist_ok=True)
G=I/'game/global';raw=(G/'g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(raw)
key=m.crc('ucb_spin_helix_mesh');root=m.effect_root('cannonbolt');start=m.crc('ucb_spin_vfx_start');stop=m.crc('ucb_spin_vfx_stop');clipkey=0xdb46cb2
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(s,rows):p[s]=m.build_vaps(s,struct.unpack_from('>H',p[s],12)[0],rows)
oldclips=m.table(p[13]);oldchannels=channel_records(p[9]);clip=oldclips[clipkey];begin,end=animation_time_range(clip,oldchannels);assert begin==0 and end==15520
frames=round(end/160)+1;stop_at=end-160;seconds=stop_at/4800
# Same validated native quaternion format as the previous 14-key Goop curve.
# Extend from its 32-frame span through every frame of the real attack.
oldcurve=next(v for k,f,v in m.vaps_rows(p[9]) if k==key);assert struct.unpack_from('>BBHHH',oldcurve)==(16,2,0x5002,14,14)
curve=bytearray(struct.pack('>BBHHH',16,2,0x5002,frames,frames))
for i in range(frames):
    angle=-math.tau*2.25*i/30 # rotations per second, about Y (vertical)
    curve.extend(struct.pack('>3hbB',0,round(32767*math.sin(angle/2)),0,round(127*math.cos(angle/2)),i))
curve=bytes(curve);assert len(curve)==8+frames*8
# Move the existing stop flag one sample before clip end, avoiding a skipped
# terminal event when the animation state immediately transitions.
flagidx=struct.unpack_from('>I',clip,80)[0];flags=m.flag_frames(oldchannels[flagidx]);assert len(flags)==2 and flags[-1][4]==m.HEAD_STOP
flags[-1][0]=fs(stop_at)[0];newflag=m.flag_channel(flags)
rows=m.vaps_rows(p[9]);assert rows[flagidx][2]==oldchannels[flagidx];rows[flagidx]=(rows[flagidx][0],rows[flagidx][1],newflag)
rows=[(k,f,curve if k==key else v) for k,f,v in rows];bank(9,rows);nc=channel_records(p[9])
assert all(streamed_clip(v,oldchannels)==streamed_clip(v,nc) for k,v in oldclips.items() if k!=clipkey)
assert animation_time_range(clip,nc)==(begin,end)

# Scale only radius (X/Z), preserving the proven height/shape and draw layout.
meshes=m.vaps_rows(p[4]);out=[]
for k,f,v in meshes:
    if k==key:
        at,vb,ib=m.mesh_buffers(v,xbox=True);q=bytearray(v)
        for i in range(0,len(vb),20):
            for axis in (0,8):
                off=at+i+axis;value=struct.unpack_from('>f',q,off)[0];struct.pack_into('>f',q,off,value*1.55)
        v=bytes(q);assert m.mesh_buffers(v,xbox=True)[2]==ib
    out.append((k,f,v))
bank(4,out)

# Native timer component sends a local event after its delay. Independent
# child and root timers ensure visibility/emitters stop even if the animation
# transition skips the terminal event.
cs=entries((G/'g_cs.xbx').read_bytes());h,b=m.node_parts(m.table(cs[14])[m.GATLING_TREE]);groups=[]
for block in b:
    if block[0]!=14:continue
    for k,t,v in m.property_entries(block):
        if t==0x1000c:groups.append([])
        groups[-1].append((k,t,v))
timer=next(g for g in groups if g[0][2]==[0x6ad0de1a]);assert len(timer)==5
def timed_stop(name):
    changes={0x8541406c:[start],0x865f80c0:fs(seconds),0xd058515c:[stop]}
    return [(m.crc(name) if t==0x1000c else k,t,changes.get(k,v)) for k,t,v in timer]
rocks={m.crc('ucb_backspin_rock_0_particles'):(8.0,.75),m.crc('ucb_backspin_rock_1_particles'):(8.8,.70)}
nodes=[];count=0
for k,f,v in m.vaps_rows(p[14]):
    if k in (root,key):
        h,bl=m.node_parts(v);updated=[]
        if k==key:h[19:26]=fs(2.7,-1.13,-.1,-1.13,1.13,2.2,1.13)
        for b in bl:
            if b[0]==0x16 and k==key:
                words=list(struct.unpack(f'>{len(curve)//4}I',curve));b=[0x16,len(words)+2]+words
            if b[0]==14:
                props=[];group=None
                for pk,pt,pv in m.property_entries(b):
                    if pt==0x1000c:group=pk
                    if k==root and group in rocks:
                        speed,life=rocks[group];pv={0x0f26fef6:fs(speed),0x3de73088:fs(life),0x7a76b57b:fs(0,-1.25,0)}.get(pk,pv)
                    if k==key and group==0xe16f3a56 and pk in (0x5e0393bd,0xf465b2b5):pv=fs(seconds+.08)
                    props.append((pk,pt,pv))
                props.extend(timed_stop('ucb_helix_root_timeout' if k==root else 'ucb_helix_child_timeout'));b=m.node_properties(props)
            updated.append(b)
        v=m.node_record(h,updated);count+=1
    nodes.append((k,f,v))
assert count==2;bank(14,nodes);result=m.package(raw,p);check=entries(result)
assert all(check[k]==v for k,v in entries(raw).items() if k not in (4,9,14));assert all(m.table(check[14])[k]==v for k,v in m.table(entries(raw)[14]).items() if k not in (root,key));assert all(m.table(check[4])[k]==v for k,v in m.table(entries(raw)[4]).items() if k!=key)
(O/'g_cb.xbx').write_bytes(result)
report=dict(old_cb_sha=hashlib.sha256(raw).hexdigest(),new_cb_sha=hashlib.sha256(result).hexdigest(),radius_multiplier=1.55,rotation_frames=frames,rotation_rps=2.25,stop_seconds=seconds,rock_nominal_ranges=[8*.75,8.8*.7],gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
