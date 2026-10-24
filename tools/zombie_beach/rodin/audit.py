"""Measure the supplied Rodin rigs and clips without changing source assets."""
import bpy,bmesh,json,hashlib,struct
import numpy as np
from pathlib import Path
from collections import Counter
ROOT=Path('/Users/donnybystrom/code/Nordic-3D-forest');OUT=ROOT/'output/zombie-beach/rodin-audit-v1';scene=bpy.data.scenes['Rodin_Review_v1']
def arrays(mesh):
    p=np.empty(len(mesh.vertices)*3,np.float64);mesh.vertices.foreach_get('co',p)
    e=np.empty(len(mesh.edges)*2,np.int32);mesh.edges.foreach_get('vertices',e)
    return p.reshape(-1,3),e.reshape(-1,2)
def reg(name):
    if name.startswith('Left') and any(k in name for k in ['Arm','ForeArm','Hand']):return 1
    if name.startswith('Right') and any(k in name for k in ['Arm','ForeArm','Hand']):return 2
    if name.startswith('Left') and any(k in name for k in ['Leg','Foot','Toe']):return 3
    if name.startswith('Right') and any(k in name for k in ['Leg','Foot','Toe']):return 4
    if name in ['Neck','Head']:return 5
    return 0
reports=[]
for mode in ['walking','crawling']:
    rig=bpy.data.objects['Rodin_'+mode+'_Rig'];ob=bpy.data.objects['Rodin_'+mode+'_Mesh'];mesh=ob.data;co,edges=arrays(mesh)
    weights=np.zeros((len(co),len(ob.vertex_groups)),np.float64)
    for v in mesh.vertices:
        for g in v.groups:weights[v.index,g.group]=g.weight
    names=[g.name for g in ob.vertex_groups];labels=np.array([reg(n) for n in names])[weights.argmax(axis=1)]
    rest=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1)
    maximum=np.zeros(len(edges));maximum_ratio=np.ones(len(edges));worst=np.zeros(len(edges),np.int32);samples=[];poses=[]
    action=next(st.action for tr in rig.animation_data.nla_tracks for st in tr.strips)
    for tr in rig.animation_data.nla_tracks:tr.mute=True
    rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0]
    end=round(float(action.frame_range[1]))
    for frame in range(end+1):
        scene.frame_set(frame);graph=bpy.context.evaluated_depsgraph_get();ev=ob.evaluated_get(graph);em=ev.to_mesh();pos,_=arrays(em);ev.to_mesh_clear()
        lengths=np.linalg.norm(pos[edges[:,0]]-pos[edges[:,1]],axis=1);growth=lengths-rest;ratio=lengths/np.maximum(rest,1e-8)
        hit=growth>maximum;worst[hit]=frame;maximum=np.maximum(maximum,growth);maximum_ratio=np.maximum(maximum_ratio,ratio)
        samples.append({'frame':frame,'max_edge_growth_m':float(growth.max()),'edges_growth_over_2cm':int((growth>.02).sum()),'edges_growth_over_5cm':int((growth>.05).sum()),'severe_ratio_over_5_and_growth_over_2cm':int(((ratio>5)&(growth>.02)).sum())})
    rig.animation_data.action=None
    for bone in rig.pose.bones:bone.matrix_basis.identity()
    scene.frame_set(0)
    topology=bmesh.new();topology.from_mesh(mesh);bmesh.ops.remove_doubles(topology,verts=list(topology.verts),dist=1e-6)
    top={'welded_vertices':len(topology.verts),'boundary_edges':sum(e.is_boundary for e in topology.edges),'nonmanifold_edges':sum(not e.is_manifold for e in topology.edges),'loose_vertices':sum(not v.link_faces for v in topology.verts)};topology.free()
    cross={str((a,b)):int((((labels[edges[:,0]]==a)&(labels[edges[:,1]]==b))|((labels[edges[:,0]]==b)&(labels[edges[:,1]]==a))).sum()) for a,b in [(1,3),(2,4),(1,4),(2,3)]}
    def vertex(v):
        ind=np.argsort(weights[v])[-8:][::-1];return {'id':int(v),'rest':co[v].tolist(),'weights':{names[g]:float(weights[v,g]) for g in ind if weights[v,g]>1e-5}}
    peak=np.argsort(maximum)[-50:][::-1]
    report={'mode':mode,'object':ob.name,'action':action.name,'fps':30,'duration_seconds':end/30,'vertices':len(co),'triangles':len(mesh.polygons),'bones':len(rig.data.bones),'height_m':float(np.ptp(co[:,2])),'rest_bounds':{'min':co.min(0).tolist(),'max':co.max(0).tolist()},'weight_sum_range':[float(weights.sum(1).min()),float(weights.sum(1).max())],'influence_counts':dict(Counter((weights>1e-7).sum(1).tolist())),'topology_after_analysis_only_uv_seam_weld':top,'cross_arm_leg_edges':cross,'samples':samples,'max_growth_edges':[{'edge':int(e),'max_growth_m':float(maximum[e]),'max_ratio':float(maximum_ratio[e]),'worst_frame':int(worst[e]),'a':vertex(edges[e,0]),'b':vertex(edges[e,1])} for e in peak]}
    reports.append(report);np.savez_compressed(OUT/(mode+'-measurements.npz'),co=co,edges=edges,weights=weights,names=np.array(names),labels=labels,max_growth=maximum,max_ratio=maximum_ratio,worst=worst)
    print(json.dumps({k:v for k,v in report.items() if k not in ['samples','max_growth_edges']},indent=2));print('peak',report['max_growth_edges'][0])
(OUT/'deformation-audit.json').write_text(json.dumps(reports,indent=2)+'\n')
rw=bpy.data.objects['Rodin_walking_Rig'];rc=bpy.data.objects['Rodin_crawling_Rig']
delta=max(np.abs(np.array(rw.data.bones[name].matrix_local)-np.array(rc.data.bones[name].matrix_local)).max() for name in rw.data.bones.keys())
print('Bind matrices walking/crawling max delta:',float(delta))
