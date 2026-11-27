"""Bake the approved Ultimate model using the native game vertex groups."""
import math
from pathlib import Path
import os
import struct
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def fit_badge_weights(body, parts):
    """Keep the raised casing outside the animated chest."""
    mesh=body.data
    faces=[tuple(face.vertices) for face in mesh.polygons]
    tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],faces,all_triangles=True)
    badge=[part for part in parts if part.name.startswith('Ultimatrix')]
    assert len(badge)==6
    for part in badge:
        part.vertex_groups.clear()
        groups={}
        for vertex in part.data.vertices:
            x,y,z=vertex.co
            hit,_,index,_=tree.ray_cast(Vector((x,-2,z)),Vector((0,1,0)),2)
            assert hit is not None
            vertex.co.y=min(y-.011,hit.y-.016)
            a,b,c=(mesh.vertices[i] for i in faces[index])
            u,v,d=b.co-a.co,c.co-a.co,hit-a.co
            uu,uv,vv=u.dot(u),u.dot(v),v.dot(v)
            determinant=uu*vv-uv*uv
            t=(vv*u.dot(d)-uv*v.dot(d))/determinant
            q=(uu*v.dot(d)-uv*u.dot(d))/determinant
            weights={}
            for node,factor in ((a,1-t-q),(b,t),(c,q)):
                for influence in node.groups:
                    name=body.vertex_groups[influence.group].name
                    weights[name]=weights.get(name,0)+max(0,factor)*influence.weight
            for name,weight in weights.items():
                if weight<=0:continue
                if name not in groups:groups[name]=part.vertex_groups.new(name=name)
                groups[name].add([vertex.index],min(1,weight),'REPLACE')
        part.data.update()

root=Path(os.environ.get('ULTIMATE_CANNONBOLT_EXPORT_DIR',str(WORK)))
root.mkdir(parents=True,exist_ok=True)
scene=bpy.data.scenes['Cannonbolt | Native rig']
bpy.context.window.scene=scene
scene.render.engine='CYCLES'
scene.cycles.samples=1
scene.cycles.device='CPU'
scene.render.bake.margin=5
scene.view_settings.view_transform='Standard'
rig=next(o for o in scene.objects if o.type=='ARMATURE')
assert len(rig.data.bones)==45
basis=lambda v:(v.x,v.z,-v.y)
for kind,collection,size in [('body','BODY - native vertex order',1024),('ball','BALL - native vertex order',512)]:
    for child in bpy.context.view_layer.layer_collection.children: child.exclude=False
    bpy.context.view_layer.update()
    objects=list(bpy.data.collections[collection].objects)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    obj=next(o for o in objects if 'native_first_vertex' in o)
    bpy.context.view_layer.objects.active=obj
    for part in objects: part.data=part.data.copy()
    if kind=='body':fit_badge_weights(obj,objects)
    bpy.ops.object.join()
    obj.modifiers.clear()
    triangulate=obj.modifiers.new('Game triangles','TRIANGULATE')
    triangulate.keep_custom_normals=True
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    me=obj.data
    uv=me.uv_layers.new(name='Game bake')
    me.uv_layers.active=uv
    uv.active_render=True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(72),island_margin=.004,margin_method='FRACTION')
    bpy.ops.object.mode_set(mode='OBJECT')
    atlas=bpy.data.images.new(kind+' atlas',size,size,alpha=True)
    for mat in set(me.materials):
        tree=mat.node_tree
        rgb=tree.nodes.get('Principled BSDF').inputs['Base Color']
        emit=tree.nodes.new('ShaderNodeEmission')
        if rgb.is_linked:
            tree.links.new(rgb.links[0].from_socket,emit.inputs[0])
        else:
            emit.inputs[0].default_value=rgb.default_value
        tree.links.new(emit.outputs[0],tree.nodes.get('Material Output').inputs[0])
        target=tree.nodes.new('ShaderNodeTexImage')
        target.image=atlas
        tree.nodes.active=target
    bpy.ops.object.bake(type='EMIT')
    atlas.filepath_raw=str((root/f'ucb-{kind}.png').resolve())
    atlas.file_format='PNG'
    atlas.save()
    me.calc_loop_triangles()
    uv=me.uv_layers['Game bake']
    me.calc_tangents(uvmap=uv.name)
    vertices={}
    skin=[]
    raw=[]
    indices=[]
    for tri in me.loop_triangles:
        for index in tri.loops:
            loop=me.loops[index]
            v=me.vertices[loop.vertex_index]
            u,t=uv.data[index].uv
            fields=(*basis(v.co),*basis(loop.normal),*basis(loop.tangent),u,1-t)
            key=(v.index,*(round(value,5) for value in fields[3:]))
            if key not in vertices:
                vertices[key]=len(vertices)
                weights=sorted((g.weight,int(obj.vertex_groups[g.group].name.split(' ')[0])) for g in v.groups if g.weight>0)[-4:][::-1]
                assert weights and all(0<=k<45 for _,k in weights)
                total=sum(w for w,_ in weights)
                floats=[255*w/total for w,_ in weights]
                nums=[int(w) for w in floats]
                for i in sorted(range(len(nums)),key=lambda i:floats[i]-nums[i],reverse=True)[:255-sum(nums)]:nums[i]+=1
                packed=struct.pack('>11f',*fields)
                raw.append(packed)
                skin.append(packed+bytes(nums).ljust(4,b'\0')+bytes(k for _,k in weights).ljust(4,b'\0'))
            indices.append(vertices[key])
    assert len(vertices)<65536 and len(indices)<65536
    (root/f'ucb-{kind}.bin').write_bytes(struct.pack('>II',len(vertices),len(indices))+b''.join(raw)+b''.join(skin)+struct.pack(f'>{len(indices)}H',*indices))
    print(kind,len(vertices),len(indices),flush=True)
