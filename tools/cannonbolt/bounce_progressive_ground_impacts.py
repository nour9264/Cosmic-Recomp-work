"""Use one timed ground-impact sequence; conserve the stable root component budget."""
import hashlib,json,math,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries

H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'ultimate-bounce-ball-v8-progressive';O.mkdir(exist_ok=True)
stable=H/'ultimate-bounce-ball-v7-stable';r=json.loads((stable/'validation.json').read_text());previous=H/'ultimate-bounce-ball-v5-impact';sha=lambda x:hashlib.sha256(x).hexdigest()
raw=(G/'g_cb.xbx').read_bytes();d0=(G/'scripts/atk_ucb.ddf').read_bytes();normal=(G/'scripts/atk_cb.ddf').read_bytes();assert sha(raw)==r['new_cb_sha'] and sha(d0)==r['new_ucb_sha'] and sha(normal)==r['normal_ddf_sha']
assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes() and d0==(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
p=entries(raw);old=dict(p);assets=entries((previous/'g_cb.xbx').read_bytes())
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(i,rows,sort=False):p[i]=m.build_vaps(i,struct.unpack_from('>H',p[i],12)[0],m.bucket_sorted(rows) if sort else rows)
def groups(block):
    out=[]
    for a,t,v in m.property_entries(block):
        if t==0x1000c:out.append([])
        assert out;out[-1].append((a,t,v))
    return out
def flatten(gg):return [a for g in gg for a in g]
def clone(g,name,settings):return [(m.crc(name) if t==0x1000c else a,t,settings.get(a,v)) for a,t,v in g]
tex=m.crc('ucb_bounce_impact_star_tex');mesh=m.crc('ucb_bounce_impact_star');root=m.effect_root('cannonbolt');start=m.crc('ucb_bounce_contact');stop=m.crc('ucb_bounce_stop');finish=m.crc('ucb_bounce_final_stop');flecks=m.crc('ucb_bounce_late_flecks')
oldstart=m.crc('ucb_meteor_poe_contact');oldstop=m.crc('ucb_meteor_poe_fx_stop');dust_ids=[m.crc(f'ucb_meteor_poe_dust_{i}') for i in range(6)]
for part,key in ((0,tex),(3,mesh),(4,mesh)):
    rows=m.vaps_rows(p[part]);record=next(row for row in m.vaps_rows(assets[part]) if row[0]==key);assert key not in m.table(p[part]);bank(part,rows+[record],True)

# The engine dispatched only the first HEAD_START from the tested bounce clip.
# Therefore advance all three impact pulses on one native timeline, starting
# at contact 1, rather than expecting the later HEAD_START events to re-fire.
# Relative frame offsets: 0,22,46. Peak radii: 55%,78%,100%.
offsets=[x-r['contacts'][0] for x in r['contacts']];assert offsets==[0,22,46]
scales=(.55,.78,1.0);keys={}
for frame,peak in zip(offsets,scales):
    if frame:keys[frame-1]=.0001
    keys.update({frame:peak*.72,frame+2:peak,frame+5:peak*1.05,frame+8:peak*1.08,frame+10:peak*.66,frame+12:.0001})
duration=(offsets[-1]+13)/30
keys[offsets[-1]+13]=.0001
curve=[0x19,4+10*len(keys),0x0d0a5003,len(keys)<<16|len(keys)]
for frame,scale in sorted(keys.items()):curve+=fs(frame*160)+[0]*6+fs(scale,1,scale)
assert len(curve)==curve[1]

nodes=m.table(p[14]);rh,rb=m.node_parts(nodes[root]);rp=next(b for b in rb if b[0]==14);rg=groups(rp);assert len(rg)==45
original_dust=[next(g for g in rg if g[0][0]==key) for key in dust_ids]
timer=next(g for g in rg if g[0][0]==m.crc('ucb_meteor_poe_timer'))
def timer_group(name,src,dst,delay):return clone(timer,name,{0x8541406c:[src],0x865f80c0:fs(delay),0xd058515c:[dst]})
def event_group(event,target):return [(m.crc(f'{target}_{event}_forward'),0x1000c,[m.EVENT_GROUP]),(0x939b68a0,0x201000c,[event]),(0x8541406c,0x201000c,[event]),(0x557c4b4d,0x201000c,[target])]
def particle_group(name,src,tgt,template,count,size):
    return clone(template,name,{0x462ce4f5:fs(0,.14,0,0,0,0,1),0x8541406c:[src],0xf7be9018:[tgt],0x9d762289:[count],0xe7965460:fs(28),0x3de73088:fs(.30),0x0f26fef6:fs(4.0),0x297c98f1:fs(35),0x7cb5a078:fs(.6,.10,.6),0xd7943d68:fs(.7,.15,.7),0x7a76b57b:fs(0,1.2,0),0x118a27c7:fs(size),0x9c822a32:fs(size*1.5),0x5a6ce323:[0xd0ffffff],0xc365b299:[0xccffffff],0xb462820f:[0x60ffffff],0x2a0617ac:[0x00ffffff]})

# Reallocate two duplicate meteor dust bursts per retained burst: same total
# spawn count, existing mesh/ring/crater and event routing remain intact.
# The other original particle slots become lightweight timing/forward groups.
# Root group count remains EXACTLY 45; no sound components or extra emitters
# are appended beyond this known-good component budget.
late_stop=m.crc('ucb_bounce_late_flecks_stop');first_stop=m.crc('ucb_bounce_first_flecks_stop')
keep=[clone(original_dust[0],'ucb_meteor_poe_dust_0',{0x9d762289:[12],0x462ce4f5:fs(0,.11,0,0,0,0,1),0x7cb5a078:fs(.45,.10,.45),0xd7943d68:fs(.7,.1,.7)})]
newgroups=keep+[particle_group('ucb_bounce_late_particles',flecks,late_stop,original_dust[1],12,.055),timer_group('ucb_bounce_second_contact_timer',start,flecks,offsets[1]/30),timer_group('ucb_bounce_third_contact_timer',start,flecks,offsets[2]/30),timer_group('ucb_bounce_later_particles_stop',flecks,late_stop,.32),event_group(start,mesh)]
assert len(newgroups)==6
replaced=[];root_groups=[]
for g in rg:
    if g[0][0] in dust_ids:
        if not replaced:root_groups.extend(newgroups)
        replaced.append(g[0][0])
    else:root_groups.append(g)
assert len(replaced)==6 and len(root_groups)==len(rg)

# The extra child uses the tested ring descriptor and has its own local timer
# to stop itself at the end of the whole sequence, plus first-impact flecks.
# Early HEAD_STOPs do not terminate the subsequent ground pulses.
nh,nb=m.node_parts(m.table(assets[14])[mesh]);nb2=[]
for b in nb:
    if b[0]==0x19:b=curve
    elif b[0]==14:
        props=[]
        for a,t,v in m.property_entries(b):
            if v==[stop]:v=[finish]
            if a in (0x5e0393bd,0xf465b2b5):v=fs(duration)
            props.append((a,t,v))
        props+=particle_group('ucb_bounce_first_particles',start,first_stop,original_dust[1],8,.045)
        props+=timer_group('ucb_bounce_first_particles_stop',start,first_stop,.32)
        props+=timer_group('ucb_bounce_child_end_timer',start,finish,duration)
        b=m.node_properties(props)
    nb2.append(b)
newnode=m.node_record(nh,nb2)
rb2=[]
for b in rb:
    if b[0]==0x14:b=[0x14,b[1]+1,b[2]+1]+b[3:]+[mesh]
    elif b[0]==14:b=m.node_properties(flatten(root_groups))
    rb2.append(b)
newroot=m.node_record(rh,rb2);assert len(newroot)<len(nodes[root])
bank(14,[(k,f,newroot if k==root else v) for k,f,v in m.vaps_rows(p[14])]+[(mesh,0,newnode)],True)

d=bytearray(d0);changes=[]
for at in range(4,len(d),224):
    if struct.unpack_from('>I',d,at+32)[0]!=0xc9fb4de3:continue
    assert struct.unpack_from('>2I',d,at+144)==(oldstart,oldstop)
    # +52 is movement speed, +64 is the turn-rate limit. Increase the latter
    # more than the former to improve responsiveness without excessive slide.
    struct.pack_into('>f',d,at+52,1.8);struct.pack_into('>f',d,at+64,4.0);struct.pack_into('>2I',d,at+144,start,stop);changes.append(at)
assert changes==[4,3140,5380]
new=m.package(raw,p);check=entries(new);assert all(check[k]==v for k,v in old.items() if k not in (0,3,4,14))
assert all(m.table(check[i])[k]==v for i in (0,3,4) for k,v in m.table(old[i]).items())
assert all(m.table(check[14])[k]==v for k,v in nodes.items() if k!=root)
assert all(d[at:at+224]==d0[at:at+224] for at in range(4,len(d),224) if at not in changes)
(O/'g_cb.xbx').write_bytes(new);(O/'atk_ucb.ddf').write_bytes(d)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(new),old_ucb_sha=sha(d0),new_ucb_sha=sha(d),normal_ddf_sha=sha(normal),root_groups_before=len(rg),root_groups_after=len(root_groups),root_bytes_before=len(nodes[root]),root_bytes_after=len(newroot),relative_contacts=offsets,pulse_radius_factors=scales,duration=duration,steer_speed=1.8,turn_rate=4.0,animation_bank_unchanged=True,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
