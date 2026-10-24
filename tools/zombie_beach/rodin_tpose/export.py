"""Export a self-contained T-pose source/rig/animation candidate, LOD0 only."""
import bpy, json, hashlib
from pathlib import Path

ROOT=Path('/Users/donnybystrom/code/Nordic-3D-forest');OUT=ROOT/'output/zombie-beach/rodin-tpose-v1'
ASSETS=ROOT/'assets/models/zombies/rodin-tpose-working-v1';ASSETS.mkdir(exist_ok=True)
assert not bpy.data.scenes.get('RodinT_Deliverable_v1')
scene=bpy.data.scenes.new('RodinT_Deliverable_v1');scene.render.fps=30
rig=bpy.data.objects['RodinT_Rig'].copy();rig.data=rig.data.copy();rig.name='RodinT_v1_Rig';scene.collection.objects.link(rig)
mesh=bpy.data.objects['RodinT_Working_Mesh'].copy();mesh.data=mesh.data.copy();mesh.name='RodinT_v1_Mesh';mesh.parent=rig;scene.collection.objects.link(mesh)
for mod in mesh.modifiers:
 if mod.type=='ARMATURE':mod.object=rig
rig.animation_data.action=None
clips=[]
for track in rig.animation_data.nla_tracks:
 track.mute=True;st=track.strips[0];clips.append({'name':track.name,'duration_seconds':float(st.frame_end-st.frame_start)/30})
for pb in rig.pose.bones:pb.matrix_basis.identity()
bpy.context.window.scene=scene
for ob in (mesh,rig):ob.hide_render=False;ob.hide_viewport=False;ob.hide_set(False);ob.select_set(True)
bpy.context.view_layer.objects.active=rig;scene.frame_start=0;scene.frame_end=max(round(c['duration_seconds']*30) for c in clips);scene.frame_set(0);bpy.context.view_layer.update()
glb=ASSETS/'Rodin_TPose_Working_v1.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,use_active_scene=True,
 export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,
 export_frame_range=False,export_frame_step=1,export_skins=True,export_all_influences=True,
 export_def_bones=False,export_current_frame=False,export_rest_position_armature=True,export_extras=True)
blend=ASSETS/'Rodin_TPose_Working_v1.blend';bpy.data.libraries.write(str(blend),{scene},fake_user=True,compress=True)
report={'status':'initial_rig_candidate','scene':scene.name,'rig':rig.name,'mesh':mesh.name,'bones':len(rig.data.bones),
 'vertices':len(mesh.data.vertices),'triangles':len(mesh.data.polygons),'max_influences':max(sum(g.weight>0 for g in v.groups) for v in mesh.data.vertices),'fps':30,'clips':clips,
 'files':{str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (glb,blend)},
 'changes':['New source LOD0 fitted with 52 named bones and fresh Blender heat weights.',
 'Mesh translated horizontally to center; source geometry and UV topology retained.',
 '13 clips rebaked using an explicit source T stance as reference.',
 'Original 2K PBR maps packed; normal strength 0.65; no texture regeneration.'],
 'limitations':['Lower source LODs remain unrigged and are not included in this GLB.',
 'Initial finger placement/weights; no planted-foot IK, corrective morphs, jiggle, ragdoll or fracture.']}
(OUT/'deliverable-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
bpy.context.window.scene=bpy.data.scenes['Rodin_TPose_Review_v1']
print(json.dumps({k:v for k,v in report.items() if k!='clips'},indent=2))
