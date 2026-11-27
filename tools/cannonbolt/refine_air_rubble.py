"""Replace overexposed UCB additive sprites with black-masked reference VFX."""
import hashlib,json,math,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
from extract_discord_level_images import tiled_offset,untile
from wheel_icon_texture import encode_block,from565
H = WORK;I=APP_ROOT/'installation';O=H/'reference-vfx';O.mkdir(exist_ok=True)
raw=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();assert raw==(I/'game/global/g_cb.xbx').read_bytes();parts=entries(raw)
textures=m.table(parts[0]);trows=m.vaps_rows(parts[0]);flags={k:f for k,f,v in trows};template=textures[0xf1e0d86]
def fw(x):return struct.unpack('>I',struct.pack('>f',x))[0]
def tex(name,size,pixels,source=template):
    key=m.crc(name);assert key not in textures;header=bytearray(source[:128]);struct.pack_into('>HHBB',header,6,size,size,int(math.log2(size)),int(math.log2(size)));struct.pack_into('>I',header,44,key)
    data=bytearray(16384);d=size//4
    for by in range(d):
        for bx in range(d):
            block=encode_block([(*pixels[(by*4+y)*size+bx*4+x],255) for y in range(4) for x in range(4)]);offset=tiled_offset(bx,by,d,4);assert offset+16<=len(data)
            data[offset:offset+16]=bytes(block[j^1] for j in range(16))
    trows.append((key,flags[0xf1e0d86],bytes(header)+data));return key
def decode_source(k):
    r=textures[k];w,h=struct.unpack_from('>HH',r,6);assert w==h and struct.unpack_from('>H',r,4)[0]==0x102
    tiled=untile(r[128:],w//4,h//4,4);lin=bytes(tiled[i^1] for i in range(len(tiled)));out=[None]*(w*h)
    for by in range(h//4):
        for bx in range(w//4):
            block=lin[(by*(w//4)+bx)*16:][:16];a,b=block[:2];ap=[a,b]+([((7-i)*a+i*b)//7 for i in range(1,7)] if a>b else [((5-i)*a+i*b)//5 for i in range(1,5)]+[0,255]);ai=int.from_bytes(block[2:8],'little');c,d,ci=struct.unpack('<HHI',block[8:]);c,d=from565(c),from565(d);cp=[c,d,tuple((2*x+y)//3 for x,y in zip(c,d)),tuple((x+2*y)//3 for x,y in zip(c,d))]
            for n in range(16):out[(by*4+n//4)*w+bx*4+n%4]=(*cp[(ci>>(2*n))&3],ap[(ai>>(3*n))&7])
    return w,out
def masked(k,name,dim):
    w,p=decode_source(k);out=[]
    for y in range(w):
        for x in range(w):
            r,g,b,a=p[y*w+x];edge=min(1,x/2,y/2,(w-1-x)/2,(w-1-y)/2);a=a/255*edge
            out.append(tuple(round(v*a*dim) for v in (r,g,b)))
    assert all(v== (0,0,0) for v in out[:w]);return tex(name,w,out,textures[k])
rock0=masked(0x4a64387,'ucb_rock_masked_a',.68);rock1=masked(0x43063957,'ucb_rock_masked_b',.68);dust=masked(0xf1e0d86,'ucb_dust_masked',.40)
# One camera-facing tapered wind column: tapered sides, alternating soft
# horizontal helical ribbons and a dark transparent center. Black outside
# footprint is mandatory because the particle material blends additively.
wind=[];size=128
for y in range(size):
    yy=y/(size-1);v=1-yy;radius=.17+.72*v**.75
    for x in range(size):
        u=(x/(size-1)-.5)*2;side=abs(u)/radius
        envelope=max(0,min(1,(1-side)*6))*max(0,min(1,v*13,(1-v)*11))
        phase=2*math.pi*(v*5.5 + .30*u/radius + .13*math.sin(v*13));ribbon=(.5+.5*math.cos(phase))**5
        rims=math.exp(-((side-.8)/.15)**2);intensity=envelope*(.08+.29*ribbon+.11*rims)
        val=round(255*intensity);wind.append((round(val*.84),round(val*.92),val))
assert max(max(p) for p in wind)<130 and all(p==(0,0,0) for p in wind[:size]);funnel=tex('ucb_air_funnel_masked',size,wind)
parts[0]=m.build_vaps(0,struct.unpack_from('>H',parts[0],12)[0],m.bucket_sorted(trows))
nodes=m.vaps_rows(parts[14]);root=m.effect_root('cannonbolt');oldnodes=m.table(parts[14]);groups={m.crc('ucb_spin_wind_0_particles'):'wind_base',m.crc('ucb_spin_wind_1_particles'):'funnel',m.crc('ucb_spin_wind_2_particles'):'wind_top',m.crc('ucb_backspin_rock_0_particles'):'rock0',m.crc('ucb_backspin_rock_1_particles'):'rock1',m.crc('ucb_backspin_ground_dust_particles'):'dust'}
def fs(*a):return [fw(v) for v in a]
common={0x5a6ce323:[0xffffffff],0xc365b299:[0xffffffff],0xb462820f:[0xffffffff],0x2a0617ac:[0x00ffffff]}
def shape(texid,n,rate,life,sz,spin,height,spread,velocity,accel,speed=0):
    return {**common,0x82660d72:[texid],0x9d762289:[n],0xe7965460:fs(rate),0x3de73088:fs(life),0xf26fef6:fs(speed),0x297c98f1:fs(spin),0x7cb5a078:fs(*spread),0xd7943d68:fs(*velocity),0x7a76b57b:fs(*accel),0x118a27c7:fs(sz),0x9c822a32:fs(sz),0x462ce4f5:fs(0,height,0,0,0,0,1)}
edits={
 'funnel':shape(funnel,2,3.5,.50,1.65,0,1.10,(.01,.01,.01),(0,0,0),(0,0,0)),
 'wind_base':shape(dust,6,12,.42,.23,100,.10,(.42,.03,.42),(.3,.06,.3),(0,.1,0)),
 'wind_top':shape(dust,3,5,.40,.20,-130,1.55,(.65,.1,.65),(.2,.1,.2),(0,.15,0)),
 'rock0':shape(rock0,12,15,.55,.12,-160,.12,(.38,.04,.38),(1.3,.7,1.3),(0,-7,0),3.3),
 'rock1':shape(rock1,10,13,.50,.16,170,.12,(.30,.04,.30),(1.5,.7,1.5),(0,-7,0),3.7),
 'dust':shape(dust,8,15,.42,.32,0,.08,(.38,.04,.38),(.4,.1,.4),(0,.15,0),.5),
}
out=[];changed=[]
for k,f,v in nodes:
    if k==root:
        h,blocks=m.node_parts(v);new=[]
        for b in blocks:
            if b[0]==0xe:
                p=[];mode=None
                for prop,t,vals in m.property_entries(b):
                    if t==0x1000c:
                        mode=groups.get(prop)
                        if mode:changed.append(mode)
                    if mode and prop in edits[mode] and t!=0x1000c:vals=edits[mode][prop]
                    p.append((prop,t,list(vals)))
                b=m.node_properties(p)
            new.append(b)
        v=m.node_record(h,new)
    out.append((k,f,v))
assert sorted(changed)==sorted(edits);parts[14]=m.build_vaps(14,struct.unpack_from('>H',parts[14],12)[0],out)
result=m.package(raw,parts);check=entries(result);assert all(check[k]==v for k,v in entries(raw).items() if k not in(0,14));assert all(m.table(check[0])[k]==v for k,v in textures.items());assert all(m.table(check[14])[k]==v for k,v in oldnodes.items() if k!=root)
(O/'g_cb.xbx').write_bytes(result);report=dict(old_sha=hashlib.sha256(raw).hexdigest(),sprites=[hex(k) for k in(rock0,rock1,dust,funnel)],particle_groups=changed,other_assets_unchanged=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
