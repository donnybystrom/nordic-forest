"""Transfer Meshy motion onto Rodin's own rest skeleton, keeping its bone lengths.

Global rotation deltas are transferred through rest-space conversion. Only the
hips translation is transferred, scaled by rest hip height. This is an offline
retarget candidate, not foot IK, self-collision handling or a balance solver.
"""
import bpy,json,re,math
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion
ROOT=Path('/Users/donnybystrom/code/Nordic-3D-forest');OUT=ROOT/'output/zombie-beach/rodin-audit-v1'
scene=bpy.data.scenes['Rodin_Review_v1'];bpy.context.window.scene=scene
source_template=bpy.data.objects['ZB_Source_Rig'];target_template=bpy.data.objects['Rodin_walking_Rig']
assert len(source_template.data.bones)==66 and len(target_template.data.bones)==52
assert not bpy.data.objects.get('Rodin_Working_Rig')
source=source_template.copy();source.data=source_template.data.copy();source.name='Rodin_MeshyMotion_Source';scene.collection.objects.link(source);source.hide_render=True
for tr in source.animation_data.nla_tracks:tr.mute=True
target=target_template.copy();target.data=target_template.data.copy();target.name='Rodin_Working_Rig';target.animation_data_clear();scene.collection.objects.link(target);target.animation_data_create()
for pb in target.pose.bones:pb.matrix_basis.identity()
mesh=bpy.data.objects['Rodin_WeightCandidate'].copy();mesh.data=mesh.data.copy();mesh.name='Rodin_Working_Mesh';mesh.parent=target;scene.collection.objects.link(mesh)
for modifier in mesh.modifiers:
    if modifier.type=='ARMATURE':modifier.object=target
names=[b.name for b in target.data.bones];mapping={n:'mixamorig:'+n for n in names};assert all(v in source.data.bones for v in mapping.values())
source_rest={n:source.data.bones[mapping[n]].matrix_local.to_quaternion() for n in names}
target_rest={n:target.data.bones[n].matrix_local.to_quaternion() for n in names}
parents={b.name:b.parent.name if b.parent else None for b in target.data.bones}
local_rest={n:(target_rest[parents[n]].inverted()@target_rest[n] if parents[n] else target_rest[n]) for n in names}
source_hips=source.data.bones['mixamorig:Hips'].head_local.copy();target_hips=target.data.bones['Hips'].head_local.copy();scale=target_hips.z/source_hips.z
action_records=[];validation=[]
def curves(action):
    slot=action.slots.new(id_type='OBJECT',name=target.name);layer=action.layers.new('Baked retarget');strip=layer.strips.new(type='KEYFRAME');return slot,strip.channelbags.new(slot)
def addcurve(bag,path,index,frames,values):
    curve=bag.fcurves.new(data_path=path,index=index);curve.keyframe_points.add(len(frames));points=np.stack([frames,values],axis=1).astype(np.float32).ravel();curve.keyframe_points.foreach_set('co',points)
    for key in curve.keyframe_points:key.interpolation='LINEAR'
    curve.update()
for track in source.animation_data.nla_tracks:
    original=track.strips[0].action;base=re.sub(r'\.\d{3}$','',original.name);source.animation_data.action=original;source.animation_data.action_slot=original.slots[0]
    duration=float(original.frame_range[1])/24;last=round(duration*30);frames=np.arange(last+1,dtype=float);qs={n:np.zeros((last+1,4),np.float64) for n in names};locations=np.zeros((last+1,3),np.float64)
    for i,frame in enumerate(frames):
        sf=frame*24/30;scene.frame_set(int(sf),subframe=float(sf%1));graph=bpy.context.evaluated_depsgraph_get();sp=source.evaluated_get(graph)
        desired={n:sp.pose.bones[mapping[n]].matrix.to_quaternion()@source_rest[n].inverted()@target_rest[n] for n in names}
        for n in names:
            parent=parents[n];relative=desired[parent].inverted()@desired[n] if parent else desired[n];q=local_rest[n].inverted()@relative;q.normalize()
            if i and np.dot(qs[n][i-1],np.array(q))<0:q.negate()
            qs[n][i]=q
        delta=(sp.pose.bones['mixamorig:Hips'].head-source_hips)*scale;locations[i]=target_rest['Hips'].inverted()@delta
        if i in (0,last//4,last//2,3*last//4,last):
            for n in names:target.pose.bones[n].rotation_mode='QUATERNION';target.pose.bones[n].rotation_quaternion=qs[n][i]
            target.pose.bones['Hips'].location=locations[i];bpy.context.view_layer.update()
            actual=target.evaluated_get(bpy.context.evaluated_depsgraph_get());angles=[actual.pose.bones[n].matrix.to_quaternion().rotation_difference(desired[n]).angle*180/math.pi for n in names]
            angles=[min(a,abs(360-a)) for a in angles]
            root_error=(actual.pose.bones['Hips'].head-(target_hips+delta)).length
            validation.append({'clip':base,'frame_30fps':int(frame),'max_global_rotation_error_degrees':max(angles),'hips_position_error_m':root_error})
    action=bpy.data.actions.new('Rodin_Meshy_'+base);slot,bag=curves(action)
    for n in names:
        path='pose.bones['+json.dumps(n)+'].rotation_quaternion'
        for axis in range(4):addcurve(bag,path,axis,frames,qs[n][:,axis])
    for axis in range(3):addcurve(bag,'pose.bones["Hips"].location',axis,frames,locations[:,axis])
    tr=target.animation_data.nla_tracks.new();tr.name='Meshy_'+base;strip=tr.strips.new(tr.name,0,action);strip.action_slot=slot;tr.mute=True
    action_records.append({'name':tr.name,'source_action':original.name,'duration_seconds':last/30,'frames':last+1})
for mode in ('walking','crawling'):
    rig=bpy.data.objects['Rodin_'+mode+'_Rig'];original=next(st.action for tr in rig.animation_data.nla_tracks for st in tr.strips);action=original.copy();action.name='Rodin_Native_'+original.name;tr=target.animation_data.nla_tracks.new();tr.name='Rodin_'+original.name;st=tr.strips.new(tr.name,0,action);st.action_slot=action.slots[0];tr.mute=True;action_records.append({'name':tr.name,'source_action':original.name,'duration_seconds':float(original.frame_range[1])/30,'frames':round(float(original.frame_range[1]))+1})
source.animation_data.action=None
for ob in (source,target):
    for pb in ob.pose.bones:pb.matrix_basis.identity()
scene.frame_set(0)
report={'status':'retarget_candidate','source_skeleton_bones':66,'target_skeleton_bones':52,'mapped_target_bones':len(mapping),'mapping':mapping,'source_fps':24,'target_fps':30,'root_translation_scale':scale,'method':'Rest-corrected model-space rotation deltas, target rest bone lengths retained; hips translation scaled by hip height ratio','clips':action_records,'math_validation_samples':validation,'max_rotation_error_degrees':max(r['max_global_rotation_error_degrees'] for r in validation),'max_hips_error_m':max(r['hips_position_error_m'] for r in validation),'limitations':['Mathematical transform agreement does not certify foot planting, self-collision-free movement or anatomical deformation.','No animation events, gameplay state machine or semantic labels are inferred for UUID clips.','No runtime procedural physics or jiggle has been added by this transfer.']}
assert report['max_rotation_error_degrees']<.2,report['max_rotation_error_degrees'];assert report['max_hips_error_m']<.0001
(OUT/'retarget-report.json').write_text(json.dumps(report,indent=2)+'\n')
for ob in scene.objects:
    if ob.type=='MESH':ob.hide_render=ob!=mesh;ob.hide_set(ob!=mesh)
source.hide_set(True);target_template.hide_set(True);bpy.data.objects['Rodin_crawling_Rig'].hide_set(True)
print(json.dumps({k:v for k,v in report.items() if k not in ['mapping','math_validation_samples','clips']},indent=2));print('Clips:',[r['name'] for r in action_records])
