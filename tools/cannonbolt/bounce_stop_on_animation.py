"""End the bounce ground sequence on its native animation stop marker."""
import hashlib,json,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries,channel_records,streamed_clip,animation_time_range

H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'ultimate-bounce-ball-v10-stop';O.mkdir(exist_ok=True)
sha=lambda x:hashlib.sha256(x).hexdigest();prev=json.loads((H/'ultimate-bounce-ball-v9-sync/validation.json').read_text());raw=(G/'g_cb.xbx').read_bytes();d0=(G/'scripts/atk_ucb.ddf').read_bytes();normal=(G/'scripts/atk_cb.ddf').read_bytes()
assert sha(raw)==prev['new_cb_sha'] and sha(d0)==prev['new_ucb_sha'] and sha(normal)==prev['normal_ddf_sha']
assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes() and d0==(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
p=entries(raw);old=dict(p);clips=m.table(p[13]);ch=channel_records(p[9]);key=0xc9fb4de3;clip=clips[key];flag_slot=struct.unpack_from('>I',clip,80)[0]
assert sum(struct.unpack_from('>I',v,80)[0]==flag_slot for v in clips.values())==1
frames=m.flag_frames(ch[flag_slot]);assert len(frames)==6
toframe=lambda f:round(struct.unpack('>f',struct.pack('>I',f[0]))[0]/160)
assert [(toframe(f),f[4]) for f in frames]==[(18,m.HEAD_START),(30,m.HEAD_STOP),(40,m.HEAD_START),(52,m.HEAD_STOP),(64,m.HEAD_START),(76,m.HEAD_STOP)]
# The whole progressive ground effect now runs as ONE sequence. The native
# HEAD slot is a visual-effect dispatcher; the ball position/scale and attack
# hit parameters stay untouched. The last existing HEAD_STOP is an actual
# animation marker, so it's unaffected by effect timer scheduling or game FPS.
rows=m.vaps_rows(p[9]);k,f,_=rows[flag_slot];rows[flag_slot]=(k,f,m.flag_channel([frames[0],frames[-1]]));p[9]=m.build_vaps(9,struct.unpack_from('>H',p[9],12)[0],rows)

# The last stop must be sent to the existing forwarding group on the root.
# Also use the same native stop event for the normal attack cancellation path.
root=m.effect_root('cannonbolt');mesh=m.crc('ucb_bounce_impact_star');start=m.crc('ucb_bounce_contact');obsolete=m.crc('ucb_bounce_stop');finish=m.crc('ucb_bounce_final_stop');timer=m.crc('ucb_bounce_root_end_timer')
nodes=m.table(p[14]);h,blocks=m.node_parts(nodes[root]);out=[];removed=[];has_forward=False
for b in blocks:
    if b[0]==14:
        props=[];skip=False
        for a,t,v in m.property_entries(b):
            if t==0x1000c:skip=a==timer
            if skip:removed.append((a,t,v))
            else:props.append((a,t,v))
        assert (0x939b68a0,0x201000c,[finish]) in props and (0x8541406c,0x201000c,[finish]) in props
        b=m.node_properties(props)
    out.append(b)
assert len(removed)==5 and (0xd058515c,0x201000c,[finish]) in removed
newroot=m.node_record(h,out);p[14]=m.build_vaps(14,struct.unpack_from('>H',p[14],12)[0],[(k,f,newroot if k==root else v) for k,f,v in m.vaps_rows(p[14])])
_,child_blocks=m.node_parts(nodes[mesh]);child_props=[v for b in child_blocks if b[0]==14 for v in m.property_entries(b)];assert (0xa3911ca7,0x201000c,[finish]) in child_props and (0xf7be9018,0x201000c,[finish]) in child_props

d=bytearray(d0);changed=[]
for at in range(4,len(d),224):
    if struct.unpack_from('>I',d,at+32)[0]!=key:continue
    assert struct.unpack_from('>2I',d,at+144)==(start,obsolete)
    struct.pack_into('>I',d,at+148,finish);changed.append(at)
assert changed==[4,3140,5380]
new=m.package(raw,p);check=entries(new);nch=channel_records(check[9]);assert all(check[k]==v for k,v in old.items() if k not in (9,14))
assert len(nch)==len(ch) and [i for i,(a,b) in enumerate(zip(ch,nch)) if a!=b]==[flag_slot]
assert animation_time_range(clip,ch)==animation_time_range(clip,nch) and all(streamed_clip(v,ch)==streamed_clip(v,nch) for k,v in clips.items() if k!=key)
assert all(m.table(check[14])[k]==v for k,v in nodes.items() if k!=root)
assert all(d[at:at+224]==d0[at:at+224] for at in range(4,len(d),224) if at not in changed)
(O/'g_cb.xbx').write_bytes(new);(O/'atk_ucb.ddf').write_bytes(d)
report=dict(old_cb_sha=sha(raw),new_cb_sha=sha(new),old_ucb_sha=sha(d0),new_ucb_sha=sha(d),normal_ddf_sha=sha(normal),first_contact_frame=18,last_stop_frame=76,clip_end_frame=79,stop_event=hex(finish),effect_timer_removed=True,width_and_audio_unchanged=True,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
