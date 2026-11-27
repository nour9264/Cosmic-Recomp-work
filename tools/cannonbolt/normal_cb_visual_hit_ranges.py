"""Match Normal Cannonbolt hit volumes to the approved visual contacts."""
import datetime, hashlib, json, math, statistics, struct, sys
from pathlib import Path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, animation_time_range

H=WORK
APP=APP_ROOT;G=APP/'installation/game/global';N=APP/'installation/vilgax/cannonbolt'
targets=(G/'g_cb.xbx',N/'g_cb.xbx')
sha=lambda b:hashlib.sha256(b).hexdigest()
fw=lambda v:struct.unpack('>I',struct.pack('>f',v))[0]
f=lambda v:struct.unpack('>f',struct.pack('>I',v))[0]
fs=lambda *v:[fw(x) for x in v]
ident=lambda s:m.crc('cosmic_cb_normal_contact_'+s)
raw=targets[0].read_bytes()
assert raw==targets[1].read_bytes()
assert sha(raw)=='45bfb00a077417e9d0653558bbd31567c69b737ded270e0160d99f5bf0de88ed'
p=entries(raw);before=dict(p);nodes=m.table(p[14]);meshes=m.table(p[4]);root=0xfb61a9c2
attack=(G/'scripts/atk_cb.ddf').read_bytes()
assert attack==(N/'atk_cb.ddf').read_bytes() and sha(attack)=='67e86abac9ea398e57783b4444759caa370ef81b52353f3bef749df9605691c0'
protected={x:sha(x.read_bytes()) for x in (G/'scripts/atk_cb.ddf',N/'atk_cb.ddf',
    G/'g_ucb.xbx',G/'scripts/atk_ucb.ddf',APP/'installation/vilgax/ultimatecannonbolt/g_ucb.xbx',
    APP/'installation/vilgax/ultimatecannonbolt/atk_ucb.ddf',APP/'runtime/ben10.exe',APP/'runtime/SHA256SUMS.txt')}
rows=list(struct.iter_unpack('>56I',attack[4:]))
slots={'circle':0x549d5666,'triangle':0x239a66f0,'square':0xba93374a,'cross':0xcaf9c3c5}
by_slot={k:[r for r in rows if r[40]==v] for k,v in slots.items()}
assert all(len(rs)==3 for rs in by_slot.values())
amounts={k:statistics.median(f(r[15]) for r in rs) for k,rs in by_slot.items()}
assert amounts=={'circle':1.,'triangle':.75,'square':1.75,'cross':1.5}

def groups(bs):
    gg=[]
    for b in bs:
        if b[0]!=14:continue
        for k,t,v in m.property_entries(b):
            if t==0x1000c:gg.append([])
            gg[-1].append((k,t,list(v)))
    return gg
def group(bs,kind):
    return next(g for g in groups(bs) if g[0][2]==[kind])
def val(g,k):return next(v[0] for pk,t,v in g if pk==k)
def clone(g,changes,name=None):
    return [(ident(name) if name and t==0x1000c else k,t,list(changes.get(k,v))) for k,t,v in g]
def props(gg):return m.node_properties([x for g in gg for x in g])

# Use only the native stock hit component, as in the proven UCB hit pass.
# A regular native hit checks enemy capsule overlaps and applies hit reactions.
bc=m.table(entries((G/'g_bc.xbx').read_bytes())[14])
_,bb=m.node_parts(bc[0x36046fd3]);hit=group(bb,0x961699b1)
assert val(hit,0x11c8546c)==fw(1) and val(hit,0xb823fe47)==0x11abfea5
_,hb=m.node_parts(nodes[0x533d1abf]);modifiers=group(hb,0x293c8e8b)
assert (0x293c8e8b,0x9010014,[1,0x4c6b3fe3,fw(1)]) in modifiers

impact=0x61d53120
_,vbuf,_=m.mesh_buffers(meshes[impact],xbox=True)
vertices=list(struct.iter_unpack('>5f',vbuf))
visual_radius=max(math.hypot(x,z) for x,y,z,u,v in vertices)
assert 6.74<visual_radius<6.75

# Derive the ball radius from the 880 vertices rigidly assigned to bone 44,
# whose skeleton tag is 193, rather than the surrounding Burnout dust mesh.
skin=m.table(p[22])[0x58ec2e03];sk=m.table(p[12])[0x8b21e1f6]
assert struct.unpack_from('>I',sk,52+44*44)[0]==193
bindroot=struct.unpack_from('>10f',sk,12)
bindball=struct.unpack_from('>10f',sk,12+44*44)
bind=tuple(a+b for a,b in zip(bindroot[4:7],bindball[4:7]))
pts=[struct.unpack_from('>3f',skin,i) for i in range(80,len(skin),52)
    if skin[i+48:i+52]==bytes((44,0,0,0))]
assert len(pts)==880
ball_radius=max(math.dist(v,bind) for v in pts)
assert .80<ball_radius<.81

# The animated rolling ball center follows the actor, with its authored
# root-relative transform. During Burnout its translation is constant.
clips=m.table(p[13]);ch=channel_records(p[9]);burnout=clips[by_slot['cross'][0][8]]
assert burnout[:64].split(b'\0')[0]==b'burnout_run_01'
assert animation_time_range(burnout,ch)==(2400.,3360.)
assert m.bone_ids(burnout)[44]==193
def channel(i):return ch[struct.unpack_from('>I',burnout,216+4*i)[0]]
root_pos=struct.unpack_from('>3f',channel(0),12)
off=struct.unpack_from('>3f',channel(132),12)
x,y,z,w,_=struct.unpack_from('>3hbB',channel(1),8)
q=(-x/32767,-y/32767,-z/32767,w/127)
nn=math.sqrt(sum(a*a for a in q));x,y,z,w=(a/nn for a in q)
a,b,c=off
tx,ty,tz=2*(y*c-z*b),2*(z*a-x*c),2*(x*b-y*a)
rot=(a+w*tx+y*tz-z*ty,b+w*ty+z*tx-x*tz,c+w*tz+x*ty-y*tx)
ball_pos=tuple(a+b for a,b in zip(root_pos,rot))
assert .74<ball_pos[1]<.76 and .17<ball_pos[2]<.19

tri_visuals=(0x61d53120,0x758ff880,0x0288c816,0x9cec5db5,0xebeb6d23,0x72e23c99)
dash_visual=0xc470850d;meteor_visual=0xe637d703
rh,rb=m.node_parts(nodes[root]);children=next(b[3:] for b in rb if b[0]==0x14)
assert len(children)==18 and all(k in children for k in (*tri_visuals,dash_visual,meteor_visual))
legacy_circle,legacy_triangle,legacy_burnout=0xee1e1be5,0xb48a66d5,0x010dda58
legacy=(legacy_circle,legacy_triangle,legacy_burnout)
assert all(k in children and k not in meshes for k in legacy)
# Those three dormant/incorrect stock shockwave archetype nodes contain
# missing mesh references. Reuse them as non-rendered native hit volumes.
template_h,_=m.node_parts(nodes[legacy_circle])
assert template_h[6]==0x59bfb057
_,vb=m.node_parts(nodes[impact]);timer_template=group(vb,0x6ad0de1a)
curve_template=group(vb,0x60bf9208)
def timer(label,start,end,seconds):
    return clone(timer_template,{0x8541406c:[start],0xd058515c:[end],0x865f80c0:fs(seconds)},label)
def collider(key,label,pos,start,rad,damage,seconds,delay=None):
    end=ident(label+'_end')
    h=list(template_h);h[0]=key;h[4]=0x40000;h[6]=m.crc('root')
    h[7:14]=fs(*pos,0,0,0,1)
    bound=rad+.5;h[19:26]=fs(bound,-bound,-bound,-bound,bound,bound,bound)
    hg=clone(hit,{0x8541406c:[start],0xf7be9018:[end],0x11c8546c:fs(damage),
        0x3b7c6e5a:fs(rad),0x17d9eb2:fs(0)},label+'_hit')
    # Same native timeline technique as the successful stock/UCB setup,
    # and a local end timer. No global named-node forwarding or scanner.
    timeline=clone(curve_template,{0x8541406c:[start],0xf7be9018:[end]})
    scale=[0x19,24,0x0d0a5003,0x00020002]+fs(0)+[0]*6+fs(1,1,1)+fs(seconds*4800)+[0]*6+fs(1,1,1)
    gg=[hg,modifiers,timeline,timer(label+'_close',start,end,seconds)]
    if delay:gg.append(timer(label+'_contact',delay[0],start,delay[1]))
    assert len(set(g[0][0] for g in gg))==len(gg)
    return m.node_record(h,[[8,3,root],scale,props(gg)])

def visual_contact(key):
    h,b=m.node_parts(nodes[key]);gg=groups(b)
    mesh=group(b,0xe16f3a56);start=val(mesh,0x750f694a)
    delay=None
    for g in gg:
        if g[0][2]==[0x6ad0de1a] and val(g,0xd058515c)==start:
            assert delay is None;delay=(val(g,0x8541406c),f(val(g,0x865f80c0)))
    # Same horizontal landing center. A sphere is centred slightly above the
    # floor for actor-capsule overlap; radius is exactly the actual mesh rim.
    x,_,z=map(f,h[7:10]);return (x,.55,z),start,delay

revised={};new_keys=[];records=[]
def add_visual_hit(key,label,visual,damage):
    pos,start,delay=visual_contact(visual)
    if delay:
        # Independent but identically scheduled timer, directly on its
        # collider. Do not rely on a sibling's timer broadcasting globally.
        start=ident(label+'_begin')
    revised[key]=collider(key,label,pos,start,visual_radius,damage,1280/4800,delay)
    records.append(dict(label=label,visual=hex(visual),collider=hex(key),center=pos,radius=visual_radius,
        damage=damage,delay_seconds=delay[1] if delay else 0.0,active_seconds=1280/4800))
    if key not in nodes:new_keys.append(key)

add_visual_hit(legacy_circle,'circle',dash_visual,amounts['circle'])
for i,v in enumerate(tri_visuals):
    key=legacy_triangle if i==0 else ident(f'triangle_{i+1}_node')
    add_visual_hit(key,f'triangle_{i+1}',v,amounts['triangle']/6)
add_visual_hit(ident('square_node'),'square',meteor_visual,amounts['square'])

# Burnout's damage follows the visible rolling ball during its forward
# attack; a sphere around the actual ball, not a ranged shockwave. The
# existing visual timer defines the active forward burst (.42 s).
_,burnout_effect=m.node_parts(nodes[0xe365c4ed])
bt=group(burnout_effect,0x6ad0de1a);burnout_start=val(bt,0x8541406c)
burnout_seconds=f(val(bt,0x865f80c0))
assert burnout_start==by_slot['cross'][0][36]==0xbb52f086 and .41<burnout_seconds<.43
revised[legacy_burnout]=collider(legacy_burnout,'cross',ball_pos,burnout_start,ball_radius,
    amounts['cross'],burnout_seconds)
records.append(dict(label='cross',collider=hex(legacy_burnout),center=ball_pos,radius=ball_radius,
    damage=amounts['cross'],active_seconds=burnout_seconds))

assert len(new_keys)==6 and not set(new_keys)&set(nodes)
revised[root]=m.node_record(rh,[[0x14,b[1]+len(new_keys),b[2]+len(new_keys)]+b[3:]+new_keys
    if b[0]==0x14 else b for b in rb])
bankrows=[(k,flags,revised.get(k,v)) for k,flags,v in m.vaps_rows(p[14])]
bankrows.extend((k,0,revised[k]) for k in new_keys)
p[14]=m.build_vaps(14,struct.unpack_from('>H',p[14],12)[0],m.bucket_sorted(bankrows))
result=m.package(raw,p,(0,3,4,9,12,13,14,22,24));check=entries(result);nd=m.table(check[14])
assert all(check[k]==v for k,v in before.items() if k!=14)
assert all(nd[k]==v for k,v in nodes.items() if k not in revised)
assert all(nd[k]==v for k,v in revised.items()) and len(nd)==len(nodes)+6
assert all(nd[v]==nodes[v] for v in (*tri_visuals,dash_visual,meteor_visual,0xe365c4ed,0xdc6ba6d2))
for info in records:
    k=int(info['collider'],16);h,b=m.node_parts(nd[k]);gg=groups(b)
    assert [8,3,root] in b and not any(x[0]==0 for x in b)
    hitg=group(b,0x961699b1)
    assert val(hitg,0x3b7c6e5a)==fw(info['radius'])
    assert val(hitg,0x11c8546c)==fw(info['damage'])
    assert all(g[0][2]!=[m.EVENT_GROUP] for g in gg)
assert math.isclose(sum(r['damage'] for r in records if r['label'].startswith('triangle')),amounts['triangle'])

out=H/'normal-cb-visual-hit-ranges'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
out.mkdir(parents=True)
for path in targets:
    dest=out/'before'/path.relative_to(APP);dest.parent.mkdir(parents=True);dest.write_bytes(path.read_bytes())
    assert dest.read_bytes()==raw
(out/'g_cb.xbx').write_bytes(result)
report=dict(before=sha(raw),after=sha(result),mesh_radius=visual_radius,ball_radius=ball_radius,
    damage_budget=amounts,collision_volumes=records,all_visual_nodes_unchanged=True,
    ultimate_runtime_attacks_unchanged=True,gameplay_verified=False)
(out/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2));print('Backup and candidate:',out)
if '--install' in sys.argv:
    done=[]
    try:
        for path in targets:
            assert path.read_bytes()==raw
            tmp=path.with_name(path.name+'.normal-hit-new');assert not tmp.exists();tmp.write_bytes(result);tmp.replace(path)
            done.append(path);assert path.read_bytes()==result
        assert all(sha(path.read_bytes())==v for path,v in protected.items())
    except BaseException:
        for path in reversed(done):
            tmp=path.with_name(path.name+'.normal-hit-restore');assert not tmp.exists();tmp.write_bytes(raw);tmp.replace(path)
        raise
    print('Installed both normal packages; all protected files verified.')
