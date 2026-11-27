"""Extend the approved spin mesh vertically and forward-only debris travel."""
import hashlib,json,math,struct,sys
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
import prepare_vilgax_import as m
from merge_alien_streams import entries

H = WORK;I=APP_ROOT/'installation';O=H/'spin-clearance-height-distance';O.mkdir(exist_ok=True)
raw=(I/'game/global/g_cb.xbx').read_bytes();assert raw==(I/'vilgax/cannonbolt/g_cb.xbx').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='02a5b3caf306f4a7c81727ec496ddcaef7d5ac7a20beaf9af67faf357d83f178'
p=entries(raw);key=m.crc('ucb_spin_helix_mesh');root=m.effect_root('cannonbolt');scale=1.18
def fs(*v):return [struct.unpack('>I',struct.pack('>f',x))[0] for x in v]
def bank(s,rows):p[s]=m.build_vaps(s,struct.unpack_from('>H',p[s],12)[0],rows)
meshes=[];bounds=None
for k,f,v in m.vaps_rows(p[4]):
    if k==key:
        at,vb,ib=m.mesh_buffers(v,xbox=True);q=bytearray(v);ys=[struct.unpack_from('>f',vb,i+4)[0] for i in range(0,len(vb),20)];base=min(ys);top=max(ys)
        # Keep the local vertical axis fixed. Give the lower helix enough
        # clearance to surround the spikes rather than slice the ball when
        # camera perspective exposes the near side of the ribbon.
        for i,y in enumerate(ys):
            pos=at+i*20;x,z=struct.unpack_from('>f',q,pos)[0],struct.unpack_from('>f',q,pos+8)[0]
            t=(y-base)/(top-base);radius=math.hypot(x,z);target=max(radius,1.11+.07*t);factor=target/radius
            struct.pack_into('>3f',q,pos,x*factor,base+(y-base)*scale,z*factor)
        v=bytes(q);_,nv,ni=m.mesh_buffers(v,xbox=True);assert ni==ib and all(nv[i+12:i+20]==vb[i+12:i+20] for i in range(0,len(vb),20))
        bounds=(base,top,base+(top-base)*scale)
    meshes.append((k,f,v))
assert bounds;bank(4,meshes)
rock_edits={m.crc('ucb_backspin_rock_0_particles'):(12.0,.82),m.crc('ucb_backspin_rock_1_particles'):(12.7,.77)};seen=set();nodes=[]
for k,f,v in m.vaps_rows(p[14]):
    if k in (root,key):
        h,blocks=m.node_parts(v);out=[]
        if k==key:
            top=bounds[2]+.15;h[19:26]=fs(math.hypot(1.28,top),-1.28,-.1,-1.28,1.28,top,1.28)
        for b in blocks:
            if b[0]==14 and k==root:
                pp=[];group=None
                for pk,pt,pv in m.property_entries(b):
                    if pt==0x1000c:group=pk
                    if group in rock_edits:
                        speed,life=rock_edits[group];pv={0x0f26fef6:fs(speed),0x3de73088:fs(life),0x7a76b57b:fs(0,-.85,0)}.get(pk,pv);seen.add(group)
                    pp.append((pk,pt,pv))
                b=m.node_properties(pp)
            out.append(b)
        v=m.node_record(h,out)
    nodes.append((k,f,v))
assert seen==set(rock_edits);bank(14,nodes);result=m.package(raw,p);check=entries(result)
assert all(check[k]==v for k,v in entries(raw).items() if k not in (4,14));assert all(m.table(check[14])[k]==v for k,v in m.table(entries(raw)[14]).items() if k not in (root,key));assert all(m.table(check[4])[k]==v for k,v in m.table(entries(raw)[4]).items() if k!=key)
(O/'g_cb.xbx').write_bytes(result)
report=dict(old_cb_sha=hashlib.sha256(raw).hexdigest(),new_cb_sha=hashlib.sha256(result).hexdigest(),height_multiplier=scale,rock_nominal_ranges=[s*l for s,l in rock_edits.values()],other_sections_preserved=True,gameplay_verified=False);(O/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
