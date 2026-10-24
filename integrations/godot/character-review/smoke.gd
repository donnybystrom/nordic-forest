extends SceneTree

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	create_timer(45).timeout.connect(func(): push_error("Asset smoke timed out"); quit(1))
	var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://characters.json"))
	var results: Array = []
	for entry: Dictionary in catalog.characters:
		var packed := load(str(entry.scene)) as PackedScene
		assert(packed != null)
		var character := packed.instantiate()
		root.add_child(character)
		await process_frame
		var skeleton := character.find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
		var player := character.find_children("*", "AnimationPlayer", true, false)[0] as AnimationPlayer
		var mesh := character.find_children("*", "MeshInstance3D", true, false)[0] as MeshInstance3D
		assert(skeleton.get_bone_count() == int(entry.bones))
		assert(mesh.skin != null and mesh.skin.get_bind_count() == int(entry.bones))
		var eight_weights: bool = mesh.mesh.surface_get_format(0) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS != 0
		assert(eight_weights == bool(entry.eight_bone_weights))
		var material := mesh.mesh.surface_get_material(0) as StandardMaterial3D
		assert(material != null and material.albedo_texture != null and material.normal_texture != null)
		assert(material.albedo_texture.get_width() == int(entry.texture_size))
		var names := player.get_animation_list()
		var samples := 0
		var track_count := 0
		var duration_error := 0.0
		var pose_variation := {}
		for clip: Dictionary in catalog.clips:
			var name: String = clip.name
			assert(name in names, name)
			var animation := player.get_animation(name)
			var error := absf(animation.length - float(clip.duration_seconds))
			duration_error = maxf(duration_error, error)
			assert(error < 0.00002)
			var animation_root := player.get_node(player.root_node)
			for index in range(animation.get_track_count()):
				var path := animation.track_get_path(index)
				var node := animation_root.get_node_or_null(NodePath(path.get_concatenated_names()))
				assert(node != null, str(path))
				if path.get_subname_count() > 0 and node is Skeleton3D:
					assert(node.find_bone(path.get_subname(0)) >= 0, str(path))
				track_count += 1
			player.play(name)
			var first: Array[Transform3D] = []
			var variation := 0.0
			for phase: float in [0.0, 0.25, 0.5, 0.75, 1.0]:
				player.seek(animation.length * phase, true)
				player.advance(0)
				for bone in range(skeleton.get_bone_count()):
					var pose := skeleton.get_bone_global_pose(bone)
					assert(pose.is_finite())
					if phase == 0:
						first.append(pose)
					else:
						variation = maxf(variation, (pose.origin - first[bone].origin).length())
				samples += 1
			assert(variation > 0.0001, name + " has no measured motion")
			pose_variation[name] = variation
		results.append({"id":entry.id, "bones":skeleton.get_bone_count(), "skin_binds":mesh.skin.get_bind_count(),
			"clips":catalog.clips.size(), "pose_samples":samples, "validated_track_paths":track_count,
			"max_duration_error_seconds":duration_error, "eight_bone_weights":eight_weights,
			"texture_width":material.albedo_texture.get_width(), "clip_max_joint_displacement_m":pose_variation})
		root.remove_child(character)
		character.queue_free()
	var report := {"status":"pass", "engine":Engine.get_version_info().string, "characters":results,
		"limits":["Import, track resolution and finite moving bone transforms; no foot-contact or physics acceptance."]}
	var file := FileAccess.open("res://../godot-character-validation.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "\t") + "\n")
	print("CHARACTER_ASSET_SMOKE_PASS ", JSON.stringify(report))
	quit()
