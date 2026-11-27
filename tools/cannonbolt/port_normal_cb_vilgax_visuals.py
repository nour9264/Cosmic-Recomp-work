"""Port the locally extracted Vilgax Attacks Cannonbolt effects into its normal form.

Only the three normal specials are affected. The existing attack records,
animation streams, Meteor Bolt, Ultimate form and executable are untouched.
Source mesh/texture data is converted using the existing importer's Xbox format.
"""
import datetime, hashlib, json, struct, sys
from pathlib import Path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump

sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, animation_time_range

H=WORK
I=APP_ROOT/'installation'; G=I/'game/global'; N=I/'vilgax/cannonbolt'
V=vilgax_dump()
sha=lambda d:hashlib.sha256(d).hexdigest()
fw=lambda x:struct.unpack('>I',struct.pack('>f',x))[0]
fs=lambda *x:[fw(v) for v in x]
old=(G/'g_cb.xbx').read_bytes();assert old==(N/'g_cb.xbx').read_bytes()
parts=entries(old); before=dict(parts)
source=entries((V/'global/e_cb.xbx').read_bytes()); src_nodes=m.table(source[14])
stock=entries((G/'g_ucb.xbx').read_bytes()); nodes=m.table(parts[14]);root=0xfb61a9c2
rh,rb=m.node_parts(nodes[root]);childblock=next(b for b in rb if b[0]==0x14); old_children=childblock[3:]
assert len(old_children)==6 and set(old_children)=={0xee1e1be5,0xb48a66d5,0xf69eafe4,0x010dda58,0xacfe414b,0x8aff4099}
attack=(G/'scripts/atk_cb.ddf').read_bytes();assert attack==(N/'atk_cb.ddf').read_bytes()
ultimate=(G/'scripts/atk_ucb.ddf').read_bytes();ucb=(G/'g_ucb.xbx').read_bytes()
signals={}
for row in struct.iter_unpack('>56I',attack[4:]):
    if row[40] in (0x549d5666,0x239a66f0,0xcaf9c3c5):
        if row[40] in signals:assert signals[row[40]]==tuple(row[36:38])
        signals[row[40]]=tuple(row[36:38])
dash,superball,burnout=(signals[k][0] for k in (0x549d5666,0x239a66f0,0xcaf9c3c5))
assert (dash,superball,burnout)==(0x536c2df9,0x58ee2d01,0xbb52f086)

def groups(blocks):
    out=[]
    for b in blocks:
        if b[0]!=14:continue
        for p,t,v in m.property_entries(b):
            if t==0x1000c:out.append([])
            assert out;out[-1].append((p,t,list(v)))
    return out

def group(blocks,kind):return next(g for g in groups(blocks) if g[0][2]==[kind])
def clone(g,changes,name=None):
    return [(m.crc(name) if name and t==0x1000c else p,t,list(changes.get(p,v))) for p,t,v in g]
def ident(label):return m.crc('cosmic_cb_va_'+label)
def stop(label):return ident(label+'_end')
def new_header(h,key):
    h=list(h);h[0]=key;h[1]=m.NODE_REVISION;h[6]=m.crc('root');return h

# The original e_cb trail archetype has one trail group + a controller which
# maps ball dash and superball start/stop events to it. Cosmic supports the
# trail component directly, with reordered property values. No old archetype
# pointer or global named-node event dispatcher is carried across.
archetype=(V/'global/scripts/archetyp.at').read_bytes()
i=archetype.index(struct.pack('>I',0x36e4e10b));j=archetype.index(struct.pack('>2I',0xb268858f,0xb268858f),i)
assert struct.unpack_from('>I',archetype,j+12)[0]==56
trail=struct.unpack_from('>14I',archetype,j+16)
assert trail==(0,0,0x28e6a893,0,0x3f800000,0x3d23d70a,1,6,0xff0aa0c8,0x29dd18b8,0x3e99999a,4,0x3f800000,0x3f000000)
_,hand=m.node_parts(nodes[0x533d1abf]);native_trail=group(hand,0xb268858f)
_,template=m.node_parts(m.table(stock[14])[0xfed1d3c5]);mesh_group=group(template,0xe16f3a56);curve=group(template,0x60bf9208);timer=group(template,0x6ad0de1a)

# Imported normal clips issue both the original fifth-slot start and stop in
# the same animation sample. Keep gameplay events intact: visuals get their
# own one-shot end signal instead of being hidden in the same frame.
def timed(start,end,seconds,label):
    return clone(timer,{0x8541406c:[start],0x865f80c0:fs(seconds),0xd058515c:[end]},label+'_timer')

new_nodes={};mesh_sources={};added_tex={}
def add_node(key,h,b):
    assert key not in nodes and key not in new_nodes
    new_nodes[key]=m.node_record(h,b)

def trail_node(label,start,duration):
    key=ident(label);end=stop(label)
    h=new_header(rh,key);h[4]=0x40000;h[7:14]=fs(0,.8,0,0,0,0,1)
    h[19:26]=fs(2,-2,-2,-2,2,2,2)
    props=clone(native_trail,{0x8541406c:[start],0xf7be9018:[end],0xf6a5b4b4:[trail[4]],0x438170da:[trail[5]],
          0xc2267172:[trail[6]],0x1479f8c7:[trail[7]],0x665648e9:[trail[8]],0x82660d72:[trail[9]],
          0xa3bf687a:[trail[10]],0x95aba708:[trail[11]],0x6e40c442:[trail[12]],0xbc6925b9:[trail[13]]},label+'_trail')
    add_node(key,h,[[8,3,root],m.node_properties(props+timed(start,end,duration,label))])

def scale_track(keys):
    words=[]
    for time,scale in keys:words+=fs(time)+[0]*6+fs(scale,scale,scale)
    return [0x19,4+len(words),0x0d0a5003,len(keys)<<16|len(keys)]+words

def mesh_node(label,src,start,secs,position,rotation,scales,particle_src=None):
    key=ident(label);end=stop(label);h,_=m.node_parts(src_nodes[src]);h=new_header(h,key)
    h[4]=0x40000;h[7:14]=fs(*position,*rotation)
    props=clone(mesh_group,{0x750f694a:[start],0xa3911ca7:[end],0x5e0393bd:fs(secs),0xf465b2b5:fs(secs)})
    props+=clone(curve,{0x8541406c:[start],0xf7be9018:[end]})
    props+=timed(start,end,secs,label)
    if particle_src:
        _,pb=m.node_parts(src_nodes[particle_src]);pg=group(pb,0xbfdf3dde)
        # Use source emitter's BC3 sprite and normal blending, not the old
        # additive override. Place it relative to the attached visual node.
        props+=clone(pg,{0x8541406c:[start],0xf7be9018:[end],0x462ce4f5:fs(0,0,0,0,0,0,1)},label+'_particles')
    add_node(key,h,[scale_track(scales),[0,4,key,key],[8,3,root],m.node_properties(props)])
    mesh_sources[key]=src

# Original native ribbon is shared by ball dash and superball in 36e4e10b.
# The imported clips' active intervals are read directly from their flags.
clips=m.table(parts[13]);ch=channel_records(parts[9]);
assert animation_time_range(clips[0xe19178df],ch)==(4000,8800)
assert animation_time_range(clips[0x055ebd1f],ch)==(960,19200)
trail_node('balldash_ribbon',dash,(7039-4159)/4800)
trail_node('superball_ribbon',superball,(10239-3519)/4800)

# The source superball group launches e0977db0 (vertical burst), and the
# 6d95a611 hit relay spawns d4fcb339 -> 4df5e283 (radial impact).
# Repeat the original impact mesh at each of the six existing impact markers,
# using a native scale track, not duplicated world-space effect instances.
mesh_node('superball_launch',0xe0977db0,superball,.48,(0,.8,0),(0,0,0,1),[(0,.15),(640,.75),(1440,1),(2304,.02)])
pulses=[]
for at in (0,1280,2560,3840,5120,6400):
    pulses.extend([(at,.06),(at+320,.62),(at+800,1.0),(at+1279,.02)])
mesh_node('superball_impact',0x4df5e283,superball,7680/4800,(-.253,.035,0),(0,0,0,1),pulses,0x80751367)

# Burnout: the source particle node was imported before but forced additive
# and listened for the zero-duration attack window. Restore the source blend
# and its companion mesh (51248e4f). Source coordinates were relative to ball
# centre; the new weapon root follows the actor's feet.
old_particle=nodes[0xf69eafe4];ph,pb=m.node_parts(src_nodes[0xf69eafe4]);ph=new_header(ph,0xf69eafe4)
ph[8]=fw(.2);end=stop('burnout');ps=[]
for pg in groups(pb):
    assert pg[0][2]==[0xbfdf3dde]
    ps+=clone(pg,{0x8541406c:[burnout],0xf7be9018:[end]})
replacement=m.node_record(ph,[[8,3,root],m.node_properties(ps+timed(burnout,end,.42,'burnout_particles'))])
mesh_node('burnout_ground',0x51248e4f,burnout,.42,(-.016,.045,-.033),(.044,0,0,.999),[(0,1),(2016,1)])

# Translate original mesh commands, buffers, and color-bank headers using
# the tested Vilgax importer. Preserve all old entries exactly, including
# meshes shared by Ultimate Cannonbolt or the untouched Meteor move.
meshes=m.table(parts[4]);colors=m.table(parts[3]);textures=m.table(parts[0]);sm=m.table(source[4]);sc=m.table(source[3]);st=m.table(source[0])
shared=m.table(entries((V/'global/global.xbx').read_bytes())[0]);
new_mesh={};new_color={}
mesh_ref=meshes[0xfed1d3c5];color_ref=colors[0xfed1d3c5]
for key,src in mesh_sources.items():
    assert key not in meshes and key not in colors
    mesh,used=m.convert_mesh(sm[src],mesh_ref);new_mesh[key]=mesh
    row=sc[src];count=struct.unpack_from('>I',mesh,4)[0]
    assert len(row)==16+count*4 and struct.unpack_from('>I',row,8)[0]==src
    address=struct.unpack_from('<I',mesh,28)[0]-344
    new_color[key]=row[:8]+struct.pack('>I',key)+color_ref[12:16]+bytes(4)+struct.pack('<I',address)+bytes(8)+row[16:]
    for tex in used:assert tex in st and textures[tex]==m.convert_texture(st[tex])
for tex in (0x29dd18b8,0x04a64387,0x43063957,0x0f1e0d86):
    converted=m.convert_texture(shared[tex]);
    if tex in textures:assert textures[tex]==converted
    else:added_tex[tex]=converted

def bank(sec,added,replaced=None):
    replaced=replaced or {};rows=[(k,f,replaced.get(k,v)) for k,f,v in m.vaps_rows(parts[sec])]
    assert not set(added)&set(m.table(parts[sec]));rows.extend((k,0,v) for k,v in added.items())
    return m.build_vaps(sec,struct.unpack_from('>H',parts[sec],12)[0],m.bucket_sorted(rows))

newroot=m.node_record(rh,[[0x14,3+len(old_children)+len(new_nodes),len(old_children)+len(new_nodes)]+old_children+list(new_nodes) if b[0]==0x14 else b for b in rb])
# Generic local relay already forwards root attack events to its attached
# children. No hash-targeted global event groups are introduced.
parts[14]=bank(14,new_nodes,{root:newroot,0xf69eafe4:replacement})
parts[4]=bank(4,new_mesh);parts[3]=bank(3,new_color);parts[0]=bank(0,added_tex)
result=m.package(old,parts,(0,3,4,9,12,13,14,22,24));check=entries(result)
assert all(check[k]==v for k,v in before.items() if k not in (0,3,4,14))
for sec in (0,3,4):assert all(m.table(check[sec])[k]==v for k,v in m.table(before[sec]).items())
assert all(m.table(check[14])[k]==v for k,v in nodes.items() if k not in (root,0xf69eafe4))
assert all(m.table(check[14])[k]==v for k,v in new_nodes.items())
assert m.table(check[14])[root]==newroot and m.table(check[14])[0xf69eafe4]==replacement
assert all(0x721aeda8 not in [g[0][2][0] for g in groups(m.node_parts(v)[1])] for v in new_nodes.values())

out=H/'normal-vilgax-vfx'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');out.mkdir(parents=True)
(out/'before').mkdir();(out/'before/g_cb.xbx').write_bytes(old);(out/'g_cb.xbx').write_bytes(result)
report=dict(source=str(V/'global/e_cb.xbx'),source_sha256=sha((V/'global/e_cb.xbx').read_bytes()),before=sha(old),after=sha(result),
            imported_meshes={hex(k):hex(v) for k,v in mesh_sources.items()},new_nodes=[hex(k) for k in new_nodes],new_textures=[hex(k) for k in added_tex],
            normal_attacks_unchanged=sha(attack),ultimate_attacks_unchanged=sha(ultimate),ultimate_package_unchanged=sha(ucb),square_untouched=True,gameplay_verified=False)
(out/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));print('Candidate:',out)
if '--install' in sys.argv:
    done=[]
    try:
        for path in (G/'g_cb.xbx',N/'g_cb.xbx'):
            assert path.read_bytes()==old
            tmp=path.with_name(path.name+'.va-vfx-new');assert not tmp.exists();tmp.write_bytes(result);tmp.replace(path);done.append(path)
            assert path.read_bytes()==result
        assert (G/'scripts/atk_cb.ddf').read_bytes()==attack and (G/'scripts/atk_ucb.ddf').read_bytes()==ultimate and (G/'g_ucb.xbx').read_bytes()==ucb
    except BaseException:
        for path in reversed(done):
            tmp=path.with_name(path.name+'.va-vfx-restore');tmp.write_bytes(old);tmp.replace(path)
        raise
    print('Installed both normal form package copies.')
