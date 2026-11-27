"""One private, independently fading mesh pulse per authored ground contact."""
import datetime, hashlib, json, struct, sys
from pathlib import Path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries

H=WORK
APP=APP_ROOT; G=APP/'installation/game/global'; N=APP/'installation/vilgax/cannonbolt'
paths=(G/'g_cb.xbx',N/'g_cb.xbx')
sha=lambda b:hashlib.sha256(b).hexdigest()
fw=lambda v:struct.unpack('>I',struct.pack('>f',v))[0]
fs=lambda *v:[fw(x) for x in v]
ident=lambda s:m.crc('cosmic_cb_independent_impact_'+s)
live=paths[0].read_bytes()
assert live==paths[1].read_bytes()
assert sha(live)=='2748908ff61d8ea91e9aeca1b265ab77633e6af81e9ea3c782f9983363ba6d9c'
# The package as it was before the fade step ran: the fade step saved it under its own work folder.
baseline=next((b for b in (x.read_bytes() for x in sorted((H/'normal-cb-ground-fade').glob('*/before/installation/game/global/g_cb.xbx')))
               if sha(b)=='b1e5241aaa65464ec09d8f21f8bdd2145281a76e26782ad9cfbb537c8c3c5880'),None)
assert baseline is not None, 'run fade_normal_cb_ground_impacts.py first (its saved "before" package is the baseline)'
base=entries(baseline); p=entries(live); before=dict(p)
assert all(base[k]==p[k] for k in base if k!=14)
old=m.table(base[14]); current=m.table(p[14])
root=0xfb61a9c2; impact=0x61d53120; dash=0xc470850d; meteor=0xe637d703
assert set(current)==set(old)|{meteor}
protected={x:sha(x.read_bytes()) for x in (G/'scripts/atk_cb.ddf',N/'atk_cb.ddf',
    G/'g_ucb.xbx',G/'scripts/atk_ucb.ddf',APP/'installation/vilgax/ultimatecannonbolt/g_ucb.xbx',
    APP/'installation/vilgax/ultimatecannonbolt/atk_ucb.ddf',APP/'runtime/ben10.exe',APP/'runtime/SHA256SUMS.txt')}

def groups(bs):
    gs=[]
    for b in bs:
        if b[0]!=14:continue
        for k,t,v in m.property_entries(b):
            if t==0x1000c:gs.append([])
            gs[-1].append((k,t,list(v)))
    return gs

def clone(g,changes,name=None):
    return [(ident(name) if name and t==0x1000c else k,t,list(changes.get(k,v))) for k,t,v in g]

def val(g,k):
    return next(v[0] for pk,t,v in g if pk==k)

def propblock(gs):
    return m.node_properties([x for g in gs for x in g])

def timer(template,label,start,finish,ticks):
    assert template[0][2]==[0x6ad0de1a] and ticks>0
    return clone(template,{0x8541406c:[start],0xd058515c:[finish],0x865f80c0:fs(ticks/4800)},label)

ih,ib=m.node_parts(old[impact]);dh,db=m.node_parts(old[dash]);mh,mb=m.node_parts(current[meteor])
ig,dg,mg=groups(ib),groups(db),groups(mb)
assert [g[0][2][0] for g in ig]==[0xe16f3a56,0x60bf9208,0x6ad0de1a,0xbfdf3dde]
assert [g[0][2][0] for g in dg[:4]]==[g[0][2][0] for g in ig]
tri_event=val(ig[0],0x750f694a);dash_start=val(dg[0],0x750f694a);meteor_start=0xa18d130a
assert (tri_event,dash_start)==(0x58ee2d01,0xf1645061)

# Retain the exact six original contact offsets, decoded from the prior
# aligned track. Each mesh gets only its own constant landing position.
pos=next(b for b in ib if b[0]==0x15)
scale=next(b for b in ib if b[0]==0x19)
assert len(pos)==124 and len(scale)==244
grounds=[]
for i in range(6):
    a,b=pos[4+i*20:14+i*20],pos[14+i*20:24+i*20]
    assert a[7:10]==b[7:10] and a[0]==fw(i*1280)
    grounds.append(a[7:10])

def constant_position(xyz,stop):
    return [0x15,24,0x050ad001,0x00020002]+fs(0)+[0]*6+xyz+fs(stop)+[0]*6+xyz

# Keep the original exact growth keys and peak size. The mesh must not
# shrink to nothing during fade: hold the peak geometry while the native
# Mesh component interpolates actual alpha down to zero for 0.32 seconds.
# A final 64-tick invisible margin ensures hide cannot truncate the fade.
peak=800; fade_ticks=1536; fade_end=peak+fade_ticks; stop=2400
particle_stop=1280
assert scale[4:14][0]==fw(0) and scale[14:24][0]==fw(320) and scale[24:34][0]==fw(peak)
peak_xyz=scale[31:34]
assert peak_xyz==fs(1,1,1)
single_scale=[0x19,44,0x0d0a5003,0x00040004]+scale[4:34]+fs(stop)+[0]*6+peak_xyz

def make_pulse(key,header,xyz,label,start,delay=None,particle_template=None):
    h=list(header); h[0]=key; h[7:10]=xyz
    end=ident(label+'_hide'); fade=ident(label+'_fade'); pend=ident(label+'_particles_end')
    # Independent Mesh, timeline and emitter groups. The stock 'fadeout'
    # input and 'fadealpha' property provide true opacity interpolation.
    # Alpha is restored on hide, so the next attack can reuse the node.
    gmesh=clone(ig[0],{0x750f694a:[start],0xa3911ca7:[end],
        0x0597de41:[fade],0x3fe4f6d6:[0],0xe43374cd:fs(0),
        0x5e0393bd:fs(fade_ticks/4800),0xe5b40266:[1]})
    curve=clone(ig[1],{0x8541406c:[start],0xf7be9018:[end]})
    particle=clone(particle_template or ig[3],{0x8541406c:[start],0xf7be9018:[pend]},label+'_particles')
    gg=[gmesh,curve,particle,
        timer(ig[2],label+'_fade_timer',start,fade,peak),
        timer(ig[2],label+'_particles_timer',start,pend,particle_stop),
        timer(ig[2],label+'_hide_timer',start,end,stop)]
    if delay:
        gg.append(timer(ig[2],label+'_contact_timer',delay[0],start,delay[1]))
    assert len(set(g[0][0] for g in gg))==len(gg)
    return m.node_record(h,[constant_position(xyz,stop),list(single_scale),
        [0,4,impact,impact],[8,3,root],propblock(gg)])

revised={}
new_keys=[]
for i,xyz in enumerate(grounds):
    label=f'triangle_{i+1}'
    key=impact if i==0 else ident(label)
    assert i==0 or key not in current
    start=tri_event if i==0 else ident(label+'_start')
    delay=None if i==0 else (tri_event,i*1280)
    revised[key]=make_pulse(key,ih,xyz,label,start,delay)
    if i:new_keys.append(key)

# Dash preserves its proven contact-delay timer; Meteor fires directly from
# the already authored contact event. Each uses the exact same pulse.
dash_xyz=dh[7:10]
dash_delay=val(dg[4],0x865f80c0)
dash_event=val(dg[4],0x8541406c)
assert val(dg[4],0xd058515c)==dash_start and dash_event==0x536c2df9
revised[dash]=make_pulse(dash,dh,dash_xyz,'dash',dash_start,particle_template=dg[3])
h,b=m.node_parts(revised[dash])
# Keep the original delay verbatim (including its floating-point encoding).
gg=groups(b)+[dg[4]]
revised[dash]=m.node_record(h,[propblock(gg) if z[0]==14 else z for z in b])
revised[meteor]=make_pulse(meteor,mh,mh[7:10],'meteor',meteor_start,particle_template=mg[3])

rh,rb=m.node_parts(current[root])
old_children=next(b[3:] for b in rb if b[0]==0x14)
assert len(old_children)==13 and impact in old_children and meteor in old_children
revised[root]=m.node_record(rh,[[0x14,b[1]+len(new_keys),b[2]+len(new_keys)]+b[3:]+new_keys
    if b[0]==0x14 else b for b in rb])
rows=[(k,f,revised.get(k,v)) for k,f,v in m.vaps_rows(p[14])]
rows.extend((k,0,revised[k]) for k in new_keys)
p[14]=m.build_vaps(14,struct.unpack_from('>H',p[14],12)[0],m.bucket_sorted(rows))
result=m.package(live,p,(0,3,4,9,12,13,14,22,24))
check=entries(result); nd=m.table(check[14])
assert all(check[k]==v for k,v in before.items() if k!=14)
assert all(nd[k]==v for k,v in current.items() if k not in revised)
assert len(nd)==len(current)+5 and all(nd[k]==v for k,v in revised.items())
for i,k in enumerate([impact,*new_keys]):
    h,b=m.node_parts(nd[k]);assert h[7:10]==grounds[i]
    assert next(z for z in b if z[0]==0x19)==single_scale
    g=groups(b);assert g[0][0][2]==[0xe16f3a56] and g[3][0][2]==[0x6ad0de1a]
    assert val(g[0],0x0597de41)==val(g[3],0xd058515c)
    assert val(g[0],0xa3911ca7)==val(g[5],0xd058515c)
    if i:
        assert val(g[-1],0x8541406c)==tri_event and val(g[-1],0x865f80c0)==fw(i*1280/4800)
        assert val(g[-1],0xd058515c)==val(g[0],0x750f694a)
    assert all(q[0][2]!=[m.EVENT_GROUP] for q in g)
    assert [0,4,impact,impact] in b and [8,3,root] in b
assert impact in m.table(check[4]) and impact in m.table(check[3])
assert len(set(val(groups(m.node_parts(nd[k])[1])[0],0x750f694a) for k in [impact,*new_keys]))==6

out=H/'normal-cb-independent-fade'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
out.mkdir(parents=True)
for path in paths:
    dst=out/'before'/path.relative_to(APP);dst.parent.mkdir(parents=True);dst.write_bytes(path.read_bytes())
    assert dst.read_bytes()==live
(out/'g_cb.xbx').write_bytes(result)
report=dict(before=sha(live),after=sha(result),
    triangle_landing_ticks=[3520+i*1280 for i in range(6)],
    triangle_nodes=[hex(k) for k in [impact,*new_keys]],
    independent_pulses=True,mesh_growth_keys=[0,320,800],peak_scale=1,
    opacity_fade_seconds=fade_ticks/4800,hide_seconds=stop/4800,
    particle_emit_seconds=particle_stop/4800,maximum_simultaneous_triangle_meshes=2,
    runtime_and_attacks_unchanged=True,gameplay_verified=False)
(out/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2));print('Backup and candidate:',out)
if '--install' in sys.argv:
    done=[]
    try:
        for path in paths:
            assert path.read_bytes()==live
            tmp=path.with_name(path.name+'.independent-fade-new');assert not tmp.exists()
            tmp.write_bytes(result);tmp.replace(path);done.append(path)
            assert path.read_bytes()==result
        assert all(sha(path.read_bytes())==v for path,v in protected.items())
    except BaseException:
        for path in reversed(done):
            tmp=path.with_name(path.name+'.independent-fade-restore');assert not tmp.exists()
            tmp.write_bytes(live);tmp.replace(path)
        raise
    print('Installed both normal packages; protected files verified.')
