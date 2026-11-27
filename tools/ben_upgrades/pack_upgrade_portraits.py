from pathlib import Path
import sys,math
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
sys.path.insert(0, str(REPO / 'tools'))
from wheel_icon_texture import read_png
from make_hologram_pictures import write_png
out=WORK
def raw(n):return 256,256,(out/f'portrait-{n}.rgba').read_bytes()
def trim(image):
 w,h,p=image;points=[(i//4%w,i//4//w) for i in range(0,len(p),4) if p[i+3]>30]
 left=min(x for x,y in points);right=max(x for x,y in points)+1;top=min(y for x,y in points);bottom=max(y for x,y in points)+1
 return right-left,bottom-top,b''.join(p[(y*w+left)*4:(y*w+right)*4] for y in range(top,bottom))
def place(dst,image,x,y,width,height):
 w,h,p=trim(image);scale=min(width/w,height/h);nw,nh=max(1,round(w*scale)),max(1,round(h*scale));x+=round((width-nw)/2);y+=round((height-nh)/2)
 for yy in range(nh):
  for xx in range(nw):
   sx=min(w-1,int(xx/scale));sy=min(h-1,int(yy/scale));q=(sy*w+sx)*4;r=((y+yy)*256+x+xx)*4
   if not (0<=x+xx<256 and 0<=y+yy<256):continue
   a=p[q+3]/255;da=dst[r+3]/255;alpha=a+da*(1-a)
   if alpha:
    for c in range(3):dst[r+c]=round((p[q+c]*a+dst[r+c]*da*(1-a))/alpha)
    dst[r+3]=round(alpha*255)
images=[]
for n in [29,45]:
 dst=bytearray(256*256*4);place(dst,raw(n),6,4,244,248);images.append(dst)
dst=bytearray(256*256*4)
for i,name in enumerate(['jetray','chromastone','goop']):
 p=WORK/'alien-force-art-refresh/pictures'/(name+'_ring.png');place(dst,read_png(p),i*70-8,8,118,210)
place(dst,read_png(out/'ncb-s2f1.png'),40,138,170,115);images.append(dst)
dst=bytearray(256*256*4)
# Seven installed Ultimate forms, with staggered heads kept unobscured.
place(dst,read_png(out/'ultimate-ubc.png'),0,8,125,132)
place(dst,read_png(out/'ultimate-way-big.png'),92,0,78,213)
place(dst,read_png(out/'ultimate-usf.png'),170,12,85,161)
place(dst,read_png(out/'ultimate-usm.png'),0,124,100,127)
place(dst,read_png(out/'ultimate-uec.png'),65,112,62,140)
place(dst,read_png(out/'ultimate-uhm.png'),113,131,109,119)
place(dst,read_png(out/'ultimate-cannonbolt.png'),182,173,74,79)
images.append(dst)
(out/'upgrade-portraits.rgba').write_bytes(b''.join(images))
sheet=bytearray(1024*256*4)
for i,p in enumerate(images):
 write_png(out/f'upgrade-portrait-{i+1}.png',256,256,p)
 for y in range(256):sheet[(y*1024+i*256)*4:(y*1024+(i+1)*256)*4]=p[y*256*4:(y+1)*256*4]
write_png(out/'upgrade-portrait-preview.png',1024,256,sheet)
print('Four portrait tiles packed:',(out/'upgrade-portraits.rgba').stat().st_size)
