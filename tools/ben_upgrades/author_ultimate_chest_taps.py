"""Local Blender review only: seven NORMAL forms and chest-tap actions."""
import bpy, math, sys, struct, bisect
from pathlib import Path
from mathutils import Vector, Quaternion, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # Blender does not put the script folder on the path
from ben_upgrade_paths import APP as APP_ROOT, ORIGINALS, REPO, WORK, BLEND, vilgax_dump, ffmpeg
sys.path.insert(0,str(REPO / 'tools'))
from merge_alien_streams import entries, channel_records
from prepare_vilgax_import import table, mesh_buffers, bone_ids
from extract_discord_level_images import untile
from make_hologram_pictures import write_png

root=REPO; out=WORK/'ultimate-chest-tap-review-v8';out.mkdir(parents=True,exist_ok=True)
game=APP_ROOT/'installation/game/global'
forms=[('Humungousaur','hm'),('Swampfire','sf'),('Echo Echo','ec'),('Big Chill','bc'),('Spider Monkey','sm'),('Cannonbolt','cb')]
names={0:'Root',31:'Hips',32:'Spine',33:'Chest',2:'Neck',1:'Head',37:'Clavicle.R',38:'UpperArm.R',39:'Forearm.R',40:'Hand.R',56:'Clavicle.L',57:'UpperArm.L',58:'Forearm.L',59:'Hand.L'}
def co(p):return Vector((p[0],-p[2],p[1]))
def image(r,name):
    magic,fmt,w,h=struct.unpack_from('>IHHH',r);bc1=magic>>28!=0xa and fmt in (0x104,0x11c)
    assert fmt in (0x104,0x11c,0x102,0x11a),(name,fmt)
    log=3 if bc1 else 4;raw=bytearray(untile(r[128:],w//4,h//4,log));raw[0::2],raw[1::2]=raw[1::2],raw[0::2]
    pixels=bytearray(w*h*4)
    for j in range(w*h//16):
        b=raw[j*(1<<log):(j+1)*(1<<log)];c=b if bc1 else b[8:];ca,cz=struct.unpack_from('<2H',c)
        colors=[((v>>11)*255//31,((v>>5)&63)*255//63,(v&31)*255//31) for v in (ca,cz)]
        a,z=colors;colors+= [tuple((2*x+y)//3 for x,y in zip(a,z)),tuple((x+2*y)//3 for x,y in zip(a,z))] if not bc1 or ca>cz else [tuple((x+y)//2 for x,y in zip(a,z)),(0,0,0)]
        ci=int.from_bytes(c[4:8],'little')
        if not bc1:
            a,z=b[:2];al=[a,z]+([((7-i)*a+i*z)//7 for i in range(1,7)] if a>z else [((5-i)*a+i*z)//5 for i in range(1,5)]+[0,255]);ai=int.from_bytes(b[2:8],'little')
        for i in range(16):
            k=(ci>>(2*i))&3;alpha=(0 if ca<=cz and k==3 else 255) if bc1 else al[(ai>>(3*i))&7]
            x=j%(w//4)*4+i%4;y=j//(w//4)*4+i//4;at=(y*w+x)*4;pixels[at:at+4]=bytes((*colors[k],alpha))
    path=out/(name+'.png');write_png(path,w,h,pixels);im=bpy.data.images.load(str(path));im.pack();return im
def model(scene,label,code):
    p=entries((game/f'g_{code}.xbx').read_bytes());key,skin=next(iter(table(p[22]).items()));sk=next(iter(table(p[12]).values()))
    n=struct.unpack_from('>H',sk)[0];rows=[struct.unpack_from('>10fI',sk,12+44*i) for i in range(n)]
    tags=[r[-1]&0xffffff for r in rows];world=[];parents=[]
    for i,r in enumerate(rows):
        par=r[-1]>>24;parents.append(par);loc=Vector(r[4:7]);q=Quaternion((r[3],-r[0],-r[1],-r[2])).normalized()
        local=Matrix.LocRotScale(loc,q,Vector(r[7:10]));world.append(local if par==255 else world[par]@local)
    heads=[co(w.translation) for w in world]
    a=bpy.data.armatures.new(label+' skeleton');rig=bpy.data.objects.new(label+' rig',a);scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    bones=[];preferred={0:31,31:32,32:33,33:2,2:1,37:38,38:39,39:40,56:57,57:58,58:59}
    for i,t in enumerate(tags):
        bone=a.edit_bones.new(names.get(t,f'Bone_{t:03}'));bone.head=heads[i]
        child=preferred.get(t);candidates=[j for j,par in enumerate(parents) if par==i and (heads[j]-heads[i]).length>.001]
        j=tags.index(child) if child in tags and parents[tags.index(child)]==i else (candidates[0] if candidates else None)
        bone.tail=heads[j] if j is not None else heads[i]+Vector((0,0,.08))
        if (bone.tail-bone.head).length<.001:bone.tail=bone.head+Vector((0,0,.08))
        if parents[i]!=255:bone.parent=bones[parents[i]]
        bones.append(bone)
    bpy.ops.object.mode_set(mode='OBJECT')
    for i,t in enumerate(tags):
        b=a.bones[names.get(t,f'Bone_{t:03}')];b['game_bone_id']=t;b['game_bone_index']=i
    mesh=table(p[4])[key];at,v,idx=mesh_buffers(mesh,True);verts=list(struct.iter_unpack('>11f',v));indices=struct.unpack('>'+str(len(idx)//2)+'H',idx);textures=table(p[0]);ranges=[]
    for pos in range(376,at-32,4):
        word=struct.unpack_from('>I',mesh,pos)[0];tex=struct.unpack_from('>I',mesh,pos+28)[0]
        if word&31!=2 or tex not in textures:continue
        start,count=struct.unpack_from('>HH',mesh,pos+6)
        if count and start+count<=len(indices) and count%3==0:ranges.append((start,count,tex))
    if not ranges:
        tex=next((struct.unpack_from('>I',mesh,pos+8)[0] for pos in range(396,at-15,16) if struct.unpack_from('>I',mesh,pos)[0]==1 and struct.unpack_from('>I',mesh,pos+8)[0] in textures),next(iter(textures)))
        ranges=[(0,len(indices),tex)]
    geometry=bpy.data.meshes.new(label+' original model');faces=[];slots=[];materials=[]
    for i,(start,count,tex) in enumerate(ranges):
        mat=bpy.data.materials.new(label+f' {tex:08x}');mat.use_nodes=True;nodes=mat.node_tree.nodes;t=nodes.new('ShaderNodeTexImage');t.image=image(textures[tex],f'{code}_{tex:08x}')
        mat.node_tree.links.new(t.outputs['Color'],nodes['Principled BSDF'].inputs['Base Color']);materials.append(mat)
        for ind in range(start,start+count,3):
            f=indices[ind:ind+3]
            if len(set(f))==3:faces.append(f);slots.append(i)
    correction=Matrix.Rotation(math.pi/2,3,'Z') if code=='sf' else Matrix.Identity(3)
    geometry.from_pydata([correction@co(v[:3]) for v in verts],[],faces)
    for mat in materials:geometry.materials.append(mat)
    uv=geometry.uv_layers.new(name='Native UV')
    for poly,i in zip(geometry.polygons,slots):
        poly.material_index=i;poly.use_smooth=True
        for l in poly.loop_indices:
            u,v=verts[geometry.loops[l].vertex_index][9:];uv.data[l].uv=(u,1-v)
    obj=bpy.data.objects.new(label+' normal form',geometry);scene.collection.objects.link(obj)
    groups=[obj.vertex_groups.new(name=names.get(t,f'Bone_{t:03}')) for t in tags]
    assert len(verts)==(len(skin)-80)//52
    for i in range(len(verts)):
        o=80+52*i;ws=skin[o+44:o+48];ids=skin[o+48:o+52];total=sum(ws)
        for j,w in zip(ids,ws):
            if w:groups[j].add([i],w/total,'REPLACE')
    obj.parent=rig;mod=obj.modifiers.new('Native skin','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=True
    # Cannonbolt has a separately skinned ball in the same mesh. Hide that
    # branch in the normal standing preview (without modifying the model).
    if code=='cb':
        ball=next(b for b in rig.pose.bones if b.bone.get('game_bone_id')==193);ball.scale=(0,0,0)
    return rig,obj,p,sk

def idle_pose(rig,package,sk,tick=0):
    rows=[struct.unpack_from('>10fI',sk,12+44*i) for i in range(struct.unpack_from('>H',sk)[0])]
    tags=[r[-1]&0xffffff for r in rows];lookup={b.bone.get('game_bone_id'):b for b in rig.pose.bones}
    clips=table(package[13]);idle=next((c for c in clips.values() if c.startswith(b'idle_01\0') and set(bone_ids(c))==set(tags)),None)
    if idle is None:raise ValueError('Missing matching idle')
    ids=bone_ids(idle);channels=channel_records(package[9]);bind=[];posed=[]
    C=Matrix(((1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)))
    for i,r in enumerate(rows):
        par=r[-1]>>24;tag=tags[i];q=Quaternion((r[3],-r[0],-r[1],-r[2])).normalized();p=Vector(r[4:7]);s=Vector(r[7:10]);local=Matrix.LocRotScale(p,q,s)
        bind.append(local if par==255 else bind[par]@local)
        a,b,c=struct.unpack_from('>3I',idle,216+12*ids.index(tag))
        def sample(index,rotation=False):
            data=channels[index]
            if rotation:
                keys=[(t*160,Quaternion((w/127,-x/32767,-y/32767,-z/32767)).normalized()) for x,y,z,w,t in struct.iter_unpack('>3hbB',data[8:])]
            else:keys=[(t,Vector((x,y,z))) for t,x,y,z in struct.iter_unpack('>4f',data[8:])]
            j=bisect.bisect_right([t for t,v in keys],tick)
            if j==0:return keys[0][1]
            if j==len(keys):return keys[-1][1]
            t0,v0=keys[j-1];t1,v1=keys[j];u=(tick-t0)/(t1-t0)
            return v0.slerp(v1,u) if rotation else v0.lerp(v1,u)
        if a!=0xffffffff:p=sample(a)
        if b!=0xffffffff:
            q=sample(b,True)
        if c!=0xffffffff:s=sample(c)
        local=Matrix.LocRotScale(p,q,s);posed.append(local if par==255 else posed[par]@local)
        bone=lookup[tag];bone.matrix=C@posed[i]@bind[i].inverted()@C.inverted()@bone.bone.matrix_local
        bpy.context.view_layer.update()
    return True

def aim(bone,direction,child=None):
    # Rotate current world-space bone axis to desired direction.
    axis=((child.head if child else bone.tail)-bone.head).normalized();q=axis.rotation_difference(direction.normalized())
    current=bone.matrix.copy();rot=q.to_matrix().to_4x4();rot.translation=bone.head
    current.translation=(0,0,0);bone.matrix=rot@current
    bpy.context.view_layer.update()

def animate(scene,rig,obj,label,package,sk):
    lookup={b.bone.get('game_bone_id'):b for b in rig.pose.bones}
    arm,fore,hand=(lookup[x] for x in (38,39,40))
    idle_pose(rig,package,sk,960);bpy.context.view_layer.update()
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());points=[v.co.copy() for v in evaluated.data.vertices]
    lo=Vector(tuple(min(p[i] for p in points) for i in range(3)));hi=Vector(tuple(max(p[i] for p in points) for i in range(3)));height=hi.z-lo.z
    # Native front is -Y. Locate chest surface by intersecting the rendered
    # mesh at upper-torso height. Keep the palm slightly in front of it.
    chest=lookup.get(33,lookup[32]).head.copy()
    z=chest.z+(lookup[2].head.z-chest.z)*.36 if 2 in lookup else chest.z
    if label=='Cannonbolt':z=lo.z+height*.43
    if label=='Spider Monkey':z=lo.z+height*.70
    if label=='Swampfire':z+=height*.035
    tree=BVHTree.FromPolygons(points,[tuple(p.vertices) for p in obj.data.polygons],all_triangles=True)
    target,_,_,_=tree.ray_cast(Vector((0,lo.y-height,z)),Vector((0,1,0)))
    if target is None:target=Vector((0,lo.y,z))
    precise=label in ('Swampfire','Spider Monkey','Way Big')
    if label=='Swampfire':
        target,_,_,_=tree.ray_cast(Vector((.108,lo.y-height,1.597)),Vector((0,1,0)))
    elif label=='Way Big':
        target,_,_,_=tree.ray_cast(Vector((.081,lo.y-height,1.635)),Vector((0,1,0)))
    elif label=='Spider Monkey':
        raw=[v.co.copy() for v in obj.data.vertices]
        faces=[tuple(p.vertices) for p in obj.data.polygons]
        rest_tree=BVHTree.FromPolygons(raw,faces,all_triangles=True)
        hit,_,idx,_=rest_tree.ray_cast(Vector((0,-2,.837)),Vector((0,1,0)))
        assert hit is not None
        tri=faces[idx];target=barycentric_transform(hit,*(raw[i] for i in tri),*(points[i] for i in tri))
    assert target is not None
    # Analytic two-bone IK solved and baked as FK keys; no auxiliary rig
    # constraints survive, making it suitable for later native export.
    L=(fore.head-arm.head).length;M=(hand.head-fore.head).length
    assert L>0 and M>0
    side=1 if arm.head.x>0 else -1
    rest= {b.name:b.matrix_basis.copy() for b in rig.pose.bones}
    # Tap with fingers/palm directed toward chest; wrist is forward of badge.
    # Keep fingertips pointed across the chest, with the palm face toward it.
    hand_group=obj.vertex_groups.get(hand.name)
    palm=[v.co.copy() for v in evaluated.data.vertices if any(g.group==hand_group.index and g.weight>.7 for g in obj.data.vertices[v.index].groups)] if hand_group else []
    center=sum(palm,Vector())/len(palm) if palm else hand.head+Vector((0,0,-height*.07))
    palm_offset=center-hand.head
    finger_direction=Vector((-side,.35,.05)).normalized()
    if precise:
        finger_direction=Vector((-side*.60,.20,-.77)).normalized()
        palm_local=hand.matrix.inverted()@center
    wrist=target-finger_direction*palm_offset.length+Vector((0,-height*.025,0))
    flat=label in ('Swampfire','Way Big')
    if flat:
        # Fit the open native palm, not the wrist, to the badge. Use the
        # rest-pose hand geometry and native finger bases as anatomical axes.
        rb=hand.bone.matrix_local; rh=hand.bone.head_local
        finger_bases=[lookup[t].bone.head_local for t in (44,47,50) if t in lookup]
        longitudinal=(sum(finger_bases,Vector())/len(finger_bases)-rh).normalized()
        thumb=lookup[41].bone.head_local-rh; across=(thumb-longitudinal*thumb.dot(longitudinal)).normalized()
        source_axes=Matrix((longitudinal,across,longitudinal.cross(across))).transposed()
        raw_palm=[v.co.copy() for v in obj.data.vertices if any(g.group==hand_group.index and g.weight>.7 for g in v.groups)]
        knuckles=sum(finger_bases,Vector())/len(finger_bases)-rh
        palm_rest=(sum(raw_palm,Vector())/len(raw_palm)-rh).lerp(knuckles,.40)
        # Search feasible elbow bends for a nearly straight wrist while the
        # palm lies flat on the chest, with fingers extended across it.
        best=None;s=arm.head.copy();contact=target+Vector((0,-height*.026,0))
        for degrees in range(-40,46,5):
            a=math.radians(degrees);direction=Vector((-side*math.cos(a),0,math.sin(a)))
            up=Vector((0,0,1));up=(up-direction*up.dot(direction)).normalized()
            rotation=Matrix((direction,up,direction.cross(up))).transposed()@source_axes.transposed()
            w=contact-rotation@palm_rest;delta=w-s;d=delta.length
            if not abs(L-M)+.001<d<L+M-.002:continue
            k=delta.normalized();along=(L*L-M*M+d*d)/(2*d);radius=math.sqrt(max(0,L*L-along*along))
            u=Vector((0,-1,0));u=(u-k*u.dot(k)).normalized();v=k.cross(u)
            for angle in range(0,360,5):
                e=s+k*along+radius*(u*math.cos(math.radians(angle))+v*math.sin(math.radians(angle)))
                alignment=(w-e).normalized().dot(direction)
                # Elbow should remain on its own side and in front of torso.
                score=alignment-3*max(0,-side*(e.x-target.x))-3*max(0,e.y-target.y-height*.07)-.12*abs(e.z-w.z)/height-1.5*max(0,e.z-s.z)/height
                if best is None or score>best[0]:best=(score,w,e,rotation,direction)
        assert best is not None
        _,wrist,flat_elbow,flat_rotation,finger_direction=best
        flat_hand=(flat_rotation@rb.to_3x3()).to_4x4()
        print(label,'flat palm wrist alignment',round((wrist-flat_elbow).normalized().dot(finger_direction),3),flush=True)
    shoulder=arm.head.copy()
    relaxed=hand.head.copy()
    ready=wrist+Vector((side*height*.11,-height*.13,height*.11))
    for frame,goal in [(f,None) for f in range(1,8)]+[(15,ready),(21,wrist),(25,wrist),(31,ready),(42,None)]:
        scene.frame_set(frame)
        for b in rig.pose.bones:b.matrix_basis=rest[b.name]
        if frame<=7:idle_pose(rig,package,sk,(frame-1)*160)
        bpy.context.view_layer.update()
        if goal is not None:
            s=arm.head.copy();delta=goal-s;d=max(abs(L-M)+.001,min(delta.length,L+M-.002));direction=delta.normalized()
            x=(L*L-M*M+d*d)/(2*d);bend=math.sqrt(max(0,L*L-x*x))
            pole=Vector((side,-.15,-.65));pole=(pole-direction*pole.dot(direction)).normalized()
            elbow=s+direction*x+pole*bend
            if flat and frame in (21,25):elbow=flat_elbow
            aim(arm,elbow-s,fore);aim(fore,s+direction*d-fore.head,hand)
            # Rotate around the wrist, preserving native idle fingers and lengths.
            original=rest[hand.name];hand.matrix_basis=original;bpy.context.view_layer.update()
            # Palm direction is tracked using the wrist-to-finger-base chain.
            fingers=[b for b in hand.children if (b.head-hand.head).length>.001]
            if flat:
                orientation=flat_hand.copy();orientation.translation=hand.head;hand.matrix=orientation
                # Unlike idle fists, restore the native open fingers. Keep
                # fingertips extended along each digit's first segment.
                for digit in hand.children_recursive:digit.matrix_basis=Matrix.Identity(4)
                bpy.context.view_layer.update()
                for t in (44,47,50):
                    digit=lookup.get(t);tip=lookup.get(t+1)
                    if digit and tip and tip.children:
                        aim(tip,tip.head-digit.head)
                bpy.context.view_layer.update()
            elif precise:
                offset=hand.matrix@palm_local-hand.head
                q=offset.normalized().rotation_difference(finger_direction)
                current=hand.matrix.copy();rot=q.to_matrix().to_4x4();rot.translation=hand.head;current.translation=(0,0,0);hand.matrix=rot@current
                bpy.context.view_layer.update()
            elif fingers:
                finger=max(fingers,key=lambda b:(b.head-hand.head).length)
                aim(hand,finger_direction,finger)
        for b in rig.pose.bones:
            b.rotation_mode='QUATERNION';b.keyframe_insert('rotation_quaternion',frame=frame,group=b.name);b.keyframe_insert('location',frame=frame,group=b.name);b.keyframe_insert('scale',frame=frame,group=b.name)
    action=rig.animation_data.action;action.name=label+' | Ultimatrix chest tap (normal form)';action.use_fake_user=True
    scene.frame_start=1;scene.frame_end=42;scene.render.fps=30
    for fr,name in ((1,'Ready'),(15,'Reach'),(21,'Press Ultimatrix'),(25,'Hold'),(42,'Recover')):scene.timeline_markers.new(name,frame=fr)
    scene['review_only']=True;scene['badge_target']=tuple(target)
    scene.frame_set(21)
    camera=bpy.data.objects.new(label+' review camera',bpy.data.cameras.new(label+' review camera'));scene.collection.objects.link(camera);center=(lo+hi)*.5
    camera.location=center+Vector((height*.38,-height*2.7,height*.18));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=max(height*1.25,(hi.x-lo.x)*1.15*560/448);scene.camera=camera
    scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=448;scene.render.resolution_y=560;scene.render.resolution_percentage=100
    scene.display.shading.color_type='TEXTURE';scene.display.shading.light='STUDIO';scene.display.shading.show_shadows=True
    scene.render.filepath=str(out/(label.replace(' ','-')+'-press.png'));bpy.ops.render.render(write_still=True)
    scene.frame_set(1)
    print(label,'action',action.name,'target',tuple(target),flush=True)

# Existing native normal Way Big rig is the seventh form.
bpy.ops.wm.open_mainfile(filepath=str(BLEND/'Way-Big-Native-Rig.blend'))
scene=bpy.context.scene;scene.name='07 | Way Big'
rig=next(o for o in scene.objects if o.type=='ARMATURE');obj=next(o for o in scene.objects if o.type=='MESH')
rig.animation_data_clear()
for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
way=entries((ORIGINALS/'l_tokd/g_wayb.xbx').read_bytes());way_sk=table(entries((ORIGINALS/'l_tokd/l_tokd.xbx').read_bytes())[12])[0x64ea483a]
idle_pose(rig,way,way_sk)
animate(scene,rig,obj,'Way Big',way,way_sk)
for i,(label,code) in enumerate(forms,1):
    scene=bpy.data.scenes.new(f'{i:02} | {label}');bpy.context.window.scene=scene
    rig,obj,p,sk=model(scene,label,code);animate(scene,rig,obj,label,p,sk)
bpy.context.window.scene=bpy.data.scenes['01 | Humungousaur']
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='SOLID'
            area.spaces.active.shading.color_type='TEXTURE'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Ultimate-Transformation-Review.blend'))
print('Saved all seven normal forms and their actions.',flush=True)
