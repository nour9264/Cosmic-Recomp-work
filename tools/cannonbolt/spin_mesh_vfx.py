"""3D helical wind ribbons using native effect mesh/curve and forwarding events."""
import math,struct,sys,hashlib,json
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
from wheel_icon_texture import encode_block
from extract_discord_level_images import tiled_offset

H = WORK;I=APP_ROOT/'installation';O=H/'spin-mesh-vfx';O.mkdir(exist_ok=True)
G=I/'game/global';cb=(G/'g_cb.xbx').read_bytes();assert cb==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(cb)
globalraw=(G/'global.xbx').read_bytes();gp=entries(globalraw);cs=entries((G/'g_cs.xbx').read_bytes());goop=entries((G/'g_gp.xbx').read_bytes())
key=m.crc('ucb_spin_helix_mesh');texkey=m.crc('ucb_spin_helix_material');root=m.effect_root('cannonbolt');start=m.crc('ucb_spin_vfx_start');stop=m.crc('ucb_spin_vfx_stop')
def fs(*vs): return [struct.unpack('>I',struct.pack('>f',v))[0] for v in vs]
def bank(parts,section,rows):parts[section]=m.build_vaps(section,struct.unpack_from('>H',parts[section],12)[0],m.bucket_sorted(rows))

# Two overlapping spiral ribbons. A mesh, not a camera-facing plane.
# Radius follows the observed ball diameter (~1.1 m); upper rim slightly wider.
vertices=[];indices=[];colors=[]
for strand in range(2):
    for turn in range(3):
        base=len(vertices)
        for step in range(41):
            t=step/40;progress=(turn+t)/3;phi=math.tau*(turn+t)+strand*math.pi
            y=.14+1.87*progress;radius=.53+.13*progress
            for side in (0,1,2,3,4):
                v=side/4;dy=(v-.5)*.27
                vertices.append((radius*math.cos(phi),y+dy,radius*math.sin(phi),t,v))
                # Soft edges and end fade; alpha is per vertex as well as texture.
                a=round(150*min(1,max(0,progress*9),max(0,(1-progress)*9))*math.sin(math.pi*v)**.65)
                colors.append(bytes((a,176,176,176)))
        for i in range(40):
            for j in range(4):
                a=base+i*5+j;b=a+5;c=a+1;d=b+1
                indices.extend((a,b,c,b,d,c,c,b,a,c,d,b))
assert len(vertices)<65536 and len(indices)<65536
vb=b''.join(struct.pack('>5f',*v) for v in vertices);ib=struct.pack(f'>{len(indices)}H',*indices)
donor=0xa64f48dc;r=m.table(cs[4])[donor];at,_,_=m.mesh_buffers(r,xbox=True);assert at==416 and struct.unpack_from('>I',r)[0]&15==9
head=bytearray(r[:at]);meta=struct.unpack_from('<I',head,28)[0];ia=(at+len(vb)+31)&~31
struct.pack_into('>I',head,4,len(vertices));struct.pack_into('>I',head,16,len(indices));struct.pack_into('<I',head,20,meta+ia-376)
struct.pack_into('>I',head,384,(len(indices)<<16)|(struct.unpack_from('>I',head,384)[0]&0xffff));struct.pack_into('>I',head,404,texkey)
mesh=bytes(head)+vb+bytes(ia-at-len(vb))+ib;assert m.mesh_buffers(mesh,xbox=True)==(at,vb,ib)
colhead=bytearray(m.table(cs[3])[donor][:32]);struct.pack_into('>I',colhead,8,key);struct.pack_into('<I',colhead,20,meta-344);col=bytes(colhead)+b''.join(colors)
assert len(col)==32+4*len(vertices)
bank(p,4,m.vaps_rows(p[4])+[(key,at//32,mesh)]);bank(p,3,m.vaps_rows(p[3])+[(key,1,col)])

# Actual POE Cyclone material, alpha retained rather than rectangular masks.
D=H/'original-vfx-decoded';source=(D/'Cyclone.rgba').read_bytes();assert len(source)==128*128*4
texhead=bytearray(m.table(gp[0])[0xb458a502][:128]);struct.pack_into('>I',texhead,44,texkey)
pixels=[]
for y in range(128):
    for x in range(128):
        rr,gg,bb,aa=source[4*(y*128+x):4*(y*128+x)+4];light=(rr+gg+bb)/3;edge=math.sin(math.pi*y/127)**.6
        pixels.append((180,188,192,round(min(255,(.25+.75*light/255)*aa*edge))))
tile=bytearray(16384)
for y in range(32):
    for x in range(32):
        block=encode_block([pixels[(4*y+j)*128+4*x+i] for j in range(4) for i in range(4)]);off=tiled_offset(x,y,32,4);tile[off:off+16]=bytes(block[i^1] for i in range(16))
tex=bytes(texhead)+tile;bank(p,0,m.vaps_rows(p[0])+[(texkey,4,tex)])

# Goop's native rotating effect node uses an inline quaternion curve and a
# section-9 copy by node key. Retain its known renderer/curve component layout.
donor_node=0xd313e756;dh,db=m.node_parts(m.table(goop[14])[donor_node]);curve=next(b for b in db if b[0]==0x16);cr=next((f,v) for k,f,v in m.vaps_rows(goop[9]) if k==donor_node);assert struct.pack('>30I',*curve[2:])==cr[1]
dh[0]=key;dh[7:14]=fs(0,0,0,0,0,0,1);dh[19:26]=fs(2.4,-.75,-.1,-.75,.75,2.2,.75)
groups=[]
for b in db:
    if b[0]!=14:continue
    for k,t,v in m.property_entries(b):
        if t==0x1000c:groups.append([])
        groups[-1].append((k,t,v))
props=[]
for group in groups:
    for k,t,v in group:
        v=list(v)
        if k in (0x750f694a,0x8541406c) and v[0]!=0:v=[start]
        if k in (0xa3911ca7,0xf7be9018) and v[0]!=0:v=[stop]
        props.append((k,t,v))
child=m.node_record(dh,[curve,[0,4,key,key],[8,3,root],m.node_properties(props)])
oldchannels=channel_records(p[9]);oldclips=m.table(p[13]);p[9],p[13]=m.merge_channels(p[9],p[13],[(key,*cr)]);newchannels=channel_records(p[9]);assert all(streamed_clip(v,oldchannels)==streamed_clip(m.table(p[13])[k],newchannels) for k,v in oldclips.items())

# Remove the main billboard and forward the exclusive Spin start/stop to the
# child. Leave other attacks, dust, and shockwave nodes exactly as they were.
nodes=m.vaps_rows(p[14]);rewritten=[];seen=set();rock_edits={m.crc('ucb_backspin_rock_0_particles'):(6.6,.66,.16),m.crc('ucb_backspin_rock_1_particles'):(7.2,.60,.21)}
for k,f,v in nodes:
    if k==root:
        h,b=m.node_parts(v);out=[]
        for block in b:
            if block[0]==0x14:out.append([0x14,block[1]+1,block[2]+1]+block[3:]+[key]);continue
            if block[0]!=14:out.append(block);continue
            props=[];group=None
            for pk,pt,pv in m.property_entries(block):
                if pt==0x1000c:group=pk
                if group==m.crc('ucb_spin_wind_1_particles'):continue
                if group in rock_edits:
                    speed,life,size=rock_edits[group];changes={0x0f26fef6:fs(speed),0x3de73088:fs(life),0x118a27c7:fs(size),0x9c822a32:fs(size),0x7a76b57b:fs(0,-1.6,0),0xd7943d68:fs(.17,.55,.18),0x7cb5a078:fs(.09,.02,.08)}
                    if pk in changes:pv=changes[pk]
                    seen.add(group)
                props.append((pk,pt,pv))
            for i,event in enumerate((start,stop)):
                props.extend([(m.crc(f'ucb_helix_forward_{i}'),0x1000c,[m.EVENT_GROUP]),(0x939b68a0,0x201000c,[event]),(0x8541406c,0x201000c,[event]),(0x557c4b4d,0x201000c,[key])])
            out.append(m.node_properties(props))
        v=m.node_record(h,out)
    rewritten.append((k,f,v))
assert seen==set(rock_edits);bank(p,14,rewritten+[(key,0,child)])
newcb=m.package(cb,p);check=entries(newcb);assert all(check[k]==v for k,v in entries(cb).items() if k not in (0,3,4,9,13,14));assert all(m.table(check[14])[k]==v for k,v in m.table(entries(cb)[14]).items() if k!=root)
for section in (0,3,4):assert all(m.table(check[section])[k]==v for k,v in m.table(entries(cb)[section]).items())
(O/'g_cb.xbx').write_bytes(newcb)
# Debris: render two irregular, chipped low-poly stones into the existing
# alpha sprites. Perspective, depth testing and per-face light produce
# recognizable rock facets instead of flat hexagonal silhouettes.
import random
import numpy as np
Vector=lambda v:np.array(v,dtype=float)
S=128;rock=(D/'Rock9.rgba').read_bytes();assert len(rock)==S*S*4
def stone_sprite(seed):
    rng=random.Random(seed);verts=[]
    # Uneven upper/lower rings and tips; triangulate noncoplanar faces.
    verts.append(Vector((-.11,.78,.05)))
    for level in (1,-1):
        for i in range(7):
            angle=math.tau*i/7+(0.22 if level<0 else 0);rad=rng.uniform(.57,.84)
            verts.append(Vector((rad*math.cos(angle),level*rng.uniform(.22,.43),rad*math.sin(angle))))
    verts.append(Vector((.12,-.74,-.08)))
    faces=[]
    for i in range(7):
        a=1+i;b=1+(i+1)%7;c=8+i;d=8+(i+1)%7;faces.extend(((0,b,a),(a,b,c),(b,d,c),(15,c,d)))
    # Project from a fixed elevated view; both variants have different camera
    # angles and topology. Keep the baked source rock texel variation subdued.
    ax,ay,az=.30,seed*.16,.19 if seed%2 else -.21
    rx=np.array([[1,0,0],[0,math.cos(ax),-math.sin(ax)],[0,math.sin(ax),math.cos(ax)]])
    ry=np.array([[math.cos(ay),0,math.sin(ay)],[0,1,0],[-math.sin(ay),0,math.cos(ay)]])
    rz=np.array([[math.cos(az),-math.sin(az),0],[math.sin(az),math.cos(az),0],[0,0,1]])
    rot=rz@ry@rx;verts=[rot@v for v in verts]
    buf=[(120,102,76,0)]*(S*S);depth=[-1e9]*(S*S);lamp=Vector((-.42,.68,.70));lamp/=np.linalg.norm(lamp)
    for face in faces:
        a,b,c=[verts[i] for i in face];normal=np.cross(b-a,c-a);normal/=np.linalg.norm(normal)
        if normal.dot((a+b+c)/3)<0:normal=-normal
        shade=.40+.60*max(0,normal.dot(lamp));screen=[(v[0]*66+63.5,63.5-v[1]*66,v[2]) for v in (a,b,c)];(ax,ay,az),(bx,by,bz),(cx,cy,cz)=screen
        denom=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
        if abs(denom)<1e-8:continue
        for y in range(max(0,math.floor(min(ay,by,cy))),min(S,math.ceil(max(ay,by,cy))+1)):
            for x in range(max(0,math.floor(min(ax,bx,cx))),min(S,math.ceil(max(ax,bx,cx))+1)):
                w=((by-cy)*(x-cx)+(cx-bx)*(y-cy))/denom;q=((cy-ay)*(x-cx)+(ax-cx)*(y-cy))/denom;r=1-w-q
                if min(w,q,r)<0:continue
                z=w*az+q*bz+r*cz;idx=y*S+x
                if z<=depth[idx]:continue
                depth[idx]=z;sample=[]
                for dy in range(-2,3):
                    for dx in range(-2,3):
                        off=4*(((y+dy)%S)*S+((x+dx+seed*5)%S));sample.append(rock[off:off+3])
                rgb=[sum(s[k] for s in sample)/len(sample) for k in range(3)];grain=.92+.08*math.sin(x*.35+y*.2+seed)
                buf[idx]=(*[round(min(255,v*shade*grain)) for v in rgb],255)
    return buf
rockkeys={m.crc('ucb_rock_masked_a'):stone_sprite(7),m.crc('ucb_rock_masked_b'):stone_sprite(18)}
oldglobal=m.table(gp[0]);assert set(rockkeys)<=set(oldglobal)
def rock_record(k,record):
    px=rockkeys[k];tile=bytearray(16384)
    for y in range(32):
        for x in range(32):
            b=encode_block([px[(4*y+j)*S+4*x+i] for j in range(4) for i in range(4)]);at=tiled_offset(x,y,32,4);tile[at:at+16]=bytes(b[i^1] for i in range(16))
    return record[:128]+tile
bank(gp,0,[(k,f,rock_record(k,v) if k in rockkeys else v) for k,f,v in m.vaps_rows(gp[0])]);newglobal=m.package(globalraw,gp);gcheck=entries(newglobal);assert all(gcheck[k]==v for k,v in entries(globalraw).items() if k!=0);assert all(m.table(gcheck[0])[k]==v for k,v in oldglobal.items() if k not in rockkeys)
(O/'global.xbx').write_bytes(newglobal)
def sha(b):return hashlib.sha256(b).hexdigest()
report=dict(old_cb_sha=sha(cb),new_cb_sha=sha(newcb),old_global_sha=sha(globalraw),new_global_sha=sha(newglobal),mesh_vertices=len(vertices),mesh_triangles=len(indices)//3,original_cyclone_material=True,rotation_curve_source='native Goop effect',animation_streams_unchanged=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
