"""Extract source VFX dependency records from the locally owned PS2 player wad.

The raw indexed GS upload packets are retained unchanged; decoding their
pixel layout is a separate step, not a claim of a successful texture port.
"""
import hashlib,json,struct
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
H = WORK; O=H/'original-vfx-assets';O.mkdir(exist_ok=True)
b=(H/'99_95.stream1.bin').read_bytes(); sha=lambda p:hashlib.sha256(p).hexdigest()
def u(p):return struct.unpack_from('<I',b,p)[0]
def write(name,p,n):
    assert 0<=p<p+n<=len(b);v=b[p:p+n];(O/name).write_bytes(v);return dict(offset=hex(p),bytes=n,sha256=sha(v),file=name)
records=[]
for name,mesh,mat,texref,texture,palette in [
    ('Cyclone',0x2361b0,0x56e40,0x55c20,0x517a00,0x54aa0),
    ('Rock9',0x26b4d0,0x57660,None,0x5ef2e0,0x54aa0),
    ('DustPoof',0x298130,0x57920,None,0x61c980,0x478a0),
]:
    assert b[mesh:mesh+16].split(b'\0')[0].decode()==name
    assert u(mesh+52)==mat
    if texref is not None:
        assert u(mat+8)==texref and u(texref+64)==texture
    else:assert u(mat+8)==texture
    assert palette in struct.unpack_from('<16I',b,texture)
    fmt=(u(texture+12)>>16)&255;assert fmt in (0x13,0x14)
    if texref is not None: mip=texture+48;w,h=u(mip+8),u(mip+12);transfer=u(mip+16)
    else:mip=u(texture+60);w,h=u(mip+8),u(mip+12);transfer=u(mip+16)
    assert w in (32,64,128,256) and h in (32,64,128,256)
    # The packet is bounded by the first GIF image transfer tag: the NLOOP
    # field gives the number of 16-byte image data units in the upload.
    # Source layouts can include DMA/GIF headers; preserve all bytes until
    # exactly the declared image data ends.
    tag=transfer+16; q=u(tag)&0x7fff;assert 0<q<4096
    packet_bytes=32+q*16
    pal_transfer=u(palette+40);assert 0<pal_transfer<len(b)
    pal_q=u(pal_transfer+16)&0x7fff;assert 0<pal_q<4096
    records.append(dict(name=name,format=hex(fmt),width=w,height=h,
        mesh_header=write(name+'-mesh-header.bin',mesh,64),material=write(name+'-material.bin',mat,32),
        texture_header=write(name+'-texture-header.bin',texture,64),
        gs_upload=write(name+'-gs-upload.bin',transfer,packet_bytes),
        palette_upload=write(name+'-palette-upload.bin',pal_transfer,32+pal_q*16),pixel_layout_verified=False))
assert b[0xe6040:0xe6040+32].split(b'\0')[0]==b'cycloneanim'
anim=write('cycloneanim-record.bin',0xe6040,0x170)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256=sha(b),assets=records,cyclone_animation=anim,gameplay_installed=False),indent=2))
for r in records:print(r['name'],r['width'],r['height'],r['format'],r['gs_upload']['bytes'],r['palette_upload']['bytes'])
