"""Align Vilgax ground impacts to the normal ball's authored landing poses."""
import bisect, datetime, hashlib, json, math, struct, sys
from pathlib import Path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records

H=WORK; I=APP_ROOT/'installation'; G=I/'game/global'; N=I/'vilgax/cannonbolt'
sha=lambda b:hashlib.sha256(b).hexdigest(); fw=lambda v:struct.unpack('>I',struct.pack('>f',v))[0]
fs=lambda *v:[fw(x) for x in v]
raw=(G/'g_cb.xbx').read_bytes(); assert raw==(N/'g_cb.xbx').read_bytes()
assert sha(raw)=='c7e1125bb5b94fd8c6f6996608beaccb2972143764ee8c7d04f3f60f6d79118f'
p=entries(raw);old=dict(p);nodes=m.table(p[14]);clips=m.table(p[13]);ch=channel_records(p[9])
root=0xfb61a9c2; impact=0x61d53120; launch=0xdc6ba6d2
dash_event=0x536c2df9; triangle_event=0x58ee2d01
atk=(G/'scripts/atk_cb.ddf').read_bytes();ucb=(G/'g_ucb.xbx').read_bytes();uatk=(G/'scripts/atk_ucb.ddf').read_bytes()

# Decode the real game skeleton, including the ball's parent rotation and
# scale. Tag 193 is the visible ball, a direct child of the animation root.
sk=m.table(p[12])[0x8b21e1f6]
assert struct.unpack_from('>I',sk,52+44*44)[0]==193
assert struct.unpack_from('>I',sk,52)[0]>>24==255

def sample(index,t):
    r=ch[index];kind,stride,tag,count,_=struct.unpack_from('>BBHHH',r)
    if kind==16:
        rows=[(t*160,(-x/32767,-y/32767,-z/32767,w/127)) for x,y,z,w,t in struct.iter_unpack('>3hbB',r[8:])]
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

def pose(key,t):
    clip=clips[key];ids=m.bone_ids(clip);assert ids[0]==0 and ids[44]==193
    pos,rot,scale=[sample(j,t) for j in struct.unpack_from('>3I',clip,216)]
    off=sample(struct.unpack_from('>I',clip,216+12*44)[0],t)
    v=rotate(rot,tuple(a*b for a,b in zip(off,scale)))
    return tuple(a+b for a,b in zip(pos,v))

contacts=(3520,4800,6080,7360,8640,9920)
positions=[pose(0x055ebd1f,t) for t in contacts]
assert all(.55<y<.75 for x,y,z in positions) and len({(round(x,2),round(z,2)) for x,y,z in positions})==6
dash_contact=6720;dash_pos=pose(0xe19178df,dash_contact)
assert .55<dash_pos[1]<.7 and all(dash_pos[1]<pose(0xe19178df,t)[1] for t in (6560,6880))

def position_track(keys):
    # Native Big Chill position curve format, 10 words per key, zero tangents.
    words=[]
    for t,v in keys:words+=fs(t)+[0]*6+fs(*v)
    return [0x15,4+len(words),0x050ad001,len(keys)<<16|len(keys)]+words

def groups(blocks):
    out=[]
    for block in blocks:
        if block[0]!=14:continue
        for k,t,v in m.property_entries(block):
            if t==0x1000c:out.append([])
            out[-1].append((k,t,list(v)))
    return out

def clone(g,changes,name=None):
    return [(m.crc(name) if name and t==0x1000c else k,t,list(changes.get(k,v))) for k,t,v in g]

# Keep each burst stationary in the player's attack coordinate space until
# its pulse is finished. Switch to the next real landing on the one-tick
# interval where the original scale curve is almost invisible.
ih,ib=m.node_parts(nodes[impact]);sc=next(b for b in ib if b[0]==0x19)
assert len(sc)==244;ground=[(x,.035,z) for x,_,z in positions]
keys=[]
for index,xyz in enumerate(ground):keys.extend([(index*1280,xyz),(index*1280+1279,xyz)])
ih[7:10]=fs(*ground[0]);new_impact=m.node_record(ih,[position_track(keys)]+ib)

# The larger launch burst starts at the first contact too, not at the actor
# origin; leave its exact duration and original mesh untouched.
lh,lb=m.node_parts(nodes[launch]);lh[7:10]=fs(ground[0][0],.8,ground[0][2])
new_launch=m.node_record(lh,[position_track([(0,(ground[0][0],.8,ground[0][2])),(2304,(ground[0][0],.8,ground[0][2]))])]+lb)

# Ball Dash already has its own movement and trail. Add exactly one copy of
# the original Superball impact mesh, but let a local timer fire it when the
# ball first reaches its landing minimum. No extra damage or animation event.
dash_node=m.crc('cosmic_cb_va_balldash_ground_impact');dash_start=m.crc('cosmic_cb_va_balldash_landing');dash_stop=m.crc('cosmic_cb_va_balldash_ground_end')
assert dash_node not in nodes and dash_start not in (dash_event,triangle_event)
dh=list(ih);dh[0]=dash_node;dh[7:10]=fs(dash_pos[0],.035,dash_pos[2]);pos=(dash_pos[0],.035,dash_pos[2])
one=[0x19,44,0x0d0a5003,0x00040004]+sc[4:44];assert one[-3:]==fs(.02,.02,.02)
gg=groups(ib);assert [g[0][2][0] for g in gg]==[0xe16f3a56,0x60bf9208,0x6ad0de1a,0xbfdf3dde]
old_stop=next(v[0] for k,t,v in gg[0] if k==0xa3911ca7);duration=1280/4800
changed=[]
for g in gg:
    out=[]
    for k,t,v in g:
        if v==[triangle_event]:v=[dash_start]
        elif v==[old_stop]:v=[dash_stop]
        elif k in (0x5e0393bd,0xf465b2b5,0x865f80c0):v=fs(duration)
        if t==0x1000c and g[0][2][0] in (0x6ad0de1a,0xbfdf3dde):k=m.crc('cosmic_cb_va_dash_'+hex(g[0][2][0]))
        out.append((k,t,v))
    changed.extend(out)
delay=(dash_contact-4159)/4800
changed+=clone(gg[2],{0x8541406c:[dash_event],0x865f80c0:fs(delay),0xd058515c:[dash_start]},'cosmic_cb_va_dash_landing_timer')
new_dash=m.node_record(dh,[position_track([(0,pos),(1280,pos)]),one,[0,4,impact,impact],[8,3,root],m.node_properties(changed)])

rh,rb=m.node_parts(nodes[root]);new_root=m.node_record(rh,[[0x14,b[1]+1,b[2]+1]+b[3:]+[dash_node] if b[0]==0x14 else b for b in rb])
revised={impact:new_impact,launch:new_launch,root:new_root}
rows=[(k,f,revised.get(k,v)) for k,f,v in m.vaps_rows(p[14])]+[(dash_node,0,new_dash)]
p[14]=m.build_vaps(14,struct.unpack_from('>H',p[14],12)[0],m.bucket_sorted(rows))
result=m.package(raw,p,(0,3,4,9,12,13,14,22,24));check=entries(result)
assert all(check[k]==v for k,v in old.items() if k!=14)
nd=m.table(check[14]);assert all(nd[k]==v for k,v in nodes.items() if k not in revised)
assert all(nd[k]==v for k,v in revised.items()) and nd[dash_node]==new_dash
assert len(nd)==len(nodes)+1 and next(b for b in m.node_parts(nd[impact])[1] if b[0]==0x19)==sc

out=H/'normal-cb-landing-positions'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');out.mkdir(parents=True)
(out/'before-g_cb.xbx').write_bytes(raw);(out/'g_cb.xbx').write_bytes(result)
report=dict(before=sha(raw),after=sha(result),superball_contacts=[{'tick':t,'ball':v} for t,v in zip(contacts,positions)],
            dash_contact=dash_contact,dash_ball=dash_pos,dash_delay=delay,damage_animations_audio_unchanged=True,gameplay_verified=False)
(out/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if '--install' in sys.argv:
    done=[]
    try:
        for target in (G/'g_cb.xbx',N/'g_cb.xbx'):
            assert target.read_bytes()==raw
            tmp=target.with_name(target.name+'.new-landing');assert not tmp.exists();tmp.write_bytes(result);tmp.replace(target);done.append(target)
            assert target.read_bytes()==result
        assert (G/'scripts/atk_cb.ddf').read_bytes()==atk and (G/'g_ucb.xbx').read_bytes()==ucb and (G/'scripts/atk_ucb.ddf').read_bytes()==uatk
    except BaseException:
        for target in reversed(done):
            tmp=target.with_name(target.name+'.restore-landing');tmp.write_bytes(raw);tmp.replace(target)
        raise
    print('Installed normal Cannonbolt landing effects. Backup:',out)
