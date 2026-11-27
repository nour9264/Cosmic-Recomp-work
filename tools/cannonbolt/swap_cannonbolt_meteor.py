"""Swap both R2+Square routes, keeping each form's attack record identity."""
import hashlib,json,struct
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
H = WORK;I=APP_ROOT/'installation';G=I/'game/global/scripts';O=H/'cannonbolt-meteor-swap';O.mkdir(exist_ok=True)
normal=(G/'atk_cb.ddf').read_bytes();ultimate=(G/'atk_ucb.ddf').read_bytes();original=(H/'normal-cannonbolt-meteor/pre-install/game/global/scripts/atk_cb.ddf').read_bytes()
assert normal==(I/'vilgax/cannonbolt/atk_cb.ddf').read_bytes() and ultimate==(I/'vilgax/ultimatecannonbolt/atk_ucb.ddf').read_bytes()
sha=lambda b:hashlib.sha256(b).hexdigest();assert sha(normal)=='5e55d22399bdd6413addf0545b0341bfd47ad1cbb87a33fb94ddadfbc59623e5' and sha(ultimate)=='6aff1e43dbea08c396e448737ae1d830890ce1e6209951524075ed26d370f0e7' and sha(original)=='c09f0114f4504889989cf121f3c8a367716dbd7e41bf6d518e02c73d34a61582'
nc=bytearray(normal);uc=bytearray(ultimate);changed=[]
for at in range(4,len(normal),224):
    if struct.unpack_from('>I',original,at+160)[0]!=0xba93374a:continue
    assert struct.unpack_from('>I',ultimate,at+160)[0]==0xba93374a
    nc[at+4:at+224]=ultimate[at+4:at+224]
    uc[at+4:at+224]=original[at+4:at+224]
    changed.append(at)
assert changed==[4,3140,5380]
for at in range(4,len(normal),224):
    if at not in changed:assert nc[at:at+224]==normal[at:at+224] and uc[at:at+224]==ultimate[at:at+224]
    else:assert nc[at+4:at+224]==ultimate[at+4:at+224] and uc[at+4:at+224]==original[at+4:at+224]
(O/'atk_cb.ddf').write_bytes(nc);(O/'atk_ucb.ddf').write_bytes(uc)
report=dict(old_cb_sha=sha(normal),new_cb_sha=sha(nc),old_ucb_sha=sha(ultimate),new_ucb_sha=sha(uc),swapped_records=changed,sound_routes_swapped=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
