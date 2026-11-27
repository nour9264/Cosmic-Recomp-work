"""Port the locally extracted POE pressureburst geometry and texture, not a screen overlay."""
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
H = WORK; I=APP_ROOT/'installation'; O=H/'poe-pressureburst-port';O.mkdir(exist_ok=True)
s=(H/'99_95.stream1.bin').read_bytes();raw=(I/'game/global/g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(raw)
assert hashlib.sha256(raw).hexdigest()=='026b5bfac67307a05219bdc62b04fdbfbae731ccf6e0bc4bd2e2ed95c3675103'
def u(q):return struct.unpack_from('<I',s,q)[0]
assert s[0x42c45b:0x42c469]==b'pressureburst\0' and u(0x4d3464)==0x42c45b and u(0x42b3e0)==0x23f260
assert s[0x23f270:0x23f280]==b'pressurestreaks\0' and u(0x23f270+52)==0x56f80 and u(0x56f80+8)==0x538700
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(i,rows):p[i]=m.build_vaps(i,struct.unpack_from('>H',p[i],12)[0],m.bucket_sorted(rows))
def palette(at):
    raw=s[u(at+40)+32:u(at+40)+32+1024];return [tuple(raw[4*((i&~24)|((i&8)<<1)|((i&16)>>1)):4*((i&~24)|((i&8)<<1)|((i&16)>>1))+4]) for i in range(256)]
def decode4():
    w,h=64,32;data=s[0x538790+32:0x538790+32+1024];pal=palette(0x54aa0);csa=(u(0x538700+12)>>8)&31;pixels=[];seen=set()
    for y in range(h):
        for x in range(w):
            pos=(x//32)*16*h+(y//16)*32+(((y//4)*2+(y&1))&7)*h*2+4*((x+4*((y+2)//4&1))&7)+(x//8&3);n=(y>>1)&1;seen.add(pos*2+n);idx=((data[pos]>>(4*n))&15)+16*csa;r,g,b,a=pal[idx];pixels.append((r,g,b,a))
    assert len(seen)==w*h
    return w,h,pixels
def decode8():
    w=h=64;raw=s[0x53a750+32:0x53a750+32+4096];mip=u(0x53a700+16);raw=s[mip+32:mip+32+4096];pal=palette(0x38800);mem=bytearray(8192);occupied=set()
    def block(x,y):return (x&1)|((y&1)<<1)|((x&2)<<1)|((y&2)<<2)|((x&4)<<2)
    def word(x,y):return (x&1)|((y&1)<<1)|((x&6)<<1)
    for y in range(32):
        for x in range(32):
            off=256*block(x//8,y//8)+64*((y%8)//2)+4*word(x%8,y%2);mem[off:off+4]=raw[4*(y*32+x):4*(y*32+x)+4];occupied.update(range(off,off+4))
    out=[]
    for y in range(64):
        for x in range(64):
            col=(y%16)//4;cy=y%4;cx=x%16;sx=(cx%8+4*((col&1)^(cy//2)))%8;off=256*block(x//16,y//16)+64*col+4*word(sx,cy%2)+2*(cx//8)+cy//2;assert off in occupied;out.append(pal[mem[off]])
    return w,h,out
donor=m.table(p[0])[0x82365e33];streaktex=m.crc('poe_pressureburst_streaks');glowtex=m.crc('poe_pressureburst_glow')
def encode(key,data):
    w,h,pixels=data;head=bytearray(donor[:128]);struct.pack_into('>I',head,44,key);tile=bytearray(16384)
    # Original PS2 additive intensity mapped into an alpha-blended native texture.
    rgb=[]
    for y in range(128):
        for x in range(128):
            r,g,b,a=pixels[min(h-1,y*h//128)*w+min(w-1,x*w//128)];v=max(r,g,b);rgb.append((255,255,255,round(v*min(1,a/128))))
    for y in range(32):
        for x in range(32):
            block=encode_block([rgb[(4*y+j)*128+4*x+i] for j in range(4) for i in range(4)]);at=tiled_offset(x,y,32,4);tile[at:at+16]=bytes(block[i^1] for i in range(16))
    return bytes(head)+tile
bank(0,m.vaps_rows(p[0])+[(streaktex,4,encode(streaktex,decode4())),(glowtex,4,encode(glowtex,decode8()))])
# Original PS2 VIF packet: 68 positions and 68 UV/ADC triplets, 17 strips of four vertices.
at=0x23f2f0;assert u(at+36)==0x68448001 and u(0x23f75c)==0x69448002
pts=list(struct.iter_unpack('<3f',s[at+40:at+40+68*12]));uv=list(struct.iter_unpack('<3H',s[0x23f760:0x23f760+68*6]));verts=[];colors=[];ind=[]
# Cross four azimuths in world space rather than a camera-facing giant quad.
for plane in range(4):
    angle=plane*math.pi/4;base=len(verts)
    for (x,y,z),(a,b,adc) in zip(pts,uv):
        verts.append((x*.21*math.cos(angle),y*.18,x*.21*math.sin(angle),a/4095,b/4095));colors.append(bytes((180,237,247,255)))
    for i in range(0,68,4):
        a=base+i;ind.extend((a,a+1,a+2,a+2,a+1,a+3,a+2,a+1,a,a+3,a+1,a+2))
key=m.crc('ucb_suction_release_ring');root=m.effect_root('cannonbolt');mesh=m.table(p[4])[key];off,_,_=m.mesh_buffers(mesh,xbox=True);head=bytearray(mesh[:off]);meta=struct.unpack_from('<I',head,28)[0];vb=b''.join(struct.pack('>5f',*v) for v in verts);ib=struct.pack(f'>{len(ind)}H',*ind);ia=(off+len(vb)+31)&~31
struct.pack_into('>I',head,4,len(verts));struct.pack_into('>I',head,16,len(ind));struct.pack_into('<I',head,20,meta+ia-376);struct.pack_into('>I',head,384,(len(ind)<<16)|(struct.unpack_from('>I',head,384)[0]&0xffff));assert struct.unpack_from('>I',head,404)[0]==0x82365e33;struct.pack_into('>I',head,404,streaktex);mesh=bytes(head)+vb+bytes(ia-off-len(vb))+ib;assert m.mesh_buffers(mesh,xbox=True)==(off,vb,ib)
bank(4,[(k,f,mesh if k==key else v) for k,f,v in m.vaps_rows(p[4])]);bank(3,[(k,f,v[:32]+b''.join(colors) if k==key else v) for k,f,v in m.vaps_rows(p[3])])
flash=m.crc('ucb_suction_core_flash');flashstop=m.crc('ucb_suction_flash_fade_timer');ringtimer=m.crc('ucb_suction_ring_timer');n=m.table(p[14]);rows=[]
for k,f,v in m.vaps_rows(p[14]):
    if k in (root,key):
        h,blocks=m.node_parts(v);out=[]
        if k==key:h[19:26]=fs(6,-4,0,-4,4,4,4)
        for b in blocks:
            if k==key and b[0]==0x19:
                b=[0x19,24,0x0d0a5003,0x00020002]+fs(0)+[0]*6+fs(.32,.32,.32)+fs(2600)+[0]*6+fs(1.18,1.12,1.18)
            if b[0]==14:
                pp=[];group=None
                for a,t,x in m.property_entries(b):
                    if t==0x1000c:group=a
                    if k==root and group==flash:
                        x={0x82660d72:[glowtex],0x118a27c7:fs(2.65),0x9c822a32:fs(3.4),0x3de73088:fs(1.10),0x5a6ce323:[0xd0ffffff],0xc365b299:[0xbcffffff],0xb462820f:[0x60ffffff],0x2a0617ac:[0x00ffffff]}.get(a,x)
                    if k==root and group==flashstop and a==0x865f80c0:x=fs(2.77)
                    if k==root and group==ringtimer and a==0x865f80c0:x=fs(2.29)
                    if k==key and group==0xe16f3a56 and a in (0x5e0393bd,0xf465b2b5):x=fs(.63)
                    pp.append((a,t,x))
                b=m.node_properties(pp)
            out.append(b)
        v=m.node_record(h,out)
    rows.append((k,f,v))
bank(14,rows);new=m.package(raw,p);check=entries(new);old=entries(raw)
assert all(check[k]==v for k,v in old.items() if k not in (0,3,4,14));assert all(m.table(check[14])[k]==v for k,v in n.items() if k not in (root,key));assert m.table(check[4])[m.crc('ucb_suction_side_ribbons')]==m.table(old[4])[m.crc('ucb_suction_side_ribbons')]
(O/'g_cb.xbx').write_bytes(new);report={'old_cb_sha':hashlib.sha256(raw).hexdigest(),'new_cb_sha':hashlib.sha256(new).hexdigest(),'source_pressureburst_record':'0x4d3464','source_mesh':'0x23f270','source_textures':['0x538700','0x53a6c0'],'source_quads':17,'crossed_planes':4,'side_mesh_unchanged':True,'gameplay_verified':False};(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
