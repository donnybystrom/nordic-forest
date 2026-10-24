"""Smooth only residual high-strain shoulder/underarm weight transitions."""
import bpy,numpy as np,json
from pathlib import Path
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1')
ob=bpy.data.objects['ZB_Repaired_Mesh'];m=ob.data;d=np.load(OUT/'repaired-measurements.npz')
edges=d['edges'];co=d['co'];n=len(co);weights=d['weights'].copy();original=weights.copy();labels=d['labels']
seed=np.unique(edges[d['max_growth']>0.025]);seed=seed[(co[seed,2]>1.06)&(co[seed,2]<1.4)&np.isin(labels[seed],[0,1,2])]
distance=np.full(n,99,np.int32);distance[seed]=0
for i in range(1,5):
    vv=np.unique(edges[(distance[edges[:,0]]<i)|(distance[edges[:,1]]<i)]);vv=vv[(co[vv,2]>1.04)&(co[vv,2]<1.43)];distance[vv]=np.minimum(distance[vv],i)
mask=distance<4;alpha=np.maximum(0,1-distance/4)*0.35
ea=np.concatenate([edges[:,0],edges[:,1]]);eb=np.concatenate([edges[:,1],edges[:,0]]);counts=np.bincount(ea,minlength=n)
for _ in range(18):
    average=np.stack([np.bincount(ea,weights=weights[eb,j],minlength=n) for j in range(weights.shape[1])],axis=1)/np.maximum(counts[:,None],1)
    weights[mask]+=alpha[mask,None]*(average[mask]-weights[mask])
weights/=np.maximum(weights.sum(axis=1,keepdims=True),1e-12)
changed=np.flatnonzero(np.abs(weights-original).max(axis=1)>1e-5).tolist()
for group in ob.vertex_groups:group.remove(changed)
for v in changed:
    for g in np.flatnonzero(weights[v]>1e-7):ob.vertex_groups[int(g)].add([v],float(weights[v,g]),'REPLACE')
report=json.loads((OUT/'repair-changes.json').read_text());report['shoulder_weight_smoothing']={'iterations':18,'seed':'Sampled edges growing >25mm, only z=1.06..1.4m shoulder/underarm region','changed_candidate_vertex_ids':changed};(OUT/'repair-changes.json').write_text(json.dumps(report,indent=2)+'\n')
print('Smoothed shoulder/underarm weights:',len(changed),'vertices')
