"""Private UCB event project, using existing event slots and converted PS2 PCM."""
import hashlib,json,struct,sys,wave
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
H = WORK; I=APP_ROOT/'installation'; O=H/'remaining-candidate'
raw=(I/'vilgax/ultimatecannonbolt/g_ucb.xbx').read_bytes(); assert raw==(I/'game/global/g_ucb.xbx').read_bytes()
cb=entries((I/'vilgax/cannonbolt/g_cb.xbx').read_bytes())[24]
rows=m.vaps_rows(cb); assert len(rows)==2 and rows[0][0]==rows[1][0]==m.crc('cboltva')
key= m.crc('ucbpova'); oldkey=struct.pack('>I',rows[0][0]); newkey=struct.pack('>I',key)
fev=rows[0][2].replace(b'cboltva',b'ucbpova').replace(oldkey,newkey)
assert len(fev)==len(rows[0][2]) and b'cboltva' not in fev and fev[32:36]==b'FEV1'
wrapper=bytearray(rows[1][2][:32].replace(oldkey,newkey)); fsb=rows[1][2][32:]
assert fsb[:4]==b'FSB4'; count,hsize,dsize,version,flags=struct.unpack_from('<5I',fsb,4)
assert count==29 and hsize==29*112 and len(fsb)==48+hsize+dsize
# Keep the same wave indices as the native cannonbolt project. The unused
# slots in this independent project carry silent PCM; normal CB retains XMA.
slots={6:'spin_cycle',7:'spin_cycle',8:'backspin_burnout',9:'backspin_burnout',14:'meteor_candidate',15:'suction_blast'}
pcm_template=(I/'vilgax/ultimatecannonbolt/callout.fsb').read_bytes(); assert pcm_template[:4]==b'FSB4'
mode=struct.unpack_from('<I',pcm_template,48+48)[0]; assert mode==0x131
headers=bytearray(); payload=bytearray(); mapping=[]
for j in range(count):
    old=fsb[48+j*112:48+(j+1)*112]; assert struct.unpack_from('<H',old)[0]==112
    h=bytearray(old[:80]); name=old[2:32].split(b'\0')[0].decode()
    if j in slots:
        with wave.open(str(O/(slots[j]+'.wav')),'rb') as w:
            assert w.getnchannels()==1 and w.getsampwidth()==2; rate=w.getframerate(); n=w.getnframes(); pcm=w.readframes(n)
        mapping.append(dict(slot=j,wave=name,source=slots[j],samples=n,rate=rate))
    else:rate=48000;n=512;pcm=bytes(n*2)
    pcm+=bytes((-len(pcm))%2048)
    struct.pack_into('<H',h,0,80)
    struct.pack_into('<6I',h,32,n,len(pcm),0,n-1,mode,rate)
    struct.pack_into('<H',h,62,1)
    headers.extend(h);payload.extend(pcm)
header=bytearray(fsb[:48]);struct.pack_into('<3I',header,4,count,len(headers),len(payload))
newfsb=bytes(header+headers+payload); assert len(newfsb)==48+80*count+len(payload)
struct.pack_into('>I',wrapper,4,len(newfsb))
bank=m.build_vaps(24,struct.unpack_from('>H',cb,12)[0],[(key,rows[0][1],fev),(key,rows[1][1],bytes(wrapper)+newfsb)])
parts=entries(raw); assert 24 not in parts; parts[24]=bank
new=m.package(raw,parts); check=entries(new)
assert all(check[k]==v for k,v in entries(raw).items())
assert m.vaps_rows(check[24])[1][2][32:]==newfsb
(O/'g_ucb.xbx').write_bytes(new);(O/'ucbpova.fsb').write_bytes(newfsb)
routes={0x2d806255:('ucb_poe_backspin',0,'cbolt_ball_dash'),0xd8baecc8:('ucb_poe_meteor',15,'cbolt_powerflop'),0x754d9887:('ucb_poe_suction',2,'cbolt_superball'),0xdb46cb2:('ucb_poe_spin',19,'cbolt_burnout')}
d=bytearray((O/'atk_ucb.ddf').read_bytes()); counts={k:0 for k in routes}
for at in range(4,len(d),224):
    k=struct.unpack_from('>I',d,at+32)[0]
    if k not in routes:continue
    name,event,original=routes[k]; assert struct.unpack_from('>I',d,at+152)[0]==m.crc(original)
    struct.pack_into('>I',d,at+152,m.crc(name));counts[k]+=1
assert set(counts.values())=={3}
(O/'atk_ucb.ddf').write_bytes(d)
(O/'sounds.txt').write_text(''.join(f'<sound name="{n}" id="{event}" swpgroupid="0" prjid="ucbpova"/>\n' for n,event,_ in routes.values()),encoding='ascii')
report=dict(project='ucbpova',native_events={n:e for n,e,_ in routes.values()},pcm_slots=mapping,original_ucb_sha256=hashlib.sha256(raw).hexdigest(),unverified_event_playback=True)
(O/'sound-bank-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
