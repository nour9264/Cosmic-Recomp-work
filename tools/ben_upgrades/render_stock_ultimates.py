import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
import bpy,json
from pathlib import Path
from mathutils import Vector
root=WORK;assets=root/'stock-ultimate-portraits'
for code in ['usf']:
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;data=json.loads((assets/(code+'.json')).read_text());verts=data['vertices'];indices=data['indices'];faces=[];slots=[]
 materials=[]
 for m,part in enumerate(data['ranges']):
  material=bpy.data.materials.new(code+' '+str(m));material.use_nodes=True;shader=material.node_tree.nodes.get('Principled BSDF');tex=material.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(assets/part['texture']));material.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color']);material.node_tree.links.new(tex.outputs['Alpha'],shader.inputs['Alpha']);shader.inputs['Roughness'].default_value=.85;materials.append(material)
  for i in range(part['start'],part['start']+part['count'],3):
   face=indices[i:i+3]
   if len(set(face))==3:faces.append(face);slots.append(m)
 mesh=bpy.data.meshes.new(code);mesh.from_pydata(verts,[],faces);mesh.materials.clear()
 for m in materials:mesh.materials.append(m)
 uv=mesh.uv_layers.new(name='Native UV')
 for poly,m in zip(mesh.polygons,slots):
  poly.material_index=m;poly.use_smooth=True
  for i in poly.loop_indices:
   u,v=data['uvs'][mesh.loops[i].vertex_index];uv.data[i].uv=(u,1-v)
 obj=bpy.data.objects.new(code,mesh);scene.collection.objects.link(obj)
 points=[Vector(v) for v in verts];lo=Vector(tuple(min(v[i] for v in points) for i in range(3)));hi=Vector(tuple(max(v[i] for v in points) for i in range(3)));center=(lo+hi)/2;extent=max(hi-lo)
 camera=bpy.data.objects.new('Portrait camera',bpy.data.cameras.new('Portrait camera'));scene.collection.objects.link(camera);camera.location=center+Vector((extent*.12,-extent*3,extent*.05));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=max(hi.z-lo.z,hi.x-lo.x)*1.1;scene.camera=camera
 for j,(pos,power) in enumerate([((-1,-2,3),180),((2,-1,1),110),((0,2,2),160)]):
  o=bpy.data.objects.new('Light'+str(j),bpy.data.lights.new('Light'+str(j),'AREA'));scene.collection.objects.link(o);o.location=center+Vector(pos)*extent;o.rotation_euler=(center-o.location).to_track_quat('-Z','Y').to_euler();o.data.energy=power*extent*extent;o.data.size=extent*3
 scene.world=bpy.data.worlds.new('Ambient');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.25,.25,.25,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.5
 scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True;scene.render.resolution_x=512;scene.render.resolution_y=512;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.view_settings.exposure=0;scene.render.filepath=str(root/('ultimate-'+code+'.png'));bpy.ops.render.render(write_still=True);print('FINISHED',code,flush=True)
