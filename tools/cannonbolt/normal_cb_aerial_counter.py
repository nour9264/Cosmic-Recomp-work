"""Route the Normal Cannonbolt counter pair to the proven Ultimate aerial clips."""
import datetime, hashlib, json, struct, sys
from pathlib import Path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, animation_time_range

H=WORK; APP=APP_ROOT
I=APP/'installation'; G=I/'game/global'; N=I/'vilgax/cannonbolt'
paths=(G/'scripts/atk_cb.ddf',N/'atk_cb.ddf')
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=paths[0].read_bytes()
assert raw==paths[1].read_bytes()
assert sha(raw)=='67e86abac9ea398e57783b4444759caa370ef81b52353f3bef749df9605691c0'
ucb=(G/'scripts/atk_ucb.ddf').read_bytes()
assert ucb==(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
cb=(G/'g_cb.xbx').read_bytes()
assert cb==(N/'g_cb.xbx').read_bytes()
assert sha(cb)=='0e035cb59652cffb6a9bf58c3113ef5699f44ab8cbe190b6e70c91650b9e79a4'
protected={p:sha(p.read_bytes()) for p in (
    G/'g_cb.xbx',N/'g_cb.xbx',G/'g_ucb.xbx',I/'vilgax/ultimatecannonbolt/g_ucb.xbx',
    G/'scripts/atk_ucb.ddf',I/'vilgax/ultimatecannonbolt/atk_ucb.ddf',
    APP/'runtime/ben10.exe',APP/'runtime/SHA256SUMS.txt')}
parts=entries(cb);clips=m.table(parts[13]);ch=channel_records(parts[9])
row=struct.Struct('>56I'); new=bytearray(raw)
normal_ids={0x6c20e604,0x645af6c9}
ultimate_ids={0x3f8ec388,0x3c181fb6}
old_route=(0x548fcee2,0xc5bb6972,0xae4f5133)
new_route=(0x40fbaf0c,0x2be2d09f,0xc8da9b47)
names=[]
for k in new_route:
    c=clips[k];assert len(m.bone_ids(c))==45 and m.bone_ids(c)[44]==193
    names.append(c[:64].split(b'\0')[0].decode('ascii'))
assert names==['cosmic_ucb_aerial_travel','cosmic_ucb_dodge_counter_aerial_hit','cosmic_ucb_dodge_counter_aerial_out']
assert [animation_time_range(clips[k],ch) for k in new_route]==[(0,1600),(0,1120),(0,2560)]
changed=[]
for at in range(4,len(raw),row.size):
    r=row.unpack_from(raw,at);u=row.unpack_from(ucb,at)
    if r[0] not in normal_ids:continue
    assert u[0] in ultimate_ids and r[40]==u[40]==0x47c02d3b
    assert r[7:10]==old_route and u[7:10]==new_route
    struct.pack_into('>3I',new,at+28,*new_route)
    changed.append((at,r[0],u[0]))
assert {k for _,k,_ in changed}==normal_ids and {k for _,_,k in changed}==ultimate_ids
result=bytes(new)
for at in range(4,len(raw),row.size):
    a,b=row.unpack_from(raw,at),row.unpack_from(result,at)
    if a[0] in normal_ids:
        assert a[:7]==b[:7] and a[10:]==b[10:] and b[7:10]==new_route
    else:assert a==b
out=H/'normal-cb-aerial-counter'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
out.mkdir(parents=True)
for p in paths:
    dest=out/'before'/p.relative_to(APP);dest.parent.mkdir(parents=True);dest.write_bytes(p.read_bytes())
    assert dest.read_bytes()==raw
(out/'atk_cb.ddf').write_bytes(result)
report=dict(before=sha(raw),after=sha(result),records=[hex(k) for _,k,_ in changed],
    clips=names,only_animation_route_changed=True,all_vfx_damage_runtime_unchanged=True,gameplay_verified=False)
(out/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2));print('Backup:',out)
if '--install' in sys.argv:
    done=[]
    try:
        for p in paths:
            assert p.read_bytes()==raw
            tmp=p.with_name(p.name+'.aerial-counter-new');assert not tmp.exists()
            tmp.write_bytes(result);tmp.replace(p);done.append(p);assert p.read_bytes()==result
        assert all(sha(p.read_bytes())==v for p,v in protected.items())
    except BaseException:
        for p in reversed(done):
            tmp=p.with_name(p.name+'.aerial-counter-restore');assert not tmp.exists()
            tmp.write_bytes(raw);tmp.replace(p)
        raise
    print('Installed both normal attack records; all protected files unchanged.')
