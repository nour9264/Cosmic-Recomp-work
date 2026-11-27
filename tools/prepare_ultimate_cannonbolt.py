"""Build a private Ultimate Cannonbolt bundle (form 24) from the owner's Blender exports and the normal Cannonbolt bundle.

    python tools/prepare_ultimate_cannonbolt.py --exports <folder> --installation <installation> --normal <bundle> --output <new folder>

--exports       ucb-body.bin, ucb-ball.bin, ucb-body.png, ucb-ball.png and Ultimate_Cannonbolt_Clean.wav (the owner's Blender export)
--installation  an installation whose game/global/scripts has globals.ds.cosmic-original
--normal        the normal Cannonbolt bundle (installation/vilgax/cannonbolt)
The bundle holds the model package, attack table, records, registration scripts and voice; the animation clips and finishing
steps are added afterwards (docs/ULTIMATE_CANNONBOLT.md)."""
from pathlib import Path
import struct
import wave

from convert_four_arms_meshes import mesh_buffers
from extract_discord_level_images import tiled_offset, untile
from merge_alien_streams import entries
from prepare_all_aliens_candidate import Code, encode, records
from prepare_vilgax_import import bank, crc, decode, package, replace_arguments, table
from wheel_icon_texture import encode_block, read_png

SOURCE = INSTALLATION = NORMAL = OUTPUT = None  # set from the command line by main()
MESH = crc('ultimate_cannonbolt_mesh')
CHARACTER = crc('character_ucb')
VOICE = 'ult_cannonbolt_name_callout'
EVENT = crc('cosmic_ultimate_cannonbolt_voice')
ID = 24

def game_texture(path, template, key, *, diffuse_scale=1.0, full_strength_cell=None):
    width, height, pixels = read_png(path)
    assert width == height and width in (512, 1024)
    dim = width // 4
    result = bytearray(dim * dim * 8)
    for by in range(dim):
        for bx in range(dim):
            scale = 1.0 if (bx//16, by//16) == full_strength_cell else diffuse_scale
            colors = []
            for y in range(4):
                for x in range(4):
                    at = ((by * 4 + y) * width + bx * 4 + x) * 4
                    rgb = tuple(round(channel * scale) for channel in pixels[at:at+3])
                    colors.append((*rgb, 255))
            block = bytearray(encode_block(colors)[8:])
            block[0::2], block[1::2] = block[1::2], block[0::2]
            at = tiled_offset(bx, by, dim, 3)
            result[at:at+8] = block
    header = bytearray(template[:128])
    struct.pack_into('>HHBB', header, 6, width, height, width.bit_length()-1, height.bit_length()-1)
    struct.pack_into('>I', header, 44, key)
    assert len(untile(result, dim, dim, 3)) == len(result)
    return bytes(header + result)

def constant_game_texture(template, key, color):
    """Fill every BC1 block, including the donor's mip storage."""
    header = bytearray(template[:128])
    struct.pack_into('>I', header, 44, key)
    block = encode_block([(*color, 255)] * 16)[8:]
    return bytes(header) + bytes(block[i ^ 1] for i in range(8)) * ((len(template)-128)//8)

def game_model(data):
    normal_key = 0x58ec2e03
    original = table(data[4])[normal_key]
    vertex_at, _, _ = mesh_buffers(original, xbox=True)
    assert vertex_at == 512
    body_tex = crc('ucb_body_diffuse')
    ball_tex = crc('ucb_ball_diffuse')
    old_tex = table(data[0])
    textures = {}
    # Fill the two original body shader slots with new neutral maps.
    # The donor maps have different UVs, and omitted slots can leave stale state.
    header = bytearray(original[:vertex_at])
    for operand, expected, name, color in [
        (436, 0x5eb38914, 'ucb_matte_specular', (0, 0, 0)),
        (452, 0xbed172f8, 'ucb_flat_normal', (128, 128, 255)),
    ]:
        assert struct.unpack_from('>I', header, operand)[0] == expected
        key = crc(name)
        textures[key] = constant_game_texture(old_tex[expected], key, color)
        struct.pack_into('>I', header, operand, key)
    all_vertices, all_skin, all_indices = bytearray(), bytearray(), bytearray()
    total = 0
    for name, draw, key, old_key in [('body',376,body_tex,0x46cb9ef2),('ball',460,ball_tex,0xdb869166)]:
        exported = (SOURCE / f'ucb-{name}.bin').read_bytes()
        vertices, length = struct.unpack_from('>II', exported)
        assert len(exported) == 8 + vertices * 96 + length * 2
        points = exported[8:8+vertices*44]
        skin = exported[8+vertices*44:8+vertices*96]
        for index in range(vertices):
            row = skin[index*52:(index+1)*52]
            assert row[:44] == points[index*44:(index+1)*44]
            assert sum(row[44:48]) == 255 and max(row[48:]) < 45
        indices = tuple(i+total for i, in struct.iter_unpack('>H', exported[-2*length:]))
        assert max(indices)<total+vertices
        assert struct.unpack_from('>I', header, draw+28)[0] == old_key
        struct.pack_into('>HH', header, draw+6, len(all_indices)//2,length)
        struct.pack_into('>I', header, draw+28,key)
        all_vertices += points
        all_skin += skin
        all_indices += struct.pack(f'>{len(indices)}H',*indices)
        textures[key] = game_texture(SOURCE / f'ucb-{name}.png', old_tex[0x46cb9ef2],key)
        total += vertices
    index_at = (len(header)+len(all_vertices)+31)&~31
    address, = struct.unpack_from('<I', header, 28)
    struct.pack_into('>I', header, 4, total)
    struct.pack_into('>I', header, 16, len(all_indices)//2)
    struct.pack_into('<I', header, 20, address+index_at-376)
    result = bytes(header + all_vertices + bytes(index_at-len(header)-len(all_vertices)) + all_indices)
    assert mesh_buffers(result, xbox=True)[1:] == (all_vertices, all_indices)
    skin = bytearray(table(data[22])[normal_key][:80])
    struct.pack_into('>II',skin,72,total,total)
    colors = table(data[3])[normal_key]
    assert struct.unpack_from('>I',colors,8)[0] == normal_key
    colors = colors[:8]+struct.pack('>I',MESH)+colors[12:]
    result = {0:(textures,4),3:({MESH:colors},0),4:({MESH:result},len(header)//32),22:({MESH:bytes(skin+all_skin)},0)}
    return {part:bank(part,struct.unpack_from('>H',data[part],12)[0],rows,lambda _:flag)
            for part,(rows,flag) in result.items()}

def voice_bank():
    # One signed, mono PCM16 subsound. The retail bank flags select little endian.
    with wave.open(str(SOURCE/'Ultimate_Cannonbolt_Clean.wav'),'rb') as audio:
        assert (audio.getnchannels(),audio.getsampwidth(),audio.getcomptype()) == (1,2,'NONE')
        length, rate = audio.getnframes(), audio.getframerate()
        sample = bytearray(audio.readframes(length))
    sample += bytes((-len(sample)) % 2048)
    original = (NORMAL/'callout.fsb').read_bytes()
    header = bytearray(original[:48])
    entry = bytearray(original[48:128])
    struct.pack_into('<H30s6I',entry,0,80,VOICE.encode(),length,len(sample),0,0,0x131,rate)
    struct.pack_into('<III',header,4,1,80,len(sample))
    return bytes(header + entry + sample)

def register():
    c=Code()
    c.get(0,'gFormData')
    c.num(1,ID)
    c.table(2)
    c.store(0,1,2)
    c.emit(3<<8|5,CHARACTER)
    c.fieldput(2,'character',3)
    for field,value in [('characterFile','g_ucb'),(0x7fb535f8,'atk_ucb.ddf')]:
        words=struct.unpack(f'>{(len(value)+4)//4}I',value.encode().ljust((len(value)+4)//4*4,b'\0'))
        c.emit(3<<8|4,*words)
        c.fieldput(2,field,3)
    c.get(3,'Cosmic_ultimatecannonbolt_init')
    c.fieldput(2,0x89d9800b,3)
    c.table(3)
    c.fieldput(2,0x224117f6,3)
    for button,slot in enumerate([0xd44b7a60,0x47f5d4c7,0x0137a091,0x93eb00b0],1):
        c.num(4,button)
        c.emit(5<<8|5,slot)
        c.store(3,4,5)
    c.num(4,23)
    c.index(5,0,4)
    c.fieldput(5,0x461241eb,1)
    c.done()
    return c.finish()

def attacks():
    data=(NORMAL/'atk_cb.ddf').read_bytes()
    rows=list(struct.iter_unpack('>56I',data[4:]))
    ids={row[0]:crc(f'ucb_attack_{row[0]:08x}') for row in rows}
    result=bytearray(data[:4])
    costs=dict(zip((0x549d5666,0x239a66f0,0xba93374a,0xcaf9c3c5),(4,6,8,10)))
    word=lambda n: struct.unpack('>I',struct.pack('>f',n))[0]
    for original in rows:
        row=[ids.get(value,value) for value in original]
        if row[15]:
            row[15]=word(1.75) if row[40] in costs else word(max(.35,struct.unpack('>f',struct.pack('>I',row[15]))[0]))
        if 0x4c6b3fe3 in row[46:46+2*row[45]:2]:
            row[42]=word(costs[row[40]]/60)
        result += struct.pack('>56I',*row)
    return bytes(result),ids

def forms(ids):
    scripts={key:code for key,_,code in records((NORMAL/'forms.bin').read_bytes())}
    template={key:code for key,_,code in records((INSTALLATION/'game/global/scripts/globals.ds.cosmic-original').read_bytes())}
    cb=scripts[crc('Cosmic_cannonbolt_init')]
    donor=template[0x9d32ddf9]
    cb_words,_=decode(cb)
    assert cb_words[18] == 0x1f8e916b and cb_words[44] == 0xae0228ed
    words,_=decode(donor)
    start=next(i for i,v in enumerate(words) if v==0x098c5946)-5
    end=next(i for i,v in enumerate(words) if v==0xd1b37389)-20
    assert words[start]==0x907 and words[end]==0x907
    call=Code()
    call.call('Cosmic_ultimatecannonbolt_attacks')
    donor=donor[:start*4]+call.finish()+donor[end*4:]
    init=replace_arguments(donor,{
        0x14081bc6:0x1f8e916b, 0xf54b5e78:crc('ultimatecannonbolt'),
        0xe81bb8f4:cb_words[34], 0xf706fb8b:cb_words[40], 0x00d9521e:cb_words[42],
        0xcb6c9eaf:CHARACTER, 0xebf8da66:cb_words[46], 0x0be8d0f4:cb_words[48],
        0xe8c0396d:crc('Cosmic_ultimatecannonbolt_vo'),
    })
    attack=replace_arguments(scripts[crc('Cosmic_cannonbolt_attacks')],
                            {**ids,crc('Cosmic_cannonbolt_upgrades'):crc('Cosmic_ultimatecannonbolt_upgrades')})
    resolver=Code()
    resolver.emit(4<<8|5,EVENT)
    resolver.binary(0x10,5,0,4)
    resolver.false(5,'normal')
    resolver.emit(4<<8|5,crc(VOICE),4<<8|0x22)
    resolver.label('normal')
    resolver.call('Cosmic_cannonbolt_vo',[0,1])
    resolver.emit(20<<8|0x22)
    resolver.done()
    return encode([(crc('Cosmic_ultimatecannonbolt_'+name),args,code) for name,args,code in [
        ('register',0,register()),('init',0,init),('attacks',0,attack),('vo',2,resolver.finish()),
        ('upgrades',0,replace_arguments(scripts[crc('Cosmic_cannonbolt_upgrades')],{0x41b80000:0x41c00000})),
        ('costs',0,replace_arguments(scripts[crc('Cosmic_cannonbolt_costs')],{crc('cannonbolt'):crc('ultimatecannonbolt')})),
    ]])

def main():
    import argparse
    global SOURCE, INSTALLATION, NORMAL, OUTPUT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--exports', type=Path, required=True)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--normal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    SOURCE, INSTALLATION, NORMAL, OUTPUT = args.exports, args.installation, args.normal, args.output
    normal=(NORMAL/'g_cb.xbx').read_bytes()
    model=game_model(entries(normal))
    character=bytearray((NORMAL/'character-records.bin').read_bytes())
    assert character[24:44]==b'character_cannonbolt' and struct.unpack_from('>I',character,60)[0]==0x58ec2e03
    struct.pack_into('>I',character,0,CHARACTER)
    character[24:48]=b'character_ucb'.ljust(24,b'\0')
    struct.pack_into('>I',character,60,MESH)
    attack,ids=attacks()
    files={
        'character-records.bin':character,'xbx-records.bin':b'','player-records.bin':b'',
        'forms.bin':forms(ids),'form-ids.txt':b'ultimatecannonbolt 24\n',
        'g_ucb.xbx':package(normal,model,sorted(model)),'atk_ucb.ddf':attack,
        'callout.fsb':voice_bank(),'callout.txt':VOICE.encode()+b'\n',
        'transform.wav':(SOURCE/'Ultimate_Cannonbolt_Clean.wav').read_bytes(),
        'albedo.txt':f'g_ucb.xbx {crc("ucb_body_diffuse"):08x}\n'.encode('ascii'),
    }
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():
        (OUTPUT/name).write_bytes(data)

if __name__=='__main__':
    main()
