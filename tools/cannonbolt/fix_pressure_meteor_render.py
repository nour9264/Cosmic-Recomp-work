"""Correct render-space artifacts: shaped ground ring, low crater, soft air burst."""
import sys,struct,math,hashlib,json
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
from wheel_icon_texture import encode_block
from extract_discord_level_images import tiled_offset
H = WORK;I=APP_ROOT/'installation';O=H/'pressure-meteor-render-fix';O.mkdir(exist_ok=True)
raw=(I/'game/global/g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();assert hashlib.sha256(raw).hexdigest()=='c32321ecbece37ddc014ac88e1b0dca6dbbe86ec58f4f179a90eb75f0c5a670a';p=entries(raw);old=entries(raw)
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(i,rows):p[i]=m.build_vaps(i,struct.unpack_from('>H',p[i],12)[0],rows)
def clamp(x):return max(0,min(1,x))
def smooth(x):x=clamp(x);return x*x*(3-2*x)
ring=m.crc('ucb_meteor_poe_ring');crater=m.crc('ucb_meteor_poe_crater');burst=m.crc('ucb_suction_release_ring');root=m.effect_root('cannonbolt')
rt=m.crc('poe_deep_impact_ring_tex');ct=m.crc('poe_deep_impact_crater_tex');st=m.crc('poe_pressureburst_streaks');gt=m.crc('poe_pressureburst_glow')
def texture(key,record):
    pixels=[]
    for y in range(128):
        for x in range(128):
            u=x/127;v=y/127;r=math.hypot(2*u-1,2*v-1)
            if key==rt:
                # UV v crosses the annulus; zero RGB AND alpha at both edges.
                a=math.sin(math.pi*v)**2;rgb=(160,180,190)
            elif key==ct:
                a=smooth((1-r)*3)*(.5+.2*math.sin(19*u+6*math.sin(11*v)));rgb=(75,67,59)
            elif key==st:
                # Longitudinal falloff and broad, feathered pressure ribbons.
                a=smooth(u*5)*smooth((1-u)*3)*math.sin(math.pi*v)**1.5;rgb=(188,210,226)
            else:
                a=math.exp(-5*r*r)*smooth((1-r)*4);rgb=(210,231,244)
            a=clamp(a);pixels.append((*[round(c*a) for c in rgb],round(255*a)))
    tile=bytearray(16384)
    for y in range(32):
        for x in range(32):
            b=encode_block([pixels[(4*y+j)*128+4*x+i] for j in range(4) for i in range(4)]);off=tiled_offset(x,y,32,4);tile[off:off+16]=bytes(b[i^1] for i in range(16))
    return record[:128]+tile
bank(0,[(k,f,texture(k,v) if k in (rt,ct,st,gt) else v) for k,f,v in m.vaps_rows(p[0])])
# Actual annulus rather than a square floor card. No fragments can lie outside the ring.
verts=[];inds=[];colors=[]
for j in range(65):
    angle=math.tau*j/64
    for i in range(7):
        t=i/6;r=1.65+.52*t;verts.append((r*math.cos(angle),.065,r*math.sin(angle),j/64,t));colors.append(bytes((round(145*math.sin(math.pi*t)**.5),220,236,245)))
for j in range(64):
    for i in range(6):
        a=j*7+i;b=a+7;c=a+1;d=b+1;inds.extend((a,b,c,b,d,c))
def rebuild(rec,verts,inds):
    off,_,_=m.mesh_buffers(rec,xbox=True);head=bytearray(rec[:off]);meta=struct.unpack_from('<I',head,28)[0];vb=b''.join(struct.pack('>5f',*v) for v in verts);ib=struct.pack(f'>{len(inds)}H',*inds);ia=(off+len(vb)+31)&~31;struct.pack_into('>I',head,4,len(verts));struct.pack_into('>I',head,16,len(inds));struct.pack_into('<I',head,20,meta+ia-376);struct.pack_into('>I',head,384,(len(inds)<<16)|(struct.unpack_from('>I',head,384)[0]&0xffff));v=bytes(head)+vb+bytes(ia-off-len(vb))+ib;assert m.mesh_buffers(v,xbox=True)==(off,vb,ib);return v
rows=[]
for k,f,v in m.vaps_rows(p[4]):
    if k==ring:v=rebuild(v,verts,inds)
    elif k==crater:
        off,vb,ib=m.mesh_buffers(v,xbox=True);q=bytearray(v)
        # Keep the original crater silhouette, flatten its raised pieces into the floor.
        for i in range(0,len(vb),20):
            x,y,z,u,w=struct.unpack_from('>5f',vb,i);struct.pack_into('>3f',q,off+i,x*.92,.035+max(0,y-.045)*.11,z*.92)
        v=bytes(q);assert m.mesh_buffers(v,xbox=True)[2]==ib
    elif k==burst:
        off,vb,ib=m.mesh_buffers(v,xbox=True);q=bytearray(v)
        for i in range(0,len(vb),20):
            x,y,z,u,w=struct.unpack_from('>5f',vb,i);struct.pack_into('>3f',q,off+i,x*.83,y*.65,z*.83)
        v=bytes(q)
    rows.append((k,f,v))
bank(4,rows)
bank(3,[(k,f,v[:32]+b''.join(colors) if k==ring else v[:32]+b''.join(bytes((min(v[i],85 if k==crater else 125),*v[i+1:i+4])) for i in range(32,len(v),4)) if k in (crater,burst) else v) for k,f,v in m.vaps_rows(p[3])])
n=m.table(p[14]);rows=[];flash=m.crc('ucb_suction_core_flash');dusts={m.crc(f'ucb_meteor_poe_dust_{i}') for i in range(6)}
for k,f,v in m.vaps_rows(p[14]):
    if k in (root,ring,crater,burst):
        h,bl=m.node_parts(v);out=[]
        for b in bl:
            if k==ring and b[0]==0x19:b=[0x19,24,0x0d0a5003,0x00020002]+fs(0)+[0]*6+fs(.42,1,.42)+fs(2500)+[0]*6+fs(1.48,1,1.48)
            if k==root and b[0]==14:
                pp=[];group=None
                for a,t,x in m.property_entries(b):
                    if t==0x1000c:group=a
                    if group==flash:x={0x118a27c7:fs(2.1),0x9c822a32:fs(2.65),0x3de73088:fs(.86),0x5a6ce323:[0xe0ffffff],0xc365b299:[0xb0ffffff],0xb462820f:[0x50ffffff],0x2a0617ac:[0x00ffffff]}.get(a,x)
                    elif group in dusts:x={0x9d762289:[2],0xe7965460:fs(12),0x3de73088:fs(.36),0x118a27c7:fs(.23),0x9c822a32:fs(.42),0x5a6ce323:[0x58ffffff],0xc365b299:[0x68ffffff],0xb462820f:[0x28ffffff]}.get(a,x)
                    pp.append((a,t,x))
                b=m.node_properties(pp)
            out.append(b)
        v=m.node_record(h,out)
    rows.append((k,f,v))
bank(14,rows);new=m.package(raw,p);chk=entries(new);assert all(chk[k]==v for k,v in old.items() if k not in (0,3,4,14));assert m.table(chk[4])[m.crc('ucb_suction_side_ribbons')]==m.table(old[4])[m.crc('ucb_suction_side_ribbons')];assert all(m.table(chk[14])[k]==v for k,v in n.items() if k not in (root,ring,crater,burst))
(O/'g_cb.xbx').write_bytes(new);report=dict(old_cb_sha=hashlib.sha256(raw).hexdigest(),new_cb_sha=hashlib.sha256(new).hexdigest(),ring_geometry='annulus',crater_flattened=True,zero_rgb_alpha_edges=True,animation_audio_unchanged=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
