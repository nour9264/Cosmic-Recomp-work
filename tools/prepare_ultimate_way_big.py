"""Stage locally generated Ultimate Way Big resources for the Final Battle."""
import argparse
from pathlib import Path
import struct
import wave

from convert_four_arms_meshes import mesh_buffers
from extract_discord_level_images import tiled_offset
from merge_alien_streams import entries
from prepare_ultimate_cannonbolt import constant_game_texture
from prepare_vilgax_import import bank, crc, package, vaps_rows
from wheel_icon_texture import encode_block, read_png

NORMAL = 0x288341a8
# A native skinned character in the final battle bank with two unlit draws.
UNLIT_DONOR = 0x70ef15f2
FORMS = ('ben', 'albedo')
MESH_KEYS = {mode: crc('ultimate_way_big_mesh_' + mode) for mode in FORMS}
DIFFUSE_KEYS = {mode: crc('ultimate_way_big_diffuse_' + mode) for mode in FORMS}
SHADING_MAPS = (
    (436, 0xcf33e5e9, crc('ultimate_way_big_soft_specular'), (28, 28, 28)),
    (452, 0x4bab9d0e, crc('ultimate_way_big_flat_normal'), (128, 128, 255)),
)
# The exported atlas uses display-space colors. Match the stock Xbox atlas'
# light body colors (around 130–140) before the original shader adds lighting.
DIFFUSE_SCALE = 0.55


def way_big_texture(rgb, template, key):
    """Encode the 512-square palette and every mip declared by the donor."""
    size = 512
    assert len(rgb) == size * size * 3
    header = bytearray(template[:128])
    struct.pack_into('>HHBB', header, 6, size, size, 9, 9)
    struct.pack_into('>I', header, 44, key)
    levels, = struct.unpack_from('>I', header, 28)
    # The 32-pixel level is the last standalone level declared by this header.
    if levels != 5:
        raise ValueError(f'Unexpected Way Big mip count: {levels}')
    pages = []
    for level in range(levels):
        blocks = size // 4
        pitch = (blocks + 31) // 32 * 32
        tiled = bytearray(pitch * pitch * 8)
        for by in range(blocks):
            for bx in range(blocks):
                at = (by * size + bx) * 12
                pixels = [(*rgb[p:p+3], 255)
                          for y in range(4)
                          for p in range(at+y*size*3, at+y*size*3+12, 3)]
                block = encode_block(pixels)[8:]
                target = tiled_offset(bx, by, pitch, 3)
                tiled[target:target+8] = bytes(block[i ^ 1] for i in range(8))
        pages.append(tiled)
        if level + 1 < levels:
            row = size * 3
            rgb = bytes((rgb[i+c]+rgb[i+c+3]+rgb[i+c+row]+rgb[i+c+row+3]+2)//4
                        for y in range(0, size, 2) for i in range(y*row, (y+1)*row, 6)
                        for c in range(3))
            size //= 2
    return bytes(header) + b''.join(pages)


def palette_pixels(path, eye_cell):
    width, height, rgba = read_png(path)
    if (width, height) != (512, 512):
        raise ValueError('Expected a 512-square Way Big palette')
    rgb = bytearray(len(rgba) // 4 * 3)
    for i in range(width * height):
        scale = 1.0 if (i % width // 64, i // width // 64) == eye_cell else DIFFUSE_SCALE
        rgb[3*i:3*i+3] = bytes(round(channel*scale) for channel in rgba[4*i:4*i+3])
    return rgb


def specular_texture(assets, palette_template, specular_template, key, color, eye_cell):
    mask_file = assets / 'gill-mask.png'
    if mask_file.is_file():
        width, height, mask = read_png(mask_file)
        if (width, height) != (512, 512):
            raise ValueError('Expected the gill mask to match the palette')
        rgb = bytes(round(channel * (1-mask[i]/255)) for i in range(0, len(mask), 4)
                    for channel in color)
        return way_big_texture(rgb, palette_template, key)
    file = assets / 'gill-swatch.txt'
    if not file.is_file():
        return constant_game_texture(specular_template, key, color)
    gill = int(file.read_text(encoding='ascii'))
    if not 0 <= gill < 64 or (gill % 8, gill // 8) == eye_cell:
        raise ValueError('Invalid Ultimate Way Big gill swatch')
    # Keep the suit's lighting and remove highlights inside the gills.
    rgb = bytearray(bytes(color) * (512 * 512))
    for y in range(64):
        value = round(color[0] * (1 - min(1, max(0, (y - 15) / 24))))
        start = (((gill // 8 * 64 + y) * 512) + gill % 8 * 64) * 3
        rgb[start:start+64*3] = bytes((value,)) * (64*3)
    return way_big_texture(rgb, palette_template, key)


def add_records(raw, additions):
    original = vaps_rows(raw)
    rows = {k: data for k, _, data in original}
    if len(rows) != len(original) or rows.keys() & additions.keys():
        raise ValueError('Expected original bank with unique Way Big resource IDs')
    flags = {id(data): flag for _, flag, data in original}
    for key, (data, flag) in additions.items():
        flags[id(data)] = flag
        rows[key] = data
    part = struct.unpack_from('>I', raw, 20)[0]
    alignment = struct.unpack_from('>H', raw, 12)[0]
    result = bank(part, alignment, rows, lambda data: flags[id(data)])
    assert {key:(flag,data) for key,flag,data in vaps_rows(result)} == {
        key:(flags[id(data)],data) for key,data in rows.items()
    }
    return result

def replacement(raw, vertices, indices, count, texture, eye_indices=0, unlit=None):
    vertex_at, _, _ = mesh_buffers(raw, xbox=True)
    assert vertex_at == 512 and raw[:2] == b'\0\2'
    assert struct.unpack_from('>I', raw, 404)[0] == 0x232235c2
    # The game finds the vertex stream at the first 32-byte boundary after
    # the declared draw commands. The retained body command ends at 460.
    command_end = 460
    header = bytearray(raw[:command_end])
    body_indices = len(indices)//2 - eye_indices
    struct.pack_into('>H', header, 0, 2 if eye_indices else 1)
    struct.pack_into('>H', header, 384, body_indices)
    struct.pack_into('>I', header, 404, texture)
    for operand, donor_key, key, _ in SHADING_MAPS:
        if struct.unpack_from('>I', header, operand)[0] != donor_key:
            raise ValueError(f'Unexpected Way Big shader map at {operand}')
        struct.pack_into('>I', header, operand, key)
    if eye_indices:
        # The eyes are the last range of the same skinned vertex buffer.
        # Reuse the game's unlit geometry pass, including its vertex layout.
        draw = bytearray(unlit[412:448])
        if (unlit[:4] != raw[:4] or draw[:12] != bytes.fromhex('000000020060209a01681901')
                or struct.unpack_from('>I', draw, 20)[0] != 1):
            raise ValueError('Unexpected native unlit draw')
        struct.pack_into('>HH', draw, 6, body_indices, eye_indices)
        draw[16:20] = raw[476:480]  # Way Big's second material slot.
        struct.pack_into('>I', draw, 28, texture)
        header.extend(draw)
    header.extend(bytes((-len(header)) % 32))
    address, = struct.unpack_from('<I', header, 28)
    index_at = (len(header)+len(vertices)+31)&~31
    struct.pack_into('>I', header, 4, count)
    struct.pack_into('<I', header, 12, address+len(header)-376)
    struct.pack_into('>I', header, 16, len(indices)//2)
    struct.pack_into('<I', header, 20, address+index_at-376)
    result = bytes(header + vertices + bytes(index_at-len(header)-len(vertices)) + indices)
    assert mesh_buffers(result, xbox=True)[1:] == (vertices, indices)
    return result, len(header)//32

def prepare(level, assets, output, voice):
    model_bank = (level/'l_tokd_d.xbx').read_bytes()
    texture_bank = (level/'l_tokd_t.xbx').read_bytes()
    resident = (level/'l_tokd.xbx').read_bytes()
    sections = entries(resident)
    models = {key: data for key, _, data in vaps_rows(model_bank)}
    model = models[NORMAL]
    stock_textures = {key: data for key, _, data in vaps_rows(texture_bank)}
    texture = stock_textures[0x232235c2]
    donor_skin = next(data for key, _, data in vaps_rows(sections[22]) if key==NORMAL)
    blob = (assets/'mesh-export.bin').read_bytes()
    vertices, indices = struct.unpack_from('>II', blob)
    assert len(blob)==8+vertices*96+indices*2
    assert 0<vertices<65536 and 0<indices<65536 and indices%3==0
    raw = blob[8:8+vertices*44]
    skin_data = blob[8+44*vertices:8+96*vertices]
    for index in range(vertices):
        at = index*52
        assert skin_data[at:at+44]==raw[index*44:(index+1)*44]
        assert sum(skin_data[at+44:at+48])==255 and max(skin_data[at+48:at+52])<54
    skin_header = bytearray(donor_skin[:80])
    struct.pack_into('>II',skin_header,72,vertices,vertices)
    model_add, skin_add, texture_add = {}, {}, {}
    eye_file = assets / 'eye-swatch.txt'
    eye_cell = None
    if eye_file.is_file():
        eye = int(eye_file.read_text(encoding='ascii'))
        if not 0 <= eye < 64:
            raise ValueError('Invalid Ultimate Way Big eye swatch')
        eye_cell = (eye % 8, eye // 8)
    eye_range = assets / 'eye-index-count.txt'
    eye_indices = int(eye_range.read_text(encoding='ascii')) if eye_range.is_file() else 0
    if not 0 <= eye_indices < indices or eye_indices % 3 or (eye_indices and eye_cell is None):
        raise ValueError('Invalid Ultimate Way Big eye draw range')
    (_, specular_donor, specular_key, color), (_, normal_donor, normal_key, normal_rgb) = SHADING_MAPS
    specular = specular_texture(assets, texture, stock_textures[specular_donor], specular_key, color, eye_cell)
    texture_add[specular_key] = (specular, 4)
    texture_add[normal_key] = (constant_game_texture(stock_textures[normal_donor], normal_key, normal_rgb), 4)
    for mode in FORMS:
        key = MESH_KEYS[mode]
        model_add[key]=replacement(model,raw,blob[8+96*vertices:],vertices,DIFFUSE_KEYS[mode],
                                   eye_indices, models[UNLIT_DONOR] if eye_indices else None)
        skin_add[key]=(bytes(skin_header)+skin_data,0)
        diffuse = way_big_texture(palette_pixels(assets/f'{mode}.png', eye_cell), texture, DIFFUSE_KEYS[mode])
        texture_add[DIFFUSE_KEYS[mode]] = (diffuse, 4)
    # The level's _d/_t archives are streamed resources. Use the resident
    # Way Big character bank for our additional model and diffuse records.
    character = (level/'g_wayb.xbx').read_bytes()
    character_sections = entries(character)
    character_sections[4] = add_records(character_sections[4], model_add)
    character_sections[0] = add_records(character_sections[0], texture_add)
    character_order = [key for key, _, _ in sorted(
        vaps_rows_with_offsets(character), key=lambda row: row[2])]
    sections[22]=add_records(sections[22],skin_add)
    order = [key for key,_,_ in sorted(vaps_rows_with_offsets(resident),key=lambda row:row[2])]
    output.mkdir(parents=True,exist_ok=True)
    for name,data in {
        'l_tokd_d.xbx':model_bank,
        'l_tokd_t.xbx':texture_bank,
        'g_wayb.xbx':package(character,character_sections,character_order),
        'l_tokd.xbx':package(resident,sections,order),
    }.items():
        (output/name).write_bytes(data)
    with wave.open(str(voice), 'rb') as audio:
        assert audio.getnchannels()==1 and audio.getsampwidth()==2 and audio.getnframes()>0
        print('Callout:',audio.getnframes(), 'samples at',audio.getframerate(),'Hz')
    (output/'Ultimate_Way_Big_Clean.wav').write_bytes(voice.read_bytes())
    print('Prepared',vertices,'weighted vertices;',indices//3,'triangles; mesh IDs',
          ', '.join(f'{mode}={MESH_KEYS[mode]:08x}' for mode in FORMS))

def vaps_rows_with_offsets(raw):
    count = struct.unpack_from('>I',raw,36)[0]
    directory = 32+struct.unpack_from('>I',raw,44)[0]
    return struct.iter_unpack('>3I',raw[directory:directory+count*12])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--level',type=Path,required=True)
    p.add_argument('--assets',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--voice',type=Path,required=True)
    args=p.parse_args()
    prepare(args.level,args.assets,args.output,args.voice)
