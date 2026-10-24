"""Studio review setup confined to the repair scene."""
import bpy
from mathutils import Vector
scene=bpy.data.scenes['ZombieRepair_v1']
assert bpy.context.scene == scene
scene.render.engine='CYCLES'
scene.cycles.samples=16
scene.cycles.use_denoising=True
scene.render.resolution_x=768
scene.render.resolution_y=1024
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world=bpy.data.worlds.new('ZB_Review_World')
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.16,0.19,0.22,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.6
scene.view_settings.view_transform='AgX'
for name,loc,power,size in [('Key',(-2,-3,3.5),350,3),('Fill',(2,-1,2),200,2.5),('Rim',(0,2,3),300,2)]:
    data=bpy.data.lights.new('ZB_'+name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    ob=bpy.data.objects.new('ZB_'+name,data);scene.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((0,0,0.9))-ob.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('ZB_Review_Camera');cam=bpy.data.objects.new('ZB_Review_Camera',data);scene.collection.objects.link(cam);data.type='ORTHO';data.ortho_scale=1.9
cam.location=(0,-4,0.86);cam.rotation_euler=(Vector((0,0,0.86))-cam.location).to_track_quat('-Z','Y').to_euler();scene.camera=cam
scene.render.filepath='/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1/source-rest-front.png'
bpy.ops.render.render(write_still=True)
print('Review render saved',scene.render.filepath)
