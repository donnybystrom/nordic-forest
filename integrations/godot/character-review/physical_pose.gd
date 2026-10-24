extends SkeletonModifier3D
## Apply simulated body transforms after AnimationPlayer, never teleport bodies.
var controller: Node3D

func _process_modification() -> void:
	if not is_instance_valid(controller) or controller.bodies.is_empty():
		return
	var rig := get_skeleton()
	var world_to_rig := rig.global_transform.affine_inverse()
	for index in range(rig.get_bone_count()):
		if controller.by_bone.has(index):
			var entry: Dictionary = controller.by_bone[index]
			var body := entry.body as RigidBody3D
			rig.set_bone_global_pose(index, world_to_rig * body.global_transform * entry.offset.affine_inverse())
