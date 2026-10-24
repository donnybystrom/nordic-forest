"""Render transferred motion, then leave the Rodin working rig ready in Blender."""
import bpy, json
from pathlib import Path
from mathutils import Vector

ROOT = Path('/Users/donnybystrom/code/Nordic-3D-forest')
OUT = ROOT/'output/zombie-beach/rodin-audit-v1'
scene = bpy.data.scenes['Rodin_Review_v1']
bpy.context.window.scene = scene
rig = bpy.data.objects['Rodin_Working_Rig']
mesh = bpy.data.objects['Rodin_Working_Mesh']
for ob in scene.objects:
    if ob.type == 'MESH':
        ob.hide_render = ob != mesh
        ob.hide_set(ob != mesh)
for track in rig.animation_data.nla_tracks:
    track.mute = True
action = next(tr.strips[0].action for tr in rig.animation_data.nla_tracks
    if tr.name == 'Meshy_Unsteady_Walk')
rig.animation_data.action = action
rig.animation_data.action_slot = action.slots[0]
scene.frame_start = 0
scene.frame_end = 89
scene.frame_set(34)
scene.render.resolution_x = 768
scene.render.resolution_y = 1024
cam = scene.camera
cam.data.ortho_scale = 2.15
hips = rig.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones['Hips'].head
target = Vector((hips.x, hips.y, .97))
cam.location = target + Vector((1.4, -4, .1))
cam.rotation_euler = (target-cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(OUT/'rodin-meshy-unsteady-walk.png')
bpy.ops.render.render(write_still=True)
for ob in bpy.context.selected_objects:
    ob.select_set(False)
mesh.select_set(True)
bpy.context.view_layer.objects.active = mesh
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.overlay.show_overlays = False
            area.spaces.active.region_3d.view_perspective = 'CAMERA'
bpy.data.libraries.write(str(OUT/'Rodin_Review_v1.blend'), {scene}, fake_user=True, compress=True)
(OUT/'preview-pose.json').write_text(json.dumps({'animation':'Meshy_Unsteady_Walk',
    'frame_30fps':34,'normal_strength':.65,'note':'A rendered pose, not a foot-contact or motion-quality approval.'}, indent=2)+'\n')
print('Rendered Rodin with retargeted Meshy_Unsteady_Walk, frame 34 at 30fps')
