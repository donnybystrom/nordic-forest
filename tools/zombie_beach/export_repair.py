"""Build an isolated deliverable scene and export at original 30Hz timing."""
import bpy,json,re,hashlib
from pathlib import Path
ROOT=Path('/Users/donnybystrom/code/Nordic-3D-forest');OUT=ROOT/'output/zombie-beach/mesh-repair-v1';ASSETS=ROOT/'assets/models/zombies/repaired-v1';ASSETS.mkdir(exist_ok=True)
assert not bpy.data.scenes.get('ZB_Deliverable_v1')
source_scene=bpy.data.scenes['ZombieRepair_v1'];source_rig=bpy.data.objects['ZB_Source_Rig'];source_mesh=bpy.data.objects['ZB_Repaired_Mesh']
scene=bpy.data.scenes.new('ZB_Deliverable_v1');scene.render.fps=30
rig=source_rig.copy();rig.data=source_rig.data.copy();rig.name='Beachside_Revenant_Rig';rig.animation_data_clear();scene.collection.objects.link(rig)
mesh=source_mesh.copy();mesh.data=source_mesh.data.copy();mesh.name='Beachside_Revenant_Repaired';mesh.animation_data_clear();scene.collection.objects.link(mesh);mesh.parent=rig;mesh.hide_render=False
for mod in mesh.modifiers:
    if mod.type=='ARMATURE':mod.object=rig
rig.animation_data_create();scale=scene.render.fps/source_scene.render.fps
records=[]
for track in source_rig.animation_data.nla_tracks:
    for strip in track.strips:
        original=strip.action;canonical=re.sub(r'\.\d{3}$','',original.name);action=original.copy();action.name='ZB_v1_'+canonical
        for layer in action.layers:
            for ast in layer.strips:
                for bag in ast.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.co.x*=scale;key.handle_left.x*=scale;key.handle_right.x*=scale
                            if abs(key.co.x-round(key.co.x))<0.001:
                                delta=round(key.co.x)-key.co.x;key.co.x+=delta;key.handle_left.x+=delta;key.handle_right.x+=delta
                        curve.update()
        tr=rig.animation_data.nla_tracks.new();tr.name=canonical
        st=tr.strips.new(canonical,0,action);st.action_slot=action.slots[0]
        first=float(original.frame_range[0])*scale;last=float(original.frame_range[1])*scale
        if abs(first-round(first))<0.001:first=round(first)
        if abs(last-round(last))<0.001:last=round(last)
        st.action_frame_start=first;st.action_frame_end=last
        st.frame_start=0;st.frame_end=last-first;tr.mute=True
        records.append({'name':canonical,'duration_seconds':st.frame_end/scene.render.fps,'source_action':original.name})
for bone in rig.pose.bones:bone.matrix_basis.identity()
scene.frame_start=0;scene.frame_end=max(int(round(strip.frame_end)) for track in rig.animation_data.nla_tracks for strip in track.strips)
bpy.context.window.scene=scene
for ob in scene.objects:ob.select_set(True)
bpy.context.view_layer.objects.active=rig
scene.frame_set(0);bpy.context.view_layer.update()
glb=ASSETS/'Beachside_Revenant_Repaired_v1-Mixamo.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,use_active_scene=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_frame_range=False,export_frame_step=1,export_skins=True,export_all_influences=True,export_def_bones=False,export_current_frame=False,export_rest_position_armature=True,export_extras=True)
blend=ASSETS/'Beachside_Revenant_Repaired_v1.blend'
bpy.data.libraries.write(str(blend),{scene},fake_user=True,compress=True)
report={'scene':scene.name,'rig':rig.name,'mesh':mesh.name,'fps':30,'source_fps':source_scene.render.fps,'keyframe_time_scale':scale,'vertices':len(mesh.data.vertices),'triangles':len(mesh.data.polygons),'bones':len(rig.data.bones),'clips':records,'files':{str(p.relative_to(ROOT)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in (glb,blend)},'skin_influences':'JOINTS_0/WEIGHTS_0 plus JOINTS_1/WEIGHTS_1 when required; maximum eight, avoiding destructive four-weight pruning','notes':['This is a corrected prototype, not a new retopologized hand sculpt.','No Godot runtime, procedural controller, ragdoll or fracture system has been validated.']}
(OUT/'deliverable-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
bpy.context.window.scene=source_scene
print(json.dumps(report,indent=2))
