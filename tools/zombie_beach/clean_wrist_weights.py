"""Remove anatomically distant forearm influence from distal palms/fingers."""
import bpy,numpy as np,json
from pathlib import Path
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1')
ob=bpy.data.objects['ZB_Repaired_Mesh'];rig=bpy.data.objects['ZB_Source_Rig'];m=ob.data
co=np.array([v.co for v in m.vertices]);weights=np.zeros((len(co),len(ob.vertex_groups)),np.float32)
for v in m.vertices:
    for g in v.groups:weights[v.index,g.group]=g.weight
original=weights.copy();details=[]
for side in ('Left','Right'):
    fore='mixamorig:'+side+'ForeArm';hand='mixamorig:'+side+'Hand';idx=ob.vertex_groups[fore].index
    elbow=np.array(rig.data.bones[fore].head_local);wrist=np.array(rig.data.bones[hand].head_local);axis=(wrist-elbow)/np.linalg.norm(wrist-elbow)
    beyond=(co-wrist)@axis
    factor=1-np.clip(beyond/0.035,0,1)
    weights[:,idx]*=factor
weights/=np.maximum(weights.sum(axis=1,keepdims=True),1e-12)
changed=np.flatnonzero(np.abs(weights-original).max(axis=1)>1e-6).tolist()
for g in ob.vertex_groups:g.remove(changed)
for v in changed:
    for g in np.flatnonzero(weights[v]>1e-7):ob.vertex_groups[int(g)].add([v],float(weights[v,g]),'REPLACE')
report=json.loads((OUT/'repair-changes.json').read_text());report['wrist_weight_cleanup']={'rule':'Forearm influence fades to zero over 35mm beyond its wrist joint in rest pose','changed_candidate_vertex_ids':changed};(OUT/'repair-changes.json').write_text(json.dumps(report,indent=2)+'\n')
print('Corrected distal wrist weights:',len(changed),'vertices')
