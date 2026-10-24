extends SceneTree

func _initialize() -> void:
	call_deferred("_run")

func _frames(count: int) -> void:
	for frame in range(count):
		await physics_frame

func _run() -> void:
	create_timer(240).timeout.connect(func(): push_error("Physics smoke timed out"); quit(1))
	var view = load("res://review.tscn").instantiate()
	root.add_child(view)
	await process_frame
	var results: Array = []
	for model in range(view.characters.size()):
		view._select_model(model)
		view._select_clip(0)
		view._set_physics_mode(1)
		var sandbox = view.physics
		await _frames(300)
		assert(sandbox.bodies.size() == 17 and sandbox.joints.size() == 16)
		var hand: RigidBody3D = sandbox.by_bone[view.skeleton.find_bone("LeftHand")].body
		var pelvis: RigidBody3D = sandbox.root_body()
		assert(hand.collision_mask & 2 != 0 and pelvis not in hand.get_collision_exceptions())
		var hips: RigidBody3D = sandbox.root_body()
		var before := hips.global_position
		print("PHYSICS_BASELINE ", view.characters[model].id, " hips=", before, " support=", sandbox.last_support_force, " joint_gap=", sandbox.max_joint_gap)
		assert(before.is_finite() and before.y > 0.5 and before.y < 1.6)
		var maximum_speed := 0.0
		var mass_sum := 0.0
		for entry: Dictionary in sandbox.bodies:
			var body := entry.body as RigidBody3D
			assert(body.global_transform.is_finite() and not body.freeze)
			maximum_speed = maxf(maximum_speed, body.linear_velocity.length())
			mass_sum += body.mass
		assert(is_equal_approx(mass_sum, sandbox.total_mass))
		assert(maximum_speed < 4.0, "Unperturbed body does not settle")
		assert(sandbox.max_joint_gap < 0.10, "Constraint anchors separate")
		assert(sandbox.modifier_samples > 0 and sandbox.max_skin_pose_error < 0.0001, "Skinning does not follow physics")
		# A freely moving ball collides with the body; no direct impulse is applied
		# to the character. Measure actual physics contacts and root displacement.
		view.push_button.pressed.emit()
		var max_displacement := 0.0
		for frame in range(150):
			await physics_frame
			assert(hips.global_transform.is_finite())
			max_displacement = maxf(max_displacement, hips.global_position.distance_to(before))
		assert(sandbox.ball_contacts > 0, "Ball never contacted a body")
		assert(max_displacement > 0.01, "Contact did not visibly displace the physical character")
		await _frames(240)
		var recovered_error := hips.global_position.distance_to(before)
		assert(recovered_error < 0.25, "Assisted character did not recover")
		# Real camera picking + mouse event handlers engage the spring, then moving
		# the mouse changes a force target, not the body's transform directly.
		sandbox.reset_ball()
		await _frames(2)
		view._process(0)
		var point: Vector2 = view.camera.unproject_position(sandbox.ball.global_position)
		var press := InputEventMouseButton.new()
		press.position = point
		press.button_index = MOUSE_BUTTON_LEFT
		press.pressed = true
		view._unhandled_input(press)
		assert(sandbox.dragging, "Ball ray picking failed")
		var initial_ball: Vector3 = sandbox.ball.global_position
		var motion := InputEventMouseMotion.new()
		motion.position = point + Vector2(90, -70)
		view._input(motion)
		await _frames(80)
		var dragged_distance: float = sandbox.ball.global_position.distance_to(initial_ball)
		assert(dragged_distance > 0.08)
		var release := InputEventMouseButton.new()
		release.button_index = MOUSE_BUTTON_LEFT
		release.pressed = false
		view._input(release)
		assert(not sandbox.dragging)
		# Animation continues as the motor target; switching and scrubbing reset
		# the physical state safely without changing controller configuration.
		var max_motion_speed := 0.0
		for clip in range(1, view.clips.item_count):
			view._select_clip(clip)
			for frame in range(ceili(view.scrub.max_value * 120.0) + 30):
				await physics_frame
				for entry: Dictionary in sandbox.bodies:
					assert(entry.body.global_transform.is_finite())
					max_motion_speed = maxf(max_motion_speed, entry.body.linear_velocity.length())
			assert(sandbox.root_body().global_position.y > -0.1, "Animated root passed through the floor")
		assert(max_motion_speed < 20.0, "Animation causes explosive body velocities")
		view._select_clip(0)
		await _frames(150)
		var standing_height := hips.global_position.y
		view.balance_slider.value = 0.0
		await _frames(240)
		var unsupported_height := hips.global_position.y
		assert(sandbox.last_support_force.is_zero_approx())
		view.balance_slider.value = 1.0
		view._reset_physics()
		await _frames(150)
		view._set_physics_mode(2)
		await _frames(420)
		assert(sandbox.last_support_force.is_zero_approx() and sandbox.max_drive_torque == 0.0)
		assert(hips.global_position.y < standing_height - 0.3, "Passive ragdoll did not fall")
		assert(sandbox.ground_contacts > 0)
		var floor_height := hips.global_position.y
		assert(floor_height > 0.05 and floor_height < 0.5, "Ragdoll did not settle on the floor")
		view._set_physics_mode(1)
		view._reset_physics()
		await _frames(180)
		assert(hips.global_position.y > 0.5)
		assert(sandbox.max_joint_gap < 0.08, "Constraint separation exceeds prototype tolerance")
		results.append({"id":view.characters[model].id, "bodies":sandbox.bodies.size(), "joints":sandbox.joints.size(),
			"mass_kg":sandbox.total_mass, "baseline_max_body_speed_m_s":maximum_speed,
			"ball_body_contacts":sandbox.ball_contacts, "max_hit_displacement_m":max_displacement,
			"assisted_recovery_error_m":recovered_error, "dragged_ball_distance_m":dragged_distance,
			"unsupported_hips_height_m":unsupported_height, "passive_hips_height_m":floor_height,
			"max_joint_gap_m":sandbox.max_joint_gap, "ground_contacts":sandbox.ground_contacts})
		results[-1]["motor_target_clips_tested"] = view.clips.item_count - 1
		results[-1]["max_animation_body_speed_m_s"] = max_motion_speed
		results[-1]["skin_pose_samples"] = sandbox.modifier_samples
		results[-1]["max_skin_pose_error_m"] = sandbox.max_skin_pose_error
		results[-1]["joint_gap_peak"] = sandbox.joint_gap_peak
		view._set_physics_mode(0)
		assert(not is_instance_valid(view.physics))
	# Repeated model changes must remove the old ball, constraints and modifier.
	view._set_physics_mode(1)
	view.muscle_slider.value = 0.55
	view.balance_slider.value = 0.6
	view.ball_mass.value = 14.0
	view.collision_toggle.button_pressed = true
	for model in [0, 1, 0, 1]:
		view._select_model(model)
		await _frames(2)
		assert(view.find_children("PhysicsSandbox", "Node3D", false, false).size() == 1)
		var modifiers := 0
		for child in view.skeleton.get_children():
			if child is SkeletonModifier3D: modifiers += 1
		assert(modifiers == 1)
		assert(is_equal_approx(view.physics.muscles, 0.55))
		assert(is_equal_approx(view.physics.balance, 0.6))
		assert(is_equal_approx(view.physics.ball.mass, 14.0))
		assert(view.physics.debug_shapes)
		for entry: Dictionary in view.physics.bodies:
			assert(entry.visual.visible)
	view.physics.reset_ball()
	await _frames(2)
	view._process(0)
	var focus_point: Vector2 = view.camera.unproject_position(view.physics.ball.global_position)
	assert(view.physics.begin_drag(focus_point, view.camera))
	view._notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	assert(not view.physics.dragging)
	var report := {"status":"pass", "engine":Engine.get_version_info().string,
		"physics_backend":ProjectSettings.get_setting("physics/3d/physics_engine"),
		"physics_hz":Engine.physics_ticks_per_second, "characters":results,
		"drag_ray_pick_and_mouse_handlers":"pass", "mode_switch_and_reset":"pass", "model_cleanup":"pass",
		"sliders_and_debug_persist_across_models":"pass", "focus_loss_releases_drag":"pass",
		"limits":["Bounded virtual pelvis support; no autonomous balance, stepping or foot IK.", "Broad joint limits and approximate mass/collision shapes; nearest two joint neighbors do not collide.", "Scripted input events exercise handlers; not an OS mouse gesture test."]}
	var file := FileAccess.open("res://../godot-active-ragdoll-validation.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "\t") + "\n")
	print("ACTIVE_RAGDOLL_SMOKE_PASS ", JSON.stringify(report))
	view._clear_physics()
	view.queue_free()
	quit()
