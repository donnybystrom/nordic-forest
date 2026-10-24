"""Locally smooth finger-shaped generation remnants on rebuilt thigh contacts."""
import bpy,json,numpy as np
from pathlib import Path
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1')
ob=bpy.data.objects['ZB_Repaired_Mesh'];m=ob.data
n=len(m.vertices);co=np.empty(n*3,np.float64);m.vertices.foreach_get('co',co);co=co.reshape(-1,3);original=co.copy()
edges=np.empty(len(m.edges)*2,np.int32);m.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
labels=np.array([a.value for a in m.attributes['anatomical_region'].data]);fid=np.array([a.value for a in m.attributes['source_face_id'].data])
patchverts=np.unique(np.concatenate([np.array(p.vertices) for p in m.polygons if fid[p.index]==-1 and all(labels[v] in (3,4) for v in p.vertices)]))
distance=np.full(n,100,np.int32);distance[patchverts]=0
for i in range(1,17):
    touched=(distance[edges[:,0]]<i)|(distance[edges[:,1]]<i)
    vv=np.unique(edges[touched]);vv=vv[np.isin(labels[vv],[3,4])];distance[vv]=np.minimum(distance[vv],i)
mask=(distance<16)&np.isin(labels,[3,4]);alpha=np.maximum(0,1-distance/16)**2*0.6
ea=np.concatenate([edges[:,0],edges[:,1]]);eb=np.concatenate([edges[:,1],edges[:,0]]);counts=np.bincount(ea,minlength=n)
for iteration in range(160):
    average=np.stack([np.bincount(ea,weights=co[eb,j],minlength=n) for j in range(3)],axis=1)/np.maximum(counts[:,None],1)
    co[mask]+=alpha[mask,None]*(average[mask]-co[mask])
shift=np.linalg.norm(co-original,axis=1)
m.vertices.foreach_set('co',co.ravel());m.update()
report=json.loads((OUT/'repair-changes.json').read_text());report['thigh_surface_smoothing']={'iterations':160,'region':'Only geodesic neighborhoods of rebuilt thigh contact patches; hands untouched','moved_vertices':int((shift>1e-6).sum()),'max_displacement_m':float(shift.max()),'p95_displacement_m':float(np.percentile(shift[shift>1e-6],95)),'vertex_ids':np.flatnonzero(shift>1e-6).tolist()};(OUT/'repair-changes.json').write_text(json.dumps(report,indent=2)+'\n')
np.savez_compressed(OUT/'thigh-surface-displacements.npz',before=original,after=co,distance_rings=distance)
print({k:v for k,v in report['thigh_surface_smoothing'].items() if k!='vertex_ids'})
