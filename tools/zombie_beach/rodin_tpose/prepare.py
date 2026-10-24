"""Create an isolated review scene; requires the previous Rodin motion asset.

Creation step for a fresh scene, not an idempotent rerun on an existing review.
"""
import bpy, json
from pathlib import Path
from mathutils import Vector

ROOT=Path('/Users/donnybystrom/code/Nordic-3D-forest');OUT=ROOT/'output/zombie-beach/rodin-tpose-v1';OUT.mkdir(exist_ok=True)
assert not bpy.data.scenes.get('Rodin_TPose_Review_v1')
if not bpy.data.objects.get('Rodin_Working_Rig'):
 with bpy.data.libraries.load(str(ROOT/'assets/models/zombies/rodin-working-v1/Rodin_Working_v1.blend'),link=False) as (available,loaded):
  loaded.objects=['Rodin_v1_Rig']
 loaded.objects[0].name='Rodin_Working_Rig'
scene=bpy.data.scenes.new('Rodin_TPose_Review_v1');scene.render.fps=30;bpy.context.window.scene=scene
source=ROOT/'assets/models/zombies/zombiegirl-rodin2-tshape-source/993bae00-0c2b-4136-888a-dec58539083d'
bpy.ops.import_scene.fbx(filepath=str(source/'lod_basic_pbr.fbx'),use_anim=True)
meshes=sorted([o for o in scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices),reverse=True)
for index,mesh in enumerate(meshes):
 mesh.name='RodinT_Source_LOD'+str(index);mesh.hide_render=index>0;mesh.hide_set(index>0)
rig=bpy.data.objects['Rodin_Working_Rig'].copy();rig.data=rig.data.copy();rig.name='RodinT_Rig';rig.animation_data_clear();scene.collection.objects.link(rig)
for pb in rig.pose.bones:pb.matrix_basis.identity()
for side,sign in [('Left',1),('Right',-1)]:
 bone=rig.data.bones[side+'Arm'];turn=(bone.tail_local-bone.head_local).rotation_difference(Vector((sign,0,0)));rest=bone.matrix_local.to_quaternion()
 rig.pose.bones[bone.name].rotation_quaternion=rest.inverted()@turn@rest
scene.frame_set(0);bpy.context.view_layer.update()
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.view_settings.view_transform='AgX'
scene.render.resolution_percentage=100;scene.world=bpy.data.worlds.new('RodinT_Studio');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.16,.19,.22,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.6
for name,location,power,size in [('Key',(-2,-3,3.5),350,3),('Fill',(2,-1,2),200,2.5),('Rim',(0,2,3),300,2)]:
 data=bpy.data.lights.new('RodinT_'+name,'AREA');data.energy=power;data.shape='DISK';data.size=size
 ob=bpy.data.objects.new(data.name,data);scene.collection.objects.link(ob);ob.location=location;ob.rotation_euler=(Vector((0,0,.95))-ob.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('RodinT_Camera');cam=bpy.data.objects.new('RodinT_Camera',data);scene.collection.objects.link(cam);scene.camera=cam
data.type='ORTHO';data.ortho_scale=2.4;cam.location=(0,-4,.89);cam.rotation_euler=(Vector((0,0,.89))-cam.location).to_track_quat('-Z','Y').to_euler()
print('Prepared new source LODs, T-stance reference rig and studio')
