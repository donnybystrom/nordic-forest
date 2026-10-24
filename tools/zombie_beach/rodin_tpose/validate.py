"""Verify isolated GLB structure, timing and evaluated skinning after reimport."""
import bpy, json, struct, re
import numpy as np
from pathlib import Path
from mathutils.kdtree import KDTree

ROOT = Path('/Users/donnybystrom/code/Nordic-3D-forest')
OUT = ROOT / 'output/zombie-beach/rodin-tpose-v1'
path = ROOT / 'assets/models/zombies/rodin-tpose-working-v1/Rodin_TPose_Working_v1.glb'
raw = path.read_bytes()
gltf = json.loads(raw[20:20+struct.unpack_from('<I', raw, 12)[0]])
manifest = json.loads((OUT/'deliverable-manifest.json').read_text())
assert len(gltf['scenes']) == len(gltf['meshes']) == len(gltf['skins']) == 1
assert len(gltf['skins'][0]['joints']) == 52
assert len(gltf['animations']) == 13
source = {c['name']: c['duration_seconds'] for c in manifest['clips']}
durations = {a['name']: max(gltf['accessors'][s['input']]['max'][0]
    for s in a['samplers']) for a in gltf['animations']}
assert set(source) == set(durations)
duration_errors = {n: abs(source[n]-durations[n]) for n in source}
assert max(duration_errors.values()) < 2e-5
attrs = gltf['meshes'][0]['primitives'][0]['attributes']
assert 'JOINTS_1' in attrs and 'WEIGHTS_1' in attrs
assert abs(gltf['materials'][0]['normalTexture']['scale'] - 0.65) < 1e-6
master_scene = bpy.data.scenes['RodinT_Deliverable_v1']
master_rig = bpy.data.objects['RodinT_v1_Rig']
master_mesh = bpy.data.objects['RodinT_v1_Mesh']
assert not master_mesh.data.validate(verbose=True, clean_customdata=False)
validation = bpy.data.scenes.new('RodinT_Roundtrip_v1')
validation.render.fps = 30
bpy.context.window.scene = validation
bpy.ops.import_scene.gltf(filepath=str(path))
rig = next(o for o in validation.objects if o.type == 'ARMATURE')
mesh = next(o for o in validation.objects if o.type == 'MESH')
ma = {tr.name: tr.strips[0].action for tr in master_rig.animation_data.nla_tracks}
ra = {re.sub(r'\.\d{3}$', '', st.action.name): st.action
    for tr in rig.animation_data.nla_tracks for st in tr.strips}
assert set(ma) == set(ra) == set(source), (list(ma), list(ra))
for arm in (rig, master_rig):
    arm.animation_data.action = None
    for track in arm.animation_data.nla_tracks:
        track.mute = True
    for bone in arm.pose.bones:
        bone.matrix_basis.identity()
tree = KDTree(len(master_mesh.data.vertices))
for v in master_mesh.data.vertices:
    tree.insert(v.co, v.index)
tree.balance()
mapping, rest_errors = [], []
for v in mesh.data.vertices:
    _, index, error = tree.find(v.co)
    mapping.append(index)
    rest_errors.append(error)
mapping = np.array(mapping, np.int32)
assert max(rest_errors) < 1e-5
def coordinates(scene, ob, frame):
    bpy.context.window.scene = scene
    scene.frame_set(int(frame), subframe=float(frame % 1))
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    em = ev.to_mesh()
    xyz = np.empty(len(em.vertices)*3, np.float64)
    em.vertices.foreach_get('co', xyz)
    ev.to_mesh_clear()
    return xyz.reshape(-1, 3)
samples = []
for name in source:
    master_rig.animation_data.action = ma[name]
    master_rig.animation_data.action_slot = ma[name].slots[0]
    rig.animation_data.action = ra[name]
    rig.animation_data.action_slot = ra[name].slots[0]
    for phase in (0, .25, .5, .75, 1):
        frame = source[name]*30*phase
        original = coordinates(master_scene, master_mesh, frame)
        imported = coordinates(validation, mesh, frame)
        error = np.linalg.norm(original[mapping]-imported, axis=1)
        samples.append({'animation': name, 'phase': phase,
            'max_vertex_error_m': float(error.max()), 'mean_vertex_error_m': float(error.mean())})
max_error = max(s['max_vertex_error_m'] for s in samples)
assert max_error < .002, max_error
report = {'status': 'pass', 'glb_scenes': 1, 'glb_meshes': 1, 'bones': 52,
    'clips': 13, 'duration_errors_seconds': duration_errors,
    'source_vertices': len(master_mesh.data.vertices),
    'imported_vertices': len(mesh.data.vertices), 'max_influences_exported': 8,
    'rest_mapping_max_error_m': max(rest_errors),
    'roundtrip_pose_samples': samples, 'roundtrip_pose_max_error_m': max_error,
    'limitations': ['Verifies export equivalence, not anatomical deformation quality or foot contact.',
        'No Godot runtime, secondary physics, ragdoll or fracture test performed.']}
(OUT/'roundtrip-validation.json').write_text(json.dumps(report, indent=2)+'\n')
for arm in (master_rig, rig):
    arm.animation_data.action = None
    for bone in arm.pose.bones:
        bone.matrix_basis.identity()
bpy.context.window.scene = bpy.data.scenes['Rodin_TPose_Review_v1']
print(json.dumps({k:v for k,v in report.items() if k not in ('roundtrip_pose_samples','duration_errors_seconds')}, indent=2))
