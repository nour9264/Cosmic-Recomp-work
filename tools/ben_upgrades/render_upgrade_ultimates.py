import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
import bpy,math,sys
from pathlib import Path
from mathutils import Vector
out=WORK
for name,source in [('ultimate-cannonbolt','Ultimate-Cannonbolt-Final-Review.blend'),('ultimate-way-big','Ultimate-Way-Big-Paired-Ribs.blend')]:
 bpy.ops.wm.open_mainfile(filepath=str(BLEND/source))
 scene=bpy.context.scene
 for o in scene.objects:
  if o.type=='MESH' and ('floor' in o.name.lower() or (name=='ultimate-cannonbolt' and any(v in o.name.lower() for v in ['ball |','ball armor','ball spike','ball circular','ball axle']))):o.hide_render=True
 objects=[o for o in scene.objects if o.type=='MESH' and not o.hide_render and not o.hide_get()]
 if not objects:raise RuntimeError('No visible model')
 points=[o.matrix_world@Vector(v) for o in objects for v in o.bound_box]
 lo=Vector(tuple(min(p[i] for p in points) for i in range(3)));hi=Vector(tuple(max(p[i] for p in points) for i in range(3)));center=(lo+hi)*.5;extent=max(hi-lo)
 for o in list(scene.objects):
  if o.type in ('CAMERA','LIGHT'):bpy.data.objects.remove(o,do_unlink=True)
 camera=bpy.data.objects.new('Upgrade portrait camera',bpy.data.cameras.new('Upgrade portrait camera'));scene.collection.objects.link(camera)
 camera.location=center+Vector((0,-extent*2.8,extent*.1));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=max(hi.z-lo.z,hi.x-lo.x)*1.12;scene.camera=camera
 for j,(pos,power,size) in enumerate([((-1,-2,3),900,4),((2,-1,1),550,3),((0,2,2),800,3)]):
  light=bpy.data.objects.new('Portrait light'+str(j),bpy.data.lights.new('Portrait light'+str(j),'AREA'));scene.collection.objects.link(light);light.location=center+Vector(pos)*extent;light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler();light.data.energy=power*extent*extent*.2;light.data.shape='DISK';light.data.size=size*extent
 scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True
 scene.render.resolution_x=512;scene.render.resolution_y=512;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.filepath=str(out/(name+'.png'));scene.world=bpy.data.worlds.new('Portrait ambient');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.25,.25,.25,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.4;scene.view_settings.exposure=-1
 bpy.ops.render.render(write_still=True)
 print('PORTRAIT COMPLETE',name,flush=True)
