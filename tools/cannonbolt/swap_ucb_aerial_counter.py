"""Move Ultimate Cannonbolt's aerial lunge to its dodge-counter routes."""
import bisect
import datetime
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,animation_time_range,streamed_clip,merge_streams

ROOT=(APP_ROOT/'installation').resolve()
G=ROOT/'game/global';U=ROOT/'vilgax/ultimatecannonbolt';N=ROOT/'vilgax/cannonbolt'
raw=(G/'g_cb.xbx').read_bytes();assert raw==(N/'g_cb.xbx').read_bytes()
parts=entries(raw);old=dict(parts);rows=m.vaps_rows(parts[9]);clips=m.vaps_rows(parts[13]);channels=channel_records(parts[9]);table=m.table(parts[13])
byname={v[:64].split(b'\0')[0].decode():k for k,v in table.items()}
FAR={0x100c7403,0x20047403};COUNTER={0x40a57603,0x40a27603}
atk=(G/'scripts/atk_ucb.ddf').read_bytes();assert atk==(U/'atk_ucb.ddf').read_bytes()
normal=(G/'scripts/atk_cb.ddf').read_bytes()
donor=entries((G/'g_fa.xbx').read_bytes());dt=m.table(donor[13]);dc=channel_records(donor[9])
timing={}
for r in struct.iter_unpack('>56I',(G/'scripts/atk_fa.ddf').read_bytes()[4:]):
    if r[4] in FAR|COUNTER:timing[r[4]]=tuple(round((lambda t:t[1]-t[0])(animation_time_range(dt[k],dc))/160) for k in r[7:10])
assert all(timing[k]==(10,6,12) for k in FAR) and all(timing[k]==(10,7,16) for k in COUNTER)

def norm(q):
    n=math.sqrt(sum(x*x for x in q));assert n>0
    return tuple(x/n for x in q)

def slerp(a,b,u):
    d=sum(x*y for x,y in zip(a,b))
    if d<0:b=tuple(-x for x in b);d=-d
    d=min(1,max(-1,d))
    if d>.9995:return norm(tuple(x+(y-x)*u for x,y in zip(a,b)))
    t=math.acos(d);s=math.sin(t)
    return norm(tuple((x*math.sin((1-u)*t)+y*math.sin(u*t))/s for x,y in zip(a,b)))

def sample_track(blob,begin,end,frames,visibility):
    kind,stride,tag,n,repeat=struct.unpack_from('>BBHHH',blob)
    assert kind in (1,12,16) and n==repeat and n>0
    if kind==16:
        samples=[(t*160,norm((x/32767,y/32767,z/32767,w/127))) for x,y,z,w,t in struct.iter_unpack('>3hbB',blob[8:])]
    else:samples=[(t,(x,y,z)) for t,x,y,z in struct.iter_unpack('>4f',blob[8:])]
    assert len(samples)==n
    times=[x[0] for x in samples];assert times==sorted(times)
    out=bytearray(struct.pack('>BBHHH',kind,stride,tag,frames+1,frames+1));previous=None
    for f in range(frames+1):
        t=begin+(end-begin)*f/frames;j=bisect.bisect_right(times,t)
        if j==0:v=samples[0][1]
        elif j==n:v=samples[-1][1]
        else:
            a,b=samples[j-1][1],samples[j][1];u=(t-times[j-1])/(times[j]-times[j-1])
            if kind==16:v=slerp(a,b,u)
            elif visibility and (max(a)<.001)!=(max(b)<.001):v=a if u<.5 else b
            else:v=tuple(x+(y-x)*u for x,y in zip(a,b))
        if kind==16:
            if previous is not None and sum(x*y for x,y in zip(v,previous))<0:v=tuple(-x for x in v)
            x,y,z,w=v;out.extend(struct.pack('>3hbB',*(max(-32767,min(32767,round(a*32767))) for a in (x,y,z)),max(-127,min(127,round(w*127))),f))
            previous=v
        else:out.extend(struct.pack('>4f',f*160,*v))
    return bytes(out)

def event_track(event_donor,frames,impact):
    c=table[event_donor];i=struct.unpack_from('>I',c,80)[0]
    assert i!=0xffffffff
    data=channels[i];n,rep=struct.unpack_from('>HH',data,4);assert n==rep and len(data)==8+36*n
    begin,end=animation_time_range(c,channels)
    times=[struct.unpack_from('>f',data,8+36*j)[0] for j in range(n)]
    idx=next(j for j in range(n) if struct.unpack_from('>I',data,8+36*j+16)[0] in (0x100000,0x80000))
    pivot=times[idx];goal=impact*160;length=frames*160
    out=bytearray(data)
    for j,t in enumerate(times):
        f=(t-begin)/max(1,pivot-begin)*goal if t<=pivot else goal+(t-pivot)/max(1,end-pivot)*(length-goal)
        struct.pack_into('>f',out,8+36*j,max(1,min(length-1,f)))
    assert all(out[a+4:a+36]==data[a+4:a+36] for a in range(8,len(data),36))
    return bytes(out)

newtracks={};added=[];expected={}
def addtrack(data,name):
    if data not in newtracks:
        newtracks[data]=len(rows);rows.append((m.crc(name),0,data))
    return newtracks[data]

def clone(name,source,frames,event_donor=None,impact=None):
    key=m.crc(name);assert key not in table and key not in expected
    c=bytearray(table[source]);assert len(m.bone_ids(c))==45
    begin,end=animation_time_range(c,channels)
    c[:64]=name.encode().ljust(64,b'\0');struct.pack_into('>2f',c,64,0,160*frames)
    event=event_track(event_donor,frames,impact) if event_donor else None
    struct.pack_into('>I',c,80,addtrack(event,name+'_events') if event else 0xffffffff)
    for at in range(216,len(c),4):
        i=struct.unpack_from('>I',c,at)[0]
        assert i!=0xffffffff
        j=addtrack(sample_track(channels[i],begin,end,frames,(at-216)//4 in (5,134)),f'{name}_{at}')
        struct.pack_into('>I',c,at,j)
    added.append((key,0,bytes(c)));expected[key]=frames
    return key

aerial_travel=byname['cosmic_ucb_aerial_travel'];ground_travel=byname['cosmic_ucb_ram_travel']
aerial_source=byname['cosmic_ucb_aerial_hit_70de98dc']
counter_hit=clone('cosmic_ucb_dodge_counter_aerial_hit',aerial_source,7,byname['punch_04'],1.5)
counter_recovery=clone('cosmic_ucb_dodge_counter_aerial_out',byname['cosmic_ucb_aerial_recovery'],16)
ground_recovery=clone('cosmic_ucb_far_ground_counter_out',byname['punch_out_04'],12)
newatk=bytearray(atk);report=[];swapped=set()
for at in range(4,len(atk),224):
    r=list(struct.unpack_from('>56I',atk,at));slot=r[4]
    if slot not in FAR|COUNTER:continue
    oldkeys=tuple(r[7:10]);assert r[40]==0x47c02d3b
    if slot in COUNTER:
        assert oldkeys==(byname['run_01'],byname['punch_04'],byname['punch_out_04'])
        r[7:10]=[aerial_travel,counter_hit,counter_recovery]
    else:
        assert r[7]==aerial_travel and r[9]==byname['cosmic_ucb_aerial_recovery']
        hit=clone(f'cosmic_ucb_far_ground_hit_{r[0]:08x}',byname['punch_04'],6,r[8],1.5)
        r[7:10]=[ground_travel,hit,ground_recovery]
    struct.pack_into('>56I',newatk,at,*r);swapped.add(slot)
    report.append({'slot':hex(slot),'before':[hex(k) for k in oldkeys],'after':[hex(k) for k in r[7:10]],'frames':timing[slot]})
assert swapped==FAR|COUNTER
for at in range(4,len(atk),224):assert atk[at:at+28]==newatk[at:at+28] and atk[at+40:at+224]==newatk[at+40:at+224]

# Append only new clips: all existing animations, including normal Cannonbolt
# and the approved dodge itself, remain byte-equivalent after reindexing.
buckets=max(1,len(rows)//4);order=sorted(range(len(rows)),key=lambda i:(rows[i][0]%buckets,rows[i][0],i));remap={i:j for j,i in enumerate(order)}
updated=[]
for k,flag,c in clips+added:
    c=bytearray(c)
    for at in [80]+list(range(216,len(c),4)):
        i=struct.unpack_from('>I',c,at)[0]
        if i!=0xffffffff:struct.pack_into('>I',c,at,remap[i])
    updated.append((k,flag,bytes(c)))
parts[9]=m.build_vaps(9,struct.unpack_from('>H',parts[9],12)[0],[rows[i] for i in order]);parts[13]=m.build_vaps(13,struct.unpack_from('>H',parts[13],12)[0],m.bucket_sorted(updated))
new=m.package(raw,parts,(0,3,4,9,12,13,14,22,24));check=entries(new);nc=channel_records(check[9]);nd=m.table(check[13])
assert all(check[k]==v for k,v in old.items() if k not in (9,13))
assert all(streamed_clip(c,channels)==streamed_clip(nd[k],nc) for k,c in table.items())
for k,f in expected.items():
    assert animation_time_range(nd[k],nc)==(0.0,f*160.0)
    s=[]
    for j in (5,134):
        ix=struct.unpack_from('>I',nd[k],216+4*j)[0];s.append([max(v[1:]) for v in struct.iter_unpack('>4f',nc[ix][8:])])
    assert all((a>.1)!=(b>.1) for a,b in zip(*s))
for entry in report:
    assert tuple(round((lambda t:t[1]-t[0])(animation_time_range(nd[int(k,16)],nc))/160) for k in entry['after'])==entry['frames']

# Verify every level can load the new imported clips with the existing loader.
archives=[(f'g_{n}.xbx',(G/f'g_{n}.xbx').read_bytes()) for n in ('ad','af','bc','ec','hm','nr','ra','sf','sm','ts','wh','ubc','uec','uhm','usf','usm')]
archives.extend((n,(G/n).read_bytes()) for n in ('a_plyr.xbx','g_fa.xbx'))
imports=[];imported_keys=set()
for d in (ROOT/'vilgax').iterdir():
    p=d/'form-ids.txt'
    if p.is_file():imports.append((int(p.read_text().split()[1]),d))
for _,d in sorted(imports):
    for p in sorted(d.glob('g_*.xbx')):
        b=new if p.name=='g_cb.xbx' else (G/p.name).read_bytes();archives.append((p.name,b));s=entries(b)
        if 13 in s:imported_keys.update(entries(s[13],True))
levels=[]
for level in sorted((ROOT/'game').glob('l_*')):
    ar=archives+[(p.name,p.read_bytes()) for p in sorted(level.glob('g_*.xbx'))]
    for p in level.glob('a_*_s.xbx'):
        current=entries(p.read_bytes(),True);merged=entries(merge_streams(p.with_name(p.name+'.cosmic-animation-original').read_bytes(),ar)[0])
        assert set(current)<=set(merged) and set(merged)-set(current)<=imported_keys
        assert all(current[k]==merged[k] for k in current if k not in imported_keys)
        assert all(merged[k]==streamed_clip(nd[k],nc) for k in expected)
        levels.append(level.name)
assert len(levels)==8

changes={G/'g_cb.xbx':(raw,new),N/'g_cb.xbx':(raw,new),G/'scripts/atk_ucb.ddf':(atk,bytes(newatk)),U/'atk_ucb.ddf':(atk,bytes(newatk))}
backup=(WORK/'ucb-aerial-counter-swap')/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');backup.mkdir(parents=True)
for p,(before,after) in changes.items():
    for folder,content in [('before',before),('after',after)]:
        save=backup/folder/p.relative_to(ROOT);save.parent.mkdir(parents=True,exist_ok=True);save.write_bytes(content)
assert all(p.read_bytes()==before for p,(before,_) in changes.items())
installed=[]
try:
    for p,(before,after) in changes.items():
        tmp=p.with_name(p.name+'.counter-new');assert not tmp.exists();tmp.write_bytes(after);tmp.replace(p);installed.append(p);assert p.read_bytes()==after
except BaseException:
    for p in reversed(installed):
        tmp=p.with_name(p.name+'.counter-restore');assert not tmp.exists();tmp.write_bytes(changes[p][0]);tmp.replace(p)
    raise
assert (G/'scripts/atk_cb.ddf').read_bytes()==normal
(backup/'validation.json').write_text(json.dumps({'routes':report,'new_clips':len(added),'levels':levels,'gameplay_verified':False},indent=2))
print('Installed aerial dodge-counter, grounded second lunge; 8 levels preflighted. Backup:',backup)
