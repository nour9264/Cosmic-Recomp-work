"""Build the live-bone suction mesh and a longer world-space pressure burst."""
import hashlib, json, struct, sys
from pathlib import Path
import numpy as np

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries

H = WORK
I = APP_ROOT/'installation'
O = H / 'ball-attached-suction-release'
O.mkdir(exist_ok=True)
raw = (I / 'game/global/g_cb.xbx').read_bytes()
assert raw == (I / 'vilgax/cannonbolt/g_cb.xbx').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '026b5bfac67307a05219bdc62b04fdbfbae731ccf6e0bc4bd2e2ed95c3675103'
p = entries(raw)
side = m.crc('ucb_suction_side_ribbons')
root = m.effect_root('cannonbolt')
flash = m.crc('ucb_suction_core_flash')
release = m.crc('ucb_suction_release')
timer = m.crc('ucb_suction_flash_fade_timer')

def fs(*v):
    return [struct.unpack('>I', struct.pack('>f', x))[0] for x in v]

def bank(s, rows):
    p[s] = m.build_vaps(s, struct.unpack_from('>H', p[s], 12)[0], rows)

def qmat(q):
    x, y, z, w = np.array(q, dtype=float) / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])

sk = m.table(p[12])[0x8b21e1f6]
a, b = [struct.unpack_from('>10f', sk, 12+44*i) for i in (0, 44)]
r0, r1 = [qmat([-x for x in v[:3]] + [v[3]]) for v in (a,b)]
rotation = r0 @ r1
translation = np.array(a[4:7]) + r0 @ np.array(b[4:7])
midpoint = np.array((0., .835, -.006))
rows = []
for k,f,v in m.vaps_rows(p[4]):
    if k == side:
        at,vb,ib = m.mesh_buffers(v,xbox=True)
        q = bytearray(v)
        for i in range(0,len(vb),20):
            xyz = np.array(struct.unpack_from('>3f',vb,i))
            local = rotation.T @ (xyz + midpoint - translation)
            assert np.max(np.abs(rotation @ local + translation - (xyz+midpoint))) < 1e-6
            struct.pack_into('>3f',q,at+i,*local)
        v = bytes(q)
        assert m.mesh_buffers(v,xbox=True)[2] == ib
    rows.append((k,f,v))
bank(4,rows)

n = m.table(p[14]); rows=[]
for k,f,v in m.vaps_rows(p[14]):
    if k in (side,root):
        h,blocks=m.node_parts(v); out=[]
        if k == side:
            # Disable authored pose curves; the native hook supplies the actual
            # ball transform every frame, including last-moment model turns.
            blocks = [x for x in blocks if x[0] not in (0x15,0x16)]
            h[19:26] = fs(3.0,-2.6,-2.6,-2.6,2.6,2.6,2.6)
        for block in blocks:
            if k == root and block[0] == 14:
                pp=[]; group=None
                for pk,pt,pv in m.property_entries(block):
                    if pt == 0x1000c: group=pk
                    if group == flash:
                        pv={0x3de73088:fs(1.32),0x5a6ce323:[0xffffffff],
                            0xc365b299:[0xffffffff],0xb462820f:[0x70ffffff],
                            0x2a0617ac:[0x00ffffff]}.get(pk,pv)
                    if group == timer:
                        pv={0x8541406c:[release],0x865f80c0:fs(1.30)}.get(pk,pv)
                    pp.append((pk,pt,pv))
                block=m.node_properties(pp)
            out.append(block)
        v=m.node_record(h,out)
    rows.append((k,f,v))
bank(14,rows)
result=m.package(raw,p); check=entries(result)
assert all(check[k]==v for k,v in entries(raw).items() if k not in (4,14))
assert all(m.table(check[14])[k]==v for k,v in n.items() if k not in (root,side))
assert all(m.table(check[4])[k]==v for k,v in m.table(entries(raw)[4]).items() if k!=side)
(O/'g_cb.xbx').write_bytes(result)
report=dict(old_cb_sha=hashlib.sha256(raw).hexdigest(),new_cb_sha=hashlib.sha256(result).hexdigest(),ball_bone_tag=193,flash_life_seconds=1.32,flash_hold_target_seconds=.44,flash_fade_target_seconds=.88,gameplay_verified=False)
(O/'validation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
