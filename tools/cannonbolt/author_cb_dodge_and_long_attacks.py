"""Normal Cannonbolt approval preview. No installation or game writes."""
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path[:0]=[str(REPO / 'tools')]
import author_ucb_dodge_and_long_attacks as a
from author_alien_actions import packed_image
from convert_four_arms_meshes import mesh_buffers
from prepare_vilgax_import import table, bone_ids

OUT=(WORK/'Cannonbolt-Dodge-and-Long-Attacks.blend').resolve()

# Reconstruct the real normal Cannonbolt body and ball from the current
# local package, keeping the native vertex order, texture and skin weights.
mesh_key=0x58ec2e03
skin=table(a.parts[22])[mesh_key]
mesh=table(a.parts[4])[mesh_key]
textures=table(a.parts[0])
_,vertices,indices=mesh_buffers(mesh,xbox=True)
rows=list(struct.iter_unpack('>11f',vertices))
split=3700
assert len(rows)==4580 and len(skin)==80+52*len(rows)
positions=[a.C@Vector(row[:3]) for row in rows]

def original_material(key,name):
    material=bpy.data.materials.new(name)
    material.diffuse_color=(.85,.63,.08,1)
    material.use_nodes=True
    tree=material.node_tree
    shader=tree.nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value=.73
    tex=tree.nodes.new('ShaderNodeTexImage')
    tex.image=packed_image(textures[key],name)
    tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
    return material

faces=[[],[]]
for i,j,k in struct.iter_unpack('>3H',indices):
    assert max(i,j,k)<split or min(i,j,k)>=split
    if len({i,j,k})<3:continue
    faces[int(i>=split)].append((i,j,k) if i<split else (i-split,j-split,k-split))

def original_model(group, start, end, triangles, material, name):
    for obj in list(group.objects):group.objects.unlink(obj)
    geo=bpy.data.meshes.new(name)
    geo.from_pydata(positions[start:end],[],triangles)
    geo.update()
    uv=geo.uv_layers.new(name='Original game UV')
    for loop in geo.loops:
        u,v=rows[start+loop.vertex_index][9:]
        uv.data[loop.index].uv=(u,1-v)
    geo.materials.append(material)
    for poly in geo.polygons:poly.use_smooth=True
    obj=bpy.data.objects.new(name,geo)
    group.objects.link(obj)
    obj.parent=a.source
    obj['native_first_vertex']=start
    groups=[obj.vertex_groups.new(name=n) for n in a.names]
    for i in range(end-start):
        at=80+(start+i)*52
        weights,bones=skin[at+44:at+48],skin[at+48:at+52]
        assert sum(weights)>0
        for w,b in zip(weights,bones):
            if w:groups[b].add([i],w/sum(weights),'REPLACE')
    mod=obj.modifiers.new('Original Cannonbolt Skin','ARMATURE')
    mod.object=a.source
    return obj

original_model(a.body,0,split,faces[0],original_material(0x46cb9ef2,'Normal Cannonbolt Body'), 'Cannonbolt | Body')
original_model(a.ball,split,len(rows),faces[1],original_material(0xdb869166,'Normal Cannonbolt Ball'), 'Cannonbolt | Ball')

for name in ('jump_01','fall_01','land_01','punch_03','punch_out_03','punch_04','punch_out_04'):
    clip=a.clips[name]
    assert bone_ids(clip)==a.ids
    ix=struct.unpack_from('>135I',clip,216)
    assert 0xffffffff not in ix
    a.decoded[name]=[a.channel_data(i) for i in ix]

def snap_roll(angle, compression=1):
    """Full forward somersault around the ball's real axle."""
    return a.rolling(angle*.77,compression=compression)

def dodge(f):
    # Normal's quick, shallow airborne flip differs from Ultimate's long,
    # grounded roll. Return straight to block rather than a long recovery.
    if f<=3:
        return a.mix(a.guard,a.idle,a.ease((f-1)/2)),0,0
    if f<=7:
        return a.pose('run_in_01',(f-3)*5/4),.07*a.ease((f-3)/4),0
    if f<=16:
        t=(f-7)/9
        return snap_roll(2*math.pi*a.ease(t)),.07+1.75*a.ease(t),.27*4*t*(1-t)
    if f<=20:
        t=(f-16)/4
        return a.pose('run_out_01',5+5*t),1.82+.12*a.ease(t),0
    return a.mix(a.unroll,a.guard,a.ease((f-20)/4)),1.94,0

def bowling(f):
    # Stay curled at impact, squash briefly, then bounce away from the target.
    # Unlike UCB's Rolling Ram there is no unrolling into a punch.
    if f<=7:
        return a.pose('run_in_01',(f-1)*5/6),.09*a.ease((f-1)/6),0
    if f<=23:
        t=(f-7)/16
        d=.09+2.95*t**1.45
        return snap_roll((d-.09)/.77),d,0
    if f<=26:
        t=(f-23)/3
        return snap_roll(2.95/.77,1-.18*math.sin(math.pi*t)),3.04,0
    if f<=34:
        t=(f-26)/8
        d=3.04-.46*a.ease(t)
        return snap_roll((d-.09)/.77),d,.30*4*t*(1-t)
    if f<=39:
        return a.pose('run_out_01',5+f-34),2.58,0
    return a.mix(a.unroll,a.idle,a.ease((f-39)/4)),2.58,0

def body_slam(f):
    # Upright jumping attack. The original jump provides the leg tuck and
    # arm silhouette; the native overhead punch supplies the contact pose.
    # No ball form at any point, unlike Ultimate's Aerial Cannonball.
    crouch=a.pose('land_01',4)
    if f<=6:
        return a.mix(a.idle,crouch,a.ease((f-1)/5)),0,0
    if f<=17:
        t=(f-6)/11
        p=a.mix(crouch,a.pose('jump_01',3+13*t),a.ease(t*2))
        return p,1.40*t,.86*math.sin(t*math.pi/2)
    if f<=28:
        t=(f-17)/11
        ready=a.pose('jump_01',16)
        strike=a.pose('punch_04',46+12*t)
        p=a.mix(ready,strike,a.ease(t*1.5))
        return p,1.40+1.55*t,.86*math.cos(t*math.pi/2)
    if f<=32:
        return a.mix(a.pose('punch_04',58),a.pose('land_01',4),a.ease((f-28)/4)),2.95,0
    return a.mix(crouch,a.idle,a.ease((f-32)/8)),2.95,0

scenes=[
    a.scene_for('01 | Normal - Quick Roll Hop',24,dodge,1.94,[(1,'Guard'),(4,'Tuck'),(8,'Hop / flip'),(16,'Contact'),(20,'Unroll'),(24,'Guard')]),
    a.scene_for('02 | Normal - Bowling Strike',43,bowling,3.04,[(1,'Anticipation'),(8,'Accelerate'),(23,'Ball impact'),(27,'Rebound'),(35,'Unroll'),(43,'Recover')]),
    a.scene_for('03 | Normal - Jumping Body Slam',40,body_slam,2.95,[(1,'Ready'),(6,'Crouch'),(7,'Launch'),(17,'Apex'),(28,'Strike / land'),(40,'Recover')],require_roll=False),
]
a.finish_preview(scenes,OUT)
