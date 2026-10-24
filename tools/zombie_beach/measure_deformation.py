"""Read-only mesh/animation measurements in the isolated ZombieRepair_v1 scene."""
import json
from pathlib import Path
from collections import Counter
import bpy
import numpy as np

OUT = Path('/Users/donnybystrom/code/Nordic-3D-forest/output/zombie-beach/mesh-repair-v1')
scene = bpy.data.scenes['ZombieRepair_v1']
prefix = globals().get('MEASURE_PREFIX', 'source')
obj = bpy.data.objects[globals().get('MEASURE_OBJECT', 'ZB_Source_Mesh')]
rig = bpy.data.objects['ZB_Source_Rig']
mesh = obj.data
assert obj.name in scene.objects and obj.parent == rig
if prefix == 'source':
    assert len(mesh.vertices) == 57964, 'Unexpected source mesh; refuse to measure another object'
scene.frame_set(0)
bpy.context.view_layer.update()
co = np.empty(len(mesh.vertices)*3, np.float64)
mesh.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
edges = np.empty(len(mesh.edges)*2, np.int32)
mesh.edges.foreach_get('vertices', edges)
edges = edges.reshape(-1, 2)
tri = np.array([tuple(p.vertices) for p in mesh.polygons], np.int32)
weights = np.zeros((len(co), len(obj.vertex_groups)), np.float32)
for v in mesh.vertices:
    for g in v.groups:
        weights[v.index, g.group] = g.weight
names = [g.name for g in obj.vertex_groups]

def region(name):
    if 'Left' in name and any(k in name for k in ('Arm','Hand','Thumb','Index','Middle','Ring','Pinky')): return 1
    if 'Right' in name and any(k in name for k in ('Arm','Hand','Thumb','Index','Middle','Ring','Pinky')): return 2
    if 'Left' in name and any(k in name for k in ('Leg','Foot','Toe')): return 3
    if 'Right' in name and any(k in name for k in ('Leg','Foot','Toe')): return 4
    if any(k in name for k in ('Head','Neck','headfront')): return 5
    return 0

regions = np.array([region(n) for n in names])
rw = np.stack([weights[:, regions == i].sum(axis=1) for i in range(6)], axis=1)
labels = rw.argmax(axis=1)
restlen = np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1)
max_ratio = np.ones(len(edges));max_growth=np.zeros(len(edges));worst_sample=np.zeros(len(edges),np.int32)
samples=[]; clip_report=[]; sample_id=0
actions = []
for track in rig.animation_data.nla_tracks:
    for strip in track.strips:
        if strip.action not in actions: actions.append(strip.action)
    track.mute=True
for a in actions:
    rig.animation_data.action=a
    rig.animation_data.action_slot=a.slots[0]
    lo,hi=map(float,a.frame_range)
    report={'action':a.name,'duration_seconds':(hi-lo)/scene.render.fps,'samples':[]}
    frames = sorted(set([lo,hi]+list(np.arange(np.ceil(lo),hi,1)))) if globals().get('SAMPLE_EVERY_FRAME',False) else np.linspace(lo,hi,17)
    for frame in frames:
        scene.frame_set(int(frame),subframe=float(frame%1))
        graph=bpy.context.evaluated_depsgraph_get()
        evaluated=obj.evaluated_get(graph)
        em=evaluated.to_mesh()
        xyz=np.empty(len(em.vertices)*3,np.float64);em.vertices.foreach_get('co',xyz);xyz=xyz.reshape(-1,3)
        evaluated.to_mesh_clear()
        lengths=np.linalg.norm(xyz[edges[:,0]]-xyz[edges[:,1]],axis=1)
        ratio=lengths/np.maximum(restlen,1e-8)
        growth=lengths-restlen
        improved=growth>max_growth
        max_growth=np.maximum(max_growth,growth)
        max_ratio=np.maximum(max_ratio,ratio)
        worst_sample[improved]=sample_id
        rec={'id':sample_id,'action':a.name,'frame':float(frame),'max_edge_length':float(lengths.max()),'edges_growth_over_2cm':int((growth>0.02).sum()),'edges_growth_over_5cm':int((growth>0.05).sum()),'edges_ratio_over_5_and_growth_over_2cm':int(((ratio>5)&(growth>0.02)).sum())}
        samples.append(rec);report['samples'].append(rec);sample_id+=1
    clip_report.append(report)
rig.animation_data.action=None
for pose in rig.pose.bones:pose.matrix_basis.identity()
scene.frame_set(0)
counts=Counter(tuple(sorted((int(labels[a]),int(labels[b])))) for a,b in edges[(labels[edges[:,0]]!=labels[edges[:,1]])])
top=np.argsort(max_growth)[-160:][::-1]
def vrec(i):
    topw=np.argsort(weights[i])[-4:][::-1]
    return {'vertex':int(i),'rest':co[i].tolist(),'weights':{names[g]:float(weights[i,g]) for g in topw if weights[i,g]>0.0001}}
result={'vertices':len(co),'triangles':len(tri),'edges':len(edges),'rest_bounds':{'min':co.min(axis=0).tolist(),'max':co.max(axis=0).tolist()},'matrix_world':[list(r) for r in obj.matrix_world],'region_names':['torso','left_arm','right_arm','left_leg','right_leg','head'],'region_vertices':np.bincount(labels,minlength=6).tolist(),'cross_region_edges':{str(k):v for k,v in counts.items()},'weight_sums':{'min':float(weights.sum(axis=1).min()),'max':float(weights.sum(axis=1).max())},'unique_rest_positions_1um':len(np.unique(np.round(co,6),axis=0)),'clips':clip_report,'top_growth_edges':[{'edge':int(e),'rest_length':float(restlen[e]),'max_growth':float(max_growth[e]),'max_ratio':float(max_ratio[e]),'sample':samples[int(worst_sample[e])],'a':vrec(edges[e,0]),'b':vrec(edges[e,1])} for e in top]}
np.savez_compressed(OUT/(prefix+'-measurements.npz'),co=co,edges=edges,tri=tri,weights=weights,weight_names=np.array(names),region_weights=rw,labels=labels,max_ratio=max_ratio,max_growth=max_growth,worst_sample=worst_sample)
(OUT/(prefix+'-deformation-audit.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'vertices':len(co),'triangles':len(tri),'samples':len(samples),'bounds':result['rest_bounds'],'cross_region_edges':result['cross_region_edges'],'top_edges':result['top_growth_edges'][:2]},indent=2))
