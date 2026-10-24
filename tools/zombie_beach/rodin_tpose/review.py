"""Measure skin deformation over every baked frame and render selected cases."""
import bpy, json
import numpy as np
from pathlib import Path
from mathutils import Vector

ROOT=Path('/Users/donnybystrom/code/Nordic-3D-forest');OUT=ROOT/'output/zombie-beach/rodin-tpose-v1'
s=bpy.data.scenes['Rodin_TPose_Review_v1'];bpy.context.window.scene=s
rig=bpy.data.objects['RodinT_Rig'];mesh=bpy.data.objects['RodinT_Working_Mesh'];cam=s.camera
co=np.array([v.co[:] for v in mesh.data.vertices]);edges=np.array([e.vertices[:] for e in mesh.data.edges]);length=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1)
actions={tr.name:tr.strips[0].action for tr in rig.animation_data.nla_tracks}
metrics=[];worst=np.zeros(len(edges))
for name,action in actions.items():
 rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0];peak=0;worstframe=0
 for frame in range(round(float(action.frame_range[1]))+1):
  s.frame_set(frame);ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());em=ev.to_mesh();a=np.empty(len(em.vertices)*3);em.vertices.foreach_get('co',a);a=a.reshape(-1,3);ev.to_mesh_clear()
  growth=np.linalg.norm(a[edges[:,0]]-a[edges[:,1]],axis=1)-length;worst=np.maximum(worst,growth)
  if growth.max()>peak:peak=float(growth.max());worstframe=frame
 metrics.append({'clip':name,'frames':round(float(action.frame_range[1]))+1,'max_edge_growth_m':peak,'worst_frame':worstframe})
np.savez_compressed(OUT/'deformation-measurements.npz',co=co,edges=edges,max_growth=worst)
top=np.argsort(worst)[-20:][::-1]
report={'clips':metrics,'frames_evaluated':sum(m['frames'] for m in metrics),'worst_edges':[{'vertex_ids':edges[i].tolist(),'rest_midpoint':co[edges[i]].mean(0).tolist(),'growth_m':float(worst[i])} for i in top],
 'limitations':['Edge strain is a diagnostic, not an anatomical or collision certificate.']}
(OUT/'deformation-report.json').write_text(json.dumps(report,indent=2)+'\n')
renders=[]
for label,name,frame in [('rest',None,0),('meshy-walk','Meshy_Unsteady_Walk',34),('rodin-crawl','Rodin_HumanZombieCrawl',74)]:
 rig.animation_data.action=actions[name] if name else None
 if name:rig.animation_data.action_slot=actions[name].slots[0]
 else:
  for pb in rig.pose.bones:pb.matrix_basis.identity()
 s.frame_set(frame)
 if name and 'Crawl' in name:
  ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());em=ev.to_mesh()
  points=np.array([ev.matrix_world@v.co for v in em.vertices]);ev.to_mesh_clear()
  target=Vector((points.min(0)+points.max(0))/2)
  cam.location=target+Vector((1.2,-3,1.8));cam.data.ortho_scale=2.0
 else:
  target=Vector((0,0,.89));cam.location=target+Vector((.9 if name else 0,-4,.05));cam.data.ortho_scale=2.4 if not name else 2.0
 cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
 s.render.resolution_x=1200 if not name else (1100 if 'Crawl' in name else 768)
 s.render.resolution_y=1000 if not name else (800 if 'Crawl' in name else 1024)
 s.render.filepath=str(OUT/('rodint-'+label+'.png'));bpy.ops.render.render(write_still=True);renders.append({'name':label,'clip':name,'frame':frame})
(OUT/'preview-poses.json').write_text(json.dumps(renders,indent=2)+'\n')
print(json.dumps({'frames_evaluated':report['frames_evaluated'],'clips':metrics,'worst_edges':report['worst_edges'][:3]},indent=2))
