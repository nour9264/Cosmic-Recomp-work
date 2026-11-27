"""Taper the approved Spin helix and stage exclusive Suction Blast VFX."""
import hashlib,math,struct,sys,json
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
from wheel_icon_texture import encode_block
from extract_discord_level_images import tiled_offset

H = WORK;I=APP_ROOT/'installation';O=H/'suction-cone-vfx';O.mkdir(exist_ok=True);G=I/'game/global'
raw=(G/'g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(raw);globalraw=(G/'global.xbx').read_bytes();gp=entries(globalraw)
ddf=(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes();assert ddf==(G/'scripts/atk_ucb.ddf').read_bytes()
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(parts,s,rows):parts[s]=m.build_vaps(s,struct.unpack_from('>H',parts[s],12)[0],rows)
root=m.effect_root('cannonbolt');helix=m.crc('ucb_spin_helix_mesh');start=m.crc('ucb_suction_vfx_start');stop=m.crc('ucb_suction_vfx_stop');blast=m.crc('ucb_suction_release');pullstop=m.crc('ucb_suction_pull_stop');blaststop=m.crc('ucb_suction_blast_stop')
# A moderate cone, keeping clearance around the widest part of the ball.
# The first quarter increases to the existing radius; upper turns widen.
rows=[];bounds=None
for k,f,v in m.vaps_rows(p[4]):
    if k==helix:
        at,vb,ib=m.mesh_buffers(v,xbox=True);q=bytearray(v);ys=[struct.unpack_from('>f',vb,i+4)[0] for i in range(0,len(vb),20)];lo,hi=min(ys),max(ys)
        for i,y in enumerate(ys):
            off=at+i*20;x,z=struct.unpack_from('>f',q,off)[0],struct.unpack_from('>f',q,off+8)[0];t=(y-lo)/(hi-lo);radius=1.00+.47*t
            s=radius/math.hypot(x,z);struct.pack_into('>3f',q,off,x*s,y,z*s)
        v=bytes(q);assert m.mesh_buffers(v,xbox=True)[2]==ib;bounds=(lo,hi)
    rows.append((k,f,v))
assert bounds;bank(p,4,rows)

# A soft, translucent wind wisp using the decoded original POE air texture.
texture=m.crc('ucb_suction_air_wisp');oldtex=m.table(gp[0]);assert texture not in oldtex
source=(H/'original-vfx-decoded/Cyclone.rgba').read_bytes();assert len(source)==128*128*4
pixels=[]
for y in range(128):
    for x in range(128):
        u=2*x/127-1;v=2*y/127-1;r,g,b,a=source[(y*128+x)*4:(y*128+x)*4+4]
        env=max(0,1-u*u-v*v)**1.6;bands=.37+.63*(r+g+b)/765
        pixels.append((205,215,222,round(255*env*bands*min(1,a/170))))
head=bytearray(oldtex[0xb458a502][:128]);struct.pack_into('>I',head,44,texture);tile=bytearray(16384)
for y in range(32):
    for x in range(32):
        b=encode_block([pixels[(4*y+j)*128+4*x+i] for j in range(4) for i in range(4)]);off=tiled_offset(x,y,32,4);tile[off:off+16]=bytes(b[i^1] for i in range(16))
bank(gp,0,m.bucket_sorted(m.vaps_rows(gp[0])+[(texture,4,bytes(head)+tile)]));newglobal=m.package(globalraw,gp)
assert all(m.table(entries(newglobal)[0])[k]==v for k,v in oldtex.items())

# Start/stop attack events are exclusive to UCB; preserve normal Cannonbolt.
oldstart,oldstop=m.effect_events('cannonbolt',0x549d5666);d=bytearray(ddf);count=0
for at in range(4,len(d),224):
    if struct.unpack_from('>I',d,at+160)[0]==0x549d5666:
        assert struct.unpack_from('>2I',d,at+144)==(oldstart,oldstop);struct.pack_into('>2I',d,at+144,start,stop);count+=1
assert count==3
clipkey=0x754d9887;oldch=channel_records(p[9]);oldclips=m.table(p[13]);clip=oldclips[clipkey];begin,end=animation_time_range(clip,oldch);assert (begin,end)==(0,7200) and struct.unpack_from('>I',clip,80)[0]==0xffffffff
flags=m.flag_channel([[fs(1)[0],0,0,0,m.HEAD_START,0,0,0,0],[fs(end-160)[0],0,0,0,m.HEAD_STOP,0,0,0,0]])
cr=[]
for k,f,v in m.vaps_rows(p[13]):
    if k==clipkey:q=bytearray(v);struct.pack_into('>I',q,80,0x80000000);v=bytes(q)
    cr.append((k,f,v))
bank(p,13,cr);p[9],p[13]=m.merge_channels(p[9],p[13],[(m.crc('ucb_suction_vfx_flags'),0,flags)],extra_count=1);nc=channel_records(p[9]);assert all(streamed_clip(v,oldch)==streamed_clip(m.table(p[13])[k],nc) for k,v in oldclips.items() if k!=clipkey)
assert animation_time_range(m.table(p[13])[clipkey],nc)==(begin,end)

oldnodes=m.table(p[14]);rh,rb=m.node_parts(oldnodes[root]);rootgroups=[]
for b in rb:
    if b[0]!=14:continue
    for k,t,v in m.property_entries(b):
        if t==0x1000c:rootgroups.append([])
        rootgroups[-1].append((k,t,v))
template=next(g for g in rootgroups if g[0][0]==m.crc('ucb_spin_wind_0_particles'));timer=next(g for g in rootgroups if g[0][2]==[0x6ad0de1a]);assert len(timer)==5
def timed(name,delay,event):
    changes={0x8541406c:[start],0x865f80c0:fs(delay),0xd058515c:[event]}
    return [(m.crc(name) if t==0x1000c else k,t,changes.get(k,v)) for k,t,v in timer]
def emitter(index,outward):
    angle=index*math.tau/6;rad=.64 if outward else 2.10;y=.42 if outward else .62+.13*(index%2)
    x,z=rad*math.sin(angle),rad*math.cos(angle);yaw=angle if outward else angle+math.pi
    # +Z local forward is the proven debris launch direction; orient it
    # toward the player for suction and away for burst.
    props={0x462ce4f5:fs(x,y,z,0,math.sin(yaw/2),0,math.cos(yaw/2)),0x8541406c:[blast if outward else start],0xf7be9018:[blaststop if outward else pullstop],0x9d762289:[5 if outward else 4],0xe7965460:fs(32 if outward else 15),0x3de73088:fs(.32 if outward else .34),0x0f26fef6:fs(8.5 if outward else 4.5),0x297c98f1:fs(45),0x7cb5a078:fs(.13,.12,.13),0xd7943d68:fs(.25,.12,.25),0x7a76b57b:fs(0,.30 if outward else 0,0),0x118a27c7:fs(.39 if outward else .22),0x9c822a32:fs(.48 if outward else .27),0x27703ece:fs(1),0xaa78333b:fs(1),0x5a6ce323:[0x90ffffff if outward else 0x30ffffff],0xc365b299:[0xb0ffffff if outward else 0x78ffffff],0xb462820f:[0x50ffffff if outward else 0x80ffffff],0x2a0617ac:[0x00ffffff],0x82660d72:[texture],0x22944c2a:[m.crc('normal')]}
    return [(m.crc(f'ucb_suction_{"out" if outward else "in"}_{index}') if t==0x1000c else k,t,props.get(k,v)) for k,t,v in template]
# Pull until frame 33; release at frame 35 (1.167s), as the ball rises.
extra=[]
for i in range(6):extra.extend(emitter(i,False));extra.extend(emitter(i,True))
for name,delay,event in [('pull_end',1.10,pullstop),('release',35/30,blast),('burst_end',1.30,blaststop),('cleanup',1.47,stop)]:extra.extend(timed('ucb_suction_'+name,delay,event))
# Matching original shockwave data, but isolated event names. No damage or
# radius changes. Its original start remains unchanged relative to the attack.
donorkey=m.crc('cannonbolt_special_549d5666_shockwave');shockkey=m.crc('ucb_suction_shockwave');h,bl=m.node_parts(oldnodes[donorkey]);h[0]=shockkey
for i,b in enumerate(bl):
    if b[0]==14:bl[i]=m.node_properties([(k,t,[start if x==oldstart else stop if x==oldstop else x for x in v]) for k,t,v in m.property_entries(b)])
shock=m.node_record(h,bl);nodes=[]
for k,f,v in m.vaps_rows(p[14]):
    if k==root:
        h,bl=m.node_parts(v);out=[]
        for b in bl:
            if b[0]==14:b=m.node_properties(m.property_entries(b)+extra)
            elif b[0]==0x14:b=[0x14,b[1]+1,b[2]+1]+b[3:]+[shockkey]
            out.append(b)
        v=m.node_record(h,out)
    elif k==helix:
        h,bl=m.node_parts(v);top=bounds[1]+.15;h[19:26]=fs(math.hypot(1.55,top),-1.55,-.1,-1.55,1.55,top,1.55);v=m.node_record(h,bl)
    nodes.append((k,f,v))
bank(p,14,m.bucket_sorted(nodes+[(shockkey,0,shock)]));newcb=m.package(raw,p);check=entries(newcb);assert all(check[k]==v for k,v in entries(raw).items() if k not in (4,9,13,14));assert all(m.table(check[14])[k]==v for k,v in oldnodes.items() if k not in (root,helix))
def sha(v):return hashlib.sha256(v).hexdigest()
(O/'g_cb.xbx').write_bytes(newcb);(O/'global.xbx').write_bytes(newglobal);(O/'atk_ucb.ddf').write_bytes(d)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(newcb),old_global_sha=sha(globalraw),new_global_sha=sha(newglobal),old_ddf_sha=sha(ddf),new_ddf_sha=sha(d),cone_radii=[1.0,1.47],suction_duration=1.5,release_seconds=35/30,emitters=12,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
