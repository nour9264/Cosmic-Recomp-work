"""Smooth POE pressure material and port the source DeepImpact ring/crater at contact."""
import sys,struct,math,hashlib,json
from pathlib import Path
import numpy as np
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip
from wheel_icon_texture import encode_block
from extract_discord_level_images import tiled_offset
H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'pressure-meteor-visuals';O.mkdir(exist_ok=True)
s=(H/'99_95.stream1.bin').read_bytes();raw=(G/'g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes();p=entries(raw);old=entries(raw)
assert hashlib.sha256(raw).hexdigest()=='caf6d2a6fd22bdfe7eff14be58eedc555f9f592a78986616c0a7845afd410782'
def u(q):return struct.unpack_from('<I',s,q)[0]
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(i,rows):p[i]=m.build_vaps(i,struct.unpack_from('>H',p[i],12)[0],m.bucket_sorted(rows))
def tex4(at):
    assert (u(at+12)>>16)&255==0x14;mp=u(at+60);w,h=u(mp+8),u(mp+12);transfer=u(mp+16);data=s[transfer+32:transfer+32+w*h//2];pa=u(at+20);pr=s[u(pa+40)+32:u(pa+40)+1056];palette=[tuple(pr[4*((i&~24)|((i&8)<<1)|((i&16)>>1)):4*((i&~24)|((i&8)<<1)|((i&16)>>1))+4]) for i in range(256)];csa=(u(at+12)>>8)&31;out=[];seen=set()
    for y in range(h):
        for x in range(w):
            pos=(x//32)*16*h+(y//16)*32+(((y//4)*2+(y&1))&7)*h*2+4*((x+4*((y+2)//4&1))&7)+(x//8&3);n=(y>>1)&1;seen.add(pos*2+n);out.append(palette[((data[pos]>>(4*n))&15)+16*csa])
    assert len(seen)==w*h;return np.array(out,dtype=float).reshape(h,w,4)
def smooth(a,passes):
    for _ in range(passes):
        for axis in (0,1):
            pad=np.pad(a,[(1,1) if i==axis else (0,0) for i in range(a.ndim)],mode='edge');a=(np.take(pad,range(a.shape[axis]),axis=axis)+2*np.take(pad,range(1,a.shape[axis]+1),axis=axis)+np.take(pad,range(2,a.shape[axis]+2),axis=axis))/4
    return a
def encode(key,a,mode):
    h,w,_=a.shape;alpha=np.clip(a[:,:,3]/128,0,1);intensity=np.max(a[:,:,:3],axis=2)
    if mode=='crater':rgb=a[:,:,:3];opacity=alpha*205
    elif mode=='dust':rgb=a[:,:,:3];opacity=alpha*255
    else:rgb=np.ones_like(a[:,:,:3])*255;opacity=intensity*alpha
    if mode=='pressure':
        opacity=smooth(opacity,2);x=np.linspace(0,1,w);y=np.linspace(0,1,h);opacity*=np.minimum(1,np.minimum(x,1-x)*7)[None,:]*np.minimum(1,np.minimum(y,1-y)*7)[:,None]
    out=np.dstack((rgb,opacity));xx=np.linspace(0,w-1,128);yy=np.linspace(0,h-1,128);res=np.zeros((128,128,4))
    for j,y in enumerate(yy):
        y0=int(y);y1=min(h-1,y0+1);f=y-y0;row=out[y0]*(1-f)+out[y1]*f
        for c in range(4):res[j,:,c]=np.interp(xx,np.arange(w),row[:,c])
    pixels=[tuple(map(int,np.clip(np.rint(v),0,255))) for v in res.reshape(-1,4)];head=bytearray(m.table(p[0])[0x82365e33][:128]);struct.pack_into('>I',head,44,key);tile=bytearray(16384)
    for y in range(32):
        for x in range(32):
            block=encode_block([pixels[(4*y+j)*128+4*x+i] for j in range(4) for i in range(4)]);at=tiled_offset(x,y,32,4);tile[at:at+16]=bytes(block[i^1] for i in range(16))
    return bytes(head)+tile
pressure=m.crc('poe_pressureburst_streaks');rt=m.crc('poe_deep_impact_ring_tex');ct=m.crc('poe_deep_impact_crater_tex');dt=m.crc('poe_deep_impact_dust_tex');assert u(0x42b540)==0x23dc20 and u(0x42b560)==0x23db00 and u(0x56ea8)==0x521a80 and u(0x56ec8)==0x522600
dust=np.frombuffer((H/'original-vfx-decoded/DustPoof.rgba').read_bytes(),dtype=np.uint8).astype(float).reshape(64,64,4);dust[:,:,3]*=.5
bank(0,[(k,f,encode(k,tex4(0x538700),'pressure') if k==pressure else v) for k,f,v in m.vaps_rows(p[0])]+[(rt,4,encode(rt,tex4(0x521a80),'ring')),(ct,4,encode(ct,tex4(0x522600),'crater')),(dt,4,encode(dt,dust,'dust'))])
root=m.effect_root('cannonbolt');burst=m.crc('ucb_suction_release_ring');ring=m.crc('ucb_meteor_poe_ring');crater=m.crc('ucb_meteor_poe_crater');start=m.crc('ucb_meteor_poe_contact');end=m.crc('ucb_meteor_poe_end');stop=m.crc('ucb_meteor_poe_fx_stop')
mesh_rows=m.vaps_rows(p[4]);col_rows=m.vaps_rows(p[3]);donor=m.table(p[4])[m.crc('ucb_suction_ground_ribbons')];ch=m.table(p[3])[m.crc('ucb_suction_ground_ribbons')]
def geom(key,at,n,uv_at,tex,scale,alpha):
    assert u(at+36)==0x68008001|(n<<16) and u(uv_at)==0x69008002|(n<<16)
    pts=list(struct.iter_unpack('<3f',s[at+40:at+40+n*12]));uv=list(struct.iter_unpack('<3H',s[uv_at+4:uv_at+4+n*6]));verts=[(x*scale,.045+y*scale,z*scale,a/4095,b/4095) for (x,y,z),(a,b,_) in zip(pts,uv)];inds=[]
    for i in range(2,n):
        if uv[i][2]&0x8000:continue
        a,b,c=i-2,i-1,i;inds.extend((a,b,c,c,b,a))
    off,_,_=m.mesh_buffers(donor,xbox=True);head=bytearray(donor[:off]);meta=struct.unpack_from('<I',head,28)[0];vb=b''.join(struct.pack('>5f',*v) for v in verts);ib=struct.pack(f'>{len(inds)}H',*inds);ia=(off+len(vb)+31)&~31;struct.pack_into('>I',head,4,len(verts));struct.pack_into('>I',head,16,len(inds));struct.pack_into('<I',head,20,meta+ia-376);struct.pack_into('>I',head,384,(len(inds)<<16)|(struct.unpack_from('>I',head,384)[0]&0xffff));struct.pack_into('>I',head,404,tex);v=bytes(head)+vb+bytes(ia-off-len(vb))+ib;assert m.mesh_buffers(v,xbox=True)==(off,vb,ib);col=bytearray(ch[:32]);struct.pack_into('>I',col,8,key);mesh_rows.append((key,off//32,v));col_rows.append((key,1,bytes(col)+bytes((alpha,255,255,255))*n))
geom(ring,0x23db70,4,0x23dbdc,rt,.25,210);geom(crater,0x23dc90,67,0x23e0ec,ct,.33,180)
bank(4,mesh_rows);bank(3,[(k,f,v[:32]+b''.join(bytes((min(v[i],138),*v[i+1:i+4])) for i in range(32,len(v),4)) if k==burst else v) for k,f,v in col_rows])
n=m.table(p[14]);h,b=m.node_parts(n[burst]);newnodes=[];release=m.crc('ucb_suction_release');ringstop=m.crc('ucb_suction_ring_stop')
for key,duration,first,last in [(ring,.65,.34,1.08),(crater,.65,.95,1.05)]:
    nh=list(h);nh[0]=key;nh[19:26]=fs(5,-4,-.1,-4,4,2,4);bl=[]
    for block in b:
        if block[0]==0x19:block=[0x19,24,0x0d0a5003,0x00020002]+fs(0)+[0]*6+fs(first,1,first)+fs(duration*4800)+[0]*6+fs(last,1,last)
        elif block[0]==0:block=[0,4,key,key]
        elif block[0]==14:
            pp=[];group=None
            for a,t,v in m.property_entries(block):
                if t==0x1000c:group=a
                if a in (0x750f694a,0x8541406c) and v==[release]:v=[start]
                if a in (0xa3911ca7,0xf7be9018) and v!=[0]:v=[stop]
                if group==0xe16f3a56 and a in (0x5e0393bd,0xf465b2b5):v=fs(duration)
                pp.append((a,t,v))
            block=m.node_properties(pp)
        bl.append(block)
    newnodes.append((key,0,m.node_record(nh,bl)))
rows=[]
for k,f,v in m.vaps_rows(p[14]):
    if k==root:
        nh,bl=m.node_parts(v);out=[]
        for block in bl:
            if block[0]==0x14:block=[0x14,block[1]+2,block[2]+2]+block[3:]+[ring,crater]
            elif block[0]==14:
                pp=m.property_entries(block);extra=[];template=[];group=None
                for a,t,v in pp:
                    if t==0x1000c:group=a
                    if group==m.crc('ucb_suction_out_0'):template.append((a,t,v))
                assert template
                for i in range(6):
                    angle=i*math.tau/6;settings={0x462ce4f5:fs(.42*math.sin(angle),.11,.42*math.cos(angle),0,math.sin(angle/2),0,math.cos(angle/2)),0x8541406c:[start],0xf7be9018:[stop],0x9d762289:[3],0xe7965460:fs(18),0x3de73088:fs(.42),0x0f26fef6:fs(3.7),0x297c98f1:fs(24),0x118a27c7:fs(.34),0x9c822a32:fs(.64),0x5a6ce323:[0x98ffffff],0xc365b299:[0xa0ffffff],0xb462820f:[0x50ffffff],0x2a0617ac:[0x00ffffff],0x82660d72:[dt],0x22944c2a:[m.crc('normal')]}
                    extra.extend((m.crc(f'ucb_meteor_poe_dust_{i}') if t==0x1000c else a,t,settings.get(a,v)) for a,t,v in template)
                for key in (ring,crater):
                    for e in (start,stop):extra.extend([(m.crc(f'{key}_{e}_forward'),0x1000c,[m.EVENT_GROUP]),(0x939b68a0,0x201000c,[e]),(0x8541406c,0x201000c,[e]),(0x557c4b4d,0x201000c,[key])])
                extra.extend([(m.crc('ucb_meteor_poe_timer'),0x1000c,[0x6ad0de1a]),(0x8ddaf3ee,0x201000c,[0]),(0x8541406c,0x201000c,[start]),(0x865f80c0,0x101000c,fs(.67)),(0xd058515c,0x201000c,[stop])]);block=m.node_properties(pp+extra)
            out.append(block)
        v=m.node_record(nh,out)
    rows.append((k,f,v))
bank(14,rows+newnodes)
# Trigger only on actual contact frame 35, using the same native HEAD channel
# as the suction attack; do not change the animation or damage curves.
clip=0xd8baecc8;clips=m.table(p[13]);oldch=channel_records(p[9]);flags=m.flag_channel([[fs(35*160)[0],0,0,0,m.HEAD_START,0,0,0,0],[fs(44*160-1)[0],0,0,0,m.HEAD_STOP,0,0,0,0]])
cr=[]
for k,f,v in m.vaps_rows(p[13]):
    if k==clip:q=bytearray(v);assert struct.unpack_from('>I',q,80)[0]==0xffffffff;struct.pack_into('>I',q,80,0x80000000);v=bytes(q)
    cr.append((k,f,v))
bank(13,cr);p[9],p[13]=m.merge_channels(p[9],p[13],[(m.crc('ucb_meteor_poe_contact_flags'),0,flags)],extra_count=1);nc=channel_records(p[9]);assert all(streamed_clip(v,oldch)==streamed_clip(m.table(p[13])[k],nc) for k,v in clips.items() if k!=clip)
d=(G/'scripts/atk_ucb.ddf').read_bytes();assert d==(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes();dd=bytearray(d);count=0
for at in range(4,len(dd),224):
    if struct.unpack_from('>I',dd,at+32)[0]==clip:struct.pack_into('>2I',dd,at+144,start,end);count+=1
assert count==3;new=m.package(raw,p);check=entries(new);assert m.table(check[4])[m.crc('ucb_suction_side_ribbons')]==m.table(old[4])[m.crc('ucb_suction_side_ribbons')];assert all(check[k]==v for k,v in old.items() if k not in (0,3,4,9,13,14))
(O/'g_cb.xbx').write_bytes(new);(O/'atk_ucb.ddf').write_bytes(dd);sha=lambda x:hashlib.sha256(x).hexdigest();report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(new),old_ddf_sha=sha(d),new_ddf_sha=sha(dd),meteor_contact_frame=35,original_ring_mesh='0x23db10',original_crater_mesh='0x23dc30',source_textures=['0x521a80','0x522600'],pressure_texture_smoothed=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
