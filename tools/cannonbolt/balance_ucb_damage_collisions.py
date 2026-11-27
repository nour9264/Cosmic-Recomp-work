"""Restore native hit components for UCB's four custom specials, without editing VFX."""
import hashlib,json,math,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,animation_time_range

H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'ultimate-cannonbolt-damage-v1';O.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest();prev=json.loads((H/'ultimate-bounce-ball-v10-stop/validation.json').read_text());sound=json.loads((H/'ultimate-bounce-ball-v12-louder/validation.json').read_text())
raw=(G/'g_cb.xbx').read_bytes();d0=(G/'scripts/atk_ucb.ddf').read_bytes();normal=(G/'scripts/atk_cb.ddf').read_bytes()
assert sha(raw)==prev['new_cb_sha'] and sha(d0)==prev['new_ucb_sha'] and sha(normal)==prev['normal_ddf_sha'] and sha((G/'g_ucb.xbx').read_bytes())==sound['new_sha']
assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes() and d0==(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
p=entries(raw);old=dict(p);nodes=m.table(p[14]);root=m.effect_root('cannonbolt');root_h,root_b=m.node_parts(nodes[root]);children=next(b for b in root_b if b[0]==0x14)[3:]
def f(x):return struct.unpack('>f',struct.pack('>I',x))[0]
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def groups(blocks):
    out=[]
    for block in blocks:
        if block[0]!=14:continue
        for a,t,v in m.property_entries(block):
            if t==0x1000c:out.append([])
            assert out;out[-1].append((a,t,v))
    return out
def group_for(blocks,kind):return next(g for g in groups(blocks) if g[0][2]==[kind])
def clone(g,settings,name=None):return [(m.crc(name) if name and t==0x1000c else a,t,settings.get(a,v)) for a,t,v in g]

# Use exact native Big Chill tornado hit metadata. The stock hit component
# handles capsule overlap, attack type and destructible objects. No authored
# instant-kill flags, enemy HP edits, direct deletion or custom enemy scanner.
bc=m.table(entries((G/'g_bc.xbx').read_bytes())[14]);bh,bb=m.node_parts(bc[0x36046fd3]);hit=group_for(bb,0x961699b1)
assert (0x11c8546c,0x101000c,fs(1)) in hit and (0xb823fe47,0x201000c,[0x11abfea5]) in hit
_,handb=m.node_parts(nodes[0x533d1abf]);props=group_for(handb,0x293c8e8b);assert (0x293c8e8b,0x9010014,[1,0x4c6b3fe3,fs(1)[0]]) in props
_,diskb=m.node_parts(nodes[0x8378e2b1]);player=group_for(diskb,0x60bf9208)
ec=m.table(entries((G/'g_ec.xbx').read_bytes())[14]);_,eb=m.node_parts(ec[0x7f0ba1ef]);relay=group_for(eb,0x2f8eb5f4)
assert (0x8541406c,0x201000c,[0x7c4a867b]) in relay and (0xd058515c,0x201000c,[0x6ae4b0ef]) in relay
def hit_group(name,begin,end,damage,radius,length):
    assert 0<damage<=2.2 and radius>0 and length>=0
    return clone(hit,{0x8541406c:[begin],0xf7be9018:[end],0x11c8546c:fs(damage),0x3b7c6e5a:fs(radius),0x17d9eb2:fs(length)},name)
def curve_player(begin,end):return clone(player,{0x8541406c:[begin],0xf7be9018:[end],0x6e023a40:[1],0x6f949845:fs(1)})
def event_track(events):
    # Native node event track, e.g. g_ubc 547d019c. Tick units are 4800/s.
    rows=[]
    for ticks,e in sorted(events):rows+=fs(ticks)+[0,0,0,8,0,0,0,e]
    return [0x17,4+len(rows),0x0a095000,len(events)<<16|len(events)]+rows
def constant_scale(end):return [0x19,24,0x0d0a5003,0x00020002]+fs(0)+[0]*6+fs(1,1,1)+fs(end)+[0]*6+fs(1,1,1)

def collider(key,begin,end,pos,rotation,radius,length,damage,last,events=None,hitgroups=None,extras=()):
    # Reuse existing, previously attached damage nodes. Remove their old
    # shockwave archetype (and missing mesh), use native plain-node collision
    # groups instead, with no renderable mesh or visual effects.
    h,b=m.node_parts(nodes[key]);assert h[6]==0x59bfb057 and key in children
    h=list(h);h[6]=m.crc('root');h[4]=0x40000;h[7:14]=fs(*pos,*rotation)
    bound=radius+length/2+.5;h[19:26]=fs(bound,-bound,-bound,-bound,bound,bound,bound)
    gg=(hitgroups if hitgroups is not None else [hit_group('ucb_native_hit_'+hex(key),begin,end,damage,radius,length)])+[props,curve_player(begin,end)]+list(extras)
    blocks=[[0x08,3,root],constant_scale(last),event_track(events if events is not None else [(last-1,end)]),m.node_properties([q for g in gg for q in g])]
    return m.node_record(h,blocks)

# Existing UCB shockwave IDs: their old start events do not reach a live
# hit volume reliably. The dormant stock powerflop node is safe to repurpose:
# both current square moves use distinct custom events instead of a3cdf08c.
spin,rocks,suction,bounce=0xf1a65474,0x8d119873,0x9ebe0b46,0xa8d502df
spin_start,spin_stop=0x3383f0c4,0xff0a1d9d;rock_start,rock_stop=0x4f343cc3,0x9429ad53
release,release_stop=0x8d0a69df,0x4f7af340;bounce_start,bounce_end=0x855115a2,0x0ab16e70
clip=m.table(p[13]);ch=channel_records(p[9]);assert animation_time_range(clip[0xdb46cb2],ch)==(0,15520) and animation_time_range(clip[0x2d806255],ch)==(0,9120)
all_attack_events={struct.unpack_from('>I',d,at+off)[0] for d in (normal,d0) for at in range(4,len(d),224) for off in (144,148)};assert 0xa3cdf08c not in all_attack_events

# Match visual geometry from the installed meshes, not an arbitrary range.
def mesh_bounds(name):
    key=m.crc(name);_,vb,_=m.mesh_buffers(m.table(p[4])[key],xbox=True);points=list(struct.iter_unpack('>5f',vb));return max(math.hypot(x,z) for x,y,z,u,v in points),max(y for x,y,z,u,v in points)
spin_radius,spin_height=mesh_bounds('ucb_spin_helix_mesh');disk_radius,_=mesh_bounds('ucb_bounce_impact_star');assert 1.4<spin_radius<1.6 and 4<spin_height<4.3 and 4.8<disk_radius<5
spin_radius=round(spin_radius+.08,2);spin_length=round(spin_height-1.5,2);spin_pos=(0,spin_height*.47,0)
spinq=tuple(f(x) for x in bh[10:14]);identity=(0,0,0,1)
# Root-relative forward corridor matches the two rock emitters' nominal
# ~10.4-unit travel. Width includes the visible narrow rock spread; no
# backwards or all-around area of effect. This is an envelope, not separate
# physics objects for every rendered particle.
rootgroups=groups(root_b);rock_groups=[next(g for g in rootgroups if g[0][0]==m.crc(f'ucb_backspin_rock_{i}_particles')) for i in (0,1)]
rock_range=max(f(next(v[0] for a,t,v in g if a==0xf26fef6))*f(next(v[0] for a,t,v in g if a==0x3de73088))+f(next(v[2] for a,t,v in g if a==0x462ce4f5)) for g in rock_groups);assert 9.5<rock_range<11
rock_radius=1.0;rock_length=round(rock_range-.6-2*rock_radius,2);rock_mid=.6+rock_radius+rock_length/2
revised={
 spin:collider(spin,spin_start,spin_stop,spin_pos,spinq,spin_radius,spin_length,2.1,96*160),
 rocks:collider(rocks,rock_start,rock_stop,(0,.5,rock_mid),identity,rock_radius,rock_length,1.8,57*160),
 suction:collider(suction,release,release_stop,(0,1.0,0),identity,5.8,0.0,1.9,16*160),
}

# One native timed sequence (the same first contact that starts the ring)
# enables three non-overlapping hit windows at frames 18,40,64. Each pulse
# has its own native hit group so a target can be struck again on a later
# landing, but the three amounts sum to only 2.15 balanced damage units.
offsets=(0,22,46);pulse_factors=(.55,.78,1.0);pulse_radii=[round(disk_radius*scale*1.08*1.5,2) for scale in pulse_factors];damage=(.5,.7,.95)
assert sum(damage)<2.2
pulse_off=m.crc('ucb_bounce_hit_window_close');events=[];hits=[]
for index,(frame,rad,amount) in enumerate(zip(offsets,pulse_radii,damage)):
    signal=m.crc(f'ucb_bounce_damage_pulse_{index}');events.append((max(1,frame*160),signal));events.append(((frame+5)*160,pulse_off))
    hits.append(hit_group(f'ucb_bounce_hit_component_{index}',signal,pulse_off,amount,rad,0.0))
events.append((58*160-1,bounce_end))
# Native end/cancellation dispatch also shuts every active pulse down.
end_relay=clone(relay,{0x8541406c:[bounce_end],0xd058515c:[pulse_off]},'ucb_bounce_damage_cancel')
revised[bounce]=collider(bounce,bounce_start,bounce_end,(0,.55,0),identity,max(pulse_radii),0,0,58*160,events,hits,[end_relay])

# Only four lightweight start forwards, keeping the existing child list,
# particles, and every visual group's data unchanged. The local timelines
# perform the exact closes; the native attack's recursive end event cancels
# them on interruption. Root byte budget remains below the tested v7 tree.
assert len(rootgroups)==42
forward=[]
for k,e in ((spin,spin_start),(rocks,rock_start),(suction,release),(bounce,bounce_start)):
    forward.extend([(m.crc(f'ucb_native_hit_forward_{k:08x}'),0x1000c,[m.EVENT_GROUP]),(0x939b68a0,0x201000c,[e]),(0x8541406c,0x201000c,[e]),(0x557c4b4d,0x201000c,[k])])
newroot=m.node_record(root_h,[m.node_properties(m.property_entries(b)+forward) if b[0]==14 else b for b in root_b]);assert len(newroot)<11392
revised[root]=newroot
p[14]=m.build_vaps(14,struct.unpack_from('>H',p[14],12)[0],[(k,flags,revised.get(k,v)) for k,flags,v in m.vaps_rows(p[14])])
new=m.package(raw,p);check=entries(new);assert all(check[k]==v for k,v in old.items() if k!=14);assert all(m.table(check[14])[k]==v for k,v in nodes.items() if k not in revised)
assert len(m.table(check[14]))==len(nodes)

# Word 15 really is damage (see AllAliensPatch.BalanceUltimateAttacks).
# Undo the accidental 2.667 damage value previously written for timing,
# and make every light attack 1.4x its equivalent ordinary Cannonbolt hit.
special_damage={0x549d5666:1.9,0x239a66f0:1.8,0xba93374a:2.15,0xcaf9c3c5:2.1};d=bytearray(d0);light=0;specials=0;changes=[]
for at in range(4,len(d),224):
    slot=struct.unpack_from('>I',d,at+160)[0];assert slot==struct.unpack_from('>I',normal,at+160)[0]
    old_damage=struct.unpack_from('>f',d,at+60)[0];normal_damage=struct.unpack_from('>f',normal,at+60)[0]
    if slot==0x47c02d3b:
        amount=round(normal_damage*1.4,2);assert .34<=amount<=.57;light+=1
    else:
        assert slot in special_damage;amount=special_damage[slot];specials+=1
    assert amount>normal_damage
    count=struct.unpack_from('>I',d,at+180)[0];assert count<=5 and all(struct.unpack_from('>I',d,at+184+i*8)[0]!=0x1ca4c331 for i in range(count))
    struct.pack_into('>f',d,at+60,amount);changes.append((hex(slot),normal_damage,old_damage,amount))
assert light==17 and specials==12
for at in range(4,len(d),224):assert d[at:at+60]==d0[at:at+60] and d[at+64:at+224]==d0[at+64:at+224]
(O/'g_cb.xbx').write_bytes(new);(O/'atk_ucb.ddf').write_bytes(d)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(new),old_ucb_sha=sha(d0),new_ucb_sha=sha(d),normal_ddf_sha=sha(normal),audio_sha=sound['new_sha'],light_attacks=light,light_multiplier=1.4,special_attacks=specials,spin_capsule_radius=spin_radius,spin_capsule_length=spin_length,rock_forward_range=rock_range,rock_radius=rock_radius,suction_radius=5.8,bounce_radii=pulse_radii,bounce_damage=damage,bounce_total_damage=sum(damage),root_property_bytes=len(newroot),root_groups=46,all_visual_banks_unchanged=True,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
