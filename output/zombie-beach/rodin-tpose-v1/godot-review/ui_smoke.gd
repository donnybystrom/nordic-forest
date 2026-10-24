extends SceneTree

func _initialize() -> void:
	call_deferred("_run")

func _key(view: Node, key: Key) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.pressed = true
	view._unhandled_input(event)

func _run() -> void:
	create_timer(45).timeout.connect(func(): push_error("UI smoke timed out"); quit(1))
	var view = load("res://review.tscn").instantiate()
	root.add_child(view)
	await process_frame
	# Deterministic time; AnimationPlayer is advanced explicitly below.
	view.set_process(false)
	assert(view.models.item_count == 2)
	var selected_count := 0
	for model in range(view.models.item_count):
		view.models.item_selected.emit(model)
		assert(view.model_index == model and view.models.selected == model)
		assert(view.character_slot.get_child_count() == 1)
		assert(view.clips.item_count == 14)
		assert(view.skeleton.get_bone_count() == int(view.characters[model].bones))
		for index in range(1, view.clips.item_count):
			view.clips.item_selected.emit(index)
			assert(view.player.assigned_animation == str(view.clips.get_item_metadata(index)))
			assert(view.player.is_playing())
			assert(not view.pause_button.disabled and view.scrub.editable)
			view.pause_button.pressed.emit()
			assert(not view.player.is_playing())
			view.scrub.value = view.scrub.max_value * 0.5
			assert(absf(view.player.current_animation_position - view.scrub.value) < 0.0001)
			view.pause_button.pressed.emit()
			assert(view.player.is_playing())
			selected_count += 1
		view.clips.item_selected.emit(0)
		assert(not view.player.is_playing() and view.bind_pose_active)
		assert(view.pause_button.disabled and not view.scrub.editable)
		for bone in range(view.skeleton.get_bone_count()):
			assert(view.skeleton.get_bone_pose(bone).is_equal_approx(view.skeleton.get_bone_rest(bone)))
	# Preserve the same clip, phase, paused state and speed across a model switch.
	view._select_model(0)
	view.clips.item_selected.emit(5)
	view.speed.value = 0.65
	view.scrub.value = view.scrub.max_value * 0.37
	view.pause_button.pressed.emit()
	var name: String = view.selected_clip()
	view.model_next.pressed.emit()
	assert(view.model_index == 1 and view.selected_clip() == name)
	assert(not view.player.is_playing() and is_equal_approx(view.player.speed_scale, 0.65))
	assert(absf(view.player.current_animation_position / view.scrub.max_value - 0.37) < 0.001)
	view.pause_button.pressed.emit()
	view.model_next.pressed.emit()
	assert(view.model_index == 0 and view.player.is_playing())
	view.model_previous.pressed.emit()
	assert(view.model_index == 1)
	_key(view, KEY_E)
	assert(view.model_index == 0)
	_key(view, KEY_Q)
	assert(view.model_index == 1)
	view._select_clip(0)
	view.clip_previous.pressed.emit()
	assert(view.clips.selected == 13)
	view.clip_next.pressed.emit()
	assert(view.clips.selected == 0)
	_key(view, KEY_RIGHT)
	assert(view.clips.selected == 1 and view.player.is_playing())
	_key(view, KEY_SPACE)
	assert(not view.player.is_playing())
	_key(view, KEY_SPACE)
	assert(view.player.is_playing())
	_key(view, KEY_LEFT)
	assert(view.bind_pose_active)
	view.model_next.pressed.emit()
	assert(view.bind_pose_active and not view.player.is_playing())
	# Exercise extensibility with a third catalog entry.
	var third: Dictionary = view.characters[1].duplicate(true)
	third.id = "test-future-character"
	third.name = "Test fixture"
	view.characters.append(third)
	view.models.add_item(third.name)
	view._step_model(-1)
	assert(view.model_index == 2 and view.character_slot.get_child_count() == 1)
	assert(view.clips.item_count == 14)
	view._select_clip(1)
	var source_clip: String = view.selected_clip()
	view._select_model(0)
	view._select_model(2)
	assert(view.selected_clip() == source_clip)
	var report := {"status":"pass", "models":2, "clips_switched":selected_count,
		"pause_resume_and_scrub":"pass", "rest_pose_reset":"pass", "model_switch_preserves_clip_phase_speed_pause":"pass",
		"buttons_wrap_and_keyboard":"pass", "third_catalog_entry":"pass", "one_active_character":"pass",
		"limits":["Exercises UI signal and keyboard handler paths; mouse orbit/zoom gestures were not automated."]}
	var file := FileAccess.open("res://../godot-character-ui-validation.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "\t") + "\n")
	print("CHARACTER_UI_SMOKE_PASS ", JSON.stringify(report))
	view.queue_free()
	quit()
