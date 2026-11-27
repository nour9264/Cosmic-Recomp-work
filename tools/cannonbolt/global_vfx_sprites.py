"""Register custom masked sprites in the native global particle texture bank."""
import hashlib,json,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
from extract_discord_level_images import tiled_offset,untile
H = WORK;I=APP_ROOT/'installation';O=H/'reference-vfx';G=I/'game/global/global.xbx';raw=G.read_bytes();parts=entries(raw);rows=m.vaps_rows(parts[0]);existing={k for k,f,v in rows}
cb=(O/'g_cb.xbx').read_bytes();cp=entries(cb);keys={m.crc(s) for s in ('ucb_rock_masked_a','ucb_rock_masked_b','ucb_dust_masked','ucb_air_funnel_masked')};assert not keys&existing
cr=m.vaps_rows(cp[0]);taken=[]
for k,f,v in cr:
    if k not in keys:continue
    w,h=struct.unpack_from('>HH',v,6);assert w==h and struct.unpack_from('>H',v,4)[0]==0x102
    d=w//4;bc3=untile(v[128:],d,d,4);bc1=bytearray(8192)
    for y in range(d):
        for x in range(d):
            at=(y*d+x)*16;dest=tiled_offset(x,y,d,3);assert dest+8<=len(bc1);bc1[dest:dest+8]=bc3[at+8:at+16]
    head=bytearray(v[:128]);struct.pack_into('>IH',head,0,0x90434000,0x104);rows.append((k,4,bytes(head)+bc1));taken.append(k)
assert set(taken)==keys
parts[0]=m.build_vaps(0,struct.unpack_from('>H',parts[0],12)[0],m.bucket_sorted(rows));result=m.package(raw,parts);check=entries(result);assert all(check[k]==v for k,v in entries(raw).items() if k!=0);assert all(m.table(check[0])[k]==v for k,v in m.table(entries(raw)[0]).items());assert keys<=set(m.table(check[0]))
# Avoid duplicate keys across global and character archives.
cp[0]=m.build_vaps(0,struct.unpack_from('>H',cp[0],12)[0],m.bucket_sorted([r for r in cr if r[0] not in keys]));newcb=m.package(cb,cp);assert all(entries(newcb)[k]==v for k,v in entries(cb).items() if k!=0)
(O/'global.xbx').write_bytes(result);(O/'g_cb-global-sprites.xbx').write_bytes(newcb)
report=dict(old_global_sha=hashlib.sha256(raw).hexdigest(),registered=[hex(k) for k in taken],native_format='BC1/0x104',other_global_sections_preserved=True,gameplay_verified=False);(O/'global-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
