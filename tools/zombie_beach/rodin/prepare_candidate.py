"""Make a reversible, local weight-cleanup candidate; preserve Rodin geometry/UVs."""
import bpy,numpy as np,json
from pathlib import Path
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/rodin-audit-v1');scene=bpy.data.scenes['Rodin_Review_v1'];src=bpy.data.objects['Rodin_walking_Mesh'];rig=bpy.data.objects['Rodin_walking_Rig']
assert not bpy.data.objects.get('Rodin_WeightCandidate')
dw=np.load(OUT/'walking-measurements.npz');dc=np.load(OUT/'crawling-measurements.npz');co=dw['co'];edges=dw['edges'];old=dw['weights'];labels=dw['labels'];n=len(co)
assert np.array_equal(co,dc['co']) and np.allclose(old,dc['weights'])
unique,inv=np.unique(np.round(co,6),axis=0,return_inverse=True);count=np.bincount(inv);uvn=len(unique)
weights=np.stack([np.bincount(inv,weights=old[:,j],minlength=uvn) for j in range(old.shape[1])],axis=1)/count[:,None]
uedges=np.unique(np.sort(inv[edges],axis=1),axis=0);uedges=uedges[uedges[:,0]!=uedges[:,1]]
worst=np.maximum(dw['max_growth'],dc['max_growth']);seed=np.unique(inv[edges[worst>.025]]);seed=seed[(unique[seed,2]>1.20)&(unique[seed,2]<1.60)]
distance=np.full(uvn,99,np.int32);distance[seed]=0
for i in range(1,6):
    vv=np.unique(uedges[(distance[uedges[:,0]]<i)|(distance[uedges[:,1]]<i)]);vv=vv[(unique[vv,2]>1.16)&(unique[vv,2]<1.64)];distance[vv]=np.minimum(distance[vv],i)
mask=distance<5;alpha=np.maximum(0,1-distance/5)*.35
ea=np.concatenate([uedges[:,0],uedges[:,1]]);eb=np.concatenate([uedges[:,1],uedges[:,0]]);counts=np.bincount(ea,minlength=uvn)
for _ in range(24):
    average=np.stack([np.bincount(ea,weights=weights[eb,j],minlength=uvn) for j in range(weights.shape[1])],axis=1)/np.maximum(counts[:,None],1)
    weights[mask]+=alpha[mask,None]*(average[mask]-weights[mask])
new=old.copy();new[mask[inv]]=weights[inv[mask[inv]]]
removed=[]
for i in np.where((new>1e-7).sum(1)>8)[0]:
    order=np.argsort(new[i])[::-1];removed.append(float(new[i,order[8:]].sum()));new[i,order[8:]]=0
new/=new.sum(1,keepdims=True)
changed=np.where(np.abs(new-old).max(1)>1e-5)[0].tolist()
ob=src.copy();ob.data=src.data.copy();ob.name='Rodin_WeightCandidate';scene.collection.objects.link(ob);ob.hide_render=False
for group in ob.vertex_groups:group.remove(changed)
for v in changed:
    for g in np.flatnonzero(new[v]>1e-7):ob.vertex_groups[int(g)].add([v],float(new[v,g]),'REPLACE')
# Morph-free source is retained. These shader controls are review settings only.
material=src.data.materials[0].copy();material.name='Rodin_PBR_Review';ob.data.materials[0]=material
normal=next(node for node in material.node_tree.nodes if node.type=='NORMAL_MAP');normal.inputs['Strength'].default_value=.65
src.hide_render=True;src.hide_set(True);bpy.data.objects['Rodin_crawling_Mesh'].hide_render=True
report={'candidate':ob.name,'changed_source_vertex_ids':changed,'geometry_edited':False,'uv_edited':False,'source_textures_edited':False,'smoothing':{'iterations':24,'factor':.35,'region':'Measured high-strain shoulder/underarm region, with five-ring falloff; coincident UV seam vertices share weights'},'skin_influence_limit':8,'vertices_limited_to_8':len(removed),'max_pruned_weight_mass':max(removed,default=0),'material_review_change':{'normal_strength_original':1,'normal_strength_candidate':.65,'note':'Reduces harsh generated normal detail; adds no new texture information.'}}
(OUT/'candidate-changes.json').write_text(json.dumps(report,indent=2)+'\n');np.savez_compressed(OUT/'candidate-weights.npz',before=old,after=new,changed=changed,vertex_to_welded_analysis=inv)
print('Candidate created; weight edits',len(changed),'max removed influence mass',max(removed,default=0))
