"""Extract measured target motion for later procedural-control experiments.

This produces reference targets, not a balance controller or verified contacts.
"""
import bpy,json,re,math
import numpy as np
from pathlib import Path
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1')
scene=bpy.data.scenes['ZB_Deliverable_v1'];rig=bpy.data.objects['Beachside_Revenant_Rig'];bpy.context.window.scene=scene
names=['Hips','Spine','Spine1','Spine2','Neck','Head','LeftShoulder','RightShoulder','LeftArm','RightArm','LeftForeArm','RightForeArm','LeftHand','RightHand','LeftUpLeg','RightUpLeg','LeftLeg','RightLeg','LeftFoot','RightFoot','LeftToeBase','RightToeBase'];names=['mixamorig:'+n for n in names]
anchors=['mixamorig:'+n for n in ['Hips','Head','LeftHand','RightHand','LeftFoot','RightFoot','LeftToeBase','RightToeBase']]
clips=[];summary=[]
def intervals(mask,times):
    result=[];start=None
    for i,on in enumerate(list(mask)+[False]):
        if on and start is None:start=i
        elif not on and start is not None:result.append([float(times[start]),float(times[i-1])]);start=None
    return result
for track in rig.animation_data.nla_tracks:
    track.mute=True
for track in rig.animation_data.nla_tracks:
    action=track.strips[0].action;rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0]
    end=round(float(action.frame_range[1]));times=np.arange(end+1)/30
    positions=[];rotations=[];hips_positions=[]
    for frame in range(end+1):
        scene.frame_set(frame)
        hips=rig.matrix_world@rig.pose.bones['mixamorig:Hips'].head
        positions.append([[round(float(v),6) for v in ((rig.matrix_world@rig.pose.bones[name].head)-hips)] for name in anchors])
        rotations.append([[round(float(v),7) for v in rig.pose.bones[name].matrix_basis.to_quaternion()] for name in names])
        hips_positions.append([round(float(v),6) for v in hips])
    contact={}
    for side in ['Left','Right']:
        foot_i=anchors.index('mixamorig:'+side+'Foot');toe_i=anchors.index('mixamorig:'+side+'ToeBase')
        ground=np.minimum(np.array(positions)[:,foot_i,2],np.array(positions)[:,toe_i,2])+np.array(hips_positions)[:,2]
        contact[side]={'height_threshold_m':float(ground.min()+.02),'candidate_intervals_seconds':intervals(ground<ground.min()+.02,times)}
    a=np.array(rotations);dot=np.minimum(1,np.abs((a[0]*a[-1]).sum(axis=1)));closure=2*np.arccos(dot)*180/math.pi
    entry={'name':track.name,'duration_seconds':end/30,'fps':30,'times_seconds':np.round(times,7).tolist(),'hips_world_positions_m':hips_positions,'anchor_positions_relative_to_hips_m':positions,'local_delta_quaternions_wxyz':rotations,'height_only_contact_candidates':contact,'endpoint_rotation_difference_degrees_mean':float(closure.mean()),'endpoint_rotation_difference_degrees_max':float(closure.max())}
    clips.append(entry);summary.append({k:entry[k] for k in ['name','duration_seconds','endpoint_rotation_difference_degrees_mean','endpoint_rotation_difference_degrees_max','height_only_contact_candidates']})
result={'schema_version':1,'status':'measured_reference_targets_only','coordinates':'Blender right-handed Z-up, meters; convert to Godot Y-up in a future adapter','quaternion_order':'w,x,y,z; local delta relative to each bone rest transform','bones':names,'anchor_order':anchors,'clips':clips,'limitations':['Height-only contacts are candidates, not confirmed planted feet or support constraints.','UUID animation names remain unchanged; inspect poses before assigning a locomotion state.','A procedural controller still needs phase control, contact planning, IK/PD constraints, damage rules and balance recovery.','No procedural locomotion or active ragdoll has been implemented by this extraction.']}
(OUT/'motion-targets.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
(OUT/'motion-summary.json').write_text(json.dumps({'status':result['status'],'coordinates':result['coordinates'],'clips':summary,'limitations':result['limitations']},indent=2)+'\n')
rig.animation_data.action=None
for bone in rig.pose.bones:bone.matrix_basis.identity()
scene.frame_set(0);bpy.context.window.scene=bpy.data.scenes['ZombieRepair_v1']
print('Extracted',sum(len(c['times_seconds']) for c in clips),'pose targets from',len(clips),'clips')
