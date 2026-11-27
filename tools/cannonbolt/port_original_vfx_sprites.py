"""Use decoded POE wind and rock material in native additive particle sprites."""
import hashlib, json, math, struct, sys, zlib
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
from extract_discord_level_images import tiled_offset
from wheel_icon_texture import encode_block

H = WORK
I=APP_ROOT/'installation'; O=H/'original-texture-port'; O.mkdir(exist_ok=True)
D=H/'original-vfx-decoded'; S=128
wind=(D/'Cyclone.rgba').read_bytes(); rock=(D/'Rock9.rgba').read_bytes()
assert len(wind)==len(rock)==S*S*4
def sample(data,u,v):
    x=max(0,min(S-1,round(u*(S-1))));y=max(0,min(S-1,round(v*(S-1))))
    return data[(y*S+x)*4:(y*S+x)*4+4]
def clamp(x):return max(0,min(1,x))
def funnel(x,y):
    v=y/(S-1);u=2*x/(S-1)-1;radius=.25+.67*(1-v)**.7
    side=u/radius
    if abs(side)>=1:return (0,0,0)
    r,g,b,a=sample(wind,(side+1)/2,v)
    edge=clamp((1-abs(side))*7)*clamp(v*10)*clamp((1-v)*10)
    # Original bands, tapered and softly masked for a billboard. Bake alpha
    # into RGB because the stock particle shader uses additive blending.
    intensity=edge*(a/255)*.65*(.5+.5*abs(side))
    return tuple(round(c*intensity) for c in (r,g,b))
def stone(x,y,variant):
    u=2*x/(S-1)-1;v=2*y/(S-1)-1
    verts=([(-.72,-.25),(-.33,-.78),(.45,-.62),(.84,.12),(.28,.76),(-.65,.54)] if variant==0 else [(-.8,-.1),(-.40,-.7),(.25,-.79),(.75,-.24),(.59,.66),(-.31,.8)])
    distances=[]
    for (ax,ay),(bx,by) in zip(verts,verts[1:]+verts[:1]):
        dx,dy=bx-ax,by-ay;distances.append((dx*(v-ay)-dy*(u-ax))/math.hypot(dx,dy))
    edge=clamp(min(distances)*35)
    samples=[sample(rock,(x/(S-1)+variant*.3+dx/S)%1,(y+dy)/(S-1)) for dx,dy in ((0,0),(1,0),(-1,0),(0,1),(0,-1))]
    r,g,b=(sum(p[i] for p in samples)/len(samples) for i in range(3))
    shade=.86 if v<-.3*u-.1 else (.56 if u>.15+.3*v else .73)
    return tuple(round(c*edge*shade) for c in (r,g,b))
sprites={m.crc('ucb_air_funnel_masked'):[funnel(x,y) for y in range(S) for x in range(S)],
         m.crc('ucb_rock_masked_a'):[stone(x,y,0) for y in range(S) for x in range(S)],
         m.crc('ucb_rock_masked_b'):[stone(x,y,1) for y in range(S) for x in range(S)]}
raw=(I/'game/global/global.xbx').read_bytes();gp=entries(raw);rows=m.vaps_rows(gp[0]);old=m.table(gp[0]);assert set(sprites)<=set(old)
def encode(key,record,pixels):
    head=bytearray(record[:128]);assert struct.unpack_from('>H',head,4)[0]==0x104
    struct.pack_into('>HHBB',head,6,S,S,7,7)
    tile=bytearray(8192); d=S//4; seen=set()
    for y in range(d):
        for x in range(d):
            b=encode_block([(*pixels[(4*y+j)*S+4*x+i],255) for j in range(4) for i in range(4)])[8:]
            at=tiled_offset(x,y,d,3);assert at not in seen and at+8<=len(tile);seen.add(at)
            tile[at:at+8]=bytes(b[j^1] for j in range(8))
    assert len(seen)==1024
    return bytes(head)+tile
gp[0]=m.build_vaps(0,struct.unpack_from('>H',gp[0],12)[0],m.bucket_sorted([(k,f,encode(k,v,sprites[k]) if k in sprites else v) for k,f,v in rows]))
newg=m.package(raw,gp);chk=entries(newg);assert all(chk[k]==v for k,v in entries(raw).items() if k!=0)
assert all(m.table(chk[0])[k]==v for k,v in old.items() if k not in sprites)
cb=(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();assert cb==(I/'game/global/g_cb.xbx').read_bytes();cp=entries(cb);root=m.effect_root('cannonbolt');oldnodes=m.table(cp[14])
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def settings(n,rate,life,size,height,colors):
    return {0x9d762289:[n],0xe7965460:fs(rate),0x3de73088:fs(life),0x118a27c7:fs(size),0x9c822a32:fs(size),0x462ce4f5:fs(0,height,0,0,0,0,1),**dict(zip((0x5a6ce323,0xc365b299,0xb462820f,0x2a0617ac),([c] for c in colors)))}
windcolors=(0x80606060,0x80707070,0x60404040,0x00000000)
dustcolors=(0x30282828,0x40383838,0x20202020,0x00000000)
rockcolors=(0x80707070,0x80909090,0x60606060,0x00000000)
edits={
 'ucb_spin_wind_1_particles':{**settings(1,4,.65,2.05,1.25,windcolors),0x7cb5a078:fs(0,0,0),0xd7943d68:fs(0,0,0),0x7a76b57b:fs(0,0,0)},
 'ucb_spin_wind_0_particles':settings(5,10,.40,.22,.10,dustcolors),
 'ucb_spin_wind_2_particles':settings(1,2,.32,.16,1.65,dustcolors),
 'ucb_backspin_rock_0_particles':settings(12,16,.58,.18,.12,rockcolors),
 'ucb_backspin_rock_1_particles':settings(10,14,.52,.23,.12,rockcolors),
 'ucb_backspin_ground_dust_particles':settings(6,12,.40,.25,.08,dustcolors),
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
assert sorted(changed)==sorted(edits)
cp[14]=m.build_vaps(14,struct.unpack_from('>H',cp[14],12)[0],nodes);newcb=m.package(cb,cp);cc=entries(newcb)
assert all(cc[k]==v for k,v in entries(cb).items() if k!=14)
assert all(m.table(cc[14])[k]==v for k,v in oldnodes.items() if k!=root)
def sha(b):return hashlib.sha256(b).hexdigest()
(O/'global.xbx').write_bytes(newg);(O/'g_cb.xbx').write_bytes(newcb)
# Show the actual precompression masked assets against black.
def chunk(t,b):return struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
scan=b''.join(b'\0'+b''.join(bytes((*p,255)) for pixels in sprites.values() for p in pixels[y*S:(y+1)*S]) for y in range(S))
(O/'preview.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',S*3,S,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
report=dict(old_cb_sha=sha(cb),old_global_sha=sha(raw),new_cb_sha=sha(newcb),new_global_sha=sha(newg),source_wind_sha=sha(wind),source_rock_sha=sha(rock),groups=len(changed),other_assets_preserved=True,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
