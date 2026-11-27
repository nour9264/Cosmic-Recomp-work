from pathlib import Path
import sys,struct,json
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
sys.path.insert(0, str(REPO / 'tools'));sys.path.insert(0,str(WORK))
from merge_alien_streams import entries
from extract_discord_level_images import table,untile
from convert_four_arms_meshes import mesh_buffers
from make_hologram_pictures import write_png
out=WORK/'stock-ultimate-portraits';out.mkdir(parents=True,exist_ok=True)
def texture(r):
 _,fmt,w,h=struct.unpack_from('>IHHH',r);bc1=fmt in (0x104,0x11c);assert bc1 or fmt in (0x102,0x11a)
 log=3 if bc1 else 4;raw=bytearray(untile(r[128:],w//4,h//4,log));raw[0::2],raw[1::2]=raw[1::2],raw[0::2];p=bytearray(w*h*4)
 for j in range(w*h//16):
  b=raw[j*(1<<log):(j+1)*(1<<log)];cb=b if bc1 else b[8:];ca,cz=struct.unpack_from('<2H',cb);colors=[]
  for v in (ca,cz):
   rr,g,bb=v>>11,(v>>5)&63,v&31;colors.append(((rr<<3)|(rr>>2),(g<<2)|(g>>4),(bb<<3)|(bb>>2)))
  a,z=colors
  colors+= [tuple((2*x+y)//3 for x,y in zip(a,z)),tuple((x+2*y)//3 for x,y in zip(a,z))] if not bc1 or ca>cz else [tuple((x+y)//2 for x,y in zip(a,z)),(0,0,0)]
  ci=int.from_bytes(cb[4:8],'little')
  if not bc1:
   a,z=b[:2];alpha=[a,z]+([((7-i)*a+i*z)//7 for i in range(1,7)] if a>z else [((5-i)*a+i*z)//5 for i in range(1,5)]+[0,255]);ai=int.from_bytes(b[2:8],'little')
  for i in range(16):
   c=(ci>>(i*2))&3;aa=(0 if ca<=cz and c==3 else 255) if bc1 else alpha[(ai>>(i*3))&7];x=(j%(w//4))*4+i%4;y=(j//(w//4))*4+i//4;q=(y*w+x)*4;p[q:q+4]=bytes((*colors[c],aa))
 return w,h,p
for code in ['ubc','uec','uhm','usf','usm']:
 b=entries((ORIGINALS/'global'/f'g_{code}.xbx').read_bytes());textures=table(b[0]);r=max((r for r in table(b[4]).values() if r[3]&15==11),key=len);at,vertices,ind=mesh_buffers(r,True)
 points=list(struct.iter_unpack('>11f',vertices));indices=struct.unpack('>'+str(len(ind)//2)+'H',ind);ranges=[]
 for pos in range(376,at-32,4):
  word=struct.unpack_from('>I',r,pos)[0];tex=struct.unpack_from('>I',r,pos+28)[0]
  if word&31!=2 or tex not in textures:continue
  start,count=struct.unpack_from('>HH',r,pos+6)
  if start+count>len(indices) or count%3:continue
  name=f'{code}-{tex:08x}.png';path=out/name
  if not path.exists():w,h,p=texture(textures[tex]);write_png(path,w,h,p)
  ranges.append(dict(start=start,count=count,texture=name))
 assert ranges,(code,'no material ranges')
 result=dict(vertices=[(v[0],-v[2],v[1]) for v in points],uvs=[v[9:] for v in points],indices=indices,ranges=ranges)
 (out/(code+'.json')).write_text(json.dumps(result));print(code,len(points),[(x['start'],x['count']) for x in ranges],flush=True)
