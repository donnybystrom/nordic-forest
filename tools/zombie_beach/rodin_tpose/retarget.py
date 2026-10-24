"""Bake the existing 13 clips onto the fitted T-pose rig.

The source reference is its posed T stance, not its lowered-arm bind pose.
Using the old bind as reference would incorrectly keep the target arms raised.
"""
import bpy, json, math
import numpy as np
from pathlib import Path
from mathutils import Quaternion

ROOT=Path('/Users/donnybystrom/code/Nordic-3D-forest');OUT=ROOT/'output/zombie-beach/rodin-tpose-v1'
scene=bpy.data.scenes['Rodin_TPose_Review_v1'];bpy.context.window.scene=scene
target=bpy.data.objects['RodinT_Rig'];assert not target.animation_data
template=bpy.data.objects['Rodin_Working_Rig'];source=template.copy();source.data=template.data.copy();source.name='RodinT_Motion_Source';scene.collection.objects.link(source);source.hide_render=True
source.animation_data.action=None
for tr in source.animation_data.nla_tracks:tr.mute=True
report=json.loads((OUT/'rig-report.json').read_text())
canonical={n:Quaternion(q) for n,q in report['canonical_source_global_quaternions'].items()}
names=[b.name for b in target.data.bones];rest={b.name:b.matrix_local.to_quaternion() for b in target.data.bones}
parents={b.name:b.parent.name if b.parent else None for b in target.data.bones}
local={n:(rest[parents[n]].inverted()@rest[n] if parents[n] else rest[n]) for n in names}
sh=source.data.bones['Hips'].head_local.copy();th=target.data.bones['Hips'].head_local.copy();scale=th.z/sh.z
target.animation_data_create();records=[];checks=[]
def addcurve(bag,path,axis,frames,values):
 fc=bag.fcurves.new(data_path=path,index=axis);fc.keyframe_points.add(len(frames));fc.keyframe_points.foreach_set('co',np.stack([frames,values],1).astype(np.float32).ravel())
 for key in fc.keyframe_points:key.interpolation='LINEAR'
 fc.update()
for track in source.animation_data.nla_tracks:
 original=track.strips[0].action;source.animation_data.action=original;source.animation_data.action_slot=original.slots[0]
 last=round(float(original.frame_range[1]));frames=np.arange(last+1,dtype=float)
 qs={n:np.empty((last+1,4)) for n in names};locations=np.empty((last+1,3))
 for i,frame in enumerate(frames):
  scene.frame_set(int(frame));sp=source.evaluated_get(bpy.context.evaluated_depsgraph_get())
  desired={n:sp.pose.bones[n].matrix.to_quaternion()@canonical[n].inverted()@rest[n] for n in names}
  for n in names:
   relative=desired[parents[n]].inverted()@desired[n] if parents[n] else desired[n]
   q=local[n].inverted()@relative;q.normalize()
   if i and np.dot(qs[n][i-1],np.array(q))<0:q.negate()
   qs[n][i]=q
  delta=(sp.pose.bones['Hips'].head-sh)*scale;locations[i]=rest['Hips'].inverted()@delta
  if i in (0,last//4,last//2,3*last//4,last):
   for n in names:target.pose.bones[n].rotation_mode='QUATERNION';target.pose.bones[n].rotation_quaternion=qs[n][i]
   target.pose.bones['Hips'].location=locations[i];bpy.context.view_layer.update();actual=target.evaluated_get(bpy.context.evaluated_depsgraph_get())
   angles=[actual.pose.bones[n].matrix.to_quaternion().rotation_difference(desired[n]).angle*180/math.pi for n in names]
   checks.append({'clip':track.name,'frame':int(frame),'max_rotation_error_degrees':max(min(a,abs(360-a)) for a in angles),'hips_position_error_m':float((actual.pose.bones['Hips'].head-(th+delta)).length)})
 action=bpy.data.actions.new('RodinT_'+track.name);slot=action.slots.new(id_type='OBJECT',name=target.name);layer=action.layers.new('T-pose retarget');st=layer.strips.new(type='KEYFRAME');bag=st.channelbags.new(slot)
 for n in names:
  for axis in range(4):addcurve(bag,'pose.bones['+json.dumps(n)+'].rotation_quaternion',axis,frames,qs[n][:,axis])
 for axis in range(3):addcurve(bag,'pose.bones["Hips"].location',axis,frames,locations[:,axis])
 tr=target.animation_data.nla_tracks.new();tr.name=track.name;strip=tr.strips.new(track.name,0,action);strip.action_slot=slot;tr.mute=True
 records.append({'name':track.name,'duration_seconds':last/30,'source_action':original.name})
source.animation_data.action=None
for arm in (target,source):
 for pb in arm.pose.bones:pb.matrix_basis.identity()
scene.frame_set(0);source.hide_set(True)
result={'status':'baked_candidate','clips':records,'root_translation_scale':scale,
 'reference':'Old Rodin skeleton posed with arms horizontal; the new skeleton has a fitted T-pose bind.',
 'samples':checks,'max_rotation_error_degrees':max(c['max_rotation_error_degrees'] for c in checks),
 'max_hips_error_m':max(c['hips_position_error_m'] for c in checks),
 'limitations':['Clips are sequentially retargeted from the previous Rodin working asset, retaining prior Meshy transfer limitations.',
 'No planted-foot IK, self-collision or balance correction.']}
assert result['max_rotation_error_degrees']<.2 and result['max_hips_error_m']<.0001
(OUT/'retarget-report.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('samples','clips')},indent=2));print('Clips',len(records))
