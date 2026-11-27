import datetime,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from vilgax_animation_paths import APP as APP_ROOT, BLEND, REPO, WORK
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as importer
from merge_alien_streams import entries
root=(APP_ROOT/'installation')
paths=[root/'vilgax/jetray/g_jr.xbx',root/'game/global/g_jr.xbx']
original=paths[0].read_bytes()
assert paths[1].read_bytes()==original
sections=entries(original)
order=[0,3,4,9,12,13,14,22,24]
assert set(sections)==set(order)
output=bytearray(importer.package(original,sections))
base=struct.unpack_from('>I',output,28)[0]
directory=32+struct.unpack_from('>I',output,44)[0]
rows={struct.unpack_from('>I',output,at)[0]:at for at in range(directory,directory+len(order)*12,12)}
alignment=1<<struct.unpack_from('>H',output,12)[0]
del output[base:]
for section in order:
    output.extend(bytes((-len(output))%alignment))
    struct.pack_into('>I',output,rows[section]+8,len(output)-base)
    output.extend(sections[section])
output.extend(bytes((-len(output))%alignment))
struct.pack_into('>I',output,16,len(output)-base)
assert entries(output)==sections
backup=(BLEND/'jetray-native-patch')/('layout-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir()
for path in paths:
    saved=backup/path.relative_to(root)
    saved.parent.mkdir(parents=True,exist_ok=True)
    saved.write_bytes(original)
for path in paths:
    pending=path.with_suffix('.xbx.layout-new')
    pending.write_bytes(output)
    pending.replace(path)
    assert path.read_bytes()==output
print('Jetray package installed in native layout. All section payloads byte-identical.')
