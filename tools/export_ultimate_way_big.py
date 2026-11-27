"""Export the approved Way Big static mesh with the native Final Battle skeleton weights."""
from pathlib import Path
import math
import os
import struct

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = Path.cwd()
OUTPUT = Path(os.environ.get('BEN10_WAY_BIG_EXPORT_DIR', ROOT / 'build' / 'ultimate-way-big'))
OUTPUT.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
source_objects = [obj for obj in scene.objects if obj.type == 'MESH' and not obj.hide_render
                  and not obj.name.startswith(('Upper mouth', 'Lower lip'))]
original_objects = set(source_objects)
rib_materials = {}
gill_blue = (.008, .022, .051)
# Pixel coordinates measured from the top of the Xbox atlas.
gill_chart = (128, 192, 256)
gill_y = (-.115, .300)
gill_z = (1.440, 1.720)
head_blue_materials = {material.name for material in scene.objects['Head blue mask'].data.materials}
collar_materials = head_blue_materials | {material.name for material in scene.objects['Red suit patterns'].data.materials}
face_materials = {material.name for name in ('Head white and center fin', 'Head red accents')
                  for material in scene.objects[name].data.materials}
detail_group_name = 'Face, collar and suit outlines'


def underarm_region(point):
    return .13 < abs(point.x) < .42 and 1.60 < point.z < 1.84


def chest_panel_region(point):
    return abs(point.x) < .22 and 1.60 < point.z < 1.815 and point.y < .035


def front_collar_region(point):
    return abs(point.x) < .113 and 1.800 < point.z < 1.899 and point.y < .087

# Use the approved gill markings without the raised lighting normals from
# the sculpted cuts. The markings follow the chest through the QTE.
for name in ('Body blue', 'Body white'):
    crease = scene.objects[name].data.shape_keys.key_blocks.get('Native rib crease')
    if crease is None:
        raise ValueError(f'{name}: missing approved rib crease')
    crease.value = 0.0


def bake_gills():
    """Project the approved dense rib shading onto a continuous side chart."""
    import numpy as np
    body = scene.objects['Body blue']
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = body.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    positions = [body.matrix_world @ vertex.co for vertex in mesh.vertices]
    marks = [entry.value for entry in mesh.attributes['Rib recess shading'].data]
    mesh.calc_loop_triangles()
    faces = [tuple(triangle.vertices) for triangle in mesh.loop_triangles
             if all(0 < positions[i].x < .265 for i in triangle.vertices)]
    surface = BVHTree.FromPolygons(positions, faces, all_triangles=True)
    size = gill_chart[2]
    mask = np.zeros((size, size), dtype=np.float32)
    for row, z in enumerate(np.linspace(*reversed(gill_z), size)):
        for col, y in enumerate(np.linspace(*gill_y, size)):
            point, _, face, _ = surface.ray_cast(Vector((.27, y, z)), Vector((-1, 0, 0)), .27)
            if face is None:
                continue
            a, b, c = faces[face]
            if not (marks[a] or marks[b] or marks[c]):
                continue
            # The ray already fixes y and z, so interpolate in the chart.
            first, second = positions[b]-positions[a], positions[c]-positions[a]
            offset = point-positions[a]
            det = first.y*second.z - first.z*second.y
            if abs(det) < 1e-12:
                continue
            u = (offset.y*second.z - offset.z*second.y) / det
            v = (first.y*offset.z - first.z*offset.y) / det
            mask[row, col] = min(1, max(0, (marks[a]*(1-u-v)+marks[b]*u+marks[c]*v)*1.35))
    evaluated.to_mesh_clear()
    # A small texel filter smooths the projection at dense source triangle edges.
    kernel = np.array((1, 4, 6, 4, 1), dtype=np.float32) / 16
    for axis in (0, 1):
        mask = np.apply_along_axis(np.convolve, axis, mask, kernel, 'same')
    if np.count_nonzero(mask > .5) < 100 or any(np.any(edge) for edge in
                                               (mask[0], mask[-1], mask[:, 0], mask[:, -1])):
        raise ValueError('The projected gill markings must fit inside their padded chart')
    return mask


gill_mask = bake_gills()


def stitch_material_seam(mesh, world, label, in_region, tolerance, slots=None):
    """Join near-coincident paint borders with different edge subdivisions."""
    edges = [edge for edge in mesh.edges if edge.is_boundary and
             (slots is None or edge.link_faces[0].material_index in slots) and
             all(in_region(world @ vertex.co) for vertex in edge.verts)]
    ends = [tuple(edge.verts) for edge in edges]
    samples = []
    for i, (first, last) in enumerate(ends):
        steps = max(1, math.ceil((world.to_3x3() @ (last.co-first.co)).length / tolerance))
        samples.extend((world @ first.co.lerp(last.co, j / steps), i) for j in range(steps + 1))
    tree = KDTree(len(samples))
    for i, (point, _) in enumerate(samples):
        tree.insert(point, i)
    tree.balance()
    materials = [edge.link_faces[0].material_index for edge in edges]
    incident = {}
    for i, ends_of_edge in enumerate(ends):
        for vertex in ends_of_edge:
            incident.setdefault(vertex, set()).add(materials[i])

    matches = {}
    for vertex, source_materials in incident.items():
        point = world @ vertex.co
        candidates = {samples[sample][1] for _, sample, _ in tree.find_range(point, tolerance*1.2)}
        nearest = tolerance
        for i in sorted(candidates):
            if materials[i] in source_materials:
                continue
            first, last = (world @ end.co for end in ends[i])
            direction = last - first
            if not direction.length_squared:
                continue
            t = min(1.0, max(0.0, (point-first).dot(direction) / direction.length_squared))
            distance = (point-first-t*direction).length
            if distance < nearest:
                matches[vertex] = i, t
                nearest = distance

    splits = {}
    weld = {}
    for vertex, (i, t) in matches.items():
        # Use an endpoint only if it also points back to this vertex's rim.
        endpoint = ends[i][round(t)]
        reverse = matches.get(endpoint)
        if (reverse is not None and ends[reverse[0]][round(reverse[1])] == vertex and
                (world.to_3x3() @ (endpoint.co - vertex.co)).length < tolerance*.5):
            if endpoint not in weld:
                weld[vertex] = endpoint
        elif 0 < t < 1:
            splits.setdefault(i, []).append((t, vertex))
    for i, locations in splits.items():
        edge = edges[i]
        start, last = ends[i]
        previous = 0.0
        for t, original in sorted(locations, key=lambda location: location[0]):
            if t - previous < 1e-6:
                continue
            _, inserted = bmesh.utils.edge_split(edge, start, (t-previous)/(1-previous))
            weld[inserted] = original
            start = inserted
            edge = next(link for link in start.link_edges if last in link.verts)
            previous = t
    # An inserted vertex may meet an endpoint that already has a weld target.
    for vertex, target in weld.items():
        while target in weld:
            target = weld[target]
        weld[vertex] = target
    bmesh.ops.weld_verts(mesh, targetmap=weld)
    remaining = sum(edge.is_boundary and all(in_region(world @ v.co) for v in edge.verts)
                    for edge in mesh.edges)
    print(f'{label}: {len(edges)} open edges before stitching, {remaining} after', flush=True)


def close_underarm_junctions(mesh, world):
    # Three colors meet here. Seal the small junction loops left after the
    # longer two-color edges have been stitched.
    def at_junction(vertex):
        p = world @ vertex.co
        return .265 < abs(p.x) < .286 and .010 < p.y < .026 and 1.685 < p.z < 1.716

    rim = [edge for edge in mesh.edges if edge.is_boundary and all(map(at_junction, edge.verts))]
    materials = {edge: edge.link_faces[0].material_index for edge in rim}
    faces = bmesh.ops.holes_fill(mesh, edges=rim, sides=8)['faces']
    for face in faces:
        border = max(face.edges, key=lambda edge: edge.calc_length())
        face.material_index = materials[border]
        face.smooth = True
    print(f'Underarm color junctions: closed {len(faces)} small openings', flush=True)


def weld_for_export(names, label):
    """Keep shared geometry connected while preserving its face materials."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    parts = [scene.objects[name] for name in names]
    bpy.ops.object.select_all(action='DESELECT')
    copies = []
    for part in parts:
        mesh = bpy.data.meshes.new_from_object(part.evaluated_get(depsgraph),
                                               preserve_all_data_layers=True, depsgraph=depsgraph)
        if mesh.attributes.get('Rib recess shading') is not None:
            for index, material in enumerate(mesh.materials):
                if material not in rib_materials:
                    rib_materials[material] = material.copy()
                mesh.materials[index] = rib_materials[material]
        obj = bpy.data.objects.new(part.name + ' | export', mesh)
        scene.collection.objects.link(obj)
        obj.matrix_world = part.matrix_world.copy()
        obj.select_set(True)
        copies.append(obj)
    obj = copies[0]
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join()
    obj.name = label
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    before = len(mesh.verts)
    bmesh.ops.remove_doubles(mesh, verts=list(mesh.verts), dist=0.000025)
    # The nape and collar are almost coincident in the approved model.
    # Close that seam before decimation so both sides share the same weights.
    collar = []
    for vert in mesh.verts:
        if vert.is_boundary:
            point = obj.matrix_world @ vert.co
            if 1.80 < point.z < 1.915 and abs(point.x) < .13:
                collar.append(vert)
    before_collar = len(mesh.verts)
    bmesh.ops.remove_doubles(mesh, verts=collar, dist=0.00035)
    collar_welds = before_collar - len(mesh.verts)
    if collar_welds <= 0:
        raise ValueError('Expected shared nape and collar boundary vertices')
    print(f'Collar seam: welded {collar_welds} boundary vertices', flush=True)
    welded = before - len(mesh.verts)
    if welded <= 0:
        raise ValueError(f'{label}: expected shared boundary vertices')
    world = obj.matrix_world
    # The chin material rims overlap in the source. Stitching them can
    # fold their surfaces across each other. Keep the rigid chin weights.
    stitch_material_seam(mesh, world, 'Underarms', underarm_region, .0022)
    stitch_material_seam(mesh, world, 'Front chest', chest_panel_region, .00065)
    close_underarm_junctions(mesh, world)
    mesh.verts.index_update()
    head_border = set()
    jaw_collar_border = set()
    suit_border = set()
    collar_interior = []
    for vert in mesh.verts:
        point = world @ vert.co
        if (vert.is_manifold and 1.825 < point.z < 1.935 and abs(point.x) < .115 and
                len({face.material_index for face in vert.link_faces}) == 1):
            collar_interior.append(vert)
    bmesh.ops.smooth_vert(mesh, verts=collar_interior, factor=.22,
                         use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for edge in mesh.edges:
        materials = {obj.data.materials[face.material_index].name for face in edge.link_faces}
        if len(materials) > 1:
            for vert in edge.verts:
                point = world @ vert.co
                if 1.80 < point.z < 2.025 and abs(point.x) < .14:
                    jaw_collar_border.add(vert.index)
                if underarm_region(point) or chest_panel_region(point):
                    suit_border.add(vert.index)
        if materials & head_blue_materials and materials - head_blue_materials:
            for vert in edge.verts:
                if (world @ vert.co).z > 1.91:
                    head_border.add(vert.index)
    mesh.to_mesh(obj.data)
    mesh.free()
    if not head_border or not jaw_collar_border:
        raise ValueError('Expected shared head, jaw and collar borders')
    border_group = obj.vertex_groups.new(name=detail_group_name)
    border_group.add(sorted(head_border | jaw_collar_border | suit_border), 1.0, 'REPLACE')
    print(f'Preserved {len(head_border)} blue outline and {len(jaw_collar_border)} jaw/collar vertices',
          flush=True)
    if 'Body blue' in names and obj.data.attributes.get('Rib recess shading') is None:
        raise ValueError('Welded body lost the approved rib shading')
    print(f'{label}: welded {welded} vertices before simplification', flush=True)
    for part in parts:
        source_objects.remove(part)
    source_objects.append(obj)


weld_for_export(('Body white', 'Body white detail', 'Red suit patterns', 'Body blue',
                 'Body dark accents', 'Head white and center fin', 'Head blue mask',
                 'Head red accents'), 'Welded Way Big body')
rib_export_materials = {material.name for material in rib_materials.values()}
donor_library = Path(os.environ.get('BEN10_WAY_BIG_DONOR_BLEND', ROOT / 'build' / 'blender' / 'Way-Big-Native-Rig.blend'))
with bpy.data.libraries.load(str(donor_library)) as (source, imported):
    imported.objects = ['Way Big | Original size']
donor, = imported.objects
donor_faces = [tuple(p.vertices) for p in donor.data.polygons if p.material_index == 0]
donor_points = [v.co.copy() for v in donor.data.vertices]
tree = BVHTree.FromPolygons(donor_points, donor_faces, all_triangles=True)
donor_weights = [
    {int(donor.vertex_groups[g.group].name.split()[0]): g.weight for g in v.groups}
    for v in donor.data.vertices
]

def blend_range(value, low, high):
    t = min(1.0, max(0.0, (value-low)/(high-low)))
    return t*t*(3-2*t)


def skin(point, rigid, rib_strength):
    if rigid is not None:
        return bytes((255,0,0,0,rigid,0,0,0))
    hit, _, index, _ = tree.find_nearest(point)
    a, b, c = donor_faces[index]
    first, second = donor_points[b]-donor_points[a], donor_points[c]-donor_points[a]
    offset = hit - donor_points[a]
    aa, ab, bb = first.dot(first), first.dot(second), second.dot(second)
    det = aa*bb - ab*ab
    t = (bb*offset.dot(first) - ab*offset.dot(second))/det if det>1e-16 else 0
    u = (aa*offset.dot(second) - ab*offset.dot(first))/det if det>1e-16 else 0
    result = {}
    for vertex, fraction in ((a, 1-t-u), (b,t), (c,u)):
        for bone, weight in donor_weights[vertex].items():
            result[bone] = result.get(bone,0) + max(0,fraction)*weight
    # The custom chin is part of the solid face mask. Keep it with the
    # head through the jaw animation and blend the attachment into the neck.
    head = blend_range(point.z, 1.915, 1.950) * (1 - blend_range(point.y, .06, .085))
    if head:
        coverage = sum(result.values())
        result = {bone: weight*(1-head) for bone, weight in result.items()}
        result[5] = result.get(5, 0) + coverage*head
    # The added gill relief belongs to the torso. Keep its ends from
    # following the shoulder bones into the wide-arm QTE pose.
    x = abs(point.x)
    torso = (blend_range(x, .06, .09) * (1-blend_range(x, .27, .31)) *
             blend_range(point.z, 1.47, 1.50) * (1-blend_range(point.z, 1.67, 1.72)) *
             blend_range(point.y, -.10, -.07) * (1-blend_range(point.y, .25, .28)))
    stabilization = max(torso, min(1.0, 5*rib_strength))
    if stabilization:
        for shoulder in (20, 33):
            removed = result.get(shoulder, 0)*stabilization
            result[shoulder] = result.get(shoulder, 0) - removed
            result[3] = result.get(3, 0) + removed
    top = sorted(((k,w) for k,w in result.items() if w>0),key=lambda item:item[1],reverse=True)[:4]
    total = sum(w for _,w in top)
    quant = [255*w/total for _,w in top]
    ints = [int(w) for w in quant]
    for i in sorted(range(len(quant)),key=lambda i: quant[i]-ints[i],reverse=True)[:255-sum(ints)]:
        ints[i]+=1
    return bytes(ints).ljust(4,b'\0') + bytes(k for k,_ in top).ljust(4,b'\0')

def game(vector):
    return vector.x,vector.z,-vector.y

palette = []
eye_swatches = set()
gill_swatches = set()
def swatch(material, mark):
    rgb = tuple(material.diffuse_color[:3])
    if mark:
        rgb = (.34,.626,1.0)
    red = rgb
    eye = 'chartreuse eyes' in material.name.lower()
    if 'hourglass' in material.name.lower() or eye:
        red = (.83,.009,.027)
    key = rgb, red, mark
    if key not in palette:
        palette.append(key)
    index = palette.index(key)
    if eye:
        eye_swatches.add(index)
    if mark:
        gill_swatches.add(index)
    return index

rows, weights, indices, eye_indices = [], [], [], []
for obj in source_objects:
    count=len(obj.data.polygons)
    if count>1500:
        mod=obj.modifiers.new('Game triangle budget','DECIMATE')
        if obj.vertex_groups.get(detail_group_name) is not None:
            mod.vertex_group=detail_group_name
            mod.invert_vertex_group=True
        mod.ratio=max(350,int(count*.042))/count

def smooth_collar_outline(mesh, world, slots):
    # Smooth along the shared painted rim so tiny differences between the
    # former pieces do not leave a sawtooth edge. Keep junctions in place.
    neighbors = {}
    for edge in mesh.edges:
        materials = {face.material_index for face in edge.link_faces}
        if len(edge.link_faces) != 2 or len(materials) != 2 or not materials <= slots:
            continue
        a, b = edge.verts
        if front_collar_region(world @ a.co) and front_collar_region(world @ b.co):
            neighbors.setdefault(a, []).append(b)
            neighbors.setdefault(b, []).append(a)
    for _ in range(4):
        updates = {}
        for vertex, adjacent in neighbors.items():
            if len(adjacent) != 2:
                continue
            a, b = (v.co for v in adjacent)
            direction = b - a
            if not direction.length_squared:
                continue
            t = (vertex.co-a).dot(direction) / direction.length_squared
            if 0 < t < 1:
                updates[vertex] = vertex.co.lerp(a+t*direction, .50)
        for vertex, point in updates.items():
            vertex.co = point


def finish_body(mesh, world):
    """Close the collar and fit the mouth to the simplified model."""
    mouth_material = bpy.data.materials.new('Way Big | mouth seam')
    mouth_material.diffuse_color = (.025, .033, .048, 1)
    mesh.materials.append(mouth_material)
    model = bmesh.new()
    model.from_mesh(mesh)
    slots = {i for i, material in enumerate(mesh.materials) if material.name in collar_materials}
    # The two paint pieces simplify to different rim subdivisions. Join the
    # final edges so both colors follow the same deformation at the collar.
    stitch_material_seam(model, world, 'Front collar',
                         front_collar_region, .0022, slots)
    smooth_collar_outline(model, world, slots)
    seeds = []
    for vertex in model.verts:
        if vertex.is_boundary:
            point = world @ vertex.co
            if abs(point.x) < .025 and 1.966 < point.z < 1.985 and point.y < -.050:
                seeds.append(vertex)
    if not seeds:
        raise ValueError('Expected a mouth boundary in the simplified face')
    rim = set()
    vertices = set()
    pending = [seeds[0]]
    while pending:
        vertex = pending.pop()
        if vertex in vertices:
            continue
        vertices.add(vertex)
        edges = [edge for edge in vertex.link_edges if edge.is_boundary]
        rim.update(edges)
        pending.extend(edge.other_vert(vertex) for edge in edges)
    points = [world @ vertex.co for vertex in vertices]
    if (len(rim) < 8 or len(rim) != len(vertices) or not set(seeds) <= vertices or
            not all(abs(p.x) < .037 and 1.962 < p.z < 1.992 and p.y < -.045 for p in points)):
        raise ValueError('Expected a closed mouth rim in the simplified face')
    filled = bmesh.ops.holes_fill(model, edges=list(rim), sides=0)['faces']
    if len(filled) != 1 or any(edge.is_boundary for edge in rim):
        raise ValueError('The mouth rim did not close')
    filled[0].material_index = len(mesh.materials) - 1
    filled[0].smooth = True
    model.to_mesh(mesh)
    model.free()
    print(f'Mouth: closed the {len(rim)}-edge face opening', flush=True)


def smooth_panel_normals(mesh, positions, normal_matrix):
    """Share shading across the painted panels of the face and upper suit."""
    vertex_normals = [(normal_matrix @ entry.vector).normalized() for entry in mesh.vertex_normals]
    surface_area = [0.0] * len(positions)
    for polygon in mesh.polygons:
        for index in polygon.vertices:
            surface_area[index] += polygon.area
    tree = KDTree(len(positions))
    for index, point in enumerate(positions):
        tree.insert(point, index)
    tree.balance()
    result = {}
    for index, point in enumerate(positions):
        on_face = abs(point.x) < .12 and 1.918 < point.z < 2.135 and point.y < .065
        on_collar = abs(point.x) < .125 and 1.82 < point.z < 1.945
        if not (on_face or on_collar or underarm_region(point) or chest_panel_region(point)):
            continue
        radius = .010 if on_face else .022
        seed = vertex_normals[index]
        total = Vector()
        for _, neighbor, distance in tree.find_range(point, radius):
            normal = vertex_normals[neighbor]
            if seed.dot(normal) >= .60:
                falloff = (1 - distance / radius)**2
                total += normal * (falloff * math.sqrt(surface_area[neighbor]))
        if total.length_squared:
            result[index] = total.normalized()
    return result


def rear_neck_normals(mesh, positions, panel_normals, normal_matrix):
    """Transfer the dense nape's shading across the simplified helmet seam."""
    source = scene.objects['Head blue mask']
    world = source.matrix_world
    normal_transform = world.to_3x3().inverted().transposed()
    samples = []
    for vertex in source.data.vertices:
        point = world @ vertex.co
        normal = (normal_transform @ vertex.normal).normalized()
        if 1.87 < point.z < 2.072 and point.y > .075 and normal.y > .15:
            samples.append((point, normal))
    tree = KDTree(len(samples))
    for index, (point, _) in enumerate(samples):
        tree.insert(point, index)
    tree.balance()

    neck = {i for polygon in mesh.polygons
            if mesh.materials[polygon.material_index].name in head_blue_materials
            for i in polygon.vertices}
    result = {}
    for i in neck:
        point = positions[i]
        coverage = (blend_range(point.y, .080, .125)
                    * blend_range(point.z, 1.885, 1.935)
                    * (1-blend_range(point.z, 2.064, 2.080)))
        if not coverage:
            continue
        normal = Vector()
        for _, neighbor, distance in tree.find_n(point, 8):
            normal += samples[neighbor][1] / (distance + .004)**2
        original = panel_normals.get(i)
        if original is None:
            original = (normal_matrix @ mesh.vertex_normals[i].vector).normalized()
        result[i] = original.lerp(normal.normalized(), coverage).normalized()
    return result


for obj in source_objects:
    deps=bpy.context.evaluated_depsgraph_get()
    eval_obj=obj.evaluated_get(deps)
    mesh=eval_obj.to_mesh(preserve_all_data_layers=True, depsgraph=deps)
    if obj.name == 'Welded Way Big body':
        finish_body(mesh, obj.matrix_world)
    mesh.calc_loop_triangles()
    matrix=obj.matrix_world
    normal_matrix=matrix.to_3x3().inverted().transposed()
    if 'trim' in obj.name.lower() or obj.name.startswith(('Omnitrix |','Ultimatrix |')):
        rigid=3
    elif 'fin' in obj.name.lower() and 'head' in obj.name.lower() or obj.name.startswith(('Green eyes','Face dark','Head ')):
        rigid=5
    else:
        rigid=None
    mark=mesh.attributes.get('Rib recess shading')
    if obj.name == 'Welded Way Big body' and mark is None:
        raise ValueError('Simplified body lost the approved rib shading')
    positions=[matrix@v.co for v in mesh.vertices]
    panel_normals = {}
    nape_normals = {}
    if obj.name == 'Welded Way Big body':
        panel_normals = smooth_panel_normals(mesh, positions, normal_matrix)
        nape_normals = rear_neck_normals(mesh, positions, panel_normals, normal_matrix)
    # The lower mask extends into the stock jaw's weight region. Its painted
    # faces and their shared outline must move as one with the upper mask.
    face = {index for polygon in mesh.polygons
            if mesh.materials[polygon.material_index].name in face_materials
            for index in polygon.vertices if positions[index].z > 1.920}
    packed=[skin(point, 5 if i in face else rigid, mark.data[i].value if mark is not None else 0)
            for i,point in enumerate(positions)]
    remap={}
    for tri in mesh.loop_triangles:
        material=mesh.materials[tri.material_index]
        rib = mark is not None and (obj in original_objects or material.name in rib_export_materials)
        column=swatch(material, rib)
        eyes = column in eye_swatches
        target = eye_indices if eyes else indices
        chart = rib and all(abs(positions[i].x) < .265 and 1.41 < positions[i].z < 1.75
                            for i in tri.vertices)
        for loop_id in tri.loops:
            loop=mesh.loops[loop_id]
            i=loop.vertex_index
            normal = panel_normals.get(i)
            if material.name in head_blue_materials:
                normal = nape_normals.get(i, normal)
            if normal is None:
                normal = (normal_matrix @ mesh.corner_normals[loop_id].vector).normalized()
            k=(i,column,chart,*(round(v,4) for v in normal))
            if k not in remap:
                remap[k]=len(rows)
                position=positions[i]
                tangent=normal.orthogonal().normalized()
                u=((column%8)*64+31.5)/512
                v=((column//8)*64+15)/512
                if chart:
                    left, top, size = gill_chart
                    horizontal = min(1, max(0, (position.y-gill_y[0])/(gill_y[1]-gill_y[0])))
                    vertical = min(1, max(0, (gill_z[1]-position.z)/(gill_z[1]-gill_z[0])))
                    u = (left + .5 + horizontal*(size-1))/512
                    v = (top + .5 + vertical*(size-1))/512
                raw=struct.pack('>11f',*game(position),*game(normal),*game(tangent),u,v)
                rows.append(raw)
                weights.append(raw+packed[i])
            target.append(remap[k])
    print(obj.name,count,len(mesh.loop_triangles),flush=True)
    eval_obj.to_mesh_clear()
indices.extend(eye_indices)
assert len(rows)<65536 and len(indices)<65536 and len(palette)<=16, (len(rows),len(indices),len(palette))
if len(eye_swatches) != 1 or len(gill_swatches) != 1:
    raise ValueError('Expected one eye-color swatch and one gill swatch')
if not eye_indices:
    raise ValueError('Expected a separate draw range for the glowing eyes')
(OUTPUT/'eye-swatch.txt').write_text(f'{next(iter(eye_swatches))}\n', encoding='ascii')
(OUTPUT/'eye-index-count.txt').write_text(f'{len(eye_indices)}\n', encoding='ascii')
(OUTPUT/'mesh-export.bin').write_bytes(struct.pack('>II',len(rows),len(indices))+b''.join(rows)+b''.join(weights)+struct.pack(f'>{len(indices)}H',*indices))
import numpy as np


def write_atlas(name, pixels):
    image = bpy.data.images.new(name, 512, 512, alpha=True)
    image.pixels.foreach_set(pixels.ravel())
    image.filepath_raw = str(OUTPUT/f'{name}.png')
    image.file_format = 'PNG'
    image.save()


left, top, size = gill_chart
region = np.s_[512-top-size:512-top, left:left+size]
mask = gill_mask[::-1, :, None]
paint = palette[next(iter(gill_swatches))][0]
specular = np.zeros((512,512,4), dtype=np.float32)
specular[:,:,3] = 1
specular[region][:,:,:3] = mask
write_atlas('gill-mask', specular)
for mode,name in enumerate(('ben','albedo')):
    pixels=np.zeros((512,512,4),dtype=np.float32)
    pixels[:,:,3]=1
    for i,entry in enumerate(palette):
        x=(i%8)*64
        y=512-(i//8+1)*64
        pixels[y:y+64,x:x+64,:3] = entry[mode]
    pixels[region][:,:,:3] = np.array(paint)*(1-mask) + np.array(gill_blue)*mask
    pixels[:,:,:3] = np.where(pixels[:,:,:3] <= .0031308, pixels[:,:,:3]*12.92, 1.055*np.power(pixels[:,:,:3],1/2.4)-.055)
    write_atlas(name, pixels)
print('Game vertices:',len(rows),'indices:',len(indices),'palette slots:',len(palette),flush=True)
