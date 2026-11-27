import math,struct,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Quaternion,Vector
from mathutils.bvhtree import BVHTree

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from cannonbolt_paths import APP as APP_ROOT, REPO, WORK, vilgax_dump
sys.path[:0]=[str(REPO / 'tools')]
from author_alien_actions import packed_image
from convert_four_arms_meshes import mesh_buffers
from merge_alien_streams import entries
from prepare_vilgax_import import table,bone_ids

OUT=WORK.resolve()
package=(APP_ROOT/'installation/game/global/g_cb.xbx')
data=entries(package.read_bytes())
mesh_key=0x58ec2e03
skin=table(data[22])[mesh_key]
skeleton=table(data[12])[0x8b21e1f6]
mesh=table(data[4])[mesh_key]
textures=table(data[0])
C=Matrix(((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)))
_,vertex_bytes,index_bytes=mesh_buffers(mesh,xbox=True)
rows=list(struct.iter_unpack('>11f',vertex_bytes))
positions=[C@Vector(row[:3]) for row in rows]
split=3700
assert len(rows)==4580 and len(skin)==80+52*len(rows)
bpy.ops.wm.read_factory_settings(use_empty=True)
native=bpy.context.scene
native.name='Cannonbolt | Native rig'
body_collection=bpy.data.collections.new('BODY - native vertex order')
ball_collection=bpy.data.collections.new('BALL - native vertex order')
native.collection.children.link(body_collection)
native.collection.children.link(ball_collection)

armature=bpy.data.armatures.new('Vilgax Attacks Cannonbolt - 45 bones')
rig=bpy.data.objects.new('Cannonbolt | Original game skeleton',armature)
native.collection.objects.link(rig)
rig['source_mesh_key']='58ec2e03'
rig['source_skeleton_key']='8b21e1f6'
bpy.context.view_layer.objects.active=rig
rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
transforms=[]
source_rows=[]
for i in range(45):
    values=struct.unpack_from('>10f',skeleton,12+44*i)
    tag=struct.unpack_from('>I',skeleton,52+44*i)[0]
    parent=tag>>24
    local=Matrix.LocRotScale(Vector(values[4:7]),Quaternion((values[3],*values[:3])).conjugated(),Vector(values[7:]))
    transform=local if parent==255 else transforms[parent]@local
    transforms.append(transform)
    source_rows.append((tag,values))
    bone=armature.edit_bones.new(f'{i:02d} - {tag&0xffffff:03d}')
    bone.matrix=C@transform
    bone.length=.10 if i!=44 else .25
    if parent!=255:bone.parent=armature.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
assert [tag&0xffffff for tag,_ in source_rows]==bone_ids(next(clip for clip in table(data[13]).values() if clip.startswith(b'idle_01\0')))
names=[]
for i,(tag,values) in enumerate(source_rows):
    name=f'{i:02d} - {tag&0xffffff:03d}'
    bone=armature.bones[name]
    bone['game_bone_index']=i
    bone['game_bone_id']=tag&0xffffff
    bone['game_parent_index']=-1 if tag>>24==255 else tag>>24
    bone['game_local_xyzw_t_s']=values
    names.append(name)
rig.hide_render=True

# One shared palette controls every material, including the embossed back.
palette=bpy.data.node_groups.new('ULTIMATE CANNONBOLT - EDIT COLORS HERE','ShaderNodeTree')
colors={
    'Skin':(.32,.39,.52,1),
    'Trim':(.023,.025,.031,1),
    'Mouth':(.17,.065,.075,1),
    'Armor':(.017,.022,.049,1),
    'Armor edge':(.027,.033,.064,1),
    'Seams':(.008,.011,.020,1),
    'Eyes and emblem':(.025,.68,.018,1),
    'Ball armor':(.026,.022,.052,1),
    'Ball edges':(.034,.029,.064,1),
    'Ball seams':(.006,.006,.014,1),
}
palette_out=palette.nodes.new('NodeGroupOutput')
palette_out.location=(420,50)
for i,(name,color) in enumerate(colors.items()):
    palette.interface.new_socket(name=name,in_out='OUTPUT',socket_type='NodeSocketColor')
    control=palette.nodes.new('ShaderNodeRGB')
    control.name=control.label=name
    control.outputs[0].default_value=color
    control.location=(0,200-i*220)
    palette.links.new(control.outputs[0],palette_out.inputs[name])
palette.use_fake_user=True

def add_palette(nodes):
    control=nodes.new('ShaderNodeGroup')
    control.node_tree=palette
    control.label='Double-click to edit shared colors'
    control.width=250
    return control

def mix(tree,first,second,factor,operation='MIX',label=''):
    node=tree.nodes.new('ShaderNodeMixRGB')
    node.blend_type=operation
    node.label=label
    for value,socket in zip((factor,first,second),node.inputs):
        if isinstance(value,bpy.types.NodeSocket):
            tree.links.new(value,socket)
        else:
            socket.default_value=value
    return node.outputs[0]

def mask_image(name,values):
    height,width,_=values.shape
    image=bpy.data.images.new(name,width,height,alpha=False)
    image.colorspace_settings.name='Non-Color'
    rgba=np.ones((height,width,4),dtype=np.float32)
    rgba[:,:,:3]=values
    image.pixels.foreach_set(rgba.ravel())
    image.pack()
    return image

native_gold=None
native_green=None
def recolor(key,label):
    global native_gold,native_green
    image=packed_image(textures[key],label+' - original texture')
    material=bpy.data.materials.new(label)
    material.diffuse_color=(.33,.40,.56,1)
    material.use_nodes=True
    tree=material.node_tree
    nodes=tree.nodes
    controls=add_palette(nodes)
    bsdf=nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value=.72
    if key==0xdb869166:
        tree.links.new(controls.outputs['Ball seams'],bsdf.inputs['Base Color'])
        return material
    pixels=np.empty(len(image.pixels),dtype=np.float32)
    image.pixels.foreach_get(pixels)
    rgb=pixels.reshape(image.size[1],image.size[0],4)[:,:,:3]
    red,green,blue=np.moveaxis(rgb,-1,0)
    gold=np.clip((green-blue)*10,0,1)*np.clip((red-blue)*10,0,1)*np.clip((red-.25)*5,0,1)
    gold*=np.clip((red-green+.035)*16,0,1)
    native_gold=gold.copy()
    # Keep the original material boundaries, while dropping the donor
    # texture's dirt, highlights and surface mottling.
    def smooth(values, repeats):
        for _ in range(repeats):
            padded=np.pad(values,((1,1),(0,0)),mode='edge')
            values=(padded[:-2]+2*padded[1:-1]+padded[2:])*.25
            padded=np.pad(values,((0,0),(1,1)),mode='edge')
            values=(padded[:,:-2]+2*padded[:,1:-1]+padded[:,2:])*.25
        return values
    neutral=(rgb.mean(2)>.19)&((rgb.max(2)-rgb.min(2))<.18)
    lime=np.clip((green-red)*8,0,1)*np.clip((green-blue)*5,0,1)
    native_green=lime.copy()
    lip=np.clip((red-green-.006)*35,0,1)*np.clip((red-blue-.006)*28,0,1)
    lip*=1-gold
    edge=lambda values,steps:np.clip((smooth(values.astype(np.float32),steps)-.38)*4,0,1)
    uv=nodes.new('ShaderNodeUVMap')
    uv.uv_map='Original game UV'
    mask=nodes.new('ShaderNodeTexImage')
    # Remove small isolated bright spots in the donor's dark trim.
    for axis in range(2):
        pad=[(0,0),(0,0)]
        pad[axis]=(5,5)
        neutral=np.lib.stride_tricks.sliding_window_view(
            np.pad(neutral,pad,mode='edge'),11,axis=axis).min(axis=-1)
    for axis in range(2):
        pad=[(0,0),(0,0)]
        pad[axis]=(5,5)
        neutral=np.lib.stride_tricks.sliding_window_view(
            np.pad(neutral,pad,mode='edge'),11,axis=axis).max(axis=-1)
    mask.image=mask_image('Clean skin, armor and mouth masks',
                           np.stack((edge(gold,5),edge(neutral,8),edge(lip,2)),axis=-1))
    tree.links.new(uv.outputs['UV'],mask.inputs['Vector'])
    components=nodes.new('ShaderNodeSeparateColor')
    tree.links.new(mask.outputs['Color'],components.inputs[0])
    eyes=nodes.new('ShaderNodeTexImage')
    eyes.image=mask_image('Clean green eye mask',np.repeat(edge(lime,2)[:,:,None],3,axis=2))
    tree.links.new(uv.outputs['UV'],eyes.inputs['Vector'])
    position=nodes.new('ShaderNodeNewGeometry')
    height=nodes.new('ShaderNodeSeparateXYZ')
    tree.links.new(position.outputs['Position'],height.inputs[0])
    above=nodes.new('ShaderNodeMath')
    above.operation='GREATER_THAN'
    tree.links.new(height.outputs['Z'],above.inputs[0])
    above.inputs[1].default_value=1.12
    eye_only=nodes.new('ShaderNodeMath')
    eye_only.operation='MULTIPLY'
    tree.links.new(above.outputs[0],eye_only.inputs[0])
    tree.links.new(eyes.outputs['Color'],eye_only.inputs[1])
    color=mix(tree,controls.outputs['Trim'],controls.outputs['Skin'],components.outputs[1],label='Matte skin and trim')
    color=mix(tree,color,controls.outputs['Armor'],components.outputs[0],label='Clean armor')
    color=mix(tree,color,controls.outputs['Mouth'],components.outputs[2],label='Mouth color')
    color=mix(tree,color,controls.outputs['Eyes and emblem'],eye_only.outputs[0],label='Green eyes')
    local=nodes.new('ShaderNodeTexCoord').outputs['Object']
    def soft_region(center, radius):
        offset=nodes.new('ShaderNodeVectorMath')
        offset.operation='SUBTRACT'
        tree.links.new(local,offset.inputs[0])
        offset.inputs[1].default_value=center
        scale=nodes.new('ShaderNodeVectorMath')
        scale.operation='DIVIDE'
        tree.links.new(offset.outputs[0],scale.inputs[0])
        scale.inputs[1].default_value=radius
        distance=nodes.new('ShaderNodeVectorMath')
        distance.operation='LENGTH'
        tree.links.new(scale.outputs[0],distance.inputs[0])
        fade=nodes.new('ShaderNodeMapRange')
        fade.inputs['From Min'].default_value=.70
        fade.inputs['To Min'].default_value=1
        fade.inputs['To Max'].default_value=0
        tree.links.new(distance.outputs['Value'],fade.inputs['Value'])
        return fade.outputs[0]
    for side in (-1,1):
        trim=soft_region((side*.895,.017,1.315),(.039,.194,.032))
        color=mix(tree,color,controls.outputs['Trim'],trim,label='Clean shoulder seam')
    detail=nodes.new('ShaderNodeTexImage')
    detail.image=image
    tree.links.new(uv.outputs['UV'],detail.inputs['Vector'])
    mouth=soft_region((0,-.495,1.115),(.386,.084,.049))
    color=mix(tree,color,detail.outputs['Color'],mouth,label='Original lip and tooth detail')
    chest=soft_region((0,-.401,.8524),(.182,.215,.160))
    color=mix(tree,color,controls.outputs['Skin'],chest,label='Clean former badge area')
    bsdf.inputs['Roughness'].default_value=.84
    bsdf.inputs['Specular IOR Level'].default_value=.19
    tree.links.new(color,bsdf.inputs['Base Color'])
    return material

def model(label,start,end,triangles,material,collection):
    geometry=bpy.data.meshes.new(label)
    geometry.from_pydata(positions[start:end],[],triangles)
    geometry.update()
    uv=geometry.uv_layers.new(name='Original game UV')
    for loop in geometry.loops:
        u,v=rows[start+loop.vertex_index][9:]
        uv.data[loop.index].uv=(u,1-v)
    geometry.materials.append(material)
    for polygon in geometry.polygons:polygon.use_smooth=True
    obj=bpy.data.objects.new(label,geometry)
    collection.objects.link(obj)
    obj.parent=rig
    obj['native_first_vertex']=start
    groups=[obj.vertex_groups.new(name=name) for name in names]
    raw_weights=[geometry.attributes.new(f'Game weight {i}','INT','POINT') for i in range(4)]
    raw_indices=[geometry.attributes.new(f'Game index {i}','INT','POINT') for i in range(4)]
    for i in range(end-start):
        at=80+(start+i)*52
        weights,indices=skin[at+44:at+48],skin[at+48:at+52]
        for j,(w,k) in enumerate(zip(weights,indices)):
            raw_weights[j].data[i].value=w
            raw_indices[j].data[i].value=k
            if w:groups[k].add([i],w/sum(weights),'REPLACE')
    modifier=obj.modifiers.new('Original Cannonbolt Skin','ARMATURE')
    modifier.object=rig
    return obj

body_faces=[]
ball_faces=[]
for a,b,c in struct.iter_unpack('>3H',index_bytes):
    assert (max(a,b,c)<split) or (min(a,b,c)>=split)
    if len({a,b,c})!=3:continue
    (body_faces if a<split else ball_faces).append((a,b,c) if a<split else (a-split,b-split,c-split))
body=model('Ultimate Cannonbolt | Body',0,split,body_faces,recolor(0x46cb9ef2,'Ultimate body diffuse'),body_collection)
ball=model('Ultimate Cannonbolt | Ball',split,len(rows),ball_faces,recolor(0xdb869166,'Ultimate ball diffuse'),ball_collection)

def material(name,color):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=mat.diffuse_color
    shader.inputs['Roughness'].default_value=.66
    return mat

armor=material('Armor | linked palette',(.017,.022,.049))
edge=material('Armor edge | linked palette',(.027,.033,.064))
ball_armor=material('Ball armor | linked palette',(.009,.011,.027))
ball_edge=material('Ball edges | linked palette',(.015,.017,.034))
for mat,color in ((armor,'Armor'),(edge,'Armor edge'),(ball_armor,'Ball armor'),(ball_edge,'Ball edges')):
    tree=mat.node_tree
    tree.links.new(add_palette(tree.nodes).outputs[color],tree.nodes.get('Principled BSDF').inputs['Base Color'])
def weighted_part(name,points,faces,bone,collection):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(points,[],faces)
    mesh.update()
    mesh.materials.append(ball_armor if collection==ball_collection else armor)
    mesh.materials.append(ball_edge if collection==ball_collection else edge)
    obj=bpy.data.objects.new(name,mesh)
    collection.objects.link(obj)
    obj.parent=rig
    group=obj.vertex_groups.new(name=names[bone])
    group.add(list(range(len(points))),1,'REPLACE')
    mod=obj.modifiers.new('Attach to original bone','ARMATURE')
    mod.object=rig
    return obj

def spike(name,pos,direction,width,height,bone,col,pointed=False):
    axis=Vector(direction).normalized()
    tangent=axis.cross(Vector((0,0,1)))
    if tangent.length<.01:tangent=axis.cross(Vector((0,1,0)))
    tangent.normalize()
    bitangent=axis.cross(tangent)
    n=8
    points=[]
    rings=[(-.025,width),(.025,width*.90),(height,width*(.04 if pointed else .40))]
    for z,r in rings:
        for i in range(n):
            angle=2*math.pi*i/n
            points.append(Vector(pos)+axis*z+r*(math.cos(angle)*tangent+math.sin(angle)*bitangent))
    faces=[tuple(reversed(range(n)))]
    for row in range(2):
        for i in range(n):
            j=(i+1)%n;a=row*n
            faces.append((a+i,a+j,a+n+j,a+n+i))
    faces.append(tuple(range(2*n,3*n)))
    obj=weighted_part(name,points,faces,bone,col)
    for polygon in obj.data.polygons:
        polygon.material_index=int(polygon.index==len(faces)-1)

body_bvh=BVHTree.FromPolygons(positions[:split],body_faces,all_triangles=True)
ball_bvh=BVHTree.FromPolygons(positions[split:],ball_faces,all_triangles=True)
# Find each original gold dome on the texture. Aim the spike through its
# area-weighted center, along the direction the dome faces.
height,width=native_gold.shape
gold_per_vertex=[native_gold[min(height-1,max(0,int((1-row[10])*height))),
                             min(width-1,max(0,int(row[9]*width)))] for row in rows[:split]]
for side in (-1,1):
    for label,x_range,z_range,width,height in [
        ('Shoulder',(.32,.96),(1.34,1.98),.107,.155),
        ('Forearm',(.96,1.50),(.81,1.37),.096,.135),
        ('Hip',(.26,.79),(.19,.76),.086,.112)]:
        centroid,axis,total=Vector(),Vector(),0
        influences={}
        for tri in body_faces:
            points=[positions[i] for i in tri]
            mean=sum(points,Vector())/3
            if not (x_range[0]<side*mean.x<x_range[1] and z_range[0]<mean.z<z_range[1]):
                continue
            coverage=min(gold_per_vertex[i] for i in tri)
            if coverage<.73:continue
            face_normal=(points[1]-points[0]).cross(points[2]-points[0])
            area=face_normal.length*coverage
            normal=sum((C.to_3x3()@Vector(rows[i][3:6]) for i in tri),Vector()).normalized()
            centroid+=mean*area
            axis+=normal*area
            total+=area
            for i in tri:
                at=80+i*52
                for w,b in zip(skin[at+44:at+48],skin[at+48:at+52]):
                    influences[b]=influences.get(b,0)+area*w
        assert total>.01,(label,side,total)
        centroid/=total
        axis.normalize()
        if axis.dot(Vector((side*.3,0,.2)))<0:axis.negate()
        surface,_,_,_=body_bvh.ray_cast(centroid+axis*.25,-axis,.38)
        assert surface is not None,(label,side,centroid,axis)
        bone=max(influences,key=influences.get)
        spike(f'{label} spike {side:+}',surface,axis,width,height,bone,body_collection)
        print('Centered',label,side,tuple(round(x,3) for x in surface),'bone',bone)

# Curved shell pieces with inset rims. Coordinates are projected onto the
# original mesh so the added armor follows the existing body silhouette.
def solid_panel(name, grid, normal, bone, collection):
    width=len(grid[0])
    points=[p for row in grid for p in row]
    faces=[]
    for row in range(len(grid)-1):
        for col in range(width-1):
            i=row*width+col
            faces.append((i,i+1,i+1+width,i+width))
    boundary=list(range(width))
    boundary += [row*width+width-1 for row in range(1,len(grid))]
    boundary += list(range(len(points)-2,len(points)-width-1,-1))
    boundary += [row*width for row in range(len(grid)-2,0,-1)]
    face=faces[len(faces)//2]
    a,b,c=(points[i] for i in face[:3])
    reverse=(b-a).cross(c-a).dot(normal(a))<0
    surface_count=len(faces)
    inside=len(points)
    points.extend(points[i]-normal(points[i])*.060 for i in boundary)
    for j,i in enumerate(boundary):
        nxt=(j+1)%len(boundary)
        faces.append((i,inside+j,inside+nxt,boundary[nxt]))
    if reverse:faces=[tuple(reversed(face)) for face in faces]
    obj=weighted_part(name,points,faces,bone,collection)
    for face in obj.data.polygons:
        face.material_index=int(face.index>=surface_count)
        face.use_smooth=face.index<surface_count

# Form the armor in the original body vertices and use the same profile
# for the embedded armor/seam material mask. No stacked back panels.
x_profile=(-1,-.80,-.52,-.25,-.18,0,.18,.25,.52,.80,1)
def shield_profile(x,z):
    width=np.interp(z,[.60,.68,.78,.95,1.16,1.38,1.54,1.73],
                     [.09,.15,.27,.36,.44,.51,.54,.24])
    a=abs(x)
    silhouette=np.minimum(np.minimum(z-.60,1.73-z),width-a)
    notch=np.interp(a,[0,.105,.21,.31,.57],[.128,.128,.078,0,0])
    height=z+notch
    strip=np.maximum.reduce([np.minimum(height-lo,hi-height)-.02*(a/.55)**2
                             for lo,hi in ((.74,.99),(1.026,1.225),(1.26,1.495))])
    strip=np.minimum(strip,silhouette-.027)
    collar=np.minimum(np.minimum(z-1.56,1.704-z),.25-a)
    outline=np.clip(silhouette/.023,0,1)
    face=np.clip(np.maximum(strip,collar)/.017,0,1)
    return outline,face

geometry=body.data
back_uv=geometry.uv_layers.new(name='Integrated dorsal shield')
for face in geometry.polygons:
    verts=[geometry.vertices[i].co for i in face.vertices]
    center=sum(verts,Vector())/len(verts)
    rear=center.y>.07 and face.normal.y>-.30
    for index in face.loop_indices:
        x,_,z=geometry.vertices[geometry.loops[index].vertex_index].co
        back_uv.data[index].uv=((x+.75)/1.5,(z-.40)/1.5) if rear else (.01,.01)
# Fit a smooth, symmetric dorsal surface only under the dark armor.
# Blend back into the donor shape near the armor boundary.
normals=[(C.to_3x3()@Vector(row[3:6])).normalized() for row in rows[:split]]
coords=np.array([tuple(v.co) for v in geometry.vertices])
x,y,z=coords.T
h=z-1.17
outline,_=shield_profile(x,z)
facing=np.array([normal.y for normal in normals])
sample=(outline>.6)&(y>.17)&(facing>.38)
assert np.count_nonzero(sample)>30
basis=np.stack((np.ones_like(x),h,h*h,h*h*h,x*x,x*x*h),axis=1)
coeff=np.linalg.lstsq(basis[sample],y[sample],rcond=None)[0]
fitted=basis@coeff
alpha=outline*np.clip((facing-.19)/.56,0,1)*np.clip((y-.17)/.16,0,1)
dy_dx=2*x*(coeff[4]+coeff[5]*h)
dy_dz=coeff[1]+2*coeff[2]*h+3*coeff[3]*h*h+coeff[5]*x*x
for i,vertex in enumerate(geometry.vertices):
    if alpha[i]==0:continue
    vertex.co.y+=float(np.clip(fitted[i]-y[i],-.07,.07)*alpha[i])
    normal=Vector((-dy_dx[i],1,-dy_dz[i])).normalized()
    normals[i]=normals[i].lerp(normal,float(alpha[i])).normalized()
# Rebuild the small embossed donor badge area from the surrounding chest.
# Keep the surrounding torso and the original skin weights.
chest_z=z-.8524
chest_radius=np.sqrt((x/.186)**2+(chest_z/.173)**2)
chest_tree=BVHTree.FromPolygons([v.co for v in geometry.vertices],body_faces,all_triangles=True)
samples=[]
for side in (-1,1):
    for lateral in np.linspace(.173,.248,8):
        for height in np.linspace(.723,.982,16):
            hit,_,_,_=chest_tree.ray_cast(Vector((side*lateral,-2,height)),Vector((0,1,0)),2)
            if hit is not None:
                dz=height-.8524
                samples.append(((1,dz,dz*dz,lateral*lateral),hit.y))
assert len(samples)>=100
design,depth=zip(*samples)
chest_basis=np.stack((np.ones_like(x),chest_z,chest_z**2,x*x),axis=1)
coeff=np.linalg.lstsq(design,depth,rcond=None)[0]
surface=chest_basis@coeff
blend=np.clip((1-chest_radius)/.24,0,1)
blend=blend*blend*(3-2*blend)
for i in np.flatnonzero((blend>0)&(y<-.22)):
    amount=float(blend[i])
    geometry.vertices[i].co.y+=float(np.clip(surface[i]-y[i],-.09,.09)*amount)
    smooth_normal=Vector((2*coeff[3]*x[i],-1,coeff[1]+2*coeff[2]*chest_z[i])).normalized()
    normals[i]=normals[i].lerp(smooth_normal,amount).normalized()
geometry.normals_split_custom_set_from_vertices(normals)
geometry.update()
body_bvh=BVHTree.FromPolygons([v.co for v in geometry.vertices],body_faces,all_triangles=True)
grid_size=512
z,x=np.mgrid[0:grid_size,0:grid_size]/(grid_size-1)
outline,strip=shield_profile(x*1.5-.75,z*1.5+.40)
back_mask=mask_image('Integrated dorsal armor and seam masks',np.stack((outline,strip,strip),axis=-1))
tree=geometry.materials[0].node_tree
nodes=tree.nodes
bsdf=nodes.get('Principled BSDF')
control=next(node for node in nodes if node.type=='GROUP')
body_color=bsdf.inputs['Base Color'].links[0].from_socket
dorsal=nodes.new('ShaderNodeTexImage')
dorsal.image=back_mask
dorsal.extension='CLIP'
uv=nodes.new('ShaderNodeUVMap')
uv.uv_map=back_uv.name
tree.links.new(uv.outputs[0],dorsal.inputs[0])
masks=nodes.new('ShaderNodeSeparateColor')
tree.links.new(dorsal.outputs[0],masks.inputs[0])
shell_color=mix(tree,control.outputs['Seams'],control.outputs['Armor'],masks.outputs[1],label='Integrated shield strips')
color=mix(tree,body_color,shell_color,masks.outputs[0],label='Rear shield only')
tree.links.new(color,bsdf.inputs['Base Color'])

for row,(z,x,radius) in enumerate([(1.37,.399,.071),(1.125,.34,.067),(.89,.265,.063)],1):
    for side in (-1,1):
        hit,_,face,_=body_bvh.ray_cast(Vector((x*side,1.2,z)),Vector((0,-1,0)),1.3)
        assert hit is not None
        axis=Vector((side*.18,1,.03)).normalized()
        tangent=axis.cross(Vector((0,0,1))).normalized()
        vertical=tangent.cross(axis)
        steps=12
        points=[]
        for height,factor in ((-.035,.94),(.0,1),(.028,.87),(.065,.69),(.075,.50)):
            for j in range(steps):
                t=math.tau*j/steps
                points.append(hit+axis*height+radius*factor*(tangent*math.cos(t)+vertical*math.sin(t)))
        tip=len(points)
        points.append(hit+axis*.076)
        faces=[(tip,4*steps+(j+1)%steps,4*steps+j) for j in range(steps)]
        for ring in range(4):
            for j in range(steps):
                a=ring*steps+j;b=ring*steps+(j+1)%steps
                faces.append((a,a+steps,b+steps,b))
        stud=weighted_part(f'Embedded dorsal stud {row} {side:+}',points,faces,3,body_collection)
        for polygon in stud.data.polygons:polygon.use_smooth=True

center=Vector((0,.006,.835))
def ball_surface(axis,lift):
    point,_,_,_=ball_bvh.ray_cast(center+axis*1.6,-axis,1.3)
    return (point if point is not None else center+axis*.7)+axis*lift

def around_axle(x,angle):
    radius=math.sqrt(1-x*x)
    return Vector((x,radius*math.sin(angle),radius*math.cos(angle)))

# Use continuous, angular strips around the rolling axis. A dark gap
# remains between each strip and the large circular plates at the ends.
for band in range(7):
    angle=band*math.tau/7
    grid=[]
    for fraction in (-1,-.91,-.58,-.2,.2,.58,.91,1):
        row=[]
        for x in x_profile:
            # At the crown negative angle is forward (-Y). Use that same
            # circumferential direction for every row of the rolling shell.
            notch=-np.interp(abs(x),[0,.18,.23,.54,1],[.24,.24,.19,0,0])
            theta=angle+notch+fraction*(.33 if abs(x)<.98 else .31)
            row.append(ball_surface(around_axle(x*.73,theta),.043 if abs(fraction)<.95 else .029))
        grid.append(row)
    solid_panel(f'Ball armor | chevron {band+1}',grid,lambda p:(p-center).normalized(),44,ball_collection)
    for side in (-1,1):
        mount=around_axle(side*.52,angle-.017)
        direction=around_axle(side*.52,angle-.12)
        spike(f'Ball spike {band+1} {side:+}',ball_surface(mount,.040),direction,.093,.31,44,ball_collection,True)

# Build a closed, skinned surface along the rolling axle. The outer
# chevrons and spikes keep their mounts on the donor shell.
segments=80
angles=[j*math.tau/segments for j in range(segments)]
cap_profile=((.09,.822),(.18,.809),(.28,.790),(.38,.755),(.46,.718),
             (.505,.690),(.526,.671),(.542,.649),(.563,.595))
points=[Vector((-.825,center.y,center.z))]
rings=[]
for radius,axial in cap_profile:
    rings.append([Vector((-axial,center.y+radius*math.sin(t),center.z+radius*math.cos(t)))
                  for t in angles])
for axial in np.linspace(-.655,.655,25):
    rings.append([ball_surface(around_axle(axial,t),0) for t in angles])
for radius,axial in reversed(cap_profile):
    rings.append([Vector((axial,center.y+radius*math.sin(t),center.z+radius*math.cos(t)))
                  for t in angles])
for ring in rings:
    points.extend(ring)
points.append(Vector((.825,center.y,center.z)))
faces=[]
material_ids=[]
for j in range(segments):
    faces.append((0,1+j,1+(j+1)%segments))
    material_ids.append(0)
for row in range(len(rings)-1):
    start=1+row*segments
    next_start=start+segments
    depth=min(row,len(rings)-2-row)
    material_index=0 if depth<5 else 1 if depth<7 else 2
    for j in range(segments):
        k=(j+1)%segments
        faces.append((start+j,next_start+j,next_start+k,start+k))
        material_ids.append(material_index)
last=1+(len(rings)-1)*segments
for j in range(segments):
    faces.append((len(points)-1,last+(j+1)%segments,last+j))
    material_ids.append(0)
old_ball=ball
base_material=old_ball.data.materials[0]
bpy.data.objects.remove(old_ball,do_unlink=True)
ball=weighted_part('Ultimate Cannonbolt | Ball',points,faces,44,ball_collection)
ball['native_first_vertex']=split
ball.data.materials.append(base_material)
for polygon,material_index in zip(ball.data.polygons,material_ids):
    polygon.material_index=material_index
    polygon.use_smooth=True
assert all(p.normal.dot(p.center-center)>0 for p in ball.data.polygons)
for side in (-1,1):
    spike(f'Ball axle spike {side:+}',Vector((side*.825,center.y,center.z)),
          Vector((side,0,0)),.11,.32,44,ball_collection,True)

# Recover the existing insignia center from the donor diffuse rather than
# guessing where it sits on the curved chest.
def chest_hit(x,z):
    point,_,index,_=body_bvh.ray_cast(Vector((x,-1.3,z)),Vector((0,1,0)),1.5)
    return point,index

def donor_green(point,index):
    i,j,k=body_faces[index]
    a,b,c=(body.data.vertices[l].co for l in (i,j,k))
    d,e,f=b-a,c-a,point-a
    dd,ee,de=d.dot(d),e.dot(e),d.dot(e)
    determinant=dd*ee-de*de
    if determinant<1e-10:return 0
    u=(ee*f.dot(d)-de*f.dot(e))/determinant
    v=(dd*f.dot(e)-de*f.dot(d))/determinant
    x,y=((1-u-v)*rows[i][n]+u*rows[j][n]+v*rows[k][n] for n in (9,10))
    h,w=native_green.shape
    return native_green[min(h-1,max(0,int((1-y)*h))),min(w-1,max(0,int(x*w)))]

badge_points=[]
for z in np.linspace(.62,1.40,100):
    for x in np.linspace(-.13,.13,35):
        pt,face=chest_hit(x,z)
        if pt is not None and donor_green(pt,face)>.6:
            badge_points.append((x,z))
assert badge_points,'The source chest emblem could not be located'
badge=np.asarray(badge_points)
badge_x=(badge[:,0].min()+badge[:,0].max())*.5
badge_z=(badge[:,1].min()+badge[:,1].max())*.5-.050
radius=max(np.ptp(badge[:,0]),np.ptp(badge[:,1]))*.88
print('Chest emblem center and housing radius:',badge_x,badge_z,radius)
radius=max(.089,min(.120,radius))
black=material('Ultimatrix housing | linked palette',(.009,.010,.013))
green=material('Ultimatrix core | linked palette',(.025,.68,.018))
for mat,color in ((black,'Seams'),(green,'Eyes and emblem')):
    tree=mat.node_tree
    shader=tree.nodes.get('Principled BSDF')
    linked=add_palette(tree.nodes).outputs[color]
    tree.links.new(linked,shader.inputs['Base Color'])
    shader.inputs['Roughness'].default_value=.40

def chest_badge_mesh(name,profile,faces,mat):
    points=[]
    for dx,dz,lift in profile:
        x,z=badge_x+dx*radius,badge_z+dz*radius
        hit,_=chest_hit(x,z)
        assert hit is not None
        points.append(Vector((x,hit.y-lift,z)))
    obj=weighted_part(name,points,faces,3,body_collection)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj

# Four rectangular swept arms sit under the beveled central housing.
for sx in (-1,1):
    for sz in (-1,1):
        profile=[(.43,.22),(.58,.62),(1.48,.99),(1.63,.72),(.80,.27)]
        points=[(sx*x,sz*z,lift) for lift in (.004,.027) for x,z in profile]
        n=len(profile)
        faces=[tuple(range(n,2*n)),tuple(reversed(range(n)))]
        faces += [(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]
        if sx*sz>0:faces=[tuple(reversed(face)) for face in faces]
        chest_badge_mesh(f'Ultimatrix arm {sx:+} {sz:+}',points,faces,black)

ring_steps=16
points=[]
for unit,lift in ((1.03,.001),(1.03,.030),(.92,.047),(.72,.048),(.70,.038)):
    for j in range(ring_steps):
        angle=(j+.5)*math.tau/ring_steps
        points.append((unit*math.cos(angle),unit*math.sin(angle),lift))
faces=[]
for rim in range(4):
    for j in range(ring_steps):
        a=rim*ring_steps+j;b=rim*ring_steps+(j+1)%ring_steps
        faces.append((a,b,b+ring_steps,a+ring_steps))
faces.append(tuple(range(4*ring_steps,5*ring_steps)))
chest_badge_mesh('Ultimatrix | black beveled housing',points,faces,black)

# Both lobes share the same waist vertices, so the center remains green.
top=[(-.53,.40),(-.39,.57),(-.19,.66),(.19,.66),(.39,.57),(.53,.40)]
points=[(x,z,.051) for x,z in top]+[(.115,0,.052),(-.115,0,.052)]
points.extend((x,-z,.051) for x,z in top)
chest_badge_mesh('Ultimatrix | continuous green hourglass',points,
                 [(7,6,5,4,3,2,1,0),(8,9,10,11,12,13,6,7)],green)

# Keep both game meshes at the native origin. The review scene uses linked
# geometry to place the two forms side by side.
preview=bpy.data.scenes.new('Ultimate Cannonbolt | Preview')
for col,offset,angle in [(body_collection,(-.92,0,.01),-.18),(ball_collection,(1.42,.45,-.03),.22)]:
    for original in col.objects:
        copy=bpy.data.objects.new(original.name+' | Display',original.data)
        preview.collection.objects.link(copy)
        copy.location=offset
        copy.rotation_euler.z=angle
world=bpy.data.worlds.new('Soft blue studio')
world.use_nodes=True
world.node_tree.nodes.get('Background').inputs[0].default_value=(.38,.47,.61,1)
world.node_tree.nodes.get('Background').inputs[1].default_value=.33
preview.world=world
bpy.context.window.scene=preview
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.025))
floor=bpy.context.object
floor.name='Preview floor'
floor.data.materials.append(material('Slate preview floor',(.06,.083,.12)))
def aim(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
for name,loc,power,size,color in [
    ('Key',(-3,-4,6),570,5,(.79,.88,1)),('Fill',(5,-1,3),320,4,(.68,.79,1)),
    ('Rim',(2,4,5),780,3,(.54,.70,1))]:
    light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='DISK';light.size=size;light.color=color
    obj=bpy.data.objects.new(name,light);preview.collection.objects.link(obj);obj.location=loc;aim(obj,(0,0,.8))
camera=bpy.data.objects.new('Character and roll preview',bpy.data.cameras.new('Preview lens'))
preview.collection.objects.link(camera)
camera.location=(3,-10,4.2);aim(camera,(0,0,.98))
camera.data.type='ORTHO';camera.data.ortho_scale=5.65
preview.camera=camera
preview.render.engine='CYCLES'
preview.cycles.samples=12
preview.cycles.use_denoising=True
preview.render.resolution_x=1152
preview.render.resolution_y=725
preview.render.resolution_percentage=100
preview.view_settings.view_transform='AgX'
bpy.ops.object.select_all(action='DESELECT')
review_body=bpy.data.objects[body.name+' | Display']
review_body.select_set(True)
bpy.context.view_layer.objects.active=review_body
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
            space.region_3d.view_location=Vector((0,0,.98))
            space.region_3d.view_distance=5.7
            space.region_3d.view_perspective='ORTHO'
            space.overlay.show_overlays=False
            space.shading.type='MATERIAL'
        if area.type=='NODE_EDITOR':
            area.spaces.active.shader_type='OBJECT'
for layer in native.view_layers:
    layer.layer_collection.children[ball_collection.name].exclude=True
assert len(armature.bones)==45 and len(body.data.vertices)==split
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Ultimate-Cannonbolt-3D-Badge.blend'))
preview.render.filepath=str(OUT/'Ultimate-Cannonbolt-3D-Badge.png')
bpy.ops.render.render(write_still=True)
camera.location=(-2.5,9,4.1)
aim(camera,(0,0,.98))
preview.render.filepath=str(OUT/'Ultimate-Cannonbolt-3D-Badge-Back.png')
bpy.ops.render.render(write_still=True)

for obj in body_collection.objects:
    bpy.data.objects[obj.name+' | Display'].hide_render=True
camera.location=(5.55,-5.4,3.05)
aim(camera,(1.42,.45,.87))
camera.data.ortho_scale=3.45
preview.render.resolution_x=820
preview.render.resolution_y=780
preview.render.filepath=str(OUT/'Ultimate-Cannonbolt-3D-Badge-Ball.png')
bpy.ops.render.render(write_still=True)


for obj in body_collection.objects:
    bpy.data.objects[obj.name+' | Display'].hide_render=False
for obj in ball_collection.objects:
    bpy.data.objects[obj.name+' | Display'].hide_render=True
camera.location=(-.92,-7,badge_z+.10)
aim(camera,(-.92,-.10,badge_z))
camera.data.ortho_scale=.93
preview.render.resolution_x=760
preview.render.resolution_y=650
preview.render.filepath=str(OUT/'Ultimate-Cannonbolt-3D-Badge-Detail.png')
bpy.ops.render.render(write_still=True)
