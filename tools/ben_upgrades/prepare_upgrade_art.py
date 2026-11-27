from pathlib import Path
import sys,struct
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
sys.path.insert(0, str(REPO / 'tools'))
from extract_discord_level_images import table,untile
from make_hologram_pictures import write_png
out=WORK
def decode(r):
 _,fmt,w,h=struct.unpack_from('>IHHH',r);assert fmt==0x102
 blocks=bytearray(untile(r[128:128+w*h],w//4,h//4,4));blocks[0::2],blocks[1::2]=blocks[1::2],blocks[0::2]
 pixels=bytearray(w*h*4)
 for index in range(w*h//16):
  b=blocks[index*16:index*16+16];a,z=b[:2];alpha=[a,z]
  alpha += [((7-i)*a+i*z)//7 for i in range(1,7)] if a>z else [((5-i)*a+i*z)//5 for i in range(1,5)]+[0,255]
  ai=int.from_bytes(b[2:8],'little');colors=[]
  for v in struct.unpack_from('<2H',b,8):
   rr,g,bb=v>>11,(v>>5)&63,v&31;colors.append(((rr<<3)|(rr>>2),(g<<2)|(g>>4),(bb<<3)|(bb>>2)))
  x,y=colors;colors += [tuple(((3-i)*a+i*b)//3 for a,b in zip(x,y)) for i in (1,2)]
  ci=int.from_bytes(b[12:16],'little')
  for i in range(16):
   xx,yy=(index%(w//4))*4+i%4,(index//(w//4))*4+i//4;p=(yy*w+xx)*4;pixels[p:p+4]=bytes((*colors[(ci>>(i*2))&3],alpha[(ai>>(i*3))&7]))
 return w,h,pixels
if __name__=='__main__':
 bank=table((ORIGINALS/'global/gtex_s.xbx').read_bytes());keys=[k for k,r in bank.items() if struct.unpack_from('>HHH',r,4)==(258,256,256)]
 sheet=bytearray(768*768*4)
 for n,k in enumerate(keys):
  w,h,p=decode(bank[k]);(out/f'portrait-{n}.rgba').write_bytes(p)
  for y in range(96):
   for x in range(96):
    a=(int(y*h/96)*w+int(x*w/96))*4;b=((n//8*96+y)*768+n%8*96+x)*4;sheet[b:b+4]=p[a:a+4]
 write_png(out/'portrait-contact.png',768,768,sheet)
 (out/'portrait-keys.txt').write_text('\n'.join(f'{i} {k:08x}' for i,k in enumerate(keys)))
 print('Decoded',len(keys),'original portraits')
