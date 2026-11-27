"""Decode the identified PS2 indexed GS transfers into reviewable RGBA images."""
import json,struct,zlib,hashlib
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
H = WORK;A=H/'original-vfx-assets';O=H/'original-vfx-decoded';O.mkdir(exist_ok=True)
manifest=json.loads((A/'manifest.json').read_text());assets={r['name']:r for r in manifest['assets']}
def png(path,w,h,rgba):
    def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    scan=b''.join(b'\0'+rgba[y*w*4:(y+1)*w*4] for y in range(h));path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
def u(p,o):return struct.unpack_from('<I',p,o)[0]
def payload(r,k):
    d=(A/r[k]['file']).read_bytes();assert hashlib.sha256(d).hexdigest()==r[k]['sha256'];return d[32:]
def palette(raw):
    assert len(raw)==1024
    return [tuple(raw[4*((i&~24)|((i&8)<<1)|((i&16)>>1)):4*((i&~24)|((i&8)<<1)|((i&16)>>1))+4]) for i in range(256)]
def block32(x,y):
    return (x&1)|((y&1)<<1)|((x&2)<<1)|((y&2)<<2)|((x&4)<<2)
def word32(x,y):return (x&1)|((y&1)<<1)|((x&6)<<1)
def gs8(raw,w,h):
    # Model the actual CT32 upload and indexed read independently. For
    # half-page textures the transfer covers only the left half of a page.
    mem=bytearray(8192);occupied=set();tw=w//2;th=h//2
    for y in range(th):
        for x in range(tw):
            block=block32(x//8,y//8);off=256*block+64*((y%8)//2)+4*word32(x%8,y%2)
            at=4*(y*tw+x);mem[off:off+4]=raw[at:at+4];occupied.update(range(off,off+4))
    result=bytearray()
    for y in range(h):
        for x in range(w):
            block=block32(x//16,y//16);col=(y%16)//4;cy=y%4;cx=x%16
            sx=(cx%8+4*((col&1)^(cy//2)))%8
            pos=256*block+64*col+4*word32(sx,cy%2)+2*(cx//8)+cy//2
            assert pos in occupied;result.append(mem[pos])
    return bytes(result)
def decode(r):
    fmt=int(r['format'],16);raw=payload(r,'gs_upload');pal=palette(payload(r,'palette_upload'));header=(A/r['texture_header']['file']).read_bytes();csa=(u(header,12)>>8)&31
    # PSMT4 logical image: one 128x128 GS page, uploaded as 64x32 CT32.
    # PSMT8 logical image: 64x64, uploaded as 32x32 CT32.
    w=h=128 if fmt==0x14 else 64;assert len(raw)==w*h//(2 if fmt==0x14 else 1)
    out=bytearray();visited=set();direct8=gs8(raw,w,h) if fmt==0x13 else None
    for y in range(h):
        for x in range(w):
            swap=4*((y+2)//4&1);row=((y//4)*2+(y&1))&7;col=4*((x+swap)&7)
            if fmt==0x14:
                pos=(x//32)*16*h+(y//16)*32+row*h*2+col+(x//8&3);nib=(y>>1)&1
                visited.add(pos*2+nib);idx=(raw[pos]>>(4*nib))&15;idx+=16*csa
            else:
                pos=(y//16)*16*w+(x//16)*32+row*w*2+col+((y>>1)&1)+((x>>2)&2);visited.add(pos);idx=direct8[y*w+x]
            assert idx<len(pal);r,g,b,a=pal[idx];out.extend((r,g,b,min(255,a*2)))
    assert len(visited)==w*h
    return w,h,bytes(out),csa
report=[];images=[]
for name,r in assets.items():
    w,h,rgba,csa=decode(r);png(O/(name+'.png'),w,h,rgba);(O/(name+'.rgba')).write_bytes(rgba);images.append((w,h,rgba));report.append(dict(name=name,width=w,height=h,csa=csa,alpha_min=min(rgba[3::4]),alpha_max=max(rgba[3::4]),source_sha256=r['gs_upload']['sha256']))
# Contact sheet composites against dark grey, enlarging nearest-neighbour so
# palette mistakes and swizzling artifacts are obvious without game testing.
w,h=768,256;sheet=bytearray(w*h*4)
for i,(iw,ih,p) in enumerate(images):
    for y in range(256):
        for x in range(256):
            a=(min(ih-1,y*ih//256)*iw+min(iw-1,x*iw//256))*4;r,g,b,alpha=p[a:a+4];bg=32 if ((x//16+y//16)&1) else 48;off=(y*w+i*256+x)*4;sheet[off:off+4]=bytes((int((r*alpha+bg*(255-alpha))/255),int((g*alpha+bg*(255-alpha))/255),int((b*alpha+bg*(255-alpha))/255),255))
png(O/'contact-sheet.png',w,h,sheet);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
