"""Retime both Cannonbolts using their exact original Four Arms attack slots."""
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
from merge_alien_streams import entries, channel_records, animation_time_range, streamed_clip, merge_streams

ROOT=(APP_ROOT/'installation').resolve()
G=ROOT/'game/global'
BUNDLE=ROOT/'vilgax/cannonbolt/g_cb.xbx'
ACTIVE=G/'g_cb.xbx'
ORDER=(0,3,4,9,12,13,14,22,24)
SLOTS={0xc0077403,0x70017403,0x100c7403,0x20047403}
SHA=lambda b:hashlib.sha256(b).hexdigest()
raw=ACTIVE.read_bytes()
assert BUNDLE.read_bytes()==raw
sections=entries(raw);old_sections=dict(sections)
rows=m.vaps_rows(sections[9]);cliprows=m.vaps_rows(sections[13])
old_channels=channel_records(sections[9]);clips=m.table(sections[13])
assert [x[2] for x in rows]==old_channels

def duration(clip,channels):
    begin,end=animation_time_range(clip,channels)
    assert abs((end-begin)/160-round((end-begin)/160))<1e-5
    return int(round((end-begin)/160))

# Match the exact original selectors, including the longer finisher route.
donor=entries((G/'g_fa.xbx').read_bytes())
donor_clips=m.table(donor[13]);donor_channels=channel_records(donor[9])
donor_routes={}
for row in struct.iter_unpack('>56I',(G/'scripts/atk_fa.ddf').read_bytes()[4:]):
    if row[4] in SLOTS:
        assert row[4] not in donor_routes
        donor_routes[row[4]]=row[7:10]
assert set(donor_routes)==SLOTS
targets={};route_report=[];attack_bytes={}
for code in ('cb','ucb'):
    path=G/'scripts'/f'atk_{code}.ddf';data=path.read_bytes();attack_bytes[path]=data
    name='cannonbolt' if code=='cb' else 'ultimatecannonbolt'
    bundle=ROOT/'vilgax'/name/path.name
    assert bundle.read_bytes()==data;attack_bytes[bundle]=data
    count=0
    for row in struct.iter_unpack('>56I',data[4:]):
        if row[4] not in SLOTS:continue
        count+=1;oldframes=[];newframes=[]
        for key,reference in zip(row[7:10],donor_routes[row[4]]):
            assert bool(key)==bool(reference)
            if not key:continue
            assert clips[key].startswith(f'cosmic_{code}_'.encode())
            target=duration(donor_clips[reference],donor_channels)
            prior=duration(clips[key],old_channels)
            assert key not in targets or targets[key]==target
            targets[key]=target;oldframes.append(prior);newframes.append(target)
        route_report.append({'form':code,'slot':hex(row[4]),'before_frames':oldframes,'native_frames':newframes})
    assert count==4
assert len(targets)==16

def norm(q):
    n=math.sqrt(sum(x*x for x in q));assert n>0
    return tuple(x/n for x in q)

def slerp(a,b,u):
    dot=sum(x*y for x,y in zip(a,b))
    if dot<0:b=tuple(-x for x in b);dot=-dot
    dot=min(1,max(-1,dot))
    if dot>.9995:return norm(tuple(x+(y-x)*u for x,y in zip(a,b)))
    angle=math.acos(dot);den=math.sin(angle)
    return norm(tuple((math.sin((1-u)*angle)*x+math.sin(u*angle)*y)/den for x,y in zip(a,b)))

def quantize(q,frame):
    x,y,z,w=q
    return struct.pack('>3hbB',*(max(-32767,min(32767,round(v*32767))) for v in (x,y,z)),max(-127,min(127,round(w*127))),frame)

def resample(channel,before,after,visibility=False):
    kind,stride,tag,count,repeated=struct.unpack_from('>BBHHH',channel)
    assert count==repeated==before+1 and kind in (1,12,16)
    if kind==16:
        origin=[norm((x/32767,y/32767,z/32767,w/127)) for x,y,z,w,t in struct.iter_unpack('>3hbB',channel[8:])]
        assert [t for *_,t in struct.iter_unpack('>3hbB',channel[8:])]==list(range(count))
    else:
        assert [t for t,*_ in struct.iter_unpack('>4f',channel[8:])]==[i*160 for i in range(count)]
        origin=[v[1:] for v in struct.iter_unpack('>4f',channel[8:])]
    out=bytearray(struct.pack('>BBHHH',kind,stride,tag,after+1,after+1));previous=None
    for frame in range(after+1):
        source=frame*before/after;lo=int(source);hi=min(lo+1,before);u=source-lo
        a,b=origin[lo],origin[hi]
        if kind==16:
            q=slerp(a,b,u)
            if previous is not None and sum(x*y for x,y in zip(q,previous))<0:q=tuple(-v for v in q)
            out.extend(quantize(q,frame));previous=q
        else:
            # Keep native body/ball form switches on the same discrete sample,
            # rather than interpolating through two partially visible forms.
            if visibility and (max(a)<.001)!=(max(b)<.001):v=a if u<.5 else b
            else:v=tuple(x+(y-x)*u for x,y in zip(a,b))
            out.extend(struct.pack('>4f',frame*160,*v))
    return bytes(out)

def retime_events(data,before,after):
    n,repeated=struct.unpack_from('>HH',data,4)
    assert n==repeated and len(data)==8+36*n
    out=bytearray(data);last=-1
    for j in range(n):
        at=8+36*j;t=struct.unpack_from('>f',data,at)[0]
        value=max(1,min(after*160-1,t*after/before))
        assert value>=last;last=value
        struct.pack_into('>f',out,at,value)
        assert out[at+4:at+36]==data[at+4:at+36]
    return bytes(out)

cache={};new_payloads={};updated=[];changed=[]
def channel_index(index,before,after,visibility=False,event=False):
    key=(index,before,after,visibility,event)
    if key not in cache:
        data=old_channels[index]
        revised=retime_events(data,before,after) if event else resample(data,before,after,visibility)
        # Do not modify a channel shared with a dodge or any other original clip.
        if revised not in new_payloads:
            name=f'cannonbolt_native_timing_{index}_{before}_{after}_{int(visibility)}_{int(event)}'
            new_payloads[revised]=len(rows);rows.append((m.crc(name),0,revised))
        cache[key]=new_payloads[revised]
    return cache[key]

for key,flag,clip in cliprows:
    before=duration(clip,old_channels) if key in targets else 0
    after=targets.get(key,before)
    if before==after:updated.append((key,flag,clip));continue
    c=bytearray(clip)
    assert animation_time_range(clip,old_channels)[0]==0
    for at in range(216,len(c),4):
        index=struct.unpack_from('>I',c,at)[0];assert index!=0xffffffff
        visibility=(at-216)//4 in (5,134)
        new_index=channel_index(index,before,after,visibility)
        struct.pack_into('>I',c,at,new_index)
    event=struct.unpack_from('>I',c,80)[0]
    if event!=0xffffffff:struct.pack_into('>I',c,80,channel_index(event,before,after,event=True))
    struct.pack_into('>2f',c,64,0,after*160)
    updated.append((key,flag,bytes(c)));changed.append(key)

# Reorder bank directory and remap every reference, preserving the original
# streamed representation of every non-target clip byte for byte.
buckets=max(1,len(rows)//4)
order=sorted(range(len(rows)),key=lambda i:(rows[i][0]%buckets,rows[i][0],i))
remap={i:j for j,i in enumerate(order)}
reindexed=[]
for key,flag,clip in updated:
    c=bytearray(clip)
    for at in [80]+list(range(216,len(c),4)):
        i=struct.unpack_from('>I',c,at)[0]
        if i!=0xffffffff:struct.pack_into('>I',c,at,remap[i])
    reindexed.append((key,flag,bytes(c)))
sections[9]=m.build_vaps(9,struct.unpack_from('>H',sections[9],12)[0],[rows[i] for i in order])
sections[13]=m.build_vaps(13,struct.unpack_from('>H',sections[13],12)[0],m.bucket_sorted(reindexed))
new=m.package(raw,sections,ORDER)
decoded=entries(new);nc=channel_records(decoded[9]);nd=m.table(decoded[13])
assert set(nd)==set(clips)
assert all(decoded[k]==v for k,v in old_sections.items() if k not in (9,13))
for key,clip in clips.items():
    if key not in changed:
        assert streamed_clip(clip,old_channels)==streamed_clip(nd[key],nc)
    if key in targets:
        assert animation_time_range(nd[key],nc)==(0.0,targets[key]*160.0)
        switches=[]
        for i in (5,134):
            ix=struct.unpack_from('>I',nd[key],216+4*i)[0]
            switches.append([max(v[1:]) for v in struct.iter_unpack('>4f',nc[ix][8:])])
        assert len(switches[0])==len(switches[1])==targets[key]+1
        assert all((a>.1)!=(b>.1) for a,b in zip(*switches)),hex(key)
        old_event=struct.unpack_from('>I',clip,80)[0];new_event=struct.unpack_from('>I',nd[key],80)[0]
        if old_event!=0xffffffff:
            o,n=old_channels[old_event],nc[new_event]
            assert o[:8]==n[:8] and all(o[a+4:a+36]==n[a+4:a+36] for a in range(8,len(o),36))
        else:assert new_event==0xffffffff

# Reconstruct launcher level streams from their originals and check the
# replacement clips, avoiding changes to unrelated level content.
archives=[]
for name in ('ad','af','bc','ec','hm','nr','ra','sf','sm','ts','wh','ubc','uec','uhm','usf','usm'):
    path=G/f'g_{name}.xbx';archives.append((path.name,path.read_bytes()))
archives.extend((name,(G/name).read_bytes()) for name in ('a_plyr.xbx','g_fa.xbx'))
imported=[]
for d in (ROOT/'vilgax').iterdir():
    p=d/'form-ids.txt'
    if p.is_file():imported.append((int(p.read_text().split()[1]),d))
imported_keys=set()
for _,d in sorted(imported):
    for p in sorted(d.glob('g_*.xbx')):
        data=new if p.name=='g_cb.xbx' else (G/p.name).read_bytes()
        archives.append((p.name,data));parts=entries(data)
        if 13 in parts:imported_keys.update(entries(parts[13],True))
levels=[]
for level in sorted((ROOT/'game').glob('l_*')):
    level_archives=archives+[(p.name,p.read_bytes()) for p in sorted(level.glob('g_*.xbx'))]
    for bank in level.glob('a_*_s.xbx'):
        original=bank.with_name(bank.name+'.cosmic-animation-original')
        assert original.is_file()
        current=entries(bank.read_bytes(),True)
        expected=entries(merge_streams(original.read_bytes(),level_archives)[0])
        assert set(current)<=set(expected) and set(expected)-set(current)<=imported_keys
        assert all(current[k]==expected[k] for k in current if k not in imported_keys)
        assert all(expected[k]==streamed_clip(nd[k],nc) for k in targets)
        levels.append(level.name)
assert len(levels)==8

backup=(WORK/'cannonbolt-long-timing-fix')/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True)
for path in (ACTIVE,BUNDLE):
    rel=path.relative_to(ROOT);saved=backup/'before'/rel;saved.parent.mkdir(parents=True);saved.write_bytes(raw)
    candidate=backup/'after'/rel;candidate.parent.mkdir(parents=True);candidate.write_bytes(new)
report={'before_sha':SHA(raw),'after_sha':SHA(new),'changed_clips':len(changed),'target_clips':len(targets),'routes':route_report,
        'level_preflight':levels,'dodge_and_specials_unchanged':True,'gameplay_verified':False}
(backup/'validation.json').write_text(json.dumps(report,indent=2))
if '--install' in sys.argv:
    assert ACTIVE.read_bytes()==BUNDLE.read_bytes()==raw
    assert all(path.read_bytes()==data for path,data in attack_bytes.items())
    installed=[]
    try:
        for path in (ACTIVE,BUNDLE):
            temp=path.with_name(path.name+'.timing-new');assert not temp.exists();temp.write_bytes(new);temp.replace(path)
            installed.append(path);assert path.read_bytes()==new
    except BaseException:
        for path in reversed(installed):
            temp=path.with_name(path.name+'.timing-restore');assert not temp.exists();temp.write_bytes(raw);temp.replace(path)
        raise
    assert all(path.read_bytes()==data for path,data in attack_bytes.items())
    print('INSTALLED',len(changed),'retimed clips;',len(levels),'level streams validated; attack and dodge data preserved.')
print(json.dumps(report,indent=2))
print('Backup:',backup)
