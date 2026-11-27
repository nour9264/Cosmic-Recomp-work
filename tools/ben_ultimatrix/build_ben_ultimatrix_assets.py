"""Stage Ben's new in-game model: body (modified cuff) + original chest piece + the new Ultimatrix.
Resources are REPLACED IN PLACE (the registry only finds keys the game already knows): Ben's mesh (l_*_d.xbx), skin (l_*.xbx) and texture (l_*_t.xbx) in every level bank.
Run: blender -b -P tools/ben_ultimatrix/build_ben_ultimatrix_assets.py -- <variant> [--export-dir D] [--banks D] [--output D]
variant = green | albedo  (the albedo variant only produces the recoloured texture record).
"""
import argparse, sys, struct, json, math, hashlib
from pathlib import Path
import numpy as np
import bpy
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
from convert_four_arms_meshes import mesh_buffers
from extract_discord_level_images import tiled_offset
from wheel_icon_texture import encode_block


def vaps_rows_with_offsets(raw):
    count = struct.unpack_from('>I', raw, 36)[0]
    directory = 32 + struct.unpack_from('>I', raw, 44)[0]
    return struct.iter_unpack('>3I', raw[directory:directory + count * 12])


# Arguments follow Blender's own: blender -b -P build_ben_ultimatrix_assets.py -- green|albedo [--export-dir D] [--banks D] [--output D]
parser = argparse.ArgumentParser()
parser.add_argument('variant', choices=['green', 'albedo'])
parser.add_argument('--export-dir', type=Path, default=ROOT / 'build/ben-ultimatrix/game-export',
                    help='Blender exports: device_v4.png, real_color(.png/_albedo.png), bolts_piece_tex.png, ben_device_export.json, ben_realistic_export.json, bolts_piece_wrist.json')
parser.add_argument('--banks', type=Path, default=ROOT / 'build/ben-ultimatrix/original-banks',
                    help='A pristine copy of the game folder holding l_*/l_*_(d|t).xbx (never the installed, already replaced banks)')
parser.add_argument('--output', type=Path, default=ROOT / 'build/ben-ultimatrix/staged')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
EXP = args.export_dir; G = args.banks; OUT = args.output; OUT.mkdir(parents=True, exist_ok=True)
OLD_MESH = 0x1bf4b1d1; OLD_TEX = 0x14934253
NEW_MESH = OLD_MESH; NEW_TEX = OLD_TEX; NEW_TEX_ALBEDO = OLD_TEX     # replaced in place: the registry only finds keys the game already knows
SIZE = 2048; CONTENT_W = 410; REAL_X = 432; REAL_W = SIZE - REAL_X; PIECE_X = 440; PIECE_Y = REAL_W + 2; PIECE_W = 214; PIECE_H = SIZE - PIECE_Y
variant = args.variant

def load_rgba(path):
    im = bpy.data.images.load(str(path), check_existing=False); w, h = im.size
    a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a); return a.reshape(h, w, 4)[::-1].copy(), w, h   # top-down

def build_canvas(albedo):
    dev, w, h = load_rgba(EXP / 'device_v4.png')
    # downscale 1024x5120 -> 410x2048 (area average via 2 box passes then bilinear)
    t = bpy.data.images.new('tmp', w, h, alpha=True); t.pixels.foreach_set(dev[::-1].reshape(-1)); t.scale(CONTENT_W, SIZE)
    a = np.empty(CONTENT_W * SIZE * 4, np.float32); t.pixels.foreach_get(a); small = a.reshape(SIZE, CONTENT_W, 4)[::-1]
    canvas = np.zeros((SIZE, SIZE, 4), np.float32); canvas[..., 3] = 1
    canvas[:, :CONTENT_W, :3] = small[..., :3]
    if albedo:                                                                  # same rule the game uses for Albedo recolours (green strip only)
        r, g, b = canvas[..., 0] * 255, canvas[..., 1] * 255, canvas[..., 2] * 255
        mask = (g > r + 12) & (g > b + 12)
        nr = np.where(mask, g, r); ng = np.where(mask, np.floor(r / 3), g)
        canvas[..., 0] = nr / 255; canvas[..., 1] = ng / 255
    # Realistic Ultimatrix atlas (base colour + emissive baked in Blender), RW px square at (REAL_X, 0)
    real, rw, rh = load_rgba(EXP / ('real_color_albedo.png' if albedo else 'real_color.png'))
    t2 = bpy.data.images.new('tmp2', rw, rh, alpha=True); t2.pixels.foreach_set(real[::-1].reshape(-1)); t2.scale(REAL_W, REAL_W)
    a2 = np.empty(REAL_W * REAL_W * 4, np.float32); t2.pixels.foreach_get(a2); rs = a2.reshape(REAL_W, REAL_W, 4)[::-1]
    canvas[:REAL_W, REAL_X:REAL_X + REAL_W, :3] = rs[..., :3]
    canvas[:REAL_W, CONTENT_W:REAL_X, :3] = rs[:, :1, :3]                       # gutter so mips do not mix the two atlases
    canvas[REAL_W:, CONTENT_W:, :3] = canvas[REAL_W - 1:REAL_W, CONTENT_W:, :3]
    # Bolts Tears piece texture (256x512) below the realistic atlas
    pc, pw0, ph0 = load_rgba(EXP / 'bolts_piece_tex.png')
    t3 = bpy.data.images.new('tmp3', pw0, ph0, alpha=True); t3.pixels.foreach_set(pc[::-1].reshape(-1)); t3.scale(PIECE_W, PIECE_H)
    a3 = np.empty(PIECE_W * PIECE_H * 4, np.float32); t3.pixels.foreach_get(a3); ps = a3.reshape(PIECE_H, PIECE_W, 4)[::-1].copy()
    if albedo:                                                                  # the same green -> red rule as the body strip
        pr, pg, pb = ps[..., 0] * 255, ps[..., 1] * 255, ps[..., 2] * 255
        pm = (pg > pr + 12) & (pg > pb + 12)
        ps[..., 0] = np.where(pm, pg, pr) / 255; ps[..., 1] = np.where(pm, np.floor(pr / 3), pg) / 255; ps[..., 2] = np.where(pm, np.floor(pb / 4), pb) / 255
    canvas[PIECE_Y:PIECE_Y + PIECE_H, PIECE_X:PIECE_X + PIECE_W, :3] = ps[..., :3]
    return canvas

def encode_texture(canvas, template, key):
    header = bytearray(template[:128])
    struct.pack_into('>HHBB', header, 6, SIZE, SIZE, 11, 11); struct.pack_into('>I', header, 44, key)
    levels = 5; struct.pack_into('>I', header, 28, levels)
    pages = []; img = canvas[..., :3]; size = SIZE
    for level in range(levels):
        blocks = size // 4; pitch = (blocks + 31) // 32 * 32
        tiled = bytearray(pitch * pitch * 8)
        px = (np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)
        for by in range(blocks):
            row = px[by * 4:by * 4 + 4]
            for bx in range(blocks):
                blk = row[:, bx * 4:bx * 4 + 4].reshape(16, 3)
                pixels = [(int(p[0]), int(p[1]), int(p[2]), 255) for p in blk]
                block = encode_block(pixels)[8:]
                target = tiled_offset(bx, by, pitch, 3)
                tiled[target:target + 8] = bytes(block[i ^ 1] for i in range(8))
        pages.append(bytes(tiled))
        if level + 1 < levels:
            img = (img[0::2, 0::2] + img[1::2, 0::2] + img[0::2, 1::2] + img[1::2, 1::2]) / 4; size //= 2
    return bytes(header) + b''.join(pages)

def tangents(pos, nrm, uv, tris):
    tan = np.zeros_like(pos)
    for a, b, c in tris:
        dp1, dp2 = pos[b] - pos[a], pos[c] - pos[a]; du1, dv1 = uv[b] - uv[a]; du2, dv2 = uv[c] - uv[a]
        den = du1 * dv2 - du2 * dv1
        if abs(den) < 1e-12: continue
        t = (dp1 * dv2 - dp2 * dv1) / den
        tan[a] += t; tan[b] += t; tan[c] += t
    out = []
    for p, n, t in zip(pos, nrm, tan):
        t = t - n * np.dot(n, t); ln = np.linalg.norm(t)
        out.append(t / ln if ln > 1e-9 else np.array([1.0, 0, 0]) if abs(n[0]) < .9 else np.array([0, 1.0, 0]))
    return np.array(out)

if variant == 'canvas':
    c = build_canvas(False); im = bpy.data.images.new('c', SIZE, SIZE, alpha=True); im.pixels.foreach_set(c[::-1].reshape(-1)); im.filepath_raw = str(OUT / 'canvas.png'); im.file_format = 'PNG'; im.save(); sys.exit(0)
if variant == 'albedo':
    template = next(d for k, fl, d in m.vaps_rows((G / 'l_mili/l_mili_t.xbx').read_bytes()) if k == OLD_TEX)
    (OUT / 'texture_albedo.bin').write_bytes(encode_texture(build_canvas(True), template, NEW_TEX_ALBEDO))
    print('albedo texture written'); sys.exit(0)

exp = json.load(open(EXP / 'ben_device_export.json'))
body_pos = np.array(exp['body_pos'], np.float64)
dpos = np.array(exp['dev_pos'], np.float64); dnrm = np.array(exp['dev_nrm'], np.float64); duv = np.array(exp['dev_uv'], np.float64); dtri = exp['dev_tri']
# game uv convention: v from top; blender export is bottom-up
duv = np.stack([duv[:, 0] * CONTENT_W / SIZE, 1.0 - duv[:, 1]], 1)
dtan = tangents(dpos, dnrm, duv, dtri)
template_tex = next(d for k, fl, d in m.vaps_rows((G / 'l_mili/l_mili_t.xbx').read_bytes()) if k == OLD_TEX)
texture = encode_texture(build_canvas(False), template_tex, NEW_TEX)
(OUT / 'texture_green.bin').write_bytes(texture)
# ---- mesh + skin from the stock Ben records (identical in every level)
level_d = G / 'l_mili/l_mili_d.xbx'; level_m = G / 'l_mili/l_mili_m.xbx'
rows_d = {k: (fl, d) for k, fl, d in m.vaps_rows(level_d.read_bytes())}
flag_mesh, rec = rows_d[OLD_MESH]
vat, verts, idx = mesh_buffers(rec, xbox=True)
assert vat == 512 and len(verts) == 4970 * 44
V = [list(struct.unpack_from('>11f', verts, i * 44)) for i in range(4970)]
I = list(struct.unpack(f'>{len(idx)//2}H', idx))
BODY_N = 4656; body_idx = I[:22914]; dev_idx = I[22914:]
assert len(dev_idx) == 882 and min(dev_idx) == 4656 and max(dev_idx) == 4920
extras = sorted({v for v in body_idx if v >= 4921})
assert len(extras) == 49 or len(extras) == 48, len(extras)
extra_map = {v: BODY_N + k for k, v in enumerate(extras)}
body_idx = [extra_map.get(v, v) for v in body_idx]
chest_old = extras
chest_tris = []
# body with the tapered cuff / skin (only vertices that moved)
moved = 0
newV = []
for i in range(BODY_N):
    v = V[i][:]; p = body_pos[i]
    if max(abs(p[k] - v[k]) for k in range(3)) > 1e-5: v[0:3] = list(p); moved += 1
    newV.append(v)
for old in chest_old:
    v = V[old][:]
    newV.append(v)
base = len(newV)
for i in range(len(dpos)):
    newV.append(list(dpos[i]) + list(dnrm[i]) + list(dtan[i]) + list(duv[i]))
green_idx = [base + t for tri in dtri for t in tri]
# realistic Ultimatrix (second draw range; the game switches between the two ranges live)
rx = json.load(open(EXP / 'ben_realistic_export.json'))
rpos = np.array(rx['pos'], np.float64); rpos[:, 0] -= 0.0215; REAL_SCALE = 1.138; rc = (rpos.min(0) + rpos.max(0)) / 2; rpos = rc + (rpos - rc) * REAL_SCALE; rnrm = np.array(rx['nrm'], np.float64); ruv = np.array(rx['uv'], np.float64); rtri = rx['tri']
ruv = np.stack([(REAL_X + ruv[:, 0] * REAL_W) / SIZE, (1.0 - ruv[:, 1]) * REAL_W / SIZE], 1)
rtan = tangents(rpos, rnrm, ruv, rtri)
real_base = len(newV)
for i in range(len(rpos)):
    newV.append(list(rpos[i]) + list(rnrm[i]) + list(rtan[i]) + list(ruv[i]))
real_idx = [real_base + t for tri in rtri for t in tri]
# Bolts Tears piece (placed on the wrist device in Blender; the same placement serves the green and the realistic device)
bp = json.load(open(EXP / 'bolts_piece_wrist.json'))
ppos = np.array(bp['pos'], np.float64); pnrm = np.array(bp['nrm'], np.float64); puv = np.array(bp['uv'], np.float64); ptri = bp['tri']; pmat = bp['mat']
BLACK_UV = (180 / 256, 4 / 512)
puv2 = []
for u, v in puv: puv2.append([(PIECE_X + u * PIECE_W) / SIZE, (PIECE_Y + (1 - v) * PIECE_H) / SIZE])
puv2 = np.array(puv2)
for t_i, mi in enumerate(pmat):                                                 # the recessed bevel uses a black texel
    if mi == 1:
        for vi in ptri[t_i]: puv2[vi] = [(PIECE_X + BLACK_UV[0] * PIECE_W) / SIZE, (PIECE_Y + (1 - BLACK_UV[1]) * PIECE_H) / SIZE]
ptan = tangents(ppos, pnrm, puv2, ptri)
piece_base = len(newV)
for i in range(len(ppos)): newV.append(list(ppos[i]) + list(pnrm[i]) + list(ptan[i]) + list(puv2[i]))
piece_idx = [piece_base + t for tri in ptri for t in tri]
# index buffer after the body: [green][piece][realistic][piece]  ->  green = (g), green+piece = (g+p), realistic = (r), realistic+piece = (r+p)
indices = body_idx + green_idx + piece_idx + real_idx + piece_idx
assert max(indices) < len(newV) < 65536
vbytes = b''.join(struct.pack('>11f', *v) for v in newV)
ibytes = struct.pack(f'>{len(indices)}H', *indices)
def make_mesh(rec):
    header = bytearray(rec[:512]); address = struct.unpack_from('<I', header, 28)[0]
    index_at = (512 + len(vbytes) + 31) & ~31
    struct.pack_into('>I', header, 4, len(newV)); struct.pack_into('<I', header, 12, address + 512 - 376)
    struct.pack_into('>I', header, 16, len(indices)); struct.pack_into('<I', header, 20, address + index_at - 376)
    struct.pack_into('>H', header, 468, len(green_idx))             # draw 2: the green Ultimatrix; the realistic one follows it in the index buffer
    struct.pack_into('>I', header, 488, NEW_TEX)
    assert struct.unpack_from('>I', rec, 488)[0] == OLD_TEX and struct.unpack_from('>H', rec, 466)[0] == 22914
    out = bytes(header) + vbytes + bytes(index_at - 512 - len(vbytes)) + ibytes
    assert mesh_buffers(out, xbox=True)[1:] == (vbytes, ibytes)
    return out
new_mesh = make_mesh(rec)# ---- skin: weights identical to the stock skin, device rigid on the forearm bone (26); bones 34/35 (core raise) folded into 26
def skin_for(stock):
    out = bytearray(stock[:80]); struct.pack_into('>II', out, 72, len(newV), len(newV))
    s0 = stock[80:]
    for v_i, v in enumerate(newV):
        if v_i < BODY_N: src = v_i
        elif v_i < base: src = chest_old[v_i - BODY_N]
        else: src = None
        vb = struct.pack('>11f', *v)
        if src is not None:
            w = list(s0[src * 52 + 44:src * 52 + 48]); ix = list(s0[src * 52 + 48:src * 52 + 52])
        else: w = [255, 0, 0, 0]; ix = [26, 0, 0, 0]
        acc = {}
        for wi, bi in zip(w, ix):
            if wi: acc[26 if bi in (34, 35) else bi] = acc.get(26 if bi in (34, 35) else bi, 0) + wi
        items = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
        w2 = [x[1] for x in items] + [0] * (4 - len(items)); ix2 = [x[0] for x in items] + [0] * (4 - len(items))
        assert sum(w2) == sum(w), (v_i, w, ix, w2)
        out += vb + bytes(w2) + bytes(ix2)
    return bytes(out)
import hashlib
def replace_rows(raw, replacements):
    """Same vaps bank, same directory/buckets/physical order; only the named records change."""
    count, rec_off, base, align_log = struct.unpack_from('>I', raw, 36)[0], struct.unpack_from('>I', raw, 44)[0], struct.unpack_from('>I', raw, 28)[0], struct.unpack_from('>H', raw, 12)[0]
    d0 = 32 + rec_off; align = 1 << align_log
    rows = [list(struct.unpack_from('>III', raw, d0 + i * 12)) for i in range(count)]
    payload = bytearray(); done = set()
    for i in sorted(range(count), key=lambda i: rows[i][2]):
        key, info, off = rows[i]
        data = replacements.get(key, raw[base + off:base + off + (info & 0xffffff)])
        if key in replacements: done.add(key)
        payload += bytes((-len(payload)) % align)
        rows[i] = [key, (info & 0xff000000) | len(data), len(payload)]
        payload += data
    payload += bytes((-len(payload)) % align)
    assert done == set(replacements)
    out = bytearray(raw[:base]); struct.pack_into('>I', out, 16, len(payload))
    for i, r in enumerate(rows): struct.pack_into('>III', out, d0 + i * 12, *r)
    out += payload
    chk = {(k, f): d for k, f, d in m.vaps_rows(bytes(out))}
    assert len(m.vaps_rows(bytes(out))) == count
    return bytes(out)

levels_done = []; meshes = set()
levels = sorted(p.name for p in G.glob('l_*') if (p / (p.name + '.xbx')).is_file())
for level in levels:
    f = G / level / (level + '.xbx'); raw = f.read_bytes(); sections = entries(raw)
    stock = next((d for k, fl, d in m.vaps_rows(sections[22]) if k == OLD_MESH), None)
    if stock is None: print('skip', level); continue
    order = [k for k, _, _ in sorted(vaps_rows_with_offsets(raw), key=lambda r: r[2])]
    sections[22] = replace_rows(sections[22], {OLD_MESH: skin_for(stock)})
    (OUT / (level + '.xbx')).write_bytes(m.package(raw, sections, order))
    d = G / level / (level + '_d.xbx'); t = G / level / (level + '_t.xbx')
    draw = d.read_bytes(); stock_mesh = next(x for k, fl, x in m.vaps_rows(draw) if k == OLD_MESH); meshes.add(hashlib.sha256(stock_mesh).hexdigest())
    (OUT / (level + '_d.xbx')).write_bytes(replace_rows(draw, {OLD_MESH: make_mesh(stock_mesh)}))
    (OUT / (level + '_t.xbx')).write_bytes(replace_rows(t.read_bytes(), {OLD_TEX: texture}))
    levels_done.append(level)
(OUT / 'manifest.json').write_text(json.dumps({'mesh': NEW_MESH, 'texture': NEW_TEX, 'texture_albedo': NEW_TEX_ALBEDO, 'levels': levels_done,
    'verts': len(newV), 'indices': len(indices), 'green_start': 22914, 'green_count': len(green_idx), 'piece_count': len(piece_idx), 'real_start': 22914 + len(green_idx) + len(piece_idx), 'real_count': len(real_idx), 'body_vertices_moved': moved}, indent=1))
print('staged', len(levels_done), 'levels; verts', len(newV), 'tris', len(indices) // 3, 'moved body verts', moved)










