"""Route normal Cannonbolt's three R2+Square records to the proven Ultimate Meteor Bolt."""
import hashlib,json,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
from merge_alien_streams import entries
import prepare_vilgax_import as m
H = WORK;I=APP_ROOT/'installation';G=I/'game/global';O=H/'normal-cannonbolt-meteor';O.mkdir(exist_ok=True)
raw=(G/'scripts/atk_cb.ddf').read_bytes();ultimate=(G/'scripts/atk_ucb.ddf').read_bytes()
assert raw==(I/'vilgax/cannonbolt/atk_cb.ddf').read_bytes() and ultimate==(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
assert len(raw)==len(ultimate)==6500
p=entries((G/'g_cb.xbx').read_bytes());assert 0xd8baecc8 in m.table(p[13]);nodes=m.table(p[14]);assert all(m.crc(n) in nodes for n in ('ucb_meteor_poe_ring','ucb_meteor_poe_crater'))
out=bytearray(raw);changed=[]
for at in range(4,len(raw),224):
    if struct.unpack_from('>I',raw,at+160)[0]!=0xba93374a:continue
    assert struct.unpack_from('>I',ultimate,at+160)[0]==0xba93374a
    assert struct.unpack_from('>I',raw,at+32)[0]==0xc9fb4de3 and struct.unpack_from('>I',ultimate,at+32)[0]==0xd8baecc8
    # Preserve normal form's distinct record ID and bank-local sound event.
    # Every other field (lead-in, jump, steering, recovery, impact VFX) is identical.
    out[at+4:at+152]=ultimate[at+4:at+152];out[at+156:at+224]=ultimate[at+156:at+224];changed.append(at)
assert len(changed)==3
for at in range(4,len(raw),224):
    if at not in changed:assert out[at:at+224]==raw[at:at+224]
    else:
        assert out[at:at+4]==raw[at:at+4] and out[at+152:at+156]==raw[at+152:at+156]
        assert out[at+4:at+152]==ultimate[at+4:at+152] and out[at+156:at+224]==ultimate[at+156:at+224]
result=bytes(out);(O/'atk_cb.ddf').write_bytes(result);sha=lambda x:hashlib.sha256(x).hexdigest();report=dict(old_sha=sha(raw),new_sha=sha(result),records=changed,animation='cosmic_poe_ucb_meteor_bolt',normal_sound_retained=True,ultimate_unchanged=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
