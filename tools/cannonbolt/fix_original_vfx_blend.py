"""Replace luminous additive debris with native normal-blended BC3 sprites."""
import hashlib,json,math,struct,sys,zlib
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
from extract_discord_level_images import tiled_offset
from wheel_icon_texture import encode_block

H = WORK; I=APP_ROOT/'installation'; O=H/'original-vfx-direction-radius';O.mkdir(exist_ok=True)
D=H/'original-vfx-decoded'; S=128
wind=(D/'Cyclone.rgba').read_bytes();rock=(D/'Rock9.rgba').read_bytes();assert len(wind)==len(rock)==S*S*4
def clamp(x):return max(0,min(1,x))
def sample(d,u,v):
    x=round(clamp(u)*(S-1));y=round(clamp(v)*(S-1));return d[(y*S+x)*4:(y*S+x)*4+4]
def funnel(x,y):
    v=y/(S-1);u=2*x/(S-1)-1
    # The runtime displays the sprite vertically flipped relative to the PNG.
    # Both ends stay close to the ball's radius; widen slightly toward the sky.
    radius=.43+.13*v
    side=u/radius
    if abs(side)>=1:return (216,220,222,0)
    r,g,b,a=sample(wind,(side+1)/2,v)
    edge=clamp((1-abs(side))*7)*clamp(v*9)*clamp((1-v)*9)
    light=(r+g+b)/765
    # Keep the original source's horizontal wind bands, with differing
    # opacity rather than luminous RGB. The wall remains visible behind them.
    opacity=edge*(.09+.48*clamp((light-.22)/.55))*((.82+.18*abs(side)))
    return (174,181,185,round(255*opacity))
def stone(x,y,variant):
    u=2*x/(S-1)-1;v=2*y/(S-1)-1
    verts=([(-.73,-.22),(-.45,-.69),(.16,-.77),(.63,-.39),(.83,.13),(.26,.75),(-.62,.48)] if variant==0 else [(-.78,-.12),(-.44,-.69),(.14,-.81),(.75,-.31),(.62,.43),(.09,.78),(-.49,.58)])
    distances=[]
    for (ax,ay),(bx,by) in zip(verts,verts[1:]+verts[:1]):
        dx,dy=bx-ax,by-ay;distances.append((dx*(v-ay)-dy*(u-ax))/math.hypot(dx,dy))
    alpha=round(255*clamp(min(distances)*35))
    samples=[sample(rock,(x/(S-1)+variant*.3+dx/S)%1,(y+dy)/(S-1)) for dx in range(-3,4) for dy in range(-3,4)]
    rgb=[sum(p[i] for p in samples)/len(samples) for i in range(3)]
    # Multiple angled faces and broad tonal variation avoid a grainy flat hexagon.
    shade=(1.03 if v<-.36*u-.18 else (.55 if u>.12+.28*v else (.77 if v<.23+.44*u else .65)))
    shade*=.94+.08*math.sin(10*u+7*v+variant)+.05*math.cos(17*v-4*u)
    return (*[round(min(255,c*shade)) for c in rgb],alpha)
sprites={m.crc('ucb_air_funnel_masked'):[funnel(x,y) for y in range(S) for x in range(S)],m.crc('ucb_rock_masked_a'):[stone(x,y,0) for y in range(S) for x in range(S)],m.crc('ucb_rock_masked_b'):[stone(x,y,1) for y in range(S) for x in range(S)]}
raw=(I/'game/global/global.xbx').read_bytes();gp=entries(raw);rows=m.vaps_rows(gp[0]);old=m.table(gp[0]);assert set(sprites)<=set(old)
# A native single-level 128x128 BC3 texture (not a guessed BC1 header).
template=old[0xb458a502];assert len(template)==16512 and template[4:10]==bytes.fromhex('010200800080')
def encode(k,pixels):
    head=bytearray(template[:128]);struct.pack_into('>I',head,44,k);tile=bytearray(16384);seen=set()
    for y in range(32):
        for x in range(32):
            p=[pixels[(4*y+j)*S+4*x+i] for j in range(4) for i in range(4)]
            b=encode_block(p);at=tiled_offset(x,y,32,4);assert at not in seen and at+16<=len(tile);seen.add(at);tile[at:at+16]=bytes(b[j^1] for j in range(16))
    assert len(seen)==1024
    return bytes(head)+tile
gp[0]=m.build_vaps(0,struct.unpack_from('>H',gp[0],12)[0],m.bucket_sorted([(k,f,encode(k,sprites[k]) if k in sprites else v) for k,f,v in rows]));newg=m.package(raw,gp);chk=entries(newg)
assert all(chk[k]==v for k,v in entries(raw).items() if k!=0);assert all(m.table(chk[0])[k]==v for k,v in old.items() if k not in sprites)
cb=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();assert cb==(I/'game/global/g_cb.xbx').read_bytes();cp=entries(cb);root=m.effect_root('cannonbolt');oldnodes=m.table(cp[14]);
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def settings(n,rate,life,size,height,colors):
    return {0x22944c2a:[m.crc('normal')],0x9d762289:[n],0xe7965460:fs(rate),0x3de73088:fs(life),0x118a27c7:fs(size),0x9c822a32:fs(size),0x462ce4f5:fs(0,height,0,0,0,0,1),**dict(zip((0x5a6ce323,0xc365b299,0xb462820f,0x2a0617ac),([c] for c in colors)))}
edits={
 'ucb_spin_wind_1_particles':settings(1,6,.5,2.05,1.18,(0xdfffffff,0xffffffff,0xffffffff,0xdfffffff)),
 'ucb_backspin_rock_0_particles':{**settings(15,24,.58,.17,.23,(0xffffffff,0xffffffff,0xffffffff,0x00ffffff)),0x462ce4f5:fs(-.06,.23,.55,0,0,0,1),0x0f26fef6:fs(5.4),0x7cb5a078:fs(.045,.02,.045),0xd7943d68:fs(.10,.55,.12),0x7a76b57b:fs(0,-2.4,0)},
 'ucb_backspin_rock_1_particles':{**settings(12,22,.52,.22,.24,(0xffffffff,0xffffffff,0xffffffff,0x00ffffff)),0x462ce4f5:fs(.06,.24,.60,0,0,0,1),0x0f26fef6:fs(6.1),0x7cb5a078:fs(.055,.02,.045),0xd7943d68:fs(.10,.6,.15),0x7a76b57b:fs(0,-2.6,0)},
}
edits={m.crc(k):v for k,v in edits.items()};changed=[];nodes=[]
for k,f,v in m.vaps_rows(cp[14]):
    if k==root:
        h,blocks=m.node_parts(v);new=[]
        for b in blocks:
            if b[0]==0xe:
                p=[];mode=None
                for prop,t,vals in m.property_entries(b):
                    if t==0x1000c:
                        mode=edits.get(prop)
                        if mode is not None:changed.append(prop)
                    if mode and prop in mode and t!=0x1000c:vals=mode[prop]
                    p.append((prop,t,list(vals)))
                b=m.node_properties(p)
            new.append(b)
        v=m.node_record(h,new)
    nodes.append((k,f,v))
assert sorted(changed)==sorted(edits);cp[14]=m.build_vaps(14,struct.unpack_from('>H',cp[14],12)[0],nodes);newcb=m.package(cb,cp);cc=entries(newcb)
assert all(cc[k]==v for k,v in entries(cb).items() if k!=14);assert all(m.table(cc[14])[k]==v for k,v in oldnodes.items() if k!=root)
def sha(b):return hashlib.sha256(b).hexdigest()
(O/'global.xbx').write_bytes(newg);(O/'g_cb.xbx').write_bytes(newcb)
def chunk(t,b):return struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
def composite(p):
    a=p[3]/255;return bytes([round(c*a+65*(1-a)) for c in p[:3]]+[255])
scan=b''.join(b'\0'+b''.join(composite(p) for pixels in sprites.values() for p in pixels[y*S:(y+1)*S]) for y in range(S));(O/'preview.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',S*3,S,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
report=dict(old_cb_sha=sha(cb),old_global_sha=sha(raw),new_cb_sha=sha(newcb),new_global_sha=sha(newg),normal_blend_groups=len(changed),other_assets_preserved=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
