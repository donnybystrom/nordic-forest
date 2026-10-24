"""Matched original/candidate views, including an explicit shoulder stress pose."""
import bpy,numpy as np,json
from pathlib import Path
from mathutils import Vector
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/rodin-audit-v1');s=bpy.data.scenes['Rodin_Review_v1'];rig=bpy.data.objects['Rodin_walking_Rig'];src=bpy.data.objects['Rodin_walking_Mesh'];dst=bpy.data.objects['Rodin_WeightCandidate'];cam=s.camera
walk=next(st.action for tr in rig.animation_data.nla_tracks for st in tr.strips);crig=bpy.data.objects['Rodin_crawling_Rig'];crawl=next(st.action for tr in crig.animation_data.nla_tracks for st in tr.strips)
rows=[];metadata=[]
s.render.resolution_x=640;s.render.resolution_y=900
for label,action,frame in [('walking',walk,20),('crawling',crawl,74),('arms90',None,0)]:
    rig.animation_data.action=action
    if action:rig.animation_data.action_slot=action.slots[0]
    else:
        for p in rig.pose.bones:p.matrix_basis.identity()
        for side,sign in [('Left',1),('Right',-1)]:
            bone=rig.data.bones[side+'Arm'];direction=bone.tail_local-bone.head_local;turn=direction.rotation_difference(Vector((sign,0,0)));rest=bone.matrix_local.to_quaternion();rig.pose.bones[bone.name].rotation_quaternion=rest.inverted()@turn@rest
    s.frame_set(frame)
    if label=='crawling':cam.location=(1,-3,1.5);target=Vector((0,0,.55));cam.data.ortho_scale=2.2
    else:cam.location=(0,-4,1);target=Vector((0,0,.98));cam.data.ortho_scale=2.25
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();pair=[]
    for suffix,shown in [('source',src),('candidate',dst)]:
        for ob in s.objects:
            if ob.type=='MESH':ob.hide_render=ob!=shown
        s.render.filepath=str(OUT/(label+'-'+suffix+'.png'));bpy.ops.render.render(write_still=True)
        image=bpy.data.images.load(s.render.filepath,check_existing=False);pixels=np.empty(640*900*4,np.float32);image.pixels.foreach_get(pixels);pair.append(pixels.reshape(900,640,4));bpy.data.images.remove(image)
    canvas=np.concatenate(pair,axis=1);image=bpy.data.images.new('Rodin_'+label+'_Comparison',width=1280,height=900,alpha=True);image.pixels.foreach_set(canvas.ravel());image.filepath_raw=str(OUT/(label+'-comparison.png'));image.file_format='PNG';image.save();rows.append(canvas);metadata.append({'case':label,'frame':frame,'action':action.name if action else 'Custom symmetric arm abduction to horizontal; no animation'})
canvas=np.concatenate(rows[::-1],axis=0);image=bpy.data.images.new('Rodin_Comparison_Grid',width=1280,height=2700,alpha=True);image.pixels.foreach_set(canvas.ravel());image.filepath_raw=str(OUT/'original-candidate-comparison.png');image.file_format='PNG';image.save()
(OUT/'comparison-poses.json').write_text(json.dumps({'columns':['original PBR','candidate weights + normal strength .65'],'rows_top_to_bottom':metadata},indent=2)+'\n')
print('Rendered walking, crawl and shoulder stress comparisons')
