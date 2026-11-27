"""Wider bounce shocks, a hard root stop, and a separate synced POE sound event."""
import hashlib,json,math,struct,sys,wave
from pathlib import Path
import numpy as np
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries

H = WORK;I=APP_ROOT/'installation';G=I/'game/global';U=I/'vilgax/ultimatecannonbolt';O=H/'ultimate-bounce-ball-v9-sync';O.mkdir(exist_ok=True)
sha=lambda x:hashlib.sha256(x).hexdigest();prev=json.loads((H/'ultimate-bounce-ball-v8-progressive/validation.json').read_text());raw=(G/'g_cb.xbx').read_bytes();d0=(G/'scripts/atk_ucb.ddf').read_bytes();u0=(G/'g_ucb.xbx').read_bytes();normal=(G/'scripts/atk_cb.ddf').read_bytes()
assert sha(raw)==prev['new_cb_sha'] and sha(d0)==prev['new_ucb_sha'] and sha(normal)==prev['normal_ddf_sha']
assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes() and d0==(U/'atk_ucb.ddf').read_bytes() and u0==(U/'g_ucb.xbx').read_bytes()
p=entries(raw);old=dict(p);root=m.effect_root('cannonbolt');mesh=m.crc('ucb_bounce_impact_star');start=m.crc('ucb_bounce_contact');finish=m.crc('ucb_bounce_final_stop');stop=m.crc('ucb_bounce_stop')
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(i,rows):p[i]=m.build_vaps(i,struct.unpack_from('>H',p[i],12)[0],rows)
def groups(b):
    out=[]
    for a,t,v in m.property_entries(b):
        if t==0x1000c:out.append([])
        assert out;out[-1].append((a,t,v))
    return out
def clone(g,name,settings):return [(m.crc(name) if t==0x1000c else a,t,settings.get(a,v)) for a,t,v in g]

# 40% wider in both ground-plane axes. Keep the working UVs, color, radius
# progression and timing curve identical.
width=1.4;rows=[]
for k,f,v in m.vaps_rows(p[4]):
    if k==mesh:
        q=bytearray(v);off,vb,ib=m.mesh_buffers(v,xbox=True)
        for at in range(0,len(vb),20):
            x,y,z=struct.unpack_from('>3f',vb,at);struct.pack_into('>3f',q,off+at,x*width,y,z*width)
        v=bytes(q);assert m.mesh_buffers(v,xbox=True)[2]==ib
    rows.append((k,f,v))
bank(4,rows)

# Stop the complete sequence just after the third disk has faded. The
# proven meteor timer lives on the root, not the self-timing child (whose
# animation continued looping). Route a dedicated final stop to the disk.
nodes=m.table(p[14]);h,b=m.node_parts(nodes[root]);rp=next(x for x in b if x[0]==14);rg=groups(rp);assert len(rg)==45
timer=next(g for g in rg if g[0][0]==m.crc('ucb_meteor_poe_timer'))
prune={m.crc(n) for n in ('ucb_bounce_late_particles','ucb_bounce_second_contact_timer','ucb_bounce_third_contact_timer','ucb_bounce_later_particles_stop')}
assert sum(g[0][0] in prune for g in rg)==4
duration=58/30
rg=[g for g in rg if g[0][0] not in prune]
rg.append(clone(timer,'ucb_bounce_root_end_timer',{0x8541406c:[start],0x865f80c0:fs(duration),0xd058515c:[finish]}))
rg.append([(m.crc('ucb_bounce_root_stop_forward'),0x1000c,[m.EVENT_GROUP]),(0x939b68a0,0x201000c,[finish]),(0x8541406c,0x201000c,[finish]),(0x557c4b4d,0x201000c,[mesh])])
assert len(rg)==43
root_record=m.node_record(h,[m.node_properties([entry for g in rg for entry in g]) if x[0]==14 else x for x in b])
assert len(root_record)<len(nodes[root])
h,b=m.node_parts(nodes[mesh]);h=list(h);h[19:26]=fs(6.5,-6.5,-.1,-6.5,6.5,2,6.5)
child_prune={m.crc(n) for n in ('ucb_bounce_first_particles','ucb_bounce_first_particles_stop','ucb_bounce_child_end_timer')};out=[]
for x in b:
    if x[0]==14:
        gg=groups(x);assert sum(g[0][0] in child_prune for g in gg)==3
        pp=[entry for g in gg if g[0][0] not in child_prune for entry in g]
        assert (0xa3911ca7,0x201000c,[finish]) in pp and (0xf7be9018,0x201000c,[finish]) in pp
        x=m.node_properties(pp)
    out.append(x)
child=m.node_record(h,out)
bank(14,[(k,f,root_record if k==root else child if k==mesh else v) for k,f,v in m.vaps_rows(p[14])])
new=m.package(raw,p);check=entries(new)
assert all(check[k]==v for k,v in old.items() if k not in (4,14))
assert all(m.table(check[4])[k]==v for k,v in m.table(old[4]).items() if k!=mesh)
assert all(m.table(check[14])[k]==v for k,v in nodes.items() if k not in (root,mesh))

# On the verified runtime the attack sound descriptor is played 0.650s
# before HEAD_START. Author three separate POE impacts into a one-shot
# wave at these contact times. Do not change the normal Meteor sound or
# the existing four active event mappings on the private UCB project.
up=entries(u0);ubank=up[24];ur=m.vaps_rows(ubank);fev=bytearray(ur[0][2][32:]);fsb=ur[1][2][32:];count,hs,ds=struct.unpack_from('<3I',fsb,4);assert count==29 and hs==80*count and len(fsb)==48+hs+ds
marker=struct.pack('<I',8)+b'ucbpova\0';wave_references=[];a=fev.find(marker)
while a>=0:
    pos=a+len(marker)
    if fev[:a].endswith(b'.wav\0'):wave_references.append(pos)
    a=fev.find(marker,pos)
used={struct.unpack_from('<I',fev,pos)[0] for pos in wave_references};assert 6 not in used and 11 not in used and 7 in used
wave_prefix=b'four_aoe.wav\0'+marker;assert fev.count(wave_prefix)==1;pos=fev.find(wave_prefix)+len(wave_prefix);assert struct.unpack_from('<II',fev,pos)==(3,580)
assert b'four_seismic_upper_aoe\0' in fev # stock one-shot event 16, no pitch offset
rate=8000;contacts=[.650+x/30 for x in prev['relative_contacts']]
with wave.open(str(H/'meteor-audio-fix/meteor_candidate.wav'),'rb') as w:
    sr=w.getframerate();assert w.getnchannels()==1 and w.getsampwidth()==2
    x=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)
# Trim the initial lead-in of the impact sample so its strongest transient
# occurs immediately after the contact; preserve its natural decay.
assert sr==48000;x=x[round(.090*sr):];x-=x.mean();x=np.array([np.mean(x[i:i+6]) for i in range(0,len(x),6)])
x*=np.minimum(1,np.arange(len(x))/32);x[-80:]*=np.linspace(1,0,80);x*=26000/max(1,np.max(np.abs(x)))
track=np.zeros(round((contacts[-1]+len(x)/rate+.025)*rate))
for when,gain in zip(contacts,(.78,.89,1.0)):
    i=round(when*rate);track[i:i+len(x)]+=x*gain
pcm=np.rint(track).astype('>i2').tobytes();ns=len(track);pcm+=bytes((-len(pcm))%2048);ms=round(ns/rate*1000)
struct.pack_into('<II',fev,pos,11,ms)
headers=bytearray();payload=bytearray();at=48+hs
for j in range(count):
    h=bytearray(fsb[48+j*80:48+(j+1)*80]);n,size,_,_,mode,sr=struct.unpack_from('<6I',h,32);assert mode==0x131 and sr==rate and n*2<=size;data=fsb[at:at+size];at+=size
    if j==6:
        # Unreferenced duplicate of slot 7: reclaim its allocation so our
        # new three-hit track does not grow the proven character package.
        assert j not in used;data=bytes(2048);struct.pack_into('<4I',h,32,16,len(data),0,0)
    elif j==11:
        assert j not in used;data=pcm;struct.pack_into('<4I',h,32,ns,len(data),0,0)
    headers.extend(h);payload.extend(data)
assert at==len(fsb);head=bytearray(fsb[:48]);struct.pack_into('<3I',head,4,count,len(headers),len(payload));newfsb=bytes(head+headers+payload)
assert len(newfsb)<=len(fsb)
wrapper=bytearray(ur[1][2][:32]);struct.pack_into('>I',wrapper,4,len(newfsb));ur[0]=(ur[0][0],ur[0][1],ur[0][2][:32]+fev);ur[1]=(ur[1][0],ur[1][1],bytes(wrapper)+newfsb)
up[24]=m.build_vaps(24,struct.unpack_from('>H',ubank,12)[0],ur);unew=m.package(u0,up);assert len(unew)<=len(u0) and all(entries(unew)[k]==v for k,v in entries(u0).items() if k!=24)

name='ucb_poe_bounce';descriptor=f'<sound name="{name}" id="16" swpgroupid="0" prjid="ucbpova"/>'.encode();soundtxt=(U/'sounds.txt').read_bytes();sounds=(G/'scripts/sounds.ddf').read_bytes();assert descriptor not in soundtxt and descriptor not in sounds
line=b'<sound name="ucb_poe_spin" id="19" swpgroupid="0" prjid="ucbpova"/>'
assert sounds.count(line+b'\r\n')==1 and soundtxt.count(line)==1
newtxt=soundtxt.rstrip(b'\r\n')+b'\n'+descriptor+b'\n';newsounds=sounds.replace(line+b'\r\n',line+b'\r\n'+descriptor+b'\r\n',1)
d=bytearray(d0);changes=[]
for at in range(4,len(d),224):
    if struct.unpack_from('>I',d,at+32)[0]!=0xc9fb4de3:continue
    assert struct.unpack_from('>I',d,at+152)[0]==m.crc('ucb_poe_meteor')
    struct.pack_into('>I',d,at+152,m.crc(name));changes.append(at)
assert changes==[4,3140,5380]
assert all(d[at:at+224]==d0[at:at+224] for at in range(4,len(d),224) if at not in changes)
for filename,data in [('g_cb.xbx',new),('g_ucb.xbx',unew),('atk_ucb.ddf',d),('sounds.txt',newtxt),('sounds.ddf',newsounds)]: (O/filename).write_bytes(data)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(new),old_ucb_sha=sha(d0),new_ucb_sha=sha(d),old_model_sha=sha(u0),new_model_sha=sha(unew),old_soundtxt_sha=sha(soundtxt),new_soundtxt_sha=sha(newtxt),old_sounds_sha=sha(sounds),new_sounds_sha=sha(newsounds),normal_ddf_sha=sha(normal),contact_seconds=contacts,sound_seconds=ns/rate,sound_event=16,width_multiplier=width,final_stop_seconds_after_first_contact=duration,root_groups_before=45,root_groups_after=43,animation_unchanged=True,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
