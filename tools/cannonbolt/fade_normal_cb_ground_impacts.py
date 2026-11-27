"""Native mesh-alpha fade and Meteor landing effect; current normal CB only."""
import bisect, datetime, hashlib, json, math, struct, sys
from pathlib import Path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records

H= WORK
APP = APP_ROOT
G = APP/'installation/game/global'
N = APP/'installation/vilgax/cannonbolt'
sha = lambda b: hashlib.sha256(b).hexdigest()
fw = lambda v: struct.unpack('>I', struct.pack('>f',v))[0]
fs = lambda *v: [fw(x) for x in v]
ident = lambda label: m.crc('cosmic_cb_va_ground_fade_'+label)
paths = (G/'g_cb.xbx', N/'g_cb.xbx')
raw = paths[0].read_bytes()
assert raw == paths[1].read_bytes()
assert sha(raw) == 'b1e5241aaa65464ec09d8f21f8bdd2145281a76e26782ad9cfbb537c8c3c5880'
unchanged = {p: sha(p.read_bytes()) for p in (
    G/'scripts/atk_cb.ddf', N/'atk_cb.ddf', G/'scripts/atk_ucb.ddf',
    G/'g_ucb.xbx', APP/'installation/vilgax/ultimatecannonbolt/g_ucb.xbx',
    APP/'installation/vilgax/ultimatecannonbolt/atk_ucb.ddf',
    APP/'runtime/ben10.exe', APP/'runtime/SHA256SUMS.txt')}
p = entries(raw)
old = dict(p)
nodes = m.table(p[14])
root, impact = 0xfb61a9c2, 0x61d53120
dash = m.crc('cosmic_cb_va_balldash_ground_impact')
meteor = ident('meteor_node')
assert meteor not in nodes
triangle_start, dash_start = 0x58ee2d01, 0xf1645061

# The current Meteor animation already emits the fifth-slot start at contact.
# Verify all three normal attack records select that same clip and event.
attack = (G/'scripts/atk_cb.ddf').read_bytes()
meteor_rows = [r for r in struct.iter_unpack('>56I',attack[4:]) if r[40]==0xba93374a]
assert len(meteor_rows)==3 and all(r[8]==0xd8baecc8 and r[36]==0xa18d130a for r in meteor_rows)
meteor_start = 0xa18d130a
clips = m.table(p[13])
ch = channel_records(p[9])
clip = clips[0xd8baecc8]
eventch = ch[struct.unpack_from('>I',clip,80)[0]]
assert eventch[0]==10 and eventch[1]==9
events = list(struct.iter_unpack('>f8I',eventch[8:]))
assert [(r[0],r[4]) for r in events if r[4]&0x1000] == [(5600.,0x1000)]

# Same root/ball transform convention as the already approved alignment script.
def sample(index,t):
    r=ch[index];kind,stride,tag,count,_=struct.unpack_from('>BBHHH',r)
    if kind==16:
        rows=[(t*160,(-x/32767,-y/32767,-z/32767,w/127))
              for x,y,z,w,t in struct.iter_unpack('>3hbB',r[8:])]
    else:
        assert kind in (1,12) and stride==4
        rows=[(t,(x,y,z)) for t,x,y,z in struct.iter_unpack('>4f',r[8:])]
    assert len(rows)==count
    j=bisect.bisect_right([x[0] for x in rows],t)
    if j==0:return rows[0][1]
    if j==len(rows):return rows[-1][1]
    a,b=rows[j-1],rows[j];f=(t-a[0])/(b[0]-a[0]);q=b[1]
    if kind==16 and sum(x*y for x,y in zip(a[1],q))<0:q=tuple(-v for v in q)
    return tuple(x+(y-x)*f for x,y in zip(a[1],q))

def rotate(q,v):
    n=math.sqrt(sum(a*a for a in q));x,y,z,w=(a/n for a in q);a,b,c=v
    tx,ty,tz=2*(y*c-z*b),2*(z*a-x*c),2*(x*b-y*a)
    return (a+w*tx+y*tz-z*ty,b+w*ty+z*tx-x*tz,c+w*tz+x*ty-y*tx)

def pose(t):
    ids=m.bone_ids(clip);assert ids[0]==0 and ids[44]==193
    pos,rot,scale=[sample(j,t) for j in struct.unpack_from('>3I',clip,216)]
    off=sample(struct.unpack_from('>I',clip,216+12*44)[0],t)
    v=rotate(rot,tuple(a*b for a,b in zip(off,scale)))
    return tuple(a+b for a,b in zip(pos,v))

contact=5600
ball=pose(contact)
assert .5<ball[1]<.9 and pose(contact-160)[1]>ball[1]+1 and abs(pose(contact+160)[1]-ball[1])<.001
ground=(ball[0],.035,ball[2])

def groups(blocks):
    out=[]
    for block in blocks:
        if block[0]!=14:continue
        for k,t,v in m.property_entries(block):
            if t==0x1000c:out.append([])
            assert out
            out[-1].append((k,t,list(v)))
    return out

def clone(g,changes,name=None):
    return [(m.crc(name) if name and t==0x1000c else k,t,list(changes.get(k,v))) for k,t,v in g]

def val(g,k):
    return next(v[0] for pk,t,v in g if pk==k)

def flatten(gs):
    return [x for g in gs for x in g]

def props_record(h,b,gs):
    assert sum(x[0]==14 for x in b)==1
    return m.node_record(h,[m.node_properties(flatten(gs)) if x[0]==14 else x for x in b])

dh,db=m.node_parts(nodes[dash])
ih,ib=m.node_parts(nodes[impact])
dg,ig=groups(db),groups(ib)
assert [g[0][2][0] for g in dg]==[0xe16f3a56,0x60bf9208,0x6ad0de1a,0xbfdf3dde,0x6ad0de1a]
assert [g[0][2][0] for g in ig]==[0xe16f3a56,0x60bf9208,0x6ad0de1a,0xbfdf3dde]
assert m.crc('mesh')==0xe16f3a56 and m.crc('fadealpha')==0xe43374cd
assert m.crc('alpha-default-in-hide')==0xe5b40266 and m.crc('fadeout')==0x90431869

# Native Mesh's fade-out input (0597de41) defaults to the CRC of "fadeout"
# in stock effect nodes; fadealpha is its target and 5e0393bd its fade period.
# Trigger the interpolation after the original scale peak, then hide at the
# original endpoint. No mesh/material/scale/position resource is altered.
peak=800
end=1279
fade_duration=(end-peak)/4800

def fade_mesh(g,fade,show=None,hide=None):
    assert val(g,0xe43374cd)==0 and val(g,0x0597de41)==0
    changes={0x0597de41:[fade],0xe43374cd:fs(0),0x5e0393bd:fs(fade_duration),
             0x3fe4f6d6:[0],0xe5b40266:[1]}
    if show is not None:changes[0x750f694a]=[show]
    if hide is not None:changes[0xa3911ca7]=[hide]
    return clone(g,changes)

def timer(g,label,start,finish,ticks):
    assert g[0][2]==[0x6ad0de1a] and ticks>0
    return clone(g,{0x8541406c:[start],0xd058515c:[finish],0x865f80c0:fs(ticks/4800)},
                 'cosmic_cb_va_ground_fade_'+label)

# Dash's existing single contact, scale and position tracks are untouched.
dash_fade=ident('dash_fade')
dash_groups=[fade_mesh(dg[0],dash_fade),*dg[1:],
             timer(dg[2],'dash_fade_timer',dash_start,dash_fade,peak)]
new_dash=props_record(dh,db,dash_groups)

# The triangle position/scale curves run continuously through all six contacts.
# Separate native mesh show/fade/hide signals cycle its opacity independently.
# Every pulse is local to this node; no globally named node events added.
tri_show,tri_fade,tri_hide=map(ident,('triangle_show','triangle_fade','triangle_hide'))
tri_groups=[fade_mesh(ig[0],tri_fade,tri_show,tri_hide),*ig[1:]]
for i in range(6):
    t=i*1280
    # The original animation raises the attack signal one tick before its
    # authored first landing; this starts visibility at the landing.
    tri_groups.extend([
        timer(ig[2],f'triangle_show_{i}',triangle_start,tri_show,t+1),
        timer(ig[2],f'triangle_fade_{i}',triangle_start,tri_fade,t+peak),
        timer(ig[2],f'triangle_hide_{i}',triangle_start,tri_hide,t+end)])
new_impact=props_record(ih,ib,tri_groups)

# Meteor: instance the precise approved Dash mesh/particle pulse under the
# Normal Cannonbolt root. The existing fifth-slot animation event triggers it
# at tick 5600; no delay, additional damage or world-space broadcast needed.
meteor_stop,meteor_fade=map(ident,('meteor_end','meteor_fade'))
dash_stop=val(dg[0],0xa3911ca7)
mh=list(dh);mh[0]=meteor;mh[7:10]=fs(*ground)
pos=next(b for b in db if b[0]==0x15)
newpos=list(pos)
assert len(newpos)==24
newpos[11:14]=fs(*ground);newpos[21:24]=fs(*ground)
mg=[]
for i,g in enumerate(dg[:4]):
    ng=[]
    for k,t,v in g:
        if v==[dash_start]:v=[meteor_start]
        elif v==[dash_stop]:v=[meteor_stop]
        if t==0x1000c and i in (2,3):k=ident(f'meteor_group_{i}')
        ng.append((k,t,v))
    mg.append(ng)
mg[0]=fade_mesh(mg[0],meteor_fade)
mg.append(timer(mg[2],'meteor_fade_timer',meteor_start,meteor_fade,peak))
new_meteor=m.node_record(mh,[newpos if b[0]==0x15 else
    m.node_properties(flatten(mg)) if b[0]==14 else b for b in db])

rh,rb=m.node_parts(nodes[root])
new_root=m.node_record(rh,[[0x14,b[1]+1,b[2]+1]+b[3:]+[meteor]
                          if b[0]==0x14 else b for b in rb])
revised={root:new_root,impact:new_impact,dash:new_dash}
rows=[(k,f,revised.get(k,v)) for k,f,v in m.vaps_rows(p[14])]
rows.append((meteor,0,new_meteor))
p[14]=m.build_vaps(14,struct.unpack_from('>H',p[14],12)[0],m.bucket_sorted(rows))
result=m.package(raw,p,(0,3,4,9,12,13,14,22,24))
check=entries(result)
assert all(check[k]==v for k,v in old.items() if k!=14)
nd=m.table(check[14])
assert len(nd)==len(nodes)+1 and nd[meteor]==new_meteor
assert all(nd[k]==v for k,v in nodes.items() if k not in revised)
assert all(nd[k]==v for k,v in revised.items())
for k in (impact,dash):
    a,b=m.node_parts(nodes[k]);c,d=m.node_parts(nd[k])
    assert a==c and [x for x in b if x[0]!=14]==[x for x in d if x[0]!=14]
assert all(g[0][2]!=[m.EVENT_GROUP] for k in (impact,dash,meteor) for g in groups(m.node_parts(nd[k])[1]))
for k in (impact,dash,meteor):
    _,bs=m.node_parts(nd[k])
    reference=next(b for b in bs if b[0]==0)
    assert reference==[0,4,impact,impact]
    assert impact in m.table(check[4]) and impact in m.table(check[3])
    assert [8,3,root] in bs
    g=groups(bs)
    assert len(set(x[0][0] for x in g))==len(g)
    assert val(g[0],0xe43374cd)==fw(0) and val(g[0],0x5e0393bd)==fw(fade_duration)

out=H/'normal-cb-ground-fade'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
out.mkdir(parents=True)
for target in paths:
    dest=out/'before'/target.relative_to(APP)
    dest.parent.mkdir(parents=True)
    dest.write_bytes(target.read_bytes())
    assert dest.read_bytes()==raw
(out/'g_cb.xbx').write_bytes(result)
report=dict(before=sha(raw),after=sha(result),meteor_landing_tick=contact,
            meteor_ball_position=ball,meteor_ground_position=ground,
            meteor_event=hex(meteor_start),meteor_node=hex(meteor),
            fade_seconds=fade_duration,triangle_contacts=[3520,4800,6080,7360,8640,9920],
            unchanged_sections=[k for k in old if k!=14],unchanged_files={str(k.relative_to(APP)):v for k,v in unchanged.items()},
            gameplay_verified=False)
(out/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
print('Candidate and backups:',out)

if '--install' in sys.argv:
    installed=[]
    try:
        for target in paths:
            assert target.read_bytes()==raw
            tmp=target.with_name(target.name+'.ground-fade-new')
            assert not tmp.exists()
            tmp.write_bytes(result)
            tmp.replace(target)
            installed.append(target)
            assert target.read_bytes()==result
        assert all(sha(k.read_bytes())==v for k,v in unchanged.items())
    except BaseException:
        for target in reversed(installed):
            tmp=target.with_name(target.name+'.ground-fade-restore')
            assert not tmp.exists()
            tmp.write_bytes(raw)
            tmp.replace(target)
        raise
    print('Installed both Normal Cannonbolt packages; all protected files unchanged.')
