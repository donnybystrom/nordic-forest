"""Fit a Mixamo-named 52-bone prototype to the new, unrigged T-pose source.

Anatomical landmarks are reviewable initial placements, not a claimed automatic
anatomy reconstruction. Finger endpoints come from surface geodesic extrema.
"""
import bpy, json
import numpy as np
from pathlib import Path
from mathutils import Vector

ROOT=Path('/Users/donnybystrom/code/Nordic-3D-forest')
OUT=ROOT/'output/zombie-beach/rodin-tpose-v1'
scene=bpy.data.scenes['Rodin_TPose_Review_v1'];bpy.context.window.scene=scene
rig=bpy.data.objects['RodinT_Rig'];src=bpy.data.objects['RodinT_Source_LOD0']
assert not bpy.data.objects.get('RodinT_Working_Mesh')
canonical={p.name:list(p.matrix.to_quaternion()) for p in rig.pose.bones}
center=(min((src.matrix_world@v.co).x for v in src.data.vertices)+max((src.matrix_world@v.co).x for v in src.data.vertices))/2
mesh=src.copy();mesh.data=src.data.copy();mesh.name='RodinT_Working_Mesh';scene.collection.objects.link(mesh)
for v in mesh.data.vertices:v.co=src.matrix_world@v.co-Vector((center,0,0))
mesh.matrix_world.identity();mesh.data.update()
for ob in bpy.context.selected_objects:ob.select_set(False)
rig.hide_set(False);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='POSE');bpy.ops.pose.armature_apply(selected=False);bpy.ops.object.mode_set(mode='EDIT')
points={
 'Hips':((-.007,-.027,1.00),(-.007,-.030,1.08)),
 'Spine':((-.007,-.030,1.08),(-.007,-.030,1.18)),
 'Spine1':((-.007,-.030,1.18),(-.004,-.005,1.29)),
 'Spine2':((-.004,-.005,1.29),(-.002,.010,1.41)),
 'Neck':((-.002,.010,1.44),(0,-.010,1.53)),
 'Head':((0,-.010,1.53),(0,-.025,1.70))}
tips={1:{'Thumb':(.77046,-.21424,1.46642),'Index':(.82111,-.20017,1.41676),
 'Middle':(.82358,-.19019,1.39007),'Ring':(.80614,-.18229,1.36920),'Pinky':(.77926,-.16390,1.35341)},
 -1:{'Thumb':(-.77236,-.21684,1.47162),'Index':(-.82690,-.20131,1.42225),
 'Middle':(-.82218,-.19308,1.39125),'Ring':(-.80190,-.18810,1.37411),'Pinky':(-.77083,-.17694,1.35980)}}
for side,sign in [('Left',1),('Right',-1)]:
 def v(x,y,z):return (x*sign,y,z)
 points.update({side+'Shoulder':(v(.04,.013,1.413),v(.167,.007,1.411)),
  side+'Arm':(v(.167,.007,1.411),v(.406,-.036,1.401)),
  side+'ForeArm':(v(.406,-.036,1.401),v(.650,-.119,1.412)),
  side+'Hand':(v(.650,-.119,1.412),v(.713,-.149,1.411)),
  side+'UpLeg':(v(.095,-.022,.96),v(.112,-.065,.525)),
  side+'Leg':(v(.112,-.065,.525),v(.170,-.025,.103)),
  side+'Foot':(v(.170,-.025,.103),v(.175,-.140,.030)),
  side+'ToeBase':(v(.175,-.140,.030),v(.175,-.205,.025))})
 bases={'Thumb':v(.695,-.155,1.434),'Index':v(.735,-.166,1.423),
  'Middle':v(.735,-.159,1.403),'Ring':v(.726,-.150,1.389),'Pinky':v(.710,-.143,1.378)}
 for finger in bases:
  base=Vector(bases[finger]);tip=Vector(tips[sign][finger]);tip-=.002*(tip-base).normalized()
  for i,(a,b) in enumerate([(0,.45),(.45,.75),(.75,1)],1):
   points[side+'Hand'+finger+str(i)]=(base.lerp(tip,a),base.lerp(tip,b))
assert set(points)==set(rig.data.edit_bones.keys())
for bone in rig.data.edit_bones:bone.use_connect=False
for name,(head,tail) in points.items():
 bone=rig.data.edit_bones[name];bone.head=head;bone.tail=tail;bone.use_deform=True
bpy.ops.object.mode_set(mode='OBJECT')
for bone in rig.pose.bones:bone.matrix_basis.identity()
for ob in bpy.context.selected_objects:ob.select_set(False)
mesh.hide_set(False);mesh.hide_render=False;mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
assert any(m.type=='ARMATURE' and m.object==rig for m in mesh.modifiers)
weights=np.zeros((len(mesh.data.vertices),len(mesh.vertex_groups)))
for vert in mesh.data.vertices:
 for group in vert.groups:weights[vert.index,group.group]=group.weight
assert np.all(weights.sum(1)>.00001), np.where(weights.sum(1)<=.00001)[0].tolist()
pruned=[]
for i,row in enumerate(weights):
 order=np.argsort(row)[::-1];pruned.append(float(row[order[8:]].sum()));row[order[8:]]=0;row/=row.sum()
indices=list(range(len(mesh.data.vertices)))
for group in mesh.vertex_groups:group.remove(indices)
for i,row in enumerate(weights):
 for j in np.flatnonzero(row>0):mesh.vertex_groups[int(j)].add([i],float(row[j]),'REPLACE')
mat=src.data.materials[0].copy();mat.name='RodinT_PBR_v1';mesh.data.materials[0]=mat
for node in mat.node_tree.nodes:
 if node.type=='NORMAL_MAP':node.inputs['Strength'].default_value=.65
 if node.type=='TEX_IMAGE' and node.image:
  node.image.pack()
src.hide_render=True;src.hide_set(True)
np.savez_compressed(OUT/'bind-weights.npz',weights=weights,labels=np.array([g.name for g in mesh.vertex_groups]),co=np.array([v.co[:] for v in mesh.data.vertices]))
report={'status':'initial_auto_weight_rig','rig':rig.name,'mesh':mesh.name,'bones':len(rig.data.bones),
 'source_x_offset_removed_m':center,'height_m':float(mesh.dimensions.z),'weight_method':'Blender bone heat after manually specified landmark fit',
 'max_influences':8,'max_pruned_weight_mass':max(pruned),'unweighted_vertices':0,
 'canonical_source_global_quaternions':canonical,
 'landmarks':{n:{'head':list(h),'tail':list(t)} for n,(h,t) in points.items()},
 'limitations':['Initial finger placements and heat weights require pose review.','No secondary physics, corrective morphs or contact IK.']}
(OUT/'rig-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('canonical_source_global_quaternions','landmarks')},indent=2))
