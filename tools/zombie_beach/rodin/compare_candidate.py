"""Measure source and candidate in the same poses on the identical Rodin rig."""
import bpy,numpy as np,json
from pathlib import Path
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/rodin-audit-v1');s=bpy.data.scenes['Rodin_Review_v1'];rig=bpy.data.objects['Rodin_walking_Rig'];src=bpy.data.objects['Rodin_walking_Mesh'];dst=bpy.data.objects['Rodin_WeightCandidate']
assert len(src.data.vertices)==len(dst.data.vertices)
clips=[]
for mode in ('walking','crawling'):
    source_rig=bpy.data.objects['Rodin_'+mode+'_Rig'];action=next(st.action for tr in source_rig.animation_data.nla_tracks for st in tr.strips);rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0]
    source=np.load(OUT/(mode+'-measurements.npz'));rest=source['co'];edges=source['edges'];restlength=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1);samples=[];max_growth=np.zeros(len(edges));worst=np.zeros(len(edges),np.int32)
    for frame in range(round(action.frame_range[1])+1):
        s.frame_set(frame);ev=dst.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();xyz=np.empty(len(m.vertices)*3,np.float64);m.vertices.foreach_get('co',xyz);xyz=xyz.reshape(-1,3);ev.to_mesh_clear()
        lengths=np.linalg.norm(xyz[edges[:,0]]-xyz[edges[:,1]],axis=1);growth=lengths-restlength;ratio=lengths/np.maximum(restlength,1e-8);hit=growth>max_growth;worst[hit]=frame;max_growth=np.maximum(max_growth,growth)
        samples.append({'frame':frame,'max_edge_growth_m':float(growth.max()),'edges_growth_over_5cm':int((growth>.05).sum()),'severe_ratio_over_5_and_growth_over_2cm':int(((ratio>5)&(growth>.02)).sum())})
    clips.append({'mode':mode,'action':action.name,'source_max_growth_m':float(source['max_growth'].max()),'candidate_max_growth_m':float(max_growth.max()),'candidate_worst_frame':int(worst[max_growth.argmax()]),'samples':samples})
rig.animation_data.action=None
for bone in rig.pose.bones:bone.matrix_basis.identity()
s.frame_set(0)
(OUT/'candidate-comparison.json').write_text(json.dumps(clips,indent=2)+'\n');print(json.dumps([{k:v for k,v in c.items() if k!='samples'} for c in clips],indent=2))
