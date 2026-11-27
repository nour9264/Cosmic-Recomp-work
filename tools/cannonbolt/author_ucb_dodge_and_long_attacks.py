"""Create an approval-only Blender file using the approved 45-bone UCB rig.

The original game's roll-in/out, guard and punch poses supply the articulation;
the travel, spin, timing and airborne arcs are authored for this preview.
No game files are written.
"""
import bisect
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path.insert(0, str(REPO / 'tools'))
from merge_alien_streams import entries, channel_records
from prepare_vilgax_import import table, bone_ids

OUT = (WORK/'Ultimate-Cannonbolt-Dodge-and-Long-Attacks.blend').resolve()
ASSET = (APP_ROOT/'installation/game/global/g_cb.xbx')
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
CI = C.inverted()
parts = entries(ASSET.read_bytes())
channels = channel_records(parts[9])
clips = {v[:64].split(b'\0')[0].decode(): v for v in table(parts[13]).values()}
native = bpy.data.scenes['Cannonbolt | Native rig']
source = next(o for o in native.objects if o.type == 'ARMATURE')
body = native.collection.children['BODY - native vertex order']
ball = native.collection.children['BALL - native vertex order']
names = [b.name for b in source.data.bones]
ids = [b['game_bone_id'] for b in source.data.bones]
assert len(ids) == len(set(ids)) == 45
parents = [int(b['game_parent_index']) for b in source.data.bones]
bind_world = []
for i,b in enumerate(source.data.bones):
    v=b['game_local_xyzw_t_s']
    local=Matrix.LocRotScale(Vector(v[4:7]),Quaternion((v[3],*v[:3])).conjugated(),Vector(v[7:]))
    bind_world.append(local if parents[i]<0 else bind_world[parents[i]]@local)


def channel_data(index):
    raw = channels[index]
    kind, stride, tag, count, _ = struct.unpack_from('>BBHHH', raw)
    if kind == 16:
        rows = [(t, Quaternion((w / 127, x / 32767, y / 32767, z / 32767)).normalized().conjugated())
                for x, y, z, w, t in struct.iter_unpack('>3hbB', raw[8:])]
    else:
        assert kind in (1, 12)
        rows = [(t / 160, Vector((x, y, z))) for t, x, y, z in struct.iter_unpack('>4f', raw[8:])]
    assert len(rows) == count
    return ([t for t, _ in rows], [v for _, v in rows])


decoded = {}
for name in ('idle_01', 'block_01', 'run_in_01', 'run_out_01', 'punch_01', 'punch_out_01'):
    clip = clips[name]
    assert bone_ids(clip) == ids
    indices = struct.unpack_from('>135I', clip, 216)
    assert 0xffffffff not in indices
    decoded[name] = [channel_data(i) for i in indices]


def sample(data, t):
    times, values = data
    j = bisect.bisect_right(times, t)
    if not j:
        return values[0].copy()
    if j == len(times):
        return values[-1].copy()
    weight = (t - times[j - 1]) / (times[j] - times[j - 1])
    a, b = values[j - 1], values[j]
    return a.slerp(b, weight) if isinstance(a, Quaternion) else a.lerp(b, weight)


def pose(name, frame):
    c = decoded[name]
    return [(sample(c[i], frame), sample(c[i+1], frame), sample(c[i+2], frame))
            for i in range(0, len(c), 3)]


def mix(a, b, weight):
    return [(p.lerp(q, weight), r.slerp(s, weight), u.lerp(v, weight))
            for (p,r,u),(q,s,v) in zip(a,b)]


def ease(t):
    t = max(0.0, min(1.0, t))
    return t*t*(3-2*t)


idle = pose('idle_01', 0)
guard = pose('block_01', 4)
curl = pose('run_in_01', 5)
unroll = pose('run_out_01', 10)
BALL = 44
BODY = 1


def rolling(distance, height=0, compression=1):
    p = [(t.copy(), q.copy(), s.copy()) for t,q,s in curl]
    # The native ball bone is a separate sibling of the body. Rotate its
    # rigid shell around the local lateral axis, not the humanoid limbs.
    loc, q, scale = p[BALL]
    parent_frame = p[0][1]
    ax = parent_frame.inverted() @ Vector((1,0,0))
    q = Quaternion(ax, distance / .77) @ q
    p[BALL] = (loc, q, Vector((scale.x, scale.y * compression, scale.z)))
    p[BODY] = (p[BODY][0], p[BODY][1], Vector((0,0,0)))
    return p


def dodge(f):
    if f <= 3:
        return mix(guard, idle, ease((f-1)/2)), 0, 0
    if f <= 8:
        return pose('run_in_01', f-3), .12*ease((f-3)/5), 0
    if f <= 20:
        t = (f-8)/12
        d = .12 + 2.15*(1-(1-t)**1.55)
        return rolling(d-.12), d, 0
    if f <= 25:
        t = (f-20)/5
        return pose('run_out_01', 5+t*5), 2.27+.16*ease(t), 0
    return mix(unroll, guard, ease((f-25)/5)), 2.43, 0


def charge(f):
    if f <= 7:
        return pose('run_in_01', (f-1)*5/6), .10*ease((f-1)/6), 0
    if f <= 23:
        t = (f-7)/16
        d = .10+3.45*t**1.25
        return rolling(d-.10), d, 0
    if f <= 28:
        t = (f-23)/5
        return pose('run_out_01', 5+t*5), 3.55+.25*ease(t), 0
    if f <= 38:
        t = (f-28)/10
        attack = pose('punch_01', 1+t*10)
        return mix(unroll, attack, ease(t*3)), 3.80+.24*ease(t), 0
    if f <= 46:
        return pose('punch_out_01',12+(f-38)*10/8), 4.04, 0
    return mix(pose('punch_out_01',22), idle, ease((f-46)/4)), 4.04, 0


def leap(f):
    if f <= 7:
        return pose('run_in_01', (f-1)*5/6), .12*ease((f-1)/6), 0
    if f <= 27:
        t = (f-7)/20
        d = .12+3.52*t
        height = 1.06*4*t*(1-t)
        return rolling(d-.12), d, height
    if f <= 30:
        t = (f-27)/3
        return rolling(3.52+.13*t, compression=1-.13*math.sin(math.pi*t)), 3.64+.13*t, 0
    if f <= 35:
        return pose('run_out_01', 5+f-30), 3.77+.11*ease((f-30)/5), 0
    return mix(unroll, idle, ease((f-35)/8)), 3.88, 0


def aim(obj, point):
    obj.rotation_euler = (Vector(point)-obj.location).to_track_quat('-Z','Y').to_euler()


def add_area(scene, name, loc, energy, size, color, target):
    light = bpy.data.lights.new(name,'AREA')
    light.energy,light.size,light.color = energy,size,color
    obj = bpy.data.objects.new(name,light)
    scene.collection.objects.link(obj)
    obj.location=loc
    aim(obj,target)


def scene_for(label, frames, motion, distance, markers, require_roll=True):
    scene = bpy.data.scenes.new(label)
    bpy.context.window.scene = scene
    scene.frame_start, scene.frame_end = 1, frames
    scene.render.fps = 30
    rig = source.copy()
    rig.name = label + ' | 45-bone rig'
    rig.animation_data_clear()
    scene.collection.objects.link(rig)
    rig.hide_render = True
    rig.show_in_front = False
    sets = []
    for group in (body,ball):
        col = bpy.data.collections.new(label+' | '+group.name.split(' - ')[0])
        scene.collection.children.link(col)
        objects=[]
        for obj in group.objects:
            cp=obj.copy()
            cp.animation_data_clear()
            col.objects.link(cp)
            cp.parent=rig
            cp.hide_viewport=False
            cp.hide_render=False
            for mod in cp.modifiers:
                if mod.type=='ARMATURE':mod.object=rig
            cp.hide_set(False)
            objects.append(cp)
        sets.append(objects)
    bones=list(rig.pose.bones)
    rests=[b.bone.matrix_local.copy() for b in bones]
    relative=[r if not b.parent else rests[names.index(b.parent.name)].inverted()@r for b,r in zip(bones,rests)]
    inv=[r.inverted() for r in relative]
    # Blender's edit-bone axes differ from the source skeleton's axes.
    # Transfer the native world-space *deformation* to the Blender bind
    # matrices rather than assigning the game's local matrices directly.
    correction=[w.inverted()@CI@r for w,r in zip(bind_world,rests)]
    for b in bones:b.rotation_mode='QUATERNION'
    previous=[None]*len(bones)
    log=[]
    # Key every native bone each frame, preserving anatomical skinning and
    # the engine's two distinct meshes during the body/ball transition.
    for f in range(1,frames+1):
        scene.frame_set(f)
        p,d,height=motion(f)
        rolling_now=max(p[BODY][2])<.1
        native_world=[]
        targets=[]
        for i,(b,(pos,q,scale)) in enumerate(zip(bones,p)):
            safe=Vector(tuple(max(.00001,x) for x in scale))
            local=Matrix.LocRotScale(pos,q,safe)
            par=parents[i]
            native_world.append(local if par<0 else native_world[par]@local)
            target=C@native_world[i]@correction[i]
            targets.append(target)
            basis=inv[i]@(target if par<0 else targets[par].inverted()@target)
            loc,rot,sc=basis.decompose()
            if previous[i] is not None and rot.dot(previous[i])<0:rot.negate()
            previous[i]=rot.copy()
            b.location,b.rotation_quaternion,b.scale=loc,rot,sc
        rig.location=(0,-d,0)
        bpy.context.view_layer.update()
        deps=bpy.context.evaluated_depsgraph_get()
        # Exact lower surface, not the armature origin or hidden mesh.
        lowest=math.inf
        for obj in sets[int(rolling_now)]:
            evaluated=obj.evaluated_get(deps)
            zrow=evaluated.matrix_world[2]
            a,b,c,dz=zrow
            lowest=min(lowest,min(a*v.co.x+b*v.co.y+c*v.co.z+dz for v in evaluated.data.vertices))
        rig.location.z=height-lowest+.015
        rig.keyframe_insert('location',frame=f)
        for b in bones:
            for prop in ('location','rotation_quaternion','scale'):
                b.keyframe_insert(prop,frame=f,group=b.name)
        log.append((f,d,height,rolling_now))
    action=rig.animation_data.action
    action.name=label
    action.use_fake_user=True
    action['approval_only']=True
    action['travel_distance_m']=distance
    action['game_bones']=45
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
    for frame,meaning in markers:scene.timeline_markers.new(meaning,frame=frame)
    assert len(log)==frames and (not require_roll or any(x[3] for x in log)) and not log[0][3] and not log[-1][3]
    # Neutral studio, with the entire actual movement in frame.
    floor=bpy.data.meshes.new(label+' | floor')
    floor.from_pydata([(-8,-9,-.006),(8,-9,-.006),(8,5,-.006),(-8,5,-.006)],[],[(0,1,2,3)])
    fo=bpy.data.objects.new('Preview floor',floor)
    scene.collection.objects.link(fo)
    mat=bpy.data.materials.new(label+' | floor material');mat.diffuse_color=(.17,.19,.23,1);mat.use_nodes=True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.17,.19,.23,1)
    floor.materials.append(mat)
    airborne=max(x[2] for x in log)>0
    midpoint=(0,-distance*.5,1.4 if airborne else .95)
    cam=bpy.data.objects.new('Review camera',bpy.data.cameras.new(label+' | camera'))
    scene.collection.objects.link(cam)
    cam.location=(7.9,-distance*.5-5.6,3.75)
    aim(cam,midpoint)
    cam.data.type='ORTHO';cam.data.ortho_scale=max(5.7,distance+3.6 if airborne else distance+3.3)
    scene.camera=cam
    add_area(scene,'Soft key',(2,-4,6),1000,5,(.83,.90,1),midpoint)
    add_area(scene,'Fill',(-4,-1,3.5),700,4,(.7,.79,1),midpoint)
    add_area(scene,'Rim',(1,3,5),1100,3,(.84,.92,1),midpoint)
    scene.world=bpy.data.worlds.new(label+' | neutral world')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.13,.16,.23,1)
    scene.render.engine='CYCLES';scene.cycles.samples=12
    scene.render.resolution_x=960;scene.render.resolution_y=540;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard'
    for obj in scene.objects:obj.select_set(False)
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    scene.frame_set(1)
    print('VALIDATED',label,'frames',frames,'distance',round(log[-1][1],2),'flight',max(x[2] for x in log), flush=True)
    return scene


def finish_preview(scenes, path):
    # Leave originals untouched on disk; the review copy only opens the
    # action scenes, and retains the linked model materials and skeleton.
    bpy.context.window.scene=scenes[0]
    for s in list(bpy.data.scenes):
        if s not in scenes:bpy.data.scenes.remove(s)
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.region_3d.view_perspective='CAMERA'
            space.overlay.show_overlays=False
            space.shading.type='MATERIAL'
        elif area.type=='DOPESHEET_EDITOR':
            area.spaces.active.dopesheet.show_only_selected=False
    bpy.ops.file.pack_all()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print('PREVIEW SAVED', path, flush=True)


if __name__=='__main__':
    scenes = [
        scene_for('01 | Forward Dodge Roll',30,dodge,2.43,[(1,'Guard'),(4,'Curl'),(9,'Roll'),(21,'Unroll'),(30,'Guard')]),
        scene_for('02 | Long Attack - Rolling Ram',50,charge,4.04,[(1,'Anticipation'),(8,'Charge'),(23,'Contact'),(29,'Follow-through'),(50,'Recover')]),
        scene_for('03 | Long Attack - Aerial Cannonball',43,leap,3.88,[(1,'Anticipation'),(8,'Launch'),(17,'Apex'),(27,'Landing'),(31,'Unroll'),(43,'Recover')]),
    ]
    finish_preview(scenes,OUT)
