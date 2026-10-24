"""Render original Rodin PBR assets under neutral, consistent studio lighting."""
import bpy
from mathutils import Vector
from pathlib import Path
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/rodin-audit-v1');s=bpy.data.scenes['Rodin_Review_v1'];bpy.context.window.scene=s
s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True;s.render.resolution_x=768;s.render.resolution_y=1024;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.view_settings.view_transform='AgX'
s.world=bpy.data.worlds.new('Rodin_Studio_World');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.16,.19,.22,1);s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.6
for name,loc,power,size in [('Key',(-2,-3,3.5),350,3),('Fill',(2,-1,2),200,2.5),('Rim',(0,2,3),300,2)]:
    data=bpy.data.lights.new('Rodin_'+name,'AREA');data.energy=power;data.shape='DISK';data.size=size;ob=bpy.data.objects.new('Rodin_'+name,data);s.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((0,0,.95))-ob.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Rodin_Studio_Camera');cam=bpy.data.objects.new('Rodin_Studio_Camera',data);s.collection.objects.link(cam);s.camera=cam;data.type='ORTHO';data.ortho_scale=2.2;cam.location=(0,-4,.98);cam.rotation_euler=(Vector((0,0,.98))-cam.location).to_track_quat('-Z','Y').to_euler()
for mode in ['walking','crawling']:
    rig=bpy.data.objects['Rodin_'+mode+'_Rig'];mesh=bpy.data.objects['Rodin_'+mode+'_Mesh'];other=bpy.data.objects['Rodin_'+('crawling' if mode=='walking' else 'walking')+'_Mesh'];mesh.hide_render=False;other.hide_render=True
    action=next(st.action for tr in rig.animation_data.nla_tracks for st in tr.strips)
    if mode=='walking':
        rig.animation_data.action=None
        for bone in rig.pose.bones:bone.matrix_basis.identity()
        s.frame_set(0);s.render.filepath=str(OUT/'rodin-pbr-rest.png');bpy.ops.render.render(write_still=True)
    rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0];s.frame_set(20 if mode=='walking' else 55)
    if mode=='crawling':
        cam.location=(1,-3,1.5);cam.rotation_euler=(Vector((0,0,.55))-cam.location).to_track_quat('-Z','Y').to_euler();data.ortho_scale=2.2
    s.render.filepath=str(OUT/('rodin-pbr-'+mode+'.png'));bpy.ops.render.render(write_still=True)
print('Rendered PBR rest, walking and crawling')
