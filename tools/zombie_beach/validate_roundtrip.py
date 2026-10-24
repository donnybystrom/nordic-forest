"""Validate GLB structure, durations, topology and evaluated skinned poses."""
import bpy,bmesh,json,struct,re
import numpy as np
from pathlib import Path
from mathutils.kdtree import KDTree
ROOT=Path('/Users/donnybystrom/code/Nordic-3D-forest');OUT=ROOT/'output/zombie-beach/mesh-repair-v1';path=ROOT/'assets/models/zombies/repaired-v1/Beachside_Revenant_Repaired_v1-Mixamo.glb'
raw=path.read_bytes();length=struct.unpack_from('<I',raw,12)[0];gltf=json.loads(raw[20:20+length]);manifest=json.loads((OUT/'deliverable-manifest.json').read_text())
assert len(gltf['scenes'])==1 and len(gltf['meshes'])==1 and len(gltf['skins'])==1
assert len(gltf['animations'])==11 and len(gltf['skins'][0]['joints'])==66
source={clip['name']:clip['duration_seconds'] for clip in manifest['clips']}
durations={a['name']:max(gltf['accessors'][sampler['input']]['max'][0] for sampler in a['samplers']) for a in gltf['animations']}
duration_errors={name:abs(source[name]-durations[name]) for name in source}
assert max(duration_errors.values())<2e-5, duration_errors
master_scene=bpy.data.scenes['ZB_Deliverable_v1'];master_rig=bpy.data.objects['Beachside_Revenant_Rig'];master_mesh=bpy.data.objects['Beachside_Revenant_Repaired']
bm=bmesh.new();bm.from_mesh(master_mesh.data)
topology={'vertices':len(bm.verts),'edges':len(bm.edges),'triangles':len(bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'loose_vertices':sum(not v.link_faces for v in bm.verts)};bm.free()
assert topology['boundary_edges']==0 and topology['nonmanifold_edges']==0 and topology['loose_vertices']==0
assert not master_mesh.data.validate(verbose=True,clean_customdata=False)
validation=bpy.data.scenes.new('ZB_Roundtrip_Validation');validation.render.fps=30;bpy.context.window.scene=validation
bpy.ops.import_scene.gltf(filepath=str(path))
rig=next(o for o in validation.objects if o.type=='ARMATURE');mesh=next(o for o in validation.objects if o.type=='MESH')
def actions(arm):
    return {re.sub(r'\.\d{3}$','',strip.action.name).removeprefix('ZB_v1_'):strip.action for track in arm.animation_data.nla_tracks for strip in track.strips}
ma=actions(master_rig);ra=actions(rig)
assert set(ma)==set(ra)==set(source),(ma.keys(),ra.keys())
for arm in (rig,master_rig):
    arm.animation_data.action=None
    for track in arm.animation_data.nla_tracks:track.mute=True
    for bone in arm.pose.bones:bone.matrix_basis.identity()
tree=KDTree(len(master_mesh.data.vertices))
for vertex in master_mesh.data.vertices:tree.insert(vertex.co,vertex.index)
tree.balance();mapping=[];rest_errors=[]
for vertex in mesh.data.vertices:
    _,index,distance=tree.find(vertex.co);mapping.append(index);rest_errors.append(distance)
mapping=np.array(mapping,np.int32)
assert max(rest_errors)<1e-5,max(rest_errors)
def evaluated_coordinates(scene,ob,frame):
    bpy.context.window.scene=scene;scene.frame_set(int(frame),subframe=float(frame%1));graph=bpy.context.evaluated_depsgraph_get();ev=ob.evaluated_get(graph);em=ev.to_mesh();xyz=np.empty(len(em.vertices)*3,np.float64);em.vertices.foreach_get('co',xyz);xyz=xyz.reshape(-1,3);ev.to_mesh_clear();return xyz
samples=[]
for name in source:
    master_rig.animation_data.action=ma[name];master_rig.animation_data.action_slot=ma[name].slots[0]
    rig.animation_data.action=ra[name];rig.animation_data.action_slot=ra[name].slots[0]
    for phase in (0,.25,.5,.75,1):
        frame=source[name]*30*phase
        original=evaluated_coordinates(master_scene,master_mesh,frame);imported=evaluated_coordinates(validation,mesh,frame)
        err=np.linalg.norm(original[mapping]-imported,axis=1)
        samples.append({'animation':name,'phase':phase,'max_vertex_error_m':float(err.max()),'mean_vertex_error_m':float(err.mean())})
max_error=max(s['max_vertex_error_m'] for s in samples)
assert max_error<0.002, max_error
report={'status':'pass','glb_scenes':len(gltf['scenes']),'glb_meshes':len(gltf['meshes']),'clips':len(source),'bones':66,'duration_errors_seconds':duration_errors,'topology_before_export':topology,'rest_mapping_max_error_m':max(rest_errors),'roundtrip_pose_samples':samples,'roundtrip_pose_max_error_m':max_error,'source_vertices':len(master_mesh.data.vertices),'imported_vertices_with_uv_material_splits':len(mesh.data.vertices),'animation_timing':'30fps export preserves original clip seconds; verification includes subframe sample times','limitations':['This does not certify hand anatomy, self-intersection-free motion or Godot runtime acceptance.','New contact surfaces use sampled skin-color materials rather than recovered missing texture detail.']}
(OUT/'roundtrip-validation.json').write_text(json.dumps(report,indent=2)+'\n')
for arm in (master_rig,rig):
    arm.animation_data.action=None
    for bone in arm.pose.bones:bone.matrix_basis.identity()
bpy.context.window.scene=bpy.data.scenes['ZombieRepair_v1']
print(json.dumps({k:v for k,v in report.items() if k not in ('roundtrip_pose_samples','duration_errors_seconds')},indent=2))
