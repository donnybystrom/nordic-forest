"""Import the supplied Mixamo GLB into a new, isolated repair scene."""
import bpy
assert not bpy.data.scenes.get('ZombieRepair_v1'), 'Repair scene already exists; do not overwrite it'
scene=bpy.data.scenes.new('ZombieRepair_v1');scene.render.fps=24;bpy.context.window.scene=scene
bpy.ops.import_scene.gltf(filepath='/Users/donnybystrom/code/Nordic-3D-forest/assets/models/zombies/Meshy_AI_Beachside_Revenant_All_Animations-Mixamo.glb')
rig=next(o for o in scene.objects if o.type=='ARMATURE');mesh=next(o for o in scene.objects if o.type=='MESH' and o.parent==rig)
assert len(mesh.data.vertices)==57964
rig.name='ZB_Source_Rig';mesh.name='ZB_Source_Mesh';rig.animation_data.action=None
for track in rig.animation_data.nla_tracks:track.mute=True
for bone in rig.pose.bones:bone.matrix_basis.identity()
scene.frame_set(0)
print('Prepared isolated source',mesh.name,rig.name)
