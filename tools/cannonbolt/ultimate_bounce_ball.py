"""Retarget the original POE bounce trajectory to Ultimate Cannonbolt only."""
import collections,hashlib,json,math,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range

H = WORK; I=APP_ROOT/'installation'; G=I/'game/global'; O=H/'ultimate-bounce-ball-v4-height'; O.mkdir(exist_ok=True)
backup=H/'ultimate-bounce-ball/pre-install'; raw=(backup/'game/global/g_cb.xbx').read_bytes(); normal=(G/'scripts/atk_cb.ddf').read_bytes(); ultimate=(backup/'game/global/scripts/atk_ucb.ddf').read_bytes()
sha=lambda x:hashlib.sha256(x).hexdigest()
assert raw==(backup/'vilgax/cannonbolt/g_cb.xbx').read_bytes()
assert normal==(I/'vilgax/cannonbolt/atk_cb.ddf').read_bytes() and ultimate==(backup/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
src=(H/'99_95.stream1.bin').read_bytes(); f=struct.unpack_from('<12I',src,0xdb620+0x50); assert f[1]==54
ptr=struct.unpack_from('<54I',src,f[8]); vals=[struct.unpack_from('<3f',src,e-12) for e in list(ptr[1:])+[f[8]]]
assert max(v[2] for v in vals)>6 and all(math.isfinite(x) for v in vals for x in v)
heights=[max(0,v[2])*.60 for v in vals]
lead=18; stretch=1.16; n=lead+round(53*stretch)+1; impacts=[lead,lead+round(19*stretch),lead+round(40*stretch)]
def z(i):
    if i<lead:
        if i<=2:return 0
        if i<=12:return 1.65*(1-(1-(i-2)/10)**2)
        return 1.65*(1-((i-12)/6)**2)
    t=min(53,(i-lead)/stretch); j=int(t); return heights[j]+(heights[min(j+1,53)]-heights[j])*(t-j)
height_multiplier=1.5
trajectory=[z(i)*height_multiplier for i in range(n)]
for i in impacts:trajectory[i]=0
peaks=[max(trajectory[a:b]) for a,b in zip([0]+impacts[:-1],impacts)]
assert peaks[0]<peaks[1]<peaks[2]
p=entries(raw); oldrows=m.vaps_rows(p[9]); rows=list(oldrows); oldclips=m.vaps_rows(p[13]); clips=m.table(p[13]); oldch=channel_records(p[9]); donor=clips[0xd8baecc8]
idx=struct.unpack_from('>135I',donor,216); assert m.bone_ids(donor)[44]==0xc1
pos=oldch[idx[132]]; samples=list(struct.iter_unpack('>4f',pos[8:])); base=samples[0][1:]; peak=max(samples,key=lambda s:math.dist(s[1:],base))[1:]; delta=[a-b for a,b in zip(peak,base)]; mag=math.sqrt(sum(x*x for x in delta)); assert mag>2; up=[x/mag for x in delta]
key=0xc9fb4de3; original=clips[key]; stockidx=struct.unpack_from('>135I',original,216)
refs=collections.Counter(struct.unpack_from('>I',v,at)[0] for v in clips.values() for at in [80]+list(range(216,len(v),4)))
c=bytearray(donor); c[:64]=original[:64]; struct.pack_into('>2f',c,64,0,(n-1)*160)
for j,ix in enumerate(idx):
    orig=oldch[ix]; kind,stride,tag,_,_=struct.unpack_from('>BBHHH',orig)
    if j==132:
        data=bytearray(struct.pack('>BBHHH',kind,stride,tag,n,n))
        for i,h in enumerate(trajectory):data.extend(struct.pack('>4f',i*160,*(a+b*h for a,b in zip(base,up))))
    elif j==134:
        # Progressively stronger squash and rebound using the native Meteor
        # ball's scale-axis convention, then recover before the next launch.
        keys={0:1.0,n-1:1.0}
        for i,strength in zip(impacts,(.13,.24,.35)):
            keys.update({i-2:1.0,i-1:1+strength*.28,i:1-strength,i+1:1-strength*.55,i+2:1+strength*.34,i+4:1.0})
        data=bytearray(struct.pack('>BBHHH',kind,stride,tag,len(keys),len(keys)))
        for i,s in sorted(keys.items()):data.extend(struct.pack('>4f',i*160,1/math.sqrt(s),s,1/math.sqrt(s)))
    else:
        data=bytearray(struct.pack('>BBHHH',kind,stride,tag,2,2)); a=bytearray(orig[8:8+stride*4]); b=bytearray(a)
        if kind==16:a[-1]=0;b[-1]=n-1
        else:struct.pack_into('>f',a,0,0);struct.pack_into('>f',b,0,(n-1)*160)
        data.extend(a+b)
    slot=stockidx[j]
    if refs[slot]==1:
        rows[slot]=(rows[slot][0],rows[slot][1],bytes(data))
    else:
        assert j!=132;slot=ix
    struct.pack_into('>I',c,216+4*j,slot)
flags=[]
for i in impacts:
    for frame,mask in ((i,m.HEAD_START),(i+12,m.HEAD_STOP)):
        flags.append([struct.unpack('>I',struct.pack('>f',frame*160.0))[0],0,0,0,mask,0,0,0,0])
assert impacts[-1]+12<n
slot=struct.unpack_from('>I',original,80)[0];assert refs[slot]==1
struct.pack_into('>I',c,80,slot);rows[slot]=(rows[slot][0],rows[slot][1],m.flag_channel(flags))
updated=[(k,fl,bytes(c) if k==key else v) for k,fl,v in oldclips]
p[9]=m.build_vaps(9,struct.unpack_from('>H',p[9],12)[0],rows);p[13]=m.build_vaps(13,struct.unpack_from('>H',p[13],12)[0],updated); new=m.package(raw,p)
assert len(new)<=len(raw)
check=entries(new); nc=m.table(check[13]); ch=channel_records(check[9]); assert animation_time_range(nc[key],ch)==(0,(n-1)*160)
assert len(nc)==len(clips) and len(ch)==len(oldch)
assert all(streamed_clip(v,oldch)==streamed_clip(nc[k],ch) for k,v in clips.items() if k!=key)
assert all(check[k]==v for k,v in entries(raw).items() if k not in (9,13))
# This revision only changes the existing ball position channel, without
# changing any animation indices, events, or timing.
previous=entries((H/'ultimate-bounce-ball-v3/g_cb.xbx').read_bytes())
old_channels=m.vaps_rows(previous[9]); new_channels=m.vaps_rows(check[9])
position_slot=struct.unpack_from('>I',nc[key],216+132*4)[0]
assert len(old_channels)==len(new_channels)
assert [i for i,(a,b) in enumerate(zip(old_channels,new_channels)) if a!=b]==[position_slot]
assert all(check[k]==v for k,v in previous.items() if k!=9)
d=bytearray(ultimate); changed=[]
for at in range(4,len(d),224):
    if struct.unpack_from('>I',d,at+160)[0]!=0xba93374a:continue
    assert struct.unpack_from('>I',normal,at+32)[0]==0xd8baecc8
    for offset in (28,36,52,60,64,100,144,148,152,168):d[at+offset:at+offset+4]=normal[at+offset:at+offset+4]
    struct.pack_into('>I',d,at+32,key);struct.pack_into('>f',d,at+60,n/30);struct.pack_into('>I',d,at+148,m.crc('ucb_meteor_poe_fx_stop'));changed.append(at)
assert changed==[4,3140,5380]
assert all(d[at:at+224]==ultimate[at:at+224] for at in range(4,len(d),224) if at not in changed)
assert bytes(d)==(H/'ultimate-bounce-ball-v3/atk_ucb.ddf').read_bytes()
(O/'g_cb.xbx').write_bytes(new);(O/'atk_ucb.ddf').write_bytes(d)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(new),old_ucb_sha=sha(ultimate),new_ucb_sha=sha(d),normal_ddf_sha=sha(normal),source='atk_jump_s_land_b',frames=n,contacts=impacts,peak_heights=peaks,old_clip_count=len(clips),new_clip_count=len(nc),old_channel_count=len(oldch),new_channel_count=len(ch),gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
