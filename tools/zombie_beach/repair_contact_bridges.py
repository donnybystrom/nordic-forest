"""Conservative candidate repair of measured arm/thigh contact bridges.

Operates only on a copy; original vertex/face IDs are saved before topology edits.
"""
import bpy,bmesh,json
import numpy as np
from pathlib import Path
OUT=Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1')
scene=bpy.data.scenes['ZombieRepair_v1'];src=bpy.data.objects['ZB_Source_Mesh'];rig=bpy.data.objects['ZB_Source_Rig']
assert src.name in scene.objects and len(src.data.vertices)==57964
assert not bpy.data.objects.get('ZB_Repaired_Mesh'), 'Candidate already exists'
d=np.load(OUT/'source-measurements.npz');co=d['co'];tri=d['tri'];rw=d['region_weights'];weights=d['weights'];names=list(d['weight_names']);labels=d['labels']
owner=labels.copy();changed=[]
ob=src.copy();ob.data=src.data.copy();ob.name='ZB_Repaired_Mesh';scene.collection.objects.link(ob)
def region(name):
    if 'Left' in name and any(k in name for k in ('Arm','Hand','Thumb','Index','Middle','Ring','Pinky')): return 1
    if 'Right' in name and any(k in name for k in ('Arm','Hand','Thumb','Index','Middle','Ring','Pinky')): return 2
    if 'Left' in name and any(k in name for k in ('Leg','Foot','Toe')): return 3
    if 'Right' in name and any(k in name for k in ('Leg','Foot','Toe')): return 4
    if any(k in name for k in ('Head','Neck','headfront')): return 5
    return 0
br=np.array([region(n) for n in names]);new_weights=weights.copy()
for arm,leg in [(1,3),(2,4)]:
    # These branches are never anatomical neighbors. Remove even weak nonlocal
    # influence, while retaining ordinary arm/torso and leg/pelvis blending.
    affected=np.where(((labels==arm)|(labels==leg))&(rw[:,arm]>1e-6)&(rw[:,leg]>1e-6))[0]
    for v in affected:
        forbidden=leg if labels[v]==arm else arm
        new_weights[v,br==forbidden]=0
        new_weights[v]/=max(float(new_weights[v].sum()),1e-12)
        changed.append(int(v))
hips=names.index('mixamorig:Hips')
for arm in (1,2):
    affected=np.where((labels==arm)&(new_weights[:,hips]>1e-7))[0]
    new_weights[affected,hips]=0
for arm in (1,2):
    affected=np.where((labels==0)&(co[:,2]<1.05)&(rw[:,arm]>1e-7))[0]
    new_weights[np.ix_(affected,np.where(br==arm)[0])]=0
new_weights/=np.maximum(new_weights.sum(axis=1,keepdims=True),1e-12)
changed=np.where(np.abs(new_weights-weights).max(axis=1)>1e-6)[0].tolist()
for group in ob.vertex_groups:
    group.remove(changed)
for v in changed:
    for g in np.flatnonzero(new_weights[v]>1e-7):ob.vertex_groups[int(g)].add([v],float(new_weights[v,g]),'REPLACE')
assert max(abs(sum(g.weight for g in ob.data.vertices[v].groups)-1) for v in changed)<1e-5
fl=labels[tri]
cut=np.zeros(len(tri),bool)
for arm,leg in [(1,3),(2,4)]:cut|=(fl==arm).any(axis=1)&(fl==leg).any(axis=1)
bm=bmesh.new();bm.from_mesh(ob.data);bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
vl=bm.verts.layers.int.new('source_vertex_id');rl=bm.verts.layers.int.new('anatomical_region');fid=bm.faces.layers.int.new('source_face_id')
for v in bm.verts:v[vl]=v.index;v[rl]=int(labels[v.index])
for f in bm.faces:f[fid]=f.index
# Weld coincident vertices only within the same semantic region. UVs remain
# per-corner, so this joins export seams without collapsing the separated limbs.
for reg in range(6):
    vv=[v for v in bm.verts if v[rl]==reg]
    if vv:bmesh.ops.remove_doubles(bm,verts=vv,dist=0.000001)
bm.faces.ensure_lookup_table()
removed=[f for f in bm.faces if cut[f[fid]]]
removed_set=set(removed)
border={e for f in removed for e in f.edges if any(g not in removed_set for g in e.link_faces)}
preexisting=sum(e.is_boundary for e in bm.edges)
bmesh.ops.delete(bm,geom=removed,context='FACES')
border=[e for e in border if e.is_valid and e.is_boundary]
from collections import Counter
degree=Counter(v for e in border for v in e.verts)
info={'input_vertices':len(co),'input_triangles':len(tri),'weight_changed_source_vertex_ids':changed,'removed_source_face_ids':np.where(cut)[0].tolist(),'preexisting_boundary_edges_after_uv_weld':preexisting,'new_cut_boundary_edges':len(border),'cut_boundary_degrees':dict(Counter(degree.values()))}
# Inspect the new boundaries before selecting a closure method.
bm.to_mesh(ob.data);bm.free();ob.data.update()
src.hide_render=True;src.hide_set(True)
rig.animation_data.action=None
for p in rig.pose.bones:p.matrix_basis.identity()
scene.frame_set(0);bpy.context.view_layer.update()
info.update({'candidate_vertices':len(ob.data.vertices),'candidate_triangles':len(ob.data.polygons),'status':'cut_candidate_not_capped_yet'})
(OUT/'repair-changes.json').write_text(json.dumps(info,indent=2)+'\n')
print(json.dumps({k:v if not isinstance(v,list) else len(v) for k,v in info.items()},indent=2))
