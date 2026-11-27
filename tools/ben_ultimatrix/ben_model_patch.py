"""Put Ben's new Ultimatrix model into a player's level banks (no Blender needed).

`build_ben_ultimatrix_assets.py` makes the new model in Blender and rebuilds every level bank. The finished model is the same
in every level except for values it copies from that level's own stock Ben records, so the finished vertices, indices and
texture can be shipped (`extract`) and combined with the player's own stock records (`apply_level`) on any machine:

    python tools/ben_ultimatrix/ben_model_patch.py extract --installation <working install> --out <patch folder>
    python tools/ben_ultimatrix/ben_model_patch.py apply --game <installation>/game --patch <patch folder>

The patch holds only the owner's new mesh data and texture (vertices.bin, indices.bin, texture.bin, params.json). Applying it
replaces three records in place in l_*.xbx (skin), l_*_d.xbx (mesh) and l_*_t.xbx (texture); everything else is untouched, and a
level that already has the model is skipped.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_vilgax_import as m  # noqa: E402
from convert_four_arms_meshes import mesh_buffers  # noqa: E402
from merge_alien_streams import entries  # noqa: E402

OLD_MESH = 0x1bf4b1d1
OLD_TEX = 0x14934253
STOCK_VERTICES = 4970
BODY_N = 4656
NEW_VERTICES = 10089


def vaps_rows_with_offsets(raw):
    count = struct.unpack_from('>I', raw, 36)[0]
    directory = 32 + struct.unpack_from('>I', raw, 44)[0]
    return struct.iter_unpack('>3I', raw[directory:directory + count * 12])


def replace_rows(raw, replacements):
    """Same vaps bank, same directory and physical order; only the named records change."""
    count, rec_off, base, align_log = (struct.unpack_from('>I', raw, 36)[0], struct.unpack_from('>I', raw, 44)[0],
                                       struct.unpack_from('>I', raw, 28)[0], struct.unpack_from('>H', raw, 12)[0])
    d0 = 32 + rec_off
    align = 1 << align_log
    rows = [list(struct.unpack_from('>III', raw, d0 + i * 12)) for i in range(count)]
    payload, done = bytearray(), set()
    for i in sorted(range(count), key=lambda i: rows[i][2]):
        key, info, off = rows[i]
        data = replacements.get(key, raw[base + off:base + off + (info & 0xffffff)])
        if key in replacements:
            done.add(key)
        payload += bytes((-len(payload)) % align)
        rows[i] = [key, (info & 0xff000000) | len(data), len(payload)]
        payload += data
    payload += bytes((-len(payload)) % align)
    assert done == set(replacements)
    out = bytearray(raw[:base])
    struct.pack_into('>I', out, 16, len(payload))
    for i, row in enumerate(rows):
        struct.pack_into('>III', out, d0 + i * 12, *row)
    out += payload
    assert len(m.vaps_rows(bytes(out))) == count
    return bytes(out)


def row(blob, key):
    return next(d for k, _, d in m.vaps_rows(blob) if k == key)


def make_mesh(stock, patch):
    vertices, indices, green = patch['vertices'], patch['indices'], patch['green_indices']
    header = bytearray(stock[:512])
    address = struct.unpack_from('<I', header, 28)[0]
    index_at = (512 + len(vertices) + 31) & ~31
    struct.pack_into('>I', header, 4, len(vertices) // 44)
    struct.pack_into('<I', header, 12, address + 512 - 376)
    struct.pack_into('>I', header, 16, len(indices) // 2)
    struct.pack_into('<I', header, 20, address + index_at - 376)
    struct.pack_into('>H', header, 468, green)
    struct.pack_into('>I', header, 488, OLD_TEX)
    assert struct.unpack_from('>I', stock, 488)[0] == OLD_TEX and struct.unpack_from('>H', stock, 466)[0] == 22914
    out = bytes(header) + vertices + bytes(index_at - 512 - len(vertices)) + indices
    assert mesh_buffers(out, xbox=True)[1:] == (vertices, indices)
    return out


def chest_vertices(stock_mesh):
    """The stock vertices above the body (chest piece) that the new mesh keeps, in index order."""
    _, _, indices = mesh_buffers(stock_mesh, xbox=True)
    ids = struct.unpack(f'>{len(indices) // 2}H', indices)
    return sorted({v for v in ids[:22914] if v >= 4921})


def make_skin(stock_skin, stock_mesh, patch):
    """Weights of the stock skin carried over to the new vertices; the device is rigid on the forearm bone (26)."""
    vertices = patch['vertices']
    count = len(vertices) // 44
    chest = chest_vertices(stock_mesh)
    base = BODY_N + len(chest)
    out = bytearray(stock_skin[:80])
    struct.pack_into('>II', out, 72, count, count)
    s0 = stock_skin[80:]
    for index in range(count):
        src = index if index < BODY_N else chest[index - BODY_N] if index < base else None
        if src is not None:
            weights, bones = list(s0[src * 52 + 44:src * 52 + 48]), list(s0[src * 52 + 48:src * 52 + 52])
        else:
            weights, bones = [255, 0, 0, 0], [26, 0, 0, 0]
        merged = {}
        for weight, bone in zip(weights, bones):
            if weight:
                key = 26 if bone in (34, 35) else bone
                merged[key] = merged.get(key, 0) + weight
        top = sorted(merged.items(), key=lambda kv: -kv[1])[:4]
        w2 = [x[1] for x in top] + [0] * (4 - len(top))
        b2 = [x[0] for x in top] + [0] * (4 - len(top))
        assert sum(w2) == sum(weights)
        out += vertices[index * 44:(index + 1) * 44] + bytes(w2) + bytes(b2)
    return bytes(out)


def load_patch(folder):
    folder = Path(folder)
    params = json.loads((folder / 'params.json').read_text(encoding='utf-8'))
    return {'vertices': (folder / 'vertices.bin').read_bytes(), 'indices': (folder / 'indices.bin').read_bytes(),
            'texture': (folder / 'texture.bin').read_bytes(), 'green_indices': params['green_indices']}


def apply_level(level, patch):
    """(l_x.xbx, l_x_d.xbx, l_x_t.xbx) bytes for a level that still has the stock Ben, or None when it already has the model."""
    main_raw = (level / f'{level.name}.xbx').read_bytes()
    draw_raw = (level / f'{level.name}_d.xbx').read_bytes()
    texture_raw = (level / f'{level.name}_t.xbx').read_bytes()
    stock_mesh = row(draw_raw, OLD_MESH)
    if struct.unpack_from('>I', stock_mesh, 4)[0] == len(patch['vertices']) // 44:
        return None
    assert struct.unpack_from('>I', stock_mesh, 4)[0] == STOCK_VERTICES, 'unexpected Ben mesh'
    sections = entries(main_raw)
    skin = make_skin(row(sections[22], OLD_MESH), stock_mesh, patch)
    order = [k for k, _, _ in sorted(vaps_rows_with_offsets(main_raw), key=lambda r: r[2])]
    sections[22] = replace_rows(sections[22], {OLD_MESH: skin})
    return (m.package(main_raw, sections, order), replace_rows(draw_raw, {OLD_MESH: make_mesh(stock_mesh, patch)}),
            replace_rows(texture_raw, {OLD_TEX: patch['texture']}))


def levels_of(game):
    return sorted(p for p in Path(game).glob('l_*') if (p / f'{p.name}.xbx').is_file() and (p / f'{p.name}_d.xbx').is_file())


def apply_all(game, patch_folder):
    patch = load_patch(patch_folder)
    done = []
    for level in levels_of(game):
        result = apply_level(level, patch)
        if result is None:
            continue
        for suffix, data in zip(('', '_d', '_t'), result):
            path = level / f'{level.name}{suffix}.xbx'
            backup = path.with_name(path.name + '.cosmic-before-ben-model')
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            temporary = path.with_name(path.name + '.cosmic-new')
            temporary.write_bytes(data)
            temporary.replace(path)
        done.append(level.name)
    return done


def extract(level, out):
    """Write the patch from one level of a working installation."""
    draw = (level / f'{level.name}_d.xbx').read_bytes()
    mesh = row(draw, OLD_MESH)
    _, vertices, indices = mesh_buffers(mesh, xbox=True)
    assert len(vertices) // 44 == NEW_VERTICES
    out.mkdir(parents=True, exist_ok=True)
    (out / 'vertices.bin').write_bytes(vertices)
    (out / 'indices.bin').write_bytes(indices)
    (out / 'texture.bin').write_bytes(row((level / f'{level.name}_t.xbx').read_bytes(), OLD_TEX))
    (out / 'params.json').write_text(json.dumps({'green_indices': struct.unpack_from('>H', mesh, 468)[0],
                                                 'vertices': NEW_VERTICES}, indent=1) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    e = sub.add_parser('extract')
    e.add_argument('--installation', type=Path, required=True)
    e.add_argument('--out', type=Path, required=True)
    a = sub.add_parser('apply')
    a.add_argument('--game', type=Path, required=True)
    a.add_argument('--patch', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'extract':
        extract(args.installation / 'game' / 'l_mili', args.out)
        print('Patch written to', args.out)
    else:
        done = apply_all(args.game, args.patch)
        print('Ben model installed in:', ', '.join(done) if done else 'nothing to do')


if __name__ == '__main__':
    main()
