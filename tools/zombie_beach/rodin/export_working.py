"""Package only the Rodin candidate and its 13 clips; leave source assets intact."""
import bpy, json, hashlib
from pathlib import Path

ROOT = Path('/Users/donnybystrom/code/Nordic-3D-forest')
OUT = ROOT / 'output/zombie-beach/rodin-audit-v1'
ASSETS = ROOT / 'assets/models/zombies/rodin-working-v1'
ASSETS.mkdir(exist_ok=True)
assert not bpy.data.scenes.get('Rodin_Deliverable_v1')
review = bpy.data.scenes['Rodin_Review_v1']
scene = bpy.data.scenes.new('Rodin_Deliverable_v1')
scene.render.fps = 30
rig = bpy.data.objects['Rodin_Working_Rig'].copy()
rig.data = rig.data.copy()
rig.name = 'Rodin_v1_Rig'
scene.collection.objects.link(rig)
mesh = bpy.data.objects['Rodin_Working_Mesh'].copy()
mesh.data = mesh.data.copy()
mesh.name = 'Rodin_v1_Mesh'
mesh.parent = rig
scene.collection.objects.link(mesh)
for mod in mesh.modifiers:
    if mod.type == 'ARMATURE':
        mod.object = rig
rig.animation_data.action = None
clips = []
for track in rig.animation_data.nla_tracks:
    track.mute = True
    strip = track.strips[0]
    clips.append({'name': track.name, 'duration_seconds': float(strip.frame_end-strip.frame_start)/30})
for bone in rig.pose.bones:
    bone.matrix_basis.identity()
for obj in (rig, mesh):
    obj.hide_render = False
    obj.hide_viewport = False
bpy.context.window.scene = scene
for obj in scene.objects:
    obj.hide_set(False)
    obj.select_set(True)
bpy.context.view_layer.objects.active = rig
scene.frame_start = 0
scene.frame_end = max(round(c['duration_seconds']*30) for c in clips)
scene.frame_set(0)
bpy.context.view_layer.update()
glb = ASSETS / 'Rodin_Working_v1.glb'
bpy.ops.export_scene.gltf(
    filepath=str(glb), export_format='GLB', use_selection=True,
    use_active_scene=True, export_animations=True, export_animation_mode='NLA_TRACKS',
    export_force_sampling=True, export_frame_range=False, export_frame_step=1,
    export_skins=True, export_all_influences=True, export_def_bones=False,
    export_current_frame=False, export_rest_position_armature=True, export_extras=True)
blend = ASSETS / 'Rodin_Working_v1.blend'
bpy.data.libraries.write(str(blend), {scene}, fake_user=True, compress=True)
report = {
    'status': 'working_candidate', 'scene': scene.name, 'rig': rig.name,
    'mesh': mesh.name, 'bones': len(rig.data.bones), 'fps': 30,
    'vertices': len(mesh.data.vertices),
    'triangles': sum(len(p.vertices)-2 for p in mesh.data.polygons), 'clips': clips,
    'files': {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size,
        'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (glb, blend)},
    'changes': ['Localized shoulder/underarm weight smoothing; geometry and UV unchanged.',
        'Original PBR maps retained; normal strength reduced to 0.65.',
        'Eleven Meshy clips retargeted to Rodin; two native Rodin clips retained.'],
    'limitations': ['Armpit webbing remains visible in the raised-arm stress pose.',
        'No foot-contact correction, secondary physics, ragdoll or procedural controller.',
        'No Godot runtime validation; this is not an accepted production character.']}
(OUT / 'deliverable-manifest.json').write_text(json.dumps(report, indent=2)+'\n')
bpy.context.window.scene = review
print(json.dumps(report, indent=2))
