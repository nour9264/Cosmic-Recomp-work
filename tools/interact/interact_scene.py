"""Blender review scene: interact animations for the Alien Force aliens, copied from the game's own interact clips.

Run inside Blender (for example through the MCP execute tool):  exec(open(path).read())  with COSMIC_APP set to the folder
that holds installation/.  Reads the player's own local game files; nothing is written outside the Blender scene.

Every playable alien in the original game has three interact clips (interact_in_01 -> interact_01 -> interact_out_01).
The imported aliens have none. Skeleton bone IDs are game-wide, so a source alien's motion is transferred by bone ID as a
rotation change from its idle pose (world space) and added to the target's own idle pose. Timing is the source's.
"""
import bisect
import math
import os
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

REPO = Path(os.environ.get('COSMIC_REPO') or Path(__file__).resolve().parents[2])
APP = Path(os.environ['COSMIC_APP'])
GAME = APP / 'installation/game/global'
VILGAX = APP / 'installation/vilgax'
sys.path.insert(0, str(REPO / 'tools'))
from extract_discord_level_images import untile
from merge_alien_streams import channel_records, entries
from prepare_vilgax_import import bone_ids, mesh_buffers, table, vaps_rows

C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
CI = C.inverted()
NAMES = {0: 'Root', 31: 'Hips', 32: 'Spine', 33: 'Chest', 2: 'Neck', 1: 'Head', 37: 'Clavicle.R', 38: 'UpperArm.R',
         39: 'Forearm.R', 40: 'Hand.R', 56: 'Clavicle.L', 57: 'UpperArm.L', 58: 'Forearm.L', 59: 'Hand.L'}
SEQUENCE = ('interact_in_01', 'interact_01', 'interact_out_01')
# Which original alien's interact each Alien Force alien takes: same bone layout where possible.
PLAN = [
    ('Chromastone', VILGAX / 'chromastone/g_cs.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
    ('Jetray', VILGAX / 'jetray/g_jr.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
    ('Goop', VILGAX / 'goop/g_gp.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
    ('Cannonbolt', VILGAX / 'cannonbolt/g_cb.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
    # The six Ultimates (second row): same arm motion as the Alien Force aliens, from Chromastone's pressing arm.
    ('Ultimate Humungousaur', GAME / 'g_uhm.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
    ('Ultimate Cannonbolt', VILGAX / 'ultimatecannonbolt/g_ucb.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
    ('Ultimate Big Chill', GAME / 'g_ubc.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
    ('Ultimate Swampfire', GAME / 'g_usf.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
    ('Ultimate Echo Echo', GAME / 'g_uec.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
    ('Ultimate Spider Monkey', GAME / 'g_usm.xbx', 'Water Hazard', GAME / 'g_wh.xbx'),
]
IDLE_FROM = {'Ultimate Cannonbolt': VILGAX / 'cannonbolt/g_cb.xbx'}   # its package carries no clips: the normal form's are used


def bone_name(tag):
    return NAMES.get(tag, f'Bone_{tag:03}')


def image(record, name):
    magic, fmt, w, h = struct.unpack_from('>IHHH', record)
    bc1 = magic >> 28 != 0xa and fmt in (0x104, 0x11c)
    assert fmt in (0x104, 0x11c, 0x102, 0x11a), (name, fmt)
    log = 3 if bc1 else 4
    raw = bytearray(untile(record[128:], w // 4, h // 4, log))
    raw[0::2], raw[1::2] = raw[1::2], raw[0::2]
    pixels = [0.0] * (w * h * 4)
    for j in range(w * h // 16):
        b = raw[j * (1 << log):(j + 1) * (1 << log)]
        c = b if bc1 else b[8:]
        ca, cz = struct.unpack_from('<2H', c)
        colors = [((v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31) for v in (ca, cz)]
        a, z = colors
        colors += ([tuple((2 * x + y) // 3 for x, y in zip(a, z)), tuple((x + 2 * y) // 3 for x, y in zip(a, z))]
                   if not bc1 or ca > cz else [tuple((x + y) // 2 for x, y in zip(a, z)), (0, 0, 0)])
        ci = int.from_bytes(c[4:8], 'little')
        if not bc1:
            a0, a1 = b[:2]
            al = [a0, a1] + ([((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)] if a0 > a1
                             else [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255])
            ai = int.from_bytes(b[2:8], 'little')
        for i in range(16):
            k = (ci >> (2 * i)) & 3
            alpha = (0 if ca <= cz and k == 3 else 255) if bc1 else al[(ai >> (3 * i)) & 7]
            x = j % (w // 4) * 4 + i % 4
            y = h - 1 - (j // (w // 4) * 4 + i // 4)
            at = (y * w + x) * 4
            pixels[at:at + 4] = [colors[k][0] / 255, colors[k][1] / 255, colors[k][2] / 255, alpha / 255]
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels = pixels
    img.pack()
    return img


class Model:
    """A game package loaded as rig + skinned mesh, with the data needed to pose it from clips."""

    def __init__(self, scene, label, path, light=False, skeleton_from=None):
        """light=True reads skeleton, clips and bind only (no rig or mesh in the scene): enough to sample poses."""
        self.label = label
        self.hidden = set()
        self.p = p = entries(Path(path).read_bytes())
        key, skin = next(iter(table(p[22]).items()))
        # Ultimate Cannonbolt has its own mesh and skin but takes skeleton, channels and clips from the normal Cannonbolt.
        d = entries(Path(skeleton_from).read_bytes()) if skeleton_from else p
        sk = next(iter(table(d[12]).values()))
        n = struct.unpack_from('>H', sk)[0]
        rows = [struct.unpack_from('>10fI', sk, 12 + 44 * i) for i in range(n)]
        self.tags = [r[-1] & 0xffffff for r in rows]
        self.parents = [(-1 if r[-1] >> 24 == 255 else r[-1] >> 24) for r in rows]
        self.bind_local, self.bind = [], []
        for i, r in enumerate(rows):
            q = Quaternion((r[3], -r[0], -r[1], -r[2])).normalized()
            local = Matrix.LocRotScale(Vector(r[4:7]), q, Vector(r[7:10]))
            self.bind_local.append(local)
            self.bind.append(local if self.parents[i] < 0 else self.bind[self.parents[i]] @ local)
        self.channels = channel_records(d[9])
        self._keys = {}
        self.clips = {c[:64].split(b'\0')[0].decode(): c for _, _, c in vaps_rows(d[13])}
        if light:
            return
        heads = [Vector((w.translation.x, -w.translation.z, w.translation.y)) for w in self.bind]
        arm = bpy.data.armatures.new(label + ' skeleton')
        self.rig = bpy.data.objects.new(label + ' rig', arm)
        scene.collection.objects.link(self.rig)
        bpy.context.view_layer.objects.active = self.rig
        self.rig.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        preferred = {0: 31, 31: 32, 32: 33, 33: 2, 2: 1, 37: 38, 38: 39, 39: 40, 56: 57, 57: 58, 58: 59}
        edit = []
        for i, t in enumerate(self.tags):
            bone = arm.edit_bones.new(bone_name(t))
            bone.head = heads[i]
            child = preferred.get(t)
            cand = [j for j, par in enumerate(self.parents) if par == i and (heads[j] - heads[i]).length > .001]
            j = self.tags.index(child) if child in self.tags and self.parents[self.tags.index(child)] == i else (cand[0] if cand else None)
            bone.tail = heads[j] if j is not None else heads[i] + Vector((0, 0, .08))
            if (bone.tail - bone.head).length < .001:
                bone.tail = bone.head + Vector((0, 0, .08))
            if self.parents[i] >= 0:
                bone.parent = edit[self.parents[i]]
            edit.append(bone)
        bpy.ops.object.mode_set(mode='OBJECT')
        self.rest = [arm.bones[bone_name(t)].matrix_local.copy() for t in self.tags]
        for i, t in enumerate(self.tags):
            arm.bones[bone_name(t)]['game_bone_id'] = t
        for pb in self.rig.pose.bones:
            pb.rotation_mode = 'QUATERNION'
        # Mesh and skin weights (bone index = skeleton index).
        mesh = table(p[4])[key]
        at, v, idx = mesh_buffers(mesh, True)
        verts = list(struct.iter_unpack('>11f', v))
        indices = struct.unpack('>' + str(len(idx) // 2) + 'H', idx)
        textures = table(p[0])
        ranges = []
        for pos in range(376, at - 32, 4):
            word = struct.unpack_from('>I', mesh, pos)[0]
            tex = struct.unpack_from('>I', mesh, pos + 28)[0]
            if word & 31 != 2 or tex not in textures:
                continue
            start, count = struct.unpack_from('>HH', mesh, pos + 6)
            if count and start + count <= len(indices) and count % 3 == 0:
                ranges.append((start, count, tex))
        if not ranges:
            tex = next((struct.unpack_from('>I', mesh, pos + 8)[0] for pos in range(396, at - 15, 16)
                        if struct.unpack_from('>I', mesh, pos)[0] == 1 and struct.unpack_from('>I', mesh, pos + 8)[0] in textures),
                       next(iter(textures)))
            ranges = [(0, len(indices), tex)]
        geometry = bpy.data.meshes.new(label + ' model')
        faces, slots, materials = [], [], []
        for i, (start, count, tex) in enumerate(ranges):
            mat = bpy.data.materials.new(f'{label} {tex:08x}')
            mat.use_nodes = True
            node = mat.node_tree.nodes.new('ShaderNodeTexImage')
            node.image = image(textures[tex], f'{label}_{tex:08x}')
            mat.node_tree.links.new(node.outputs['Color'], mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
            materials.append(mat)
            for ind in range(start, start + count, 3):
                f = indices[ind:ind + 3]
                if len(set(f)) == 3:
                    faces.append(f)
                    slots.append(i)
        geometry.from_pydata([Vector((x[0], -x[2], x[1])) for x in verts], [], faces)
        for mat in materials:
            geometry.materials.append(mat)
        uv = geometry.uv_layers.new(name='Native UV')
        for poly, i in zip(geometry.polygons, slots):
            poly.material_index = i
            poly.use_smooth = True
            for loop in poly.loop_indices:
                u, vv = verts[geometry.loops[loop].vertex_index][9:]
                uv.data[loop].uv = (u, 1 - vv)
        self.obj = bpy.data.objects.new(label + ' body', geometry)
        scene.collection.objects.link(self.obj)
        groups = [self.obj.vertex_groups.new(name=bone_name(t)) for t in self.tags]
        assert len(verts) == (len(skin) - 80) // 52
        for i in range(len(verts)):
            o = 80 + 52 * i
            ws, ids = skin[o + 44:o + 48], skin[o + 48:o + 52]
            total = sum(ws)
            for j, w in zip(ids, ws):
                if w:
                    groups[j].add([i], w / total, 'REPLACE')
        self.obj.parent = self.rig
        mod = self.obj.modifiers.new('Native skin', 'ARMATURE')
        mod.object = self.rig
        mod.use_deform_preserve_volume = True
        if any(t == 193 for t in self.tags):  # Cannonbolt's separately skinned ball: hidden in the standing pose
            self.hidden = {193}
        else:
            self.hidden = set()

    # --- clips -----------------------------------------------------------------------------------------------
    def _channel(self, index, kind):
        key = (index, kind)
        if key not in self._keys:
            data = self.channels[index][8:]
            if kind == 'rot':
                self._keys[key] = [(t * 160, Quaternion((w / 127, -x / 32767, -y / 32767, -z / 32767)).normalized())
                                   for x, y, z, w, t in struct.iter_unpack('>3hbB', data)]
            else:
                self._keys[key] = [(t, Vector((x, y, z))) for t, x, y, z in struct.iter_unpack('>4f', data)]
        return self._keys[key]

    @staticmethod
    def _sample(keys, tick, rotation):
        times = [t for t, _ in keys]
        j = bisect.bisect_right(times, tick)
        if j == 0:
            return keys[0][1].copy()
        if j == len(keys):
            return keys[-1][1].copy()
        t0, v0 = keys[j - 1]
        t1, v1 = keys[j]
        u = (tick - t0) / (t1 - t0)
        return v0.slerp(v1, u) if rotation else v0.lerp(v1, u)

    def span(self, clip):
        """(first, last) key time of the clip in ticks (4800 per second), like the game's own time range."""
        ids = bone_ids(clip)
        begin, end = 1e12, -1e12
        for i in range(len(ids)):
            for field, kind in enumerate(('pos', 'rot', 'scale')):
                index = struct.unpack_from('>3I', clip, 216 + 12 * i)[field]
                if index != 0xffffffff:
                    keys = self._channel(index, 'rot' if kind == 'rot' else 'vec')
                    begin, end = min(begin, keys[0][0]), max(end, keys[-1][0])
        return begin, end

    def clip_pose(self, clip, tick, base=None):
        """Per bone (position, rotation, scale) at a tick. A bone the clip does not name keeps the pose of `base` (the
        idle clip, which is what the game shows for it) or, without one, its bind values."""
        ids = bone_ids(clip)
        result = []
        held = self.clip_pose(base, 0) if base is not None else None
        for i, tag in enumerate(self.tags):
            loc, rot, scale = self.bind_local[i].decompose()
            if tag not in ids and held is not None:
                loc, rot, scale = held[i]
            if tag in ids:
                a, b, c = struct.unpack_from('>3I', clip, 216 + 12 * ids.index(tag))
                if a != 0xffffffff:
                    loc = self._sample(self._channel(a, 'vec'), tick, False)
                if b != 0xffffffff:
                    rot = self._sample(self._channel(b, 'rot'), tick, True)
                if c != 0xffffffff:
                    scale = self._sample(self._channel(c, 'vec'), tick, False)
            result.append((Vector(loc), Quaternion(rot), Vector(scale)))
        return result

    def worlds(self, pose):
        out = []
        for i, (loc, rot, scale) in enumerate(pose):
            local = Matrix.LocRotScale(loc, rot, scale)
            out.append(local if self.parents[i] < 0 else out[self.parents[i]] @ local)
        return out

    # --- posing ----------------------------------------------------------------------------------------------
    def set_pose(self, pose, frame):
        worlds = self.worlds(pose)
        target = [C @ worlds[i] @ self.bind[i].inverted() @ CI @ self.rest[i] for i in range(len(self.tags))]
        for i, tag in enumerate(self.tags):
            par = self.parents[i]
            basis = (self.rest[par].inverted() @ self.rest[i]).inverted() @ target[par].inverted() @ target[i] if par >= 0 \
                else self.rest[i].inverted() @ target[i]
            pb = self.rig.pose.bones[bone_name(tag)]
            loc, rot, scale = basis.decompose()
            if tag in self.hidden:
                scale = Vector((0, 0, 0))
            pb.location, pb.rotation_quaternion, pb.scale = loc, rot, scale
            pb.keyframe_insert('location', frame=frame)
            pb.keyframe_insert('rotation_quaternion', frame=frame)
            pb.keyframe_insert('scale', frame=frame)


# Both arms take the source's arm motion; everything else (torso, head, legs, tail, wings, extra bones, fingers) keeps the
# target's own idle pose, so the legs stay planted, an idle that is twisted or hunched in the source is not carried over, and
# the fingers simply ride along with the hand.
ARM_CHAINS = {'L': (56, 57, 58, 59), 'R': (37, 38, 39, 40)}   # clavicle, upper arm, forearm, hand


# Aliens whose torso bones are tilted or turned differently from the source's (a hunched Jetray, Goop's twisted spine):
# their body frame is built from the shoulder line and the vertical instead of from a torso bone.
SHOULDER_FRAME = {'Goop', 'Jetray'}


def shoulder_frame(model, pose):
    """Rotation matrix whose columns are the body's side axis (shoulder to shoulder), up and forward, from the pose."""
    worlds = model.worlds(pose)
    index = {t: i for i, t in enumerate(model.tags)}
    side = worlds[index[57]].translation - worlds[index[38]].translation
    up = Vector((0.0, 1.0, 0.0))
    side = (side - up * side.dot(up)).normalized()
    forward = side.cross(up).normalized()
    return Matrix((side, up, forward)).transposed()


def segment_directions(model, pose, chain, frame=None):
    """World directions of upper arm, forearm and hand (hand -> its fingers), and the torso's world rotation."""
    worlds = model.worlds(pose)
    index = {t: i for i, t in enumerate(model.tags)}
    clav, upper, fore, hand = chain
    pos = lambda t: worlds[index[t]].translation
    out = {upper: (pos(fore) - pos(upper)).normalized(), fore: (pos(hand) - pos(fore)).normalized()}
    kids = [k for k, p in enumerate(model.parents) if p == index[hand]]
    if kids:
        centre = sum((worlds[k].translation for k in kids), Vector((0, 0, 0))) / len(kids)
        if (centre - pos(hand)).length > 1e-6:
            out[hand] = (centre - pos(hand)).normalized()
    torso = frame if frame is not None else worlds[model.parents[index[clav]]].to_3x3().normalized()
    return out, torso


# Aliens whose idle arms are posed so differently from the source's that copying its arm swing sends the hand off to the side
# or up (Goop, Jetray): they replay what Chromastone's hands do, in body coordinates (units of arm length measured from the
# shoulder, with the body frame taken from the shoulder line and the vertical), so both hands end up where Chromastone's
# do, in front of the chest, and move the same way.
REACH_TARGETS = {'Goop', 'Jetray', 'Ultimate Humungousaur', 'Ultimate Cannonbolt', 'Ultimate Big Chill',
                 'Ultimate Swampfire', 'Ultimate Echo Echo', 'Ultimate Spider Monkey'}
REFERENCE = None


class Reference:
    """Chromastone's approved arm motion as elbow, wrist and hand direction in body coordinates, per clip and tick."""

    def __init__(self, reference_path, source_path):
        self.cs = Model(None, 'reference', reference_path, light=True)
        self.src = Model(None, 'reference source', source_path, light=True)
        self.cs_idle, self.src_idle = self.cs.clips['idle_01'], self.src.clips['idle_01']
        self.length = {}
        idle = self.cs.clip_pose(self.cs_idle, 0)
        worlds, index = self.cs.worlds(idle), {t: i for i, t in enumerate(self.cs.tags)}
        for side, (c, u, f, h) in ARM_CHAINS.items():
            self.length[side] = (worlds[index[f]].translation - worlds[index[u]].translation).length + \
                                (worlds[index[h]].translation - worlds[index[f]].translation).length
        self.idle = self.coords(idle)
        self.peak = {side: 1e-6 for side in ARM_CHAINS}
        for name in SEQUENCE:
            clip = self.src.clips[name]
            begin, end = self.src.span(clip)
            for k in range(int(round((end - begin) / 160)) + 1):
                now = self.at(name, min(end, begin + k * 160))
                for side in ARM_CHAINS:
                    self.peak[side] = max(self.peak[side], (now[side][1] - self.idle[side][1]).length)

        # Only the arm that does the pressing moves (Chromastone's other arm hardly moves); the other stays at idle.
        self.active = max(self.peak, key=self.peak.get)

    def coords(self, pose):
        worlds, index = self.cs.worlds(pose), {t: i for i, t in enumerate(self.cs.tags)}
        frame = shoulder_frame(self.cs, pose).transposed()
        out = {}
        for side, (clav, upper, fore, hand) in ARM_CHAINS.items():
            S, E, W = (worlds[index[t]].translation for t in (upper, fore, hand))
            kids = [k for k, p in enumerate(self.cs.parents) if p == index[hand]]
            tip = sum((worlds[k].translation for k in kids), Vector((0, 0, 0))) / len(kids) if kids else W + (W - E)
            direction = (tip - W).normalized() if (tip - W).length > 1e-6 else (W - E).normalized()
            L = self.length[side]
            out[side] = (frame @ (E - S) / L, frame @ (W - S) / L, frame @ direction)
        return out

    def at(self, clip_name, tick):
        src_clip = self.src.clips[clip_name]
        return self.coords(retarget(self.src, self.src_idle, self.cs, self.cs_idle, src_clip, tick))


def reach_pose(tgt, tgt_idle, reference, clip_name, tick):
    """The target's pose with each arm moved the way Chromastone's arm is moved at this clip and tick."""
    t_idle = tgt.clip_pose(tgt_idle, 0)
    index = {t: i for i, t in enumerate(tgt.tags)}
    worlds = tgt.worlds(t_idle)
    frame = shoulder_frame(tgt, t_idle)
    idle_dirs = {}
    wanted = {}
    now = reference.at(clip_name, tick)
    for side, chain in ARM_CHAINS.items():
        clav, upper, fore, hand = chain
        if side != reference.active or any(t not in index for t in chain):
            continue
        dirs, _ = segment_directions(tgt, t_idle, chain, frame)
        idle_dirs.update(dirs)
        S, E0, W0 = (worlds[index[t]].translation for t in (upper, fore, hand))
        a, b = (E0 - S).length, (W0 - E0).length
        L = a + b
        # How far this arm has moved from its idle, 0..1, by Chromastone's wrist; 0 is exactly the target's own idle pose.
        w = min(1.0, (now[side][1] - reference.idle[side][1]).length / reference.peak[side])
        e_idle, w_idle = frame.transposed() @ (E0 - S) / L, frame.transposed() @ (W0 - S) / L
        e_c, w_c, h_c = now[side]
        wrist = S + frame @ (w_idle.lerp(w_c, w) * L)
        elbow_hint = frame @ (e_idle.lerp(e_c, w) * L)
        reach = wrist - S
        d = max(1e-4, min(reach.length, a + b - 1e-4))
        axis = reach.normalized()
        x = (a * a - b * b + d * d) / (2 * d)
        h = math.sqrt(max(a * a - x * x, 0.0))
        pole = elbow_hint - axis * elbow_hint.dot(axis)
        normal = pole.normalized() if pole.length > 1e-6 else (-frame.col[1]).normalized()
        elbow = S + axis * x + normal * h
        wanted[upper] = (elbow - S).normalized()
        wanted[fore] = (wrist - elbow).normalized()
        if hand in dirs:
            wanted[hand] = dirs[hand].lerp(frame @ h_c, w).normalized()
    idle_world = []
    for i, (_, rot, _) in enumerate(t_idle):
        m = rot.to_matrix()
        idle_world.append(m if tgt.parents[i] < 0 else idle_world[tgt.parents[i]] @ m)
    result = [list(item) for item in t_idle]
    new_world = []
    for i, tag in enumerate(tgt.tags):
        parent_world = new_world[tgt.parents[i]] if tgt.parents[i] >= 0 else Matrix.Identity(3)
        before = parent_world @ t_idle[i][1].to_matrix()
        if tag in wanted:
            current = before @ (idle_world[i].inverted() @ idle_dirs[tag])
            after = current.rotation_difference(wanted[tag]).to_matrix() @ before
            result[i][1] = (parent_world.inverted() @ after).to_quaternion()
            new_world.append(after)
        else:
            new_world.append(before)
    return [tuple(item) for item in result]


def retarget(src, src_idle, tgt, tgt_idle, src_clip, tick, shoulders=False):
    """The target's pose when the source plays src_clip at tick (see the module note).

    Each arm segment is moved by the same swing the source's segment makes, measured in the torso's own frame, from the
    target's own idle direction. So the arm reaches, presses and returns the way the source's does (shoulder to elbow, elbow
    to wrist, wrist to fingers), whatever the two rigs' bone axes are, and at idle it is exactly the target's idle pose."""
    s_cur = src.clip_pose(src_clip, tick, base=src_idle)
    s_idle = src.clip_pose(src_idle, 0)
    t_idle = tgt.clip_pose(tgt_idle, 0)
    index = {t: i for i, t in enumerate(tgt.tags)}
    idle_world = []
    for i, (_, rot, _) in enumerate(t_idle):
        m = rot.to_matrix()
        idle_world.append(m if tgt.parents[i] < 0 else idle_world[tgt.parents[i]] @ m)
    result = [list(item) for item in t_idle]
    for chain in ARM_CHAINS.values():
        if any(t not in index or t not in src.tags for t in chain):
            continue
        frames = (shoulder_frame(src, s_idle), shoulder_frame(src, s_cur), shoulder_frame(tgt, t_idle)) if shoulders \
            else (None, None, None)
        s_idle_dir, s_idle_torso = segment_directions(src, s_idle, chain, frames[0])
        s_cur_dir, s_cur_torso = segment_directions(src, s_cur, chain, frames[1])
        t_idle_dir, t_torso = segment_directions(tgt, t_idle, chain, frames[2])
        parent_world = idle_world[index[chain[0]]]
        for tag in chain[1:]:
            i = index[tag]
            if tag not in t_idle_dir or tag not in s_idle_dir:
                parent_world = parent_world @ result[i][1].to_matrix()
                continue
            swing = (s_idle_torso.inverted() @ s_idle_dir[tag]).rotation_difference(
                s_cur_torso.inverted() @ s_cur_dir[tag]).to_matrix()
            desired = t_torso @ swing @ t_torso.inverted() @ t_idle_dir[tag]
            before = parent_world @ t_idle[i][1].to_matrix()
            current = before @ (idle_world[i].inverted() @ t_idle_dir[tag])
            after = current.rotation_difference(desired).to_matrix() @ before
            result[i][1] = (parent_world.inverted() @ after).to_quaternion()
            parent_world = after
    return [tuple(item) for item in result]


def reference():
    global REFERENCE
    if REFERENCE is None:
        REFERENCE = Reference(VILGAX / 'chromastone/g_cs.xbx', GAME / 'g_wh.xbx')
    return REFERENCE


def build(only=None):
    """Add one source/target pair per alien in PLAN (all of them, or just the named one) to the open scene."""
    scene = bpy.context.scene
    scene.render.fps = 30
    report = {}
    all_ranges = [scene.frame_end]
    for slot, (name, tgt_path, src_name, src_path) in enumerate(PLAN):
        if only and name != only:
            continue
        cursor_x, cursor_y = 3.2 * (slot if slot < 4 else slot - 4), (0 if slot < 4 else 4.5)
        src = Model(scene, src_name + ' (original)', src_path)
        tgt = Model(scene, name + ' (new interact)', tgt_path, skeleton_from=IDLE_FROM.get(name))
        src_idle = src.clips['idle_01']
        tgt_idle = tgt.clips['idle_01']
        # Timeline: hold idle (frames 1-10), then in -> interact -> out, then hold idle.
        for frame in (1, 10):
            src.set_pose(src.clip_pose(src_idle, 0), frame)
            tgt.set_pose(tgt.clip_pose(tgt_idle, 0), frame)
        frame = 11
        info = []
        for clip_name in SEQUENCE:
            clip = src.clips[clip_name]
            begin, end = src.span(clip)
            steps = max(1, int(round((end - begin) / 160)))
            for k in range(steps + 1):
                if k == 0 and info:
                    continue
                tick = min(end, begin + k * 160)
                src.set_pose(src.clip_pose(clip, tick, base=src_idle), frame)
                if name in REACH_TARGETS:
                    tgt.set_pose(reach_pose(tgt, tgt_idle, reference(), clip_name, tick), frame)
                else:
                    tgt.set_pose(retarget(src, src_idle, tgt, tgt_idle, clip, tick, shoulders=name in SHOULDER_FRAME), frame)
                frame += 1
            info.append((clip_name, round((end - begin) / 4800.0, 3)))
        end = frame + 10
        for model, pose in ((src, src.clip_pose(src_idle, 0)), (tgt, tgt.clip_pose(tgt_idle, 0))):
            model.set_pose(pose, end)
        all_ranges.append(end)
        # Only the Alien Force alien stays in the scene; the source's motion is already keyed on it.
        for obj in (src.obj, src.rig):
            bpy.data.objects.remove(obj, do_unlink=True)
        tgt.rig.location = (cursor_x, cursor_y, 0)
        tgt.rig.name, tgt.obj.name = f'{name} rig', name
        report[name] = {'source': src_name, 'clips_seconds': info}
    scene.frame_start, scene.frame_end = 1, max(all_ranges)
    return report


def export(out_path):
    """Write every PLAN alien's three interact clips as game-space local poses (position, quaternion w x y z, scale per skeleton
    bone, one row per 160-tick key) for tools/interact/install_interact_clips.py. Same retarget as build(); no scene needed."""
    import json
    data = {}
    for name, tgt_path, src_name, src_path in PLAN:
        src = Model(None, src_name, src_path, light=True)
        tgt = Model(None, name, tgt_path, light=True, skeleton_from=IDLE_FROM.get(name))
        src_idle, tgt_idle = src.clips['idle_01'], tgt.clips['idle_01']
        clips = {}
        for clip_name in SEQUENCE:
            clip = src.clips[clip_name]
            begin, end = src.span(clip)
            frames = []
            for k in range(int(round((end - begin) / 160)) + 1):
                tick = min(end, begin + k * 160)
                if name in REACH_TARGETS:
                    pose = reach_pose(tgt, tgt_idle, reference(), clip_name, tick)
                else:
                    pose = retarget(src, src_idle, tgt, tgt_idle, clip, tick, shoulders=name in SHOULDER_FRAME)
                frames.append([[*loc, rot.w, rot.x, rot.y, rot.z, *scale] for loc, rot, scale in pose])
            clips[clip_name] = {'seconds': (end - begin) / 4800.0, 'frames': frames}
        data[name] = {'tags': tgt.tags, 'clips': clips}
    Path(out_path).write_text(json.dumps(data))
    return {name: {c: len(v['frames']) for c, v in form['clips'].items()} for name, form in data.items()}


if os.environ.get('COSMIC_INTERACT_RUN'):
    print(build(os.environ.get('COSMIC_INTERACT_ONLY') or None))
