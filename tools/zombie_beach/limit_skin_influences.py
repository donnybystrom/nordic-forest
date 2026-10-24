"""Match Blender deformation to an explicit GLB skin influence limit."""
import bpy,numpy as np,json
from pathlib import Path
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1')
ob=bpy.data.objects['ZB_Repaired_Mesh'];updates=[];lost=[]
maximum=globals().get('MAX_INFLUENCES',8)
for v in ob.data.vertices:
    entries=sorted([(g.group,g.weight) for g in v.groups if g.weight>1e-7],key=lambda item:-item[1])
    if len(entries)>maximum:
        kept=entries[:maximum];total=sum(w for _,w in kept);updates.append((v.index,[(g,w/total) for g,w in kept]));lost.append(sum(w for _,w in entries[maximum:]))
indices=[i for i,_ in updates]
for group in ob.vertex_groups:group.remove(indices)
for i,entries in updates:
    for g,w in entries:ob.vertex_groups[g].add([i],float(w),'REPLACE')
report=json.loads((OUT/'repair-changes.json').read_text());report['skin_influence_limit']={'maximum':maximum,'vertices_pruned':len(updates),'max_removed_weight_mass':max(lost,default=0),'p95_removed_weight_mass':float(np.percentile(lost,95)) if lost else 0};(OUT/'repair-changes.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['skin_influence_limit'])
