"""Bounce Ball-only ground shock, contact sounds, and 20% more height."""
import hashlib,json,math,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range
from wheel_icon_texture import encode_block
from extract_discord_level_images import tiled_offset

H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'ultimate-bounce-ball-v5-impact';O.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
previous=json.loads((H/'ultimate-bounce-ball-v4-height/validation.json').read_text());raw=(G/'g_cb.xbx').read_bytes();ddf=(G/'scripts/atk_ucb.ddf').read_bytes();normal=(G/'scripts/atk_cb.ddf').read_bytes()
assert sha(raw)==previous['new_cb_sha'] and sha(ddf)==previous['new_ucb_sha'] and sha(normal)==previous['normal_ddf_sha']
assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes() and ddf==(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
p=entries(raw);old=dict(p);key=0xc9fb4de3;clips=m.table(p[13]);ch=channel_records(p[9]);clip=clips[key];slot=struct.unpack_from('>I',clip,216+132*4)[0]
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(i,rows,sort=False):p[i]=m.build_vaps(i,struct.unpack_from('>H',p[i],12)[0],m.bucket_sorted(rows) if sort else rows)
def groups(block):
    out=[]
    for a,t,v in m.property_entries(block):
        if t==0x1000c:out.append([])
        assert out;out[-1].append((a,t,v))
    return out
def clamp(x):return max(0,min(1,x))
def smooth(x):x=clamp(x);return x*x*(3-2*x)

# Only change the ball's existing translation curve. Exact ground contact
# times, scale/squash curves, steering, and clip/flag indices stay intact.
rows=m.vaps_rows(p[9]);k,f,v=rows[slot];position=bytearray(v);base=struct.unpack_from('>3f',v,12)
for at in range(8,len(v),16):
    t,x,y,z=struct.unpack_from('>4f',v,at);struct.pack_into('>4f',position,at,t,*(a+(b-a)*1.2 for a,b in zip(base,(x,y,z))))
rows[slot]=(k,f,bytes(position));bank(9,rows)

# The reference is a broad white-blue ground flash with tapered radial
# gaps and a feathered outside edge. A new isolated texture/material avoids
# changing the Meteor Bolt's existing ring or any other special.
tex=m.crc('ucb_bounce_impact_star_tex');mesh=m.crc('ucb_bounce_impact_star');start=m.crc('ucb_bounce_contact');stop=m.crc('ucb_bounce_stop')
ring=m.crc('ucb_meteor_poe_ring');root=m.effect_root('cannonbolt');oldstart=m.crc('ucb_meteor_poe_contact');oldstop=m.crc('ucb_meteor_poe_fx_stop')
pixels=[]
for y in range(128):
    for x in range(128):
        dx=(x-63.5)/63.5;dy=(y-63.5)/63.5;r=math.hypot(dx,dy);a=math.atan2(dy,dx)
        # Irregular tapered radial dark gaps between luminous lobes.
        phase=11*a+.52*math.sin(3*a)+.22*math.sin(7*a)+r*2.3
        spoke=(.5+.5*math.cos(phase))**8
        gap=spoke*smooth((r-.07)*13)*smooth((.89-r)*5)
        band=math.exp(-((r-.44)/.29)**2);halo=math.exp(-((r-.70)/.21)**2)
        edge=smooth((.99-r)*6);mottle=.92+.08*math.sin(17*dx+5*math.sin(13*dy))*math.cos(22*dy)
        intensity=clamp((.30*halo+.96*band*(1-.96*gap)+.18*math.exp(-29*r*r))*edge*mottle)
        blue=clamp((r-.32)/.54);rgb=(round(255-68*blue),round(255-45*blue),255)
        # Zero color outside the disk, including the transparent border.
        pixels.append((*[round(c*intensity) for c in rgb],round(255*intensity)))
header=bytearray(m.table(p[0])[m.crc('poe_deep_impact_ring_tex')][:128]);struct.pack_into('>I',header,44,tex);tile=bytearray(16384)
for y in range(32):
    for x in range(32):
        block=encode_block([pixels[(y*4+j)*128+x*4+i] for j in range(4) for i in range(4)]);at=tiled_offset(x,y,32,4);tile[at:at+16]=bytes(block[i^1] for i in range(16))
bank(0,m.vaps_rows(p[0])+[(tex,4,bytes(header)+tile)],True)

# Horizontal disk, never a camera-facing billboard. Use the already-tested
# ring material and native vertex format, but the new ground texture.
donor=m.table(p[4])[ring];off,_,_=m.mesh_buffers(donor,xbox=True);head=bytearray(donor[:off]);meta=struct.unpack_from('<I',head,28)[0]
radius=3.5;verts=[(0,.065,0,.5,.5)]
for i in range(49):
    a=math.tau*i/48;x,z=math.cos(a),math.sin(a);verts.append((radius*x,.065,radius*z,.5+.5*x,.5+.5*z))
inds=[]
for i in range(1,49):inds.extend((0,i+1,i,i, i+1,0))
vb=b''.join(struct.pack('>5f',*v) for v in verts);ib=struct.pack(f'>{len(inds)}H',*inds);ia=(off+len(vb)+31)&~31
struct.pack_into('>I',head,4,len(verts));struct.pack_into('>I',head,16,len(inds));struct.pack_into('<I',head,20,meta+ia-376);struct.pack_into('>I',head,384,(len(inds)<<16)|(struct.unpack_from('>I',head,384)[0]&0xffff));struct.pack_into('>I',head,404,tex)
meshdata=bytes(head)+vb+bytes(ia-off-len(vb))+ib;assert m.mesh_buffers(meshdata,xbox=True)==(off,vb,ib)
bank(4,m.vaps_rows(p[4])+[(mesh,off//32,meshdata)],True)
col=bytearray(m.table(p[3])[ring][:32]);struct.pack_into('>I',col,8,mesh)
bank(3,m.vaps_rows(p[3])+[(mesh,1,bytes(col)+bytes((232,255,255,255))*len(verts))],True)

# Clone the existing ground ring component and give it its own event names.
nodes=m.table(p[14]);h,blocks=m.node_parts(nodes[ring]);h=list(h);h[0]=mesh;h[19:26]=fs(5,-4.5,-.1,-4.5,4.5,2,4.5);out=[]
for b in blocks:
    if b[0]==0x19:b=[0x19,24,0x0d0a5003,0x00020002]+fs(0)+[0]*6+fs(.72,1,.72)+fs(1800)+[0]*6+fs(1.14,1,1.14)
    elif b[0]==0:b=[0,4,mesh,mesh]
    elif b[0]==14:
        pp=[]
        for a,t,v in m.property_entries(b):
            if v==[oldstart]:v=[start]
            if v==[oldstop]:v=[stop]
            if a in (0x5e0393bd,0xf465b2b5):v=fs(.4)
            pp.append((a,t,v))
        b=m.node_properties(pp)
    out.append(b)
newnode=m.node_record(h,out)

# Use a native one-shot sound component, exactly like other ground-impact
# effects, not the attack-start sound. The shared Cannonbolt bank already
# supplies cbolt_land_big (sound descriptor event 8).
sounds=(G/'scripts/sounds.ddf').read_text();assert '<sound name="cbolt_land_big" id="8"' in sounds
bc=m.table(entries((G/'g_bc.xbx').read_bytes())[14]);_,bb=m.node_parts(bc[0x28729a8b]);template=next(g for b in bb if b[0]==14 for g in groups(b) if g[0][2]==[0xf88ec384])
sound=m.crc('cbolt_land_big');soundgroup=[(m.crc('ucb_bounce_impact_sound') if t==0x1000c else a,t,{0x8541406c:[start],0x5e237e06:[sound],0xf7be9018:[0]}.get(a,v)) for a,t,v in template]
h,blocks=m.node_parts(nodes[root]);out=[]
for b in blocks:
    if b[0]==0x14:b=[0x14,b[1]+1,b[2]+1]+b[3:]+[mesh]
    elif b[0]==14:
        pp=m.property_entries(b);extra=[]
        for event in (start,stop):extra.extend([(m.crc(f'{mesh}_{event}_forward'),0x1000c,[m.EVENT_GROUP]),(0x939b68a0,0x201000c,[event]),(0x8541406c,0x201000c,[event]),(0x557c4b4d,0x201000c,[mesh])])
        extra.extend(soundgroup)
        dust=next(g for g in groups(b) if g[0][0]==m.crc('ucb_meteor_poe_dust_0'))
        for i in range(6):
            angle=math.tau*i/6;settings={0x462ce4f5:fs(.46*math.sin(angle),.13,.46*math.cos(angle),0,math.sin(angle/2),0,math.cos(angle/2)),0x8541406c:[start],0xf7be9018:[stop],0x9d762289:[3],0xe7965460:fs(18),0x3de73088:fs(.34),0x0f26fef6:fs(4.4),0x297c98f1:fs(30),0x7a76b57b:fs(0,1.1,0),0x118a27c7:fs(.045),0x9c822a32:fs(.075),0x5a6ce323:[0xf0ffffff],0xc365b299:[0xe8ffffff],0xb462820f:[0x80ffffff],0x2a0617ac:[0x00ffffff]}
            extra.extend((m.crc(f'ucb_bounce_fleck_{i}') if t==0x1000c else a,t,settings.get(a,v)) for a,t,v in dust)
        b=m.node_properties(pp+extra)
    out.append(b)
bank(14,[(k,f,m.node_record(h,out) if k==root else v) for k,f,v in m.vaps_rows(p[14])]+[(mesh,0,newnode)],True)

d=bytearray(ddf);changes=[]
for at in range(4,len(d),224):
    if struct.unpack_from('>I',d,at+32)[0]!=key:continue
    assert struct.unpack_from('>2I',d,at+144)==(oldstart,oldstop)
    struct.pack_into('>2I',d,at+144,start,stop);changes.append(at)
assert changes==[4,3140,5380]
new=m.package(raw,p);check=entries(new);newch=channel_records(check[9]);assert all(check[k]==v for k,v in old.items() if k not in (0,3,4,9,14))
assert len(newch)==len(ch) and [i for i,(a,b) in enumerate(zip(ch,newch)) if a!=b]==[slot]
assert animation_time_range(clip,newch)==animation_time_range(clip,ch)
assert all(streamed_clip(v,ch)==streamed_clip(v,newch) for k,v in clips.items() if k!=key)
assert all(m.table(check[i])[k]==v for i in (0,3,4) for k,v in m.table(old[i]).items())
assert all(m.table(check[14])[k]==v for k,v in nodes.items() if k!=root)
assert all(d[at:at+224]==ddf[at:at+224] for at in range(4,len(d),224) if at not in changes)
(O/'g_cb.xbx').write_bytes(new);(O/'atk_ucb.ddf').write_bytes(d)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(new),old_ucb_sha=sha(ddf),new_ucb_sha=sha(d),normal_ddf_sha=sha(normal),height_multiplier=1.2,peak_heights=[x*1.2 for x in previous['peak_heights']],contacts=previous['contacts'],contact_sound='cbolt_land_big',visual='reference-matched radial ground shock disk and white particles',original_texture_exact=False,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
