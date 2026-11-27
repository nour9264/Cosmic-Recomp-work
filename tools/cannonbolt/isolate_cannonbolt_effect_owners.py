"""Separate normal and Ultimate weapon effect trees.

The normal→Ultimate switch created two instances of the same root and shared
event namespace. Give normal Cannonbolt its own root, retaining its four
normal attacks and Meteor Bolt. Only Ultimate owns the four custom VFX and
their existing native collision groups. No per-frame tree scan or transform
rewrite is needed.
"""
import datetime
import hashlib
import json
import struct
import sys
from pathlib import Path

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries
from prepare_all_aliens_candidate import records,encode

HERE = WORK;APP=APP_ROOT;I=APP/'installation';G=I/'game/global';RT=APP/'runtime'
N=I/'vilgax/cannonbolt';U=I/'vilgax/ultimatecannonbolt'
sha=lambda b:hashlib.sha256(b).hexdigest()
oldcb=(G/'g_cb.xbx').read_bytes();olducb=(G/'g_ucb.xbx').read_bytes()
assert oldcb==(N/'g_cb.xbx').read_bytes() and olducb==(U/'g_ucb.xbx').read_bytes()
cb=entries(oldcb);ucb=entries(olducb);assert 14 not in ucb
nodes=m.table(cb[14]);rows=m.vaps_rows(cb[14]);flags={k:f for k,f,_ in rows}
root=m.effect_root('cannonbolt');assert root==0x1b34d861
rh,rb=m.node_parts(nodes[root]);children=next(b[3:] for b in rb if b[0]==0x14)
assert len(children)==15
normal_native={0xee1e1be5,0xb48a66d5,0xf69eafe4,0x010dda58}
normal_meteor={0x0daebb1e,0xf613bfaa}
normal_children=[k for k in children if k in normal_native|normal_meteor]
assert len(normal_children)==6
ultimate_children=[k for k in children if k not in normal_native]
assert len(ultimate_children)==11
normal_root=m.crc('cosmic_cb_normal_owned_specials_root')
node_map={root:normal_root,**{k:m.crc(f'cosmic_cb_normal_owned_child_{k:08x}') for k in normal_meteor}}
assert not set(node_map.values())&set(nodes)

normal_attack=(G/'scripts/atk_cb.ddf').read_bytes();assert normal_attack==(N/'atk_cb.ddf').read_bytes()
ultimate_attack=(G/'scripts/atk_ucb.ddf').read_bytes();assert ultimate_attack==(U/'atk_ucb.ddf').read_bytes()
events={e for row in struct.iter_unpack('>56I',normal_attack[4:]) if row[40]!=0x47c02d3b for e in row[36:38]}
assert events=={0x1a196954,0x7a469ae7,0x9f990718,0xa8907668,0xae311471,0xbc5a15e4,0xda570eb9,0xfe036c3c}
events.add(0x261f503c) # normal Meteor's private timer stop
event_map={k:m.crc(f'cosmic_cb_normal_owned_event_{k:08x}') for k in events}
assert len(set(event_map.values()))==len(events) and not set(event_map.values())&events
event_props={0x8541406c,0xf7be9018,0xd058515c,0x939b68a0}

def groups(block):
    out=[]
    for p,t,v in m.property_entries(block):
        if t==0x1000c:out.append([])
        assert out;out[-1].append((p,t,v))
    return out

def normal_properties(group,owner):
    out=[]
    for p,t,v in group:
        # Property types and mesh/texture/sound hashes stay native. Only
        # explicit event operands and child-node targets are namespaced.
        if t==0x1000c and p!=v[0]:p=m.crc(f'cosmic_cb_normal_owned_group_{owner:08x}_{p:08x}')
        if p in event_props:v=[event_map.get(x,x) for x in v]
        elif p==0x557c4b4d:v=[node_map.get(x,x) for x in v]
        out.append((p,t,v))
    return out

def child_for_normal(key):
    h,blocks=m.node_parts(nodes[key]);h=list(h);h[0]=node_map.get(key,key)
    result=[]
    for b in blocks:
        if b[0]==8:
            assert b==[8,3,root];b=[8,3,normal_root]
        elif b[0]==14:b=m.node_properties([p for group in groups(b) for p in normal_properties(group,key)])
        elif b[0]==0x17:
            b=list(b)
            for j in range(12,len(b),9):b[j]=event_map.get(b[j],b[j])
        # Mesh-reference blocks deliberately retain the original mesh keys.
        result.append(b)
    return m.node_record(h,result)

normal_h=list(rh);normal_h[0]=normal_root
normal_blocks=[];ultimate_blocks=[];kept_groups=[]
for b in rb:
    if b[0]==0x14:
        n=[node_map.get(k,k) for k in normal_children]
        normal_blocks.append([0x14,3+len(n),len(n)]+n)
        ultimate_blocks.append([0x14,3+len(ultimate_children),len(ultimate_children)]+ultimate_children)
    elif b[0]==14:
        # Only the first generic relay and groups serving normal Meteor's
        # own start/stop remain in the normal root. None of Spin/Suction/
        # Backspin/Bounce's emitters or damage forwards survive here.
        selected=[]
        for group in groups(b):
            k=group[0][0]
            if k==0x2f8eb5f4 or any(p in event_props and set(v)&events for p,t,v in group):
                selected.append(group);kept_groups.append(k)
        assert set(kept_groups)=={0x2f8eb5f4,0x1e5d32d3,0x381af74c,0x1f7a08b1,0x44405e27,0x993cd47f,0x293b453e},[hex(k) for k in kept_groups]
        normal_blocks.append(m.node_properties([p for group in selected for p in normal_properties(group,root)]))
        ultimate_blocks.append(b) # every original Ultimate visual and hit event is unchanged
    else:normal_blocks.append(b);ultimate_blocks.append(b)

normal_nodes={normal_root:m.node_record(normal_h,normal_blocks)}
for k in normal_children:normal_nodes[node_map.get(k,k)]=child_for_normal(k)
ultimate_nodes={root:m.node_record(rh,ultimate_blocks),**{k:nodes[k] for k in ultimate_children}}
# Keep the common hand-weapon tree exactly as it was in the shared archive.
other={k:v for k,v in nodes.items() if k not in {root,*children}}
assert set(normal_nodes).isdisjoint(ultimate_nodes) and set(other).isdisjoint(ultimate_nodes)
assert all(ultimate_nodes[k]==nodes[k] for k in ultimate_children)
normal_flags={node_map.get(k,k):flags[k] for k in (root,*normal_children)}
def bank(d,source):
    return m.build_vaps(14,struct.unpack_from('>H',source,12)[0],m.bucket_sorted([(k,normal_flags.get(k,flags.get(k,0)),v) for k,v in d.items()]))
cb[14]=bank({**other,**normal_nodes},cb[14]);ucb[14]=bank(ultimate_nodes,entries(oldcb)[14])
newcb=m.package(oldcb,cb,(0,3,4,9,12,13,14,22,24))
newucb=m.package(olducb,ucb,(0,3,4,14,22,24))
cbcheck,ucbcheck=entries(newcb),entries(newucb)
assert all(cbcheck[k]==v for k,v in entries(oldcb).items() if k!=14)
assert all(ucbcheck[k]==v for k,v in entries(olducb).items()) # including repaired shoulders and audio
assert m.table(cbcheck[14])=={**other,**normal_nodes} and m.table(ucbcheck[14])==ultimate_nodes
assert root not in m.table(cbcheck[14]) and normal_root not in m.table(ucbcheck[14])

# Normal attacks keep original damage, animation, sound and timing. Route
# only the explicit start/stop signals into the normal private event space.
newatk=bytearray(normal_attack);changed=0
for at in range(4,len(normal_attack),224):
    row=list(struct.unpack_from('>56I',normal_attack,at))
    if row[40]==0x47c02d3b:continue
    assert row[36] in event_map and row[37] in event_map
    row[36]=event_map[row[36]];row[37]=event_map[row[37]]
    struct.pack_into('>56I',newatk,at,*row);changed+=1
assert changed==12
for at in range(4,len(normal_attack),224):assert normal_attack[at:at+144]==newatk[at:at+144] and normal_attack[at+152:at+224]==newatk[at+152:at+224]
init_id=m.crc('Cosmic_cannonbolt_init')
def patch_init(data):
    result=[];count=0
    for k,args,code in records(data):
        if k==init_id:
            original=code;code=m.replace_arguments(code,{root:normal_root});assert code!=original and len(code)==len(original)
            assert sum(a!=b for a,b in zip(struct.iter_unpack('>I',code),struct.iter_unpack('>I',original)))==1;count+=1
        result.append((k,args,code))
    assert count==1
    return encode(result)
forms=(N/'forms.bin').read_bytes();gld=(G/'scripts/gld_xbx.ds').read_bytes()
newforms=patch_init(forms);newgld=patch_init(gld)
ultimate_init=m.crc('Cosmic_ultimatecannonbolt_init')
assert next(c for k,a,c in records(newgld) if k==ultimate_init)==next(c for k,a,c in records(gld) if k==ultimate_init)

# The earlier build swapped the runtime executable here; in the source tree the native code is compiled from native-rex/src instead.
changes={G/'g_cb.xbx':(oldcb,newcb),N/'g_cb.xbx':(oldcb,newcb),G/'g_ucb.xbx':(olducb,newucb),U/'g_ucb.xbx':(olducb,newucb),
         G/'scripts/atk_cb.ddf':(normal_attack,bytes(newatk)),N/'atk_cb.ddf':(normal_attack,bytes(newatk)),N/'forms.bin':(forms,newforms),G/'scripts/gld_xbx.ds':(gld,newgld)}
backup=HERE/'private-effect-owners'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');backup.mkdir(parents=True)
for path,(before,after) in changes.items():
    assert path.read_bytes()==before
    for folder,data in [('before',before),('after',after)]:
        dest=backup/folder/path.relative_to(APP);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
report={'normal_root':hex(normal_root),'ultimate_root':hex(root),'normal_children':len(normal_nodes)-1,'ultimate_children':len(ultimate_nodes)-1,
        'normal_attack_events_changed':changed,'ultimate_attacks_preserved':True,'shoulder_preserved':True,'gameplay_verified':False,
        'files':[{'file':str(p.relative_to(APP)),'before':sha(a),'after':sha(b)} for p,(a,b) in changes.items()]}
(backup/'validation.json').write_text(json.dumps(report,indent=2))
if '--install' not in sys.argv:
    print('Candidate validated:',backup);sys.exit(0)
installed=[]
try:
    for p,(before,after) in changes.items():
        assert p.read_bytes()==before
        tmp=p.with_name(p.name+'.private-vfx-new');assert not tmp.exists();tmp.write_bytes(after);tmp.replace(p);installed.append(p);assert p.read_bytes()==after
except BaseException:
    for p in reversed(installed):
        tmp=p.with_name(p.name+'.private-vfx-restore');assert not tmp.exists();tmp.write_bytes(changes[p][0]);tmp.replace(p)
    raise
assert (G/'scripts/atk_ucb.ddf').read_bytes()==ultimate_attack
print('Installed isolated normal/Ultimate effects:',backup)
