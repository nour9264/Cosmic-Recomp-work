"""Author Blender previews and named actions with locally imported alien assets."""
import math
import struct
import sys
import zlib
from collections import defaultdict
from pathlib import Path
import pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK

import bpy
from mathutils import Euler, Quaternion, Vector

sys.path.insert(0, str(REPO / 'tools'))
from convert_four_arms_meshes import mesh_buffers
from extract_discord_level_images import table, untile
from merge_alien_streams import entries
from prepare_vilgax_import import bone_ids

OUT = WORK.resolve()
PACKAGES = APP_ROOT / 'installation/vilgax'
ALIENS = {'Jetray': ('jr', 53), 'Chromastone': ('cs', 51)}
NAMES = {
    0: 'MotionRoot', 31: 'Hips', 32: 'Spine', 33: 'Chest', 34: 'UpperChest',
    2: 'Neck', 1: 'Head',
    37: 'UpperArm.R', 38: 'Forearm.R', 39: 'Hand.R',
    56: 'UpperArm.L', 57: 'Forearm.L', 58: 'Hand.L',
    75: 'Thigh.R', 76: 'Shin.R', 77: 'Foot.R', 78: 'Toe.R',
    93: 'Thigh.L', 94: 'Shin.L', 95: 'Foot.L', 96: 'Toe.L',
    111: 'TailBase', 112: 'TailMid', 113: 'TailTip',
}
# Articulation pivots in the mesh coordinate system (X across, Y up, Z forward).
# The native skeleton's transform conventions still need a game playback test.
PIVOTS = {
    'Chromastone': {
        31:(0,1.23,-.04), 32:(0,1.38,-.04), 33:(0,1.53,-.04), 34:(0,1.80,-.04),
        2:(0,1.95,-.025), 1:(0,2.02,-.025),
        37:(.235,1.90,-.055), 38:(.655,1.89,-.053), 39:(1.045,1.89,-.037),
        75:(.105,1.265,-.04), 76:(.116,.82,-.04), 77:(.124,.19,-.03), 78:(.136,.045,.085),
    },
    'Jetray': {
        31:(0,.735,-.04), 32:(0,.915,-.065), 33:(0,1.15,.015),
        2:(0,1.40,.075), 1:(0,1.48,.11),
        37:(.19,1.23,.013), 38:(.56,1.11,-.017), 39:(.875,.84,.127),
        75:(.117,.77,.088), 76:(.235,.467,.133), 77:(.29,.095,.033), 78:(.344,.033,.16),
        111:(0,.77,-.17), 112:(0,.47,-.234), 113:(0,.055,-.316),
    }
}
SYMMETRY = {56:37,57:38,58:39,93:75,94:76,95:77,96:78}
AUX_TEXTURE_NAMES = {1:'Base Color',9:'Game Slot 9',10:'Game Slot 10'}

def coordinates(point):
    x, y, z = point
    return Vector((x, -z, y))

def packed_image(record, name):
    fmt, width, height = struct.unpack_from('>3H', record, 4)
    assert fmt == 0x11c and width % 4 == height % 4 == 0
    blocks = untile(record[128:], width // 4, height // 4, 3)
    rgba = bytearray(width * height * 4)
    def rgb565(value):
        return ((value >> 11) * 255 // 31, (value >> 5 & 63) * 255 // 63, (value & 31) * 255 // 31)
    for block in range(len(blocks) // 8):
        raw = blocks[block * 8:block * 8 + 8]
        a, b, bits = struct.unpack('<HHI', bytes(raw[i ^ 1] for i in range(8)))
        color_a, color_b = rgb565(a), rgb565(b)
        if a > b:
            colors = [color_a, color_b,
                      tuple((2*x+y)//3 for x,y in zip(color_a,color_b)),
                      tuple((x+2*y)//3 for x,y in zip(color_a,color_b))]
            palette = [bytes((*color,255)) for color in colors]
        else:
            palette = [bytes((*color_a,255)), bytes((*color_b,255)),
                       bytes((*((x+y)//2 for x,y in zip(color_a,color_b)),255)), bytes(4)]
        bx, by = block % (width // 4), block // (width // 4)
        for i in range(16):
            position = ((by*4+i//4)*width + bx*4+i%4)*4
            rgba[position:position+4] = palette[bits >> (2*i) & 3]
    rows = b''.join(b'\0' + rgba[i:i+width*4] for i in range(0,len(rgba),width*4))
    def chunk(kind, data):
        return struct.pack('>I',len(data)) + kind + data + struct.pack('>I',zlib.crc32(kind+data))
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>2I5B',width,height,8,6,0,0,0))
           + chunk(b'IDAT',zlib.compress(rows)) + chunk(b'IEND',b''))
    path = OUT / 'textures' / f'{name}.png'
    path.write_bytes(png)
    image = bpy.data.images.load(str(path))
    image.name = name
    image.pack()
    return image

def material_for(alien, mesh, vertex_at, textures):
    material = bpy.data.materials.new(f'{alien} · Vilgax Attacks original textures')
    material.use_nodes = True
    tree = material.node_tree
    uv = tree.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'Game UV'
    uv.location = (-700, 160)
    for at in range(396, vertex_at - 15, 16):
        kind, _, key, _ = struct.unpack_from('>4I', mesh, at)
        if kind not in AUX_TEXTURE_NAMES:
            continue
        slot = AUX_TEXTURE_NAMES[kind]
        texture = tree.nodes.new('ShaderNodeTexImage')
        texture.label = f'{slot} · {key:08x}'
        texture.image = packed_image(textures[key], f'{alien}_{key:08x}')
        texture.location = (-475, 400 - 310 * len([x for x in tree.nodes if x.type=='TEX_IMAGE']))
        tree.links.new(uv.outputs['UV'], texture.inputs['Vector'])
        if kind == 1:
            tree.links.new(texture.outputs['Color'], tree.nodes.get('Principled BSDF').inputs['Base Color'])
            tree.nodes.active = texture
        else:
            texture.image.colorspace_settings.name = 'Non-Color'
    tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .65
    return material

def load_alien(alien, scene):
    code, count = ALIENS[alien]
    sections = entries((PACKAGES / alien.lower() / f'g_{code}.xbx').read_bytes())
    mesh_key, skin = next(iter(table(sections[22]).items()))
    skeleton = next(iter(table(sections[12]).values()))
    assert struct.unpack_from('>H',skeleton)[0] == count
    idle = next(clip for clip in table(sections[13]).values() if clip.startswith(b'idle_01\0'))
    ids, parents = [], []
    for index in range(count):
        tag = struct.unpack_from('>I', skeleton, 52+44*index)[0]
        ids.append(tag & 0xffffff)
        parents.append(-1 if index == 0 else tag >> 24)
    assert ids == bone_ids(idle) and all(parent < i for i,parent in enumerate(parents))
    weights = []
    centroids = defaultdict(lambda: Vector((0,0,0)))
    totals = defaultdict(int)
    for at in range(80, len(skin), 52):
        vertex = Vector(struct.unpack_from('>3f',skin,at))
        influences = [(i,w) for i,w in zip(skin[at+48:at+52],skin[at+44:at+48]) if w]
        assert influences and all(i<count for i,w in influences)
        weights.append(influences)
        for i,w in influences:
            centroids[i] += vertex*w
            totals[i] += w
    main = PIVOTS[alien]
    points = []
    for i,ident in enumerate(ids):
        if not i:
            point = Vector((0,0,0))
        elif ident in main:
            point = coordinates(main[ident])
        elif ident in SYMMETRY:
            x,y,z = main[SYMMETRY[ident]]
            point = coordinates((-x,y,z))
        elif totals[i]:
            point = coordinates(centroids[i]/totals[i]).lerp(points[parents[i]],.22)
        else:
            point = points[parents[i]].copy()
        points.append(point)
    armature = bpy.data.armatures.new(f'{alien} · {count} game bones')
    rig = bpy.data.objects.new(f'{alien} Rig', armature)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bone_names = [NAMES.get(ident, f'Bone_{ident:03d}') for ident in ids]
    preferred = {0:31,31:32,32:33,33:34 if 34 in ids else 2,34:2,2:1,
                 37:38,38:39,56:57,57:58,75:76,76:77,77:78,93:94,94:95,95:96,
                 111:112,112:113}
    made = []
    for i,ident in enumerate(ids):
        bone = armature.edit_bones.new(bone_names[i])
        bone.head = points[i]
        child_id = preferred.get(ident)
        end = points[ids.index(child_id)] if child_id in ids else None
        if end is None or (end-points[i]).length < .02:
            direction = points[i]-points[parents[i]] if i else Vector((0,0,1))
            end = points[i] + (direction.normalized() if direction.length>.01 else Vector((0,0,1)))*.09
        bone.tail = end
        if i:
            bone.parent = made[parents[i]]
        made.append(bone)
    bpy.ops.object.mode_set(mode='OBJECT')
    for index,(bone,ident) in enumerate(zip(bone_names,ids)):
        armature.bones[bone]['game_bone_id'] = ident
        armature.bones[bone]['game_bone_index'] = index
    rig['bind_note'] = 'Game bone IDs, indices, hierarchy and skin weights. Preview pivots derived from mesh anatomy and weighted vertices.'
    rig.show_in_front = False
    mesh = table(sections[4])[mesh_key]
    vertex_at, vertex_data, index_data = mesh_buffers(mesh,xbox=True)
    positions = [coordinates(struct.unpack_from('>3f',vertex_data,at)) for at in range(0,len(vertex_data),44)]
    uvs = [struct.unpack_from('>2f',vertex_data,at+36) for at in range(0,len(vertex_data),44)]
    assert len(positions) == len(weights)
    faces = [(a,b,c) for a,b,c in struct.iter_unpack('>3H',index_data) if len({a,b,c})==3]
    geometry = bpy.data.meshes.new(f'{alien} · original mesh')
    geometry.from_pydata(positions,[],faces)
    geometry.update()
    uv_layer = geometry.uv_layers.new(name='Game UV')
    for loop in geometry.loops:
        u,v = uvs[loop.vertex_index]
        uv_layer.data[loop.index].uv = (u,1-v)
    for face in geometry.polygons:
        face.use_smooth = True
    geometry.materials.append(material_for(alien,mesh,vertex_at,table(sections[0])))
    model = bpy.data.objects.new(alien,geometry)
    scene.collection.objects.link(model)
    groups = [model.vertex_groups.new(name=n) for n in bone_names]
    for vertex,influences in enumerate(weights):
        total = sum(w for _,w in influences)
        for index,weight in influences:
            groups[index].add([vertex], weight/total, 'REPLACE')
    model.parent = rig
    modifier = model.modifiers.new('Original skin weights', 'ARMATURE')
    modifier.object = rig
    modifier.use_deform_preserve_volume = True
    assert len(armature.bones) == count
    foot_vertices = [i for i,items in enumerate(weights)
                     if any(ids[index] in {77,78,81,95,96,99} and w>=100 for index,w in items)]
    return rig,model,foot_vertices

def guard(alien):
    is_ray = alien == 'Jetray'
    return {
        'Hips':(8,0,0), 'Spine':(6,0,0), 'Chest':(-7,0,0), 'Head':(-8,0,0),
        'UpperArm.R':(0,38 if is_ray else 33,-50), 'Forearm.R':(0,-10,-56),
        'UpperArm.L':(0,-38 if is_ray else -33,50), 'Forearm.L':(0,10,56),
        'Thigh.R':(-16,8,0), 'Thigh.L':(-13,-8,0),
        'Shin.R':(27,0,0), 'Shin.L':(25,0,0), 'Foot.R':(-12,0,0), 'Foot.L':(-12,0,0),
        'TailBase':(-20,0,0), 'TailMid':(-14,0,0), 'TailTip':(-7,0,0),
    }

def lunge(alien):
    ray = alien == 'Jetray'
    start = guard(alien)
    ready = dict(start, **{'Hips':(14,0,-8), 'Chest':(7,0,12), 'Thigh.R':(-33,5,0),
                 'Thigh.L':(-25,-7,0), 'Shin.R':(58,0,0), 'Shin.L':(47,0,0),
                 'UpperArm.R':(0,47,8), 'UpperArm.L':(0,-47,37), 'Forearm.R':(0,-32,-60)})
    launch = {'Hips':(26 if ray else 13,0,-12), 'Chest':(12 if ray else 0,0,6), 'Head':(-21,0,0),
              'UpperArm.R':(0,10,-38), 'UpperArm.L':(0,-20,20), 'Forearm.R':(0,-20,-45),
              'Forearm.L':(0,14,38), 'Thigh.R':(-48,7,0), 'Shin.R':(77,0,0),
              'Thigh.L':(19,-4,0), 'Shin.L':(38,0,0), 'TailBase':(-10,0,0), 'TailMid':(12,0,0)}
    strike = {'Hips':(49 if ray else 19, -7, -9), 'Spine':(9 if ray else 2,0,0),
              'Chest':(6,0,16), 'Head':(-41 if ray else -19,0,0),
              'UpperArm.R':(0,-5,-8 if ray else -70), 'Forearm.R':(0,0,-10 if ray else -4),
              'UpperArm.L':(0,5,11 if ray else 31), 'Forearm.L':(0,0,10 if ray else 62),
              'Thigh.R':(-6 if ray else -31,3,0), 'Thigh.L':(15 if ray else 26,-4,0),
              'Shin.R':(20 if ray else 45,0,0), 'Shin.L':(31 if ray else 52,0,0),
              'Foot.R':(10,0,0), 'Foot.L':(9,0,0), 'TailBase':(-18,0,0), 'TailMid':(4,0,0)}
    follow = dict(strike, **{'Hips':(36 if ray else 26,5,6),'Head':(-24,0,0),
                  'UpperArm.R':(0,24,-21 if ray else -83), 'UpperArm.L':(0,-21,25),
                  'Thigh.R':(-29,4,0), 'Shin.R':(51,0,0), 'Thigh.L':(-20,-7,0), 'Shin.L':(44,0,0)})
    land = dict(start, **{'Hips':(18,0,-7), 'Spine':(9,0,0), 'Head':(-14,0,0),
                'Thigh.R':(-39,6,0), 'Shin.R':(60,0,0), 'Foot.R':(-25,0,0),
                'Thigh.L':(-33,-8,0), 'Shin.L':(62,0,0), 'Foot.L':(-29,0,0)})
    distance = 3.05 if ray else 2.35
    return [
        (1,0,0,0,start,'Ready'),
        (5,0,.02,0,ready,'Anticipation'),
        (9,.04,-distance*.17,.48 if ray else .57,launch,'Takeoff'),
        (13,.02,-distance*.51,.67 if ray else .72,strike,'Hit pose'),
        (17,0,-distance*.79,.42 if ray else .48,follow,'Follow-through'),
        (22,0,-distance,0,land,'Landing'),
        (29,0,-distance,0,start,'Recovery'),
    ]

DIRECTIONS = {'Forward': (0,-1,0), 'Backward': (0,1,180), 'Left':(-1,0,-90), 'Right':(1,0,90)}

def dodge(alien, direction):
    x,y,heading = DIRECTIONS[direction]
    ray = alien == 'Jetray'
    guard_pose = guard(alien)
    lean = dict(guard_pose, **{'Hips':(21,-12*x,0), 'Chest':(15,0,0), 'Head':(3,0,0),
                   'Thigh.R':(-38,8,0), 'Shin.R':(68,0,0), 'Thigh.L':(-38,-8,0), 'Shin.L':(68,0,0)})
    tuck = dict(lean, **{'Hips':(26,0,0), 'Spine':(18,0,0), 'Chest':(21,0,0), 'Head':(9,0,0),
                 'UpperArm.R':(0,28,-53), 'UpperArm.L':(0,-28,53),
                 'Forearm.R':(0,-12,-43), 'Forearm.L':(0,12,43),
                 'Thigh.R':(-65,5,0), 'Thigh.L':(-61,-5,0),
                 'Shin.R':(103,0,0), 'Shin.L':(100,0,0),
                 'Foot.R':(-25,0,0), 'Foot.L':(-23,0,0),
                 'TailBase':(-32,0,0), 'TailMid':(-26,0,0), 'TailTip':(-16,0,0)})
    recover = dict(lean, **{'Hips':(16,10*x,0), 'Chest':(4,0,0), 'Head':(-11,0,0),
                    'Thigh.R':(-28,6,0), 'Thigh.L':(-29,-6,0), 'Shin.R':(48,0,0), 'Shin.L':(49,0,0)})
    end = 23 if ray else 26
    distance = 1.65 if ray else 1.52
    return [
        (1,0,0,0,guard_pose,'Block held',0),
        (4,x*.07,y*.07,0,lean,'Push off',12),
        (7,x*distance*.21,y*distance*.21,.08,tuck,'Tuck',76),
        (10,x*distance*.44,y*distance*.44,.07,tuck,'Roll',167),
        (13,x*distance*.67,y*distance*.67,.06,tuck,None,259),
        (16,x*distance*.86,y*distance*.86,0,recover,'Uncoil',327),
        (end-3,x*distance,y*distance,0,recover,'Plant',360),
        (end,x*distance,y*distance,0,guard_pose,'Block held',360),
    ]

def quat(angles):
    return Euler(tuple(math.radians(value) for value in angles),'XYZ').to_quaternion()

def support_height(scene, mesh, foot_vertices, use_body):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    deformed = evaluated.to_mesh()
    try:
        points = deformed.vertices if use_body else (deformed.vertices[i] for i in foot_vertices)
        return min((evaluated.matrix_world @ point.co).z for point in points)
    finally:
        evaluated.to_mesh_clear()

def animate(scene, alien, rig, model, foot, direction):
    poses = lunge(alien) if direction is None else dodge(alien,direction)
    title = 'Jump Lunge Attack' if direction is None else f'Block Dodge · {direction}'
    action = bpy.data.actions.new(f'{alien} | {title}')
    action.use_fake_user = True
    action['source'] = 'Authored Blender animation, 30 fps'
    action['root_motion'] = 'MotionRoot translation shows travel in Blender; reconcile with gameplay movement before export.'
    rig.animation_data_create().action = action
    active_names = sorted({name for _,_,_,_,pose,*_ in poses for name in pose if name in rig.pose.bones})
    root = rig.pose.bones['MotionRoot']
    root.rotation_mode = 'QUATERNION'
    root_basis = root.bone.matrix_local.to_quaternion()
    previous = {}
    for frame,x,y,lift,pose,marker,*rotation in poses:
        if marker:
            scene.timeline_markers.new(marker,frame=frame)
        roll_angle = rotation[0] if rotation else 0
        if direction:
            heading = math.radians(DIRECTIONS[direction][2])
            axis = Quaternion((0,0,1),heading) @ Vector((1,0,0))
            roll = Quaternion(axis,math.radians(roll_angle))
        else:
            roll = Quaternion()
        root.location = root_basis.inverted() @ Vector((x,y,0))
        for name in active_names:
            bone = rig.pose.bones[name]
            bone.rotation_mode = 'QUATERNION'
            basis = bone.bone.matrix_local.to_quaternion()
            rotation = quat(pose.get(name,(0,0,0)))
            if name == 'Hips':
                rotation = roll @ rotation
            value = basis.inverted() @ rotation @ basis
            if name in previous and value.dot(previous[name]) < 0:
                value.negate()
            bone.rotation_quaternion = value
            previous[name] = value.copy()
            bone.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=name)
        scene.frame_set(frame)
        height = support_height(scene,model,foot,65<=roll_angle<=310)
        root.location = root_basis.inverted() @ Vector((x,y,lift-height))
        root.keyframe_insert(data_path='location',frame=frame,group='MotionRoot')
    # Dense support keys keep grounded rolls and landings from intersecting the floor between poses.
    slot = action.slots[0]
    curves = action.layers[0].strips[0].channelbag(slot).fcurves
    for curve in curves:
        for point in curve.keyframe_points:
            point.interpolation = 'LINEAR'
    end_frame = poses[-1][0]
    desired = []
    for frame in range(1,end_frame+1):
        scene.frame_set(frame)
        position = root_basis @ root.location
        after = next((i for i,row in enumerate(poses) if row[0]>=frame),len(poses)-1)
        b,a = poses[after],poses[max(0,after-1)]
        t = (frame-a[0])/(b[0]-a[0]) if b[0]>a[0] else 0
        lift = (1-t)*a[3]+t*b[3]
        angle = (1-t)*a[-1]+t*b[-1] if direction else 0
        height = support_height(scene,model,foot,65<=angle<=310)
        desired.append((frame,root_basis.inverted() @ Vector((position.x,position.y,position.z+lift-height))))
    for frame,position in desired:
        root.location = position
        root.keyframe_insert(data_path='location',frame=frame,group='MotionRoot')
    for curve in curves:
        if curve.data_path.endswith('.location'):
            for point in curve.keyframe_points:
                point.interpolation = 'LINEAR'
    scene.frame_end = end_frame
    print('ACTION', action.name, tuple(action.frame_range),len(curves))

def configure(scene, alien, direction):
    scene.render.fps = 30
    scene.frame_start = 1
    scene.render.engine = 'BLENDER_WORKBENCH'
    shade = scene.display.shading
    shade.light = 'STUDIO'
    shade.studiolight_rotate_z = .4
    shade.color_type = 'TEXTURE'
    shade.show_cavity = True
    shade.cavity_type = 'BOTH'
    shade.show_shadows = False
    shade.show_specular_highlight = False
    shade.background_type = 'WORLD'
    scene.world = bpy.data.worlds.get('Preview world') or bpy.data.worlds.new('Preview world')
    scene.world.color = (.055,.065,.09)
    scene.render.resolution_x = 750
    scene.render.resolution_y = 520
    scene.render.resolution_percentage = 100
    camera_data = bpy.data.cameras.new(scene.name)
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = 5.6 if direction is None else 4.5
    camera = bpy.data.objects.new('Preview Camera',camera_data)
    scene.collection.objects.link(camera)
    if direction is None:
        middle = Vector((0,-1.1,1.05))
    else:
        x,y,_ = DIRECTIONS[direction]
        middle = Vector((x*.75,y*.75,1.05))
    camera.location = middle + Vector((4.0,-6.8,2.2)) if direction else middle + Vector((6.5,-4.0,2.2))
    camera.rotation_euler = (middle-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera = camera
    return middle,camera

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    template_scene = bpy.context.scene
    initial = None
    for alien in ALIENS:
        source_rig = source_model = None
        for direction in (None,'Forward','Backward','Left','Right'):
            name = f'{alien} | Jump Lunge Attack' if direction is None else f'{alien} | Block Dodge {direction}'
            scene = bpy.data.scenes.new(name)
            bpy.context.window.scene = scene
            if source_rig is None:
                rig,model,feet = load_alien(alien,scene)
                source_rig,source_model = rig,model
                if initial is None:
                    initial = scene
            else:
                rig,model = source_rig.copy(),source_model.copy()
                rig.animation_data_clear()
                scene.collection.objects.link(rig)
                scene.collection.objects.link(model)
                model.parent = rig
                model.modifiers[0].object = rig
            animate(scene,alien,rig,model,feet,direction)
            middle,camera = configure(scene,alien,direction)
            scene.frame_set(13 if direction is None else 1)
            if direction is None or direction=='Right':
                for frame in ((5,13,22) if direction is None else (1,7,10,16,scene.frame_end)):
                    scene.frame_set(frame)
                    scene.render.filepath = str(OUT / 'previews' / f'{alien}_{direction or "Lunge"}_{frame:02d}.png')
                    bpy.ops.render.render(write_still=True)
            scene.frame_set(1)
    bpy.context.window.scene = initial
    bpy.data.scenes.remove(template_scene)
    initial.frame_set(13)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.overlay.show_floor = False
                space.overlay.show_axis_x = False
                space.overlay.show_axis_y = False
                space.overlay.show_extras = False
                space.overlay.show_bones = False
                space.shading.color_type = 'TEXTURE'
                space.region_3d.view_perspective = 'CAMERA'
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Jetray-Chromastone-Animations.blend'),compress=True)

if __name__ == '__main__':
    main()
