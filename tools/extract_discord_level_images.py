"""Decode locally owned Xbox 360 level preview textures. No assets enter Git.

Tiled addressing follows the pinned ReXGlue SDK texture util (BSD-3-Clause,
with Xenia/UModel lineage credited there). This is lossless format conversion,
not an image generated or reconstructed from screenshots.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
from PIL import Image,ImageDraw

def table(blob):
    assert blob[:8]==bytes.fromhex('7661707300010003')
    count=struct.unpack_from('>I',blob,8)[0]
    base=struct.unpack_from('>I',blob,28)[0]
    buckets,n,bucket_at,record_at,stride=struct.unpack_from('>5I',blob,32)
    assert n==count and stride==12 and 32+record_at+n*stride<=base<=len(blob)
    result={}
    for i in range(n):
        key,info,offset=struct.unpack_from('>III',blob,32+record_at+i*stride)
        # Texture entries pack flags above their 24-bit byte count.
        size=info&0xffffff;start=base+offset
        assert start+size<=len(blob) and key not in result
        result[key]=blob[start:start+size]
    return result

def tiled_offset(x,y,pitch,log2):
    pitch=(pitch+31)&~31
    macro=((x>>5)+(y>>5)*(pitch>>5))<<(log2+7)
    micro=((x&7)+((y&14)<<2))<<log2
    offset=macro+((micro&~15)<<1)+(micro&15)+((y&1)<<4)
    return ((offset&~511)<<3)+((y&16)<<7)+((offset&448)<<2)+(((((y&8)>>2)+(x>>3))&3)<<6)+(offset&63)

def untile(data,width,height,log2):
    block=1<<log2;linear=bytearray(width*height*block)
    for y in range(height):
        for x in range(width):
            source=tiled_offset(x,y,width,log2);target=(y*width+x)*block
            assert source+block<=len(data)
            linear[target:target+block]=data[source:source+block]
    return bytes(linear)

def decode(record):
    assert len(record)>=128
    width,height=struct.unpack_from('>HH',record,6);fmt=struct.unpack_from('>H',record,4)[0]
    assert 0<width<=4096 and 0<height<=4096
    if fmt==0x184:
        raw=untile(record[128:],width,height,2)
        return Image.frombytes('RGBA',(width,height),raw,'raw','ARGB').convert('RGB')
    assert fmt in (0x104,0x102),hex(fmt)
    raw=bytearray(untile(record[128:],(width+3)//4,(height+3)//4,3 if fmt==0x104 else 4))
    for i in range(0,len(raw),2):raw[i],raw[i+1]=raw[i+1],raw[i]
    # A standard DDS wrapper lets Pillow's BC1 decoder handle color interpolation.
    header=[124,0x81007,height,width,len(raw),0,1]+[0]*11+[32,4,struct.unpack('<I',b'DXT1' if fmt==0x104 else b'DXT5')[0],0,0,0,0,0,0x1000,0,0,0,0]
    assert len(header)==31
    return Image.open(io.BytesIO(b'DDS '+struct.pack('<31I',*header)+raw)).convert('RGBA')

def extract(game,output):
    from prepare_all_aliens_candidate import records,decode as decode_script
    output.mkdir(parents=True,exist_ok=True);(output/'originals').mkdir(exist_ok=True)
    source=game/'global/gtex_s.xbx';textures=table(source.read_bytes())
    texts_blob=(game/'global/scripts/xbx_us.txt').read_bytes();assert texts_blob[:4]==bytes.fromhex('1badbabe')
    text={};at=4
    while at<len(texts_blob):
        key,size=struct.unpack_from('>II',texts_blob,at);at+=8
        text[key]=texts_blob[at:at+size].rstrip(b'\0').decode('cp1252');at+=size
    assert at==len(texts_blob)
    original_scripts=records((game/'global/scripts/globals.ds').read_bytes())
    code=next(c for h,a,c in original_scripts if h==0x705741dd)
    words,tokens=decode_script(code);levels=[];current=None
    fields={0x5e237e06:'name_key',0x1f380178:'small_texture',0x1cc23d56:'preview_texture',0x9067f23c:'mission_key'}
    for j,(pos,kind) in enumerate(tokens):
        if kind!=0x19 or words[pos+1] not in fields:continue
        previous,previous_kind=tokens[j-1];assert previous_kind==5
        field=fields[words[pos+1]];value=words[previous+1]
        if field=='name_key':
            current={};levels.append(current)
        current[field]=value
    names=['The Catacombs','Eiffel Tower',"Devil's Tower",'The Great Wall','Tokyo Nights','The Amazon','The Colosseum','The Final Battle']
    assets=['catacombs','eiffel_tower','devils_tower','great_wall','tokyo_nights','amazon','colosseum','final_battle']
    assert [text[x['name_key']] for x in levels[:8]]==names
    # The mission descriptor directly stores each mission ID and its folder.
    missions=(game/'global/scripts/missions.ddf').read_bytes()
    sheet=Image.new('RGB',(1024,560),'#171b20');draw=ImageDraw.Draw(sheet);manifest=[]
    for i,(level,name,asset) in enumerate(zip(levels[:8],names,assets)):
        signature=struct.pack('>II',level['mission_key'],0x9067f23c)
        assert missions.count(signature)==1;pos=missions.index(signature)
        folder=missions[pos+72:pos+80].split(b'\0')[0].decode('ascii')
        assert (game/folder/'scripts'/(folder+'.ds')).is_file()
        record=textures[level['preview_texture']];image=decode(record);assert image.size==(256,256)
        original=output/'originals'/(asset+'.png');image.save(original)
        target=output/(asset+'.png');image.resize((1024,1024),Image.Resampling.LANCZOS).save(target)
        x=i%4*256;y=i//4*280;sheet.paste(image,(x,y),image);draw.text((x+4,y+258),name,fill='white')
        manifest.append(dict(level=i+1,name=name,asset_key=asset,game_folder=folder,
            preview_texture=f"{level['preview_texture']:08x}",mission_key=f"{level['mission_key']:08x}",
            text_key=f"{level['name_key']:08x}",source_archive='global/gtex_s.xbx',source_format='Xbox 360 tiled BC3/DXT5, big-endian 16-bit words',
            native_size=[256,256],upload_size=[1024,1024],alpha_preserved=True,
            original_png='originals/'+asset+'.png',upload_png=asset+'.png',
            original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),upload_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    sheet.save(output/'contact-sheet.png')
    report=dict(application_id='1568421826894500000',large_image='game_cover',small_image_field='asset_key',
        evidence=['globals.ds init_level_switching: title/preview/mission mapping',
                  'xbx_us.txt: exact English titles','missions.ddf: mission-ID to folder mapping',
                  'misscr.ds: Level Select preview field 0x1cc23d56'],
        source_archive_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),levels=manifest)
    (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'UPLOAD_INSTRUCTIONS.txt').write_text('Upload the eight PNGs in this folder to Discord Rich Presence Art Assets.\nUse each filename without .png as its asset key. Keep game_cover as the large image.\nDo not upload contact-sheet.png, manifest.json, or the originals folder.\nOriginal 256x256 PNGs and upload-ready 1024x1024 PNGs preserve transparency.\nThe upload copies are enlarged, not higher-detail game artwork.\nThe exported game images are local assets and are not included in Git commits.\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--game',type=Path,default=Path('originals'))
    parser.add_argument('--output',type=Path,default=Path('build/discord-art/levels'));args=parser.parse_args()
    report=extract(args.game,args.output)
    print(json.dumps([dict(name=x['name'],folder=x['game_folder'],asset=x['asset_key']) for x in report['levels']]))
