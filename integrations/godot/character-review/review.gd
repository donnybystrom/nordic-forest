extends Node3D

const ActiveRagdoll = preload("res://active_ragdoll.gd")

var catalog: Dictionary
var characters: Array
var character_slot: Node3D
var character: Node3D
var player: AnimationPlayer
var skeleton: Skeleton3D
var camera: Camera3D
var models: OptionButton
var clips: OptionButton
var scrub: HSlider
var speed: HSlider
var pause_button: Button
var model_previous: Button
var model_next: Button
var clip_previous: Button
var clip_next: Button
var title: Label
var status: Label
var orbit := Vector2(0.25, 0.12)
var distance := 3.1
var bind_pose_active := true
var model_index := -1
var physics
var physics_mode: OptionButton
var muscle_slider: HSlider
var balance_slider: HSlider
var ball_mass: HSlider
var collision_toggle: CheckBox
var physics_status: Label
var push_button: Button

func _ready() -> void:
	catalog = JSON.parse_string(FileAccess.get_file_as_string("res://characters.json"))
	characters = catalog.characters
	character_slot = Node3D.new()
	character_slot.name = "CharacterSlot"
	add_child(character_slot)
	_build_world()
	_build_ui()
	var initial := 0
	for index in range(characters.size()):
		if characters[index].id == catalog.get("default_character", ""):
			initial = index
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--character="):
			for index in range(characters.size()):
				if characters[index].id == argument.trim_prefix("--character="):
					initial = index
	_select_model(initial)
	if "--physics" in OS.get_cmdline_user_args() or OS.has_feature("web"):
		_set_physics_mode(1)
	if OS.has_feature("web"):
		var browser_status = preload("res://web_status.gd").new()
		browser_status.view = self
		add_child(browser_status)
	print("CHARACTER_REVIEW_READY models=", models.item_count, " clips=", clips.item_count - 1)
	if "--physics-snapshots" in OS.get_cmdline_user_args():
		_capture_physics_snapshots()
	elif "--snapshot-all" in OS.get_cmdline_user_args():
		_capture_snapshots()
	elif "--snapshot" in OS.get_cmdline_user_args():
		_capture_snapshots(true)

func _build_world() -> void:
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("313d46")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color("dce4eb")
	environment.environment.ambient_light_energy = 0.5
	add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -25, 0)
	light.light_energy = 0.9
	light.shadow_enabled = true
	add_child(light)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(200, 200)
	floor_mesh.mesh = plane
	var floor_material := StandardMaterial3D.new()
	floor_material.albedo_color = Color("53616b")
	floor_material.roughness = 0.95
	floor_mesh.material_override = floor_material
	add_child(floor_mesh)
	var ground := StaticBody3D.new()
	ground.name = "PhysicsGround"
	ground.collision_layer = 1
	ground.collision_mask = 2 | 4
	var ground_shape := CollisionShape3D.new()
	var ground_box := BoxShape3D.new()
	ground_box.size = Vector3(200, 0.2, 200)
	ground_shape.shape = ground_box
	ground_shape.position.y = -0.1
	ground.add_child(ground_shape)
	add_child(ground)
	camera = Camera3D.new()
	camera.fov = 42
	add_child(camera)

func _button(parent: Node, text: String, action: Callable) -> Button:
	var button := Button.new()
	button.focus_mode = Control.FOCUS_NONE
	button.text = text
	button.pressed.connect(action)
	parent.add_child(button)
	return button

func _build_ui() -> void:
	var ui := CanvasLayer.new()
	add_child(ui)
	var panel := PanelContainer.new()
	panel.position = Vector2(16, 16)
	panel.custom_minimum_size = Vector2(525, 0)
	ui.add_child(panel)
	var box := VBoxContainer.new()
	panel.add_child(box)
	title = Label.new()
	box.add_child(title)
	var model_row := HBoxContainer.new()
	box.add_child(model_row)
	model_previous = _button(model_row, "‹ Modell", func(): _step_model(-1))
	models = OptionButton.new()
	models.focus_mode = Control.FOCUS_NONE
	models.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for entry: Dictionary in characters:
		models.add_item(entry.name)
		models.set_item_metadata(models.item_count - 1, entry.id)
	models.item_selected.connect(_select_model)
	model_row.add_child(models)
	model_next = _button(model_row, "›", func(): _step_model(1))
	var clip_row := HBoxContainer.new()
	box.add_child(clip_row)
	clip_previous = _button(clip_row, "‹ Klipp", func(): _step_clip(-1))
	clips = OptionButton.new()
	clips.focus_mode = Control.FOCUS_NONE
	clips.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	clips.item_selected.connect(_select_clip)
	clip_row.add_child(clips)
	clip_next = _button(clip_row, "›", func(): _step_clip(1))
	var buttons := HBoxContainer.new()
	box.add_child(buttons)
	pause_button = _button(buttons, "Pausa / spela", _toggle_pause)
	var speed_label := Label.new()
	speed_label.text = "Hastighet"
	buttons.add_child(speed_label)
	speed = HSlider.new()
	speed.focus_mode = Control.FOCUS_NONE
	speed.min_value = 0.1
	speed.max_value = 1.5
	speed.step = 0.05
	speed.value = 1.0
	speed.custom_minimum_size.x = 130
	speed.value_changed.connect(func(value: float):
		if is_instance_valid(player):
			player.speed_scale = value)
	buttons.add_child(speed)
	_button(buttons, "Återställ vy", func(): orbit = Vector2(0.25, 0.12); distance = 3.1)
	scrub = HSlider.new()
	scrub.focus_mode = Control.FOCUS_NONE
	scrub.step = 0.001
	scrub.value_changed.connect(func(value: float):
		if not bind_pose_active:
			player.seek(value, true)
			player.advance(0)
			_reset_physics())
	box.add_child(scrub)
	status = Label.new()
	box.add_child(status)
	var physics_row := HBoxContainer.new()
	box.add_child(physics_row)
	physics_mode = OptionButton.new()
	physics_mode.focus_mode = Control.FOCUS_NONE
	for label in ["Animation", "Aktiv fysik", "Slapp ragdoll"]:
		physics_mode.add_item(label)
	physics_mode.item_selected.connect(_set_physics_mode)
	physics_row.add_child(physics_mode)
	_button(physics_row, "Återställ kropp", _reset_physics)
	_button(physics_row, "Hämta bollen", func():
		if is_instance_valid(physics):
			physics.reset_ball())
	push_button = _button(physics_row, "Testknuff", func():
		if is_instance_valid(physics): physics.launch_ball())
	muscle_slider = _physics_slider(box, "Muskelkraft", 0.0, 1.5, 1.0)
	muscle_slider.value_changed.connect(func(value: float):
		if is_instance_valid(physics): physics.muscles = value)
	balance_slider = _physics_slider(box, "Balanshjälp", 0.0, 1.0, 1.0)
	balance_slider.tooltip_text = "Begränsad fjäderkraft vid höften. Inte självbärande balans eller fotplacering."
	balance_slider.value_changed.connect(func(value: float):
		if is_instance_valid(physics): physics.balance = value)
	ball_mass = _physics_slider(box, "Boll · kg", 1.0, 20.0, 8.0)
	ball_mass.value_changed.connect(func(value: float):
		if is_instance_valid(physics): physics.ball.mass = value)
	collision_toggle = CheckBox.new()
	collision_toggle.text = "Visa kollisionskroppar"
	collision_toggle.focus_mode = Control.FOCUS_NONE
	collision_toggle.toggled.connect(func(enabled: bool):
		if is_instance_valid(physics): physics.debug_shapes = enabled)
	box.add_child(collision_toggle)
	physics_status = Label.new()
	box.add_child(physics_status)
	var help := Label.new()
	help.text = "Dra orange boll för att putta · dra bakgrund för att rotera\nQ/E: modell · pilar: klipp · mellanslag: paus\n1/2/3: animation/aktiv/slapp · R: återställ · B: boll"
	box.add_child(help)

func _physics_slider(parent: Node, text: String, low: float, high: float, initial: float) -> HSlider:
	var row := HBoxContainer.new()
	parent.add_child(row)
	var label := Label.new()
	label.text = text
	label.custom_minimum_size.x = 125
	row.add_child(label)
	var slider := HSlider.new()
	slider.focus_mode = Control.FOCUS_NONE
	slider.min_value = low
	slider.max_value = high
	slider.step = 0.05 if high <= 2.0 else 1.0
	slider.value = initial
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(slider)
	var number := Label.new()
	number.custom_minimum_size.x = 45
	number.text = "%.2f" % initial
	slider.value_changed.connect(func(value: float): number.text = "%.2f" % value)
	row.add_child(number)
	return slider

func _clear_physics() -> void:
	if is_instance_valid(physics):
		physics.shutdown()
		remove_child(physics)
		physics.queue_free()
	physics = null

func _set_physics_mode(mode: int) -> void:
	physics_mode.select(mode)
	if mode == 0:
		_clear_physics()
		skeleton.reset_bone_poses()
		if not bind_pose_active:
			player.seek(player.current_animation_position, true)
			player.advance(0)
		return
	if not is_instance_valid(physics):
		physics = ActiveRagdoll.new()
		physics.name = "PhysicsSandbox"
		add_child(physics)
		physics.configure(self)
	physics.passive = mode == 2
	physics.muscles = muscle_slider.value
	physics.balance = balance_slider.value
	physics.ball.mass = ball_mass.value
	physics.debug_shapes = collision_toggle.button_pressed

func _reset_physics() -> void:
	if is_instance_valid(physics):
		physics.reset_pose()

func selected_clip() -> String:
	return "" if bind_pose_active else str(clips.get_item_metadata(clips.selected))

func _select_model(index: int) -> void:
	_clear_physics()
	var desired_clip := str(catalog.default_clip)
	var phase := 0.0
	var was_playing := true
	if is_instance_valid(player):
		desired_clip = selected_clip()
		was_playing = player.is_playing()
		if not bind_pose_active:
			phase = player.current_animation_position / player.get_animation(desired_clip).length
	var packed := load(str(characters[index].scene)) as PackedScene
	assert(packed != null, "Missing character scene")
	var candidate := packed.instantiate() as Node3D
	var players := candidate.find_children("*", "AnimationPlayer", true, false)
	var skeletons := candidate.find_children("*", "Skeleton3D", true, false)
	assert(players.size() == 1 and skeletons.size() == 1, "Character requires one skeleton and animation player")
	if is_instance_valid(character):
		player.stop()
		character_slot.remove_child(character)
		character.queue_free()
	character = candidate
	character_slot.add_child(character)
	player = players[0] as AnimationPlayer
	skeleton = skeletons[0] as Skeleton3D
	player.speed_scale = speed.value
	model_index = index
	models.select(index)
	clips.clear()
	clips.add_item("Vilopose · " + str(characters[index].rest_pose))
	clips.set_item_metadata(0, "")
	var selected := 0
	for name in player.get_animation_list():
		if name == "RESET":
			continue
		clips.add_item(_clip_label(name))
		var item := clips.item_count - 1
		clips.set_item_metadata(item, name)
		clips.set_item_tooltip(item, name)
		if name == desired_clip:
			selected = item
	# New characters may only have a subset of the library. Pick an available
	# motion if the previous one is missing; explicitly selected rest stays rest.
	if selected == 0 and not desired_clip.is_empty() and clips.item_count > 1:
		selected = 1
	_select_clip(selected)
	if not bind_pose_active:
		player.seek(scrub.max_value * phase, true)
		player.advance(0)
		if not was_playing:
			player.pause()
	title.text = "%s · %d ben · %d klipp" % [characters[index].name, skeleton.get_bone_count(), clips.item_count - 1]
	_set_physics_mode(physics_mode.selected)

func _clip_label(name: String) -> String:
	var labels := {"Meshy_Unsteady_Walk": "Ostadig gång", "Meshy_Walking": "Gång · Meshy", "Meshy_Running": "Löpning · Meshy", "Rodin_HumanWalking2": "Gång · Rodin", "Rodin_HumanZombieCrawl": "Zombie · krypning"}
	if labels.has(name):
		return labels[name]
	# Unknown source clips keep an identifiable source ID instead of invented actions.
	return "Meshy · " + name.trim_prefix("Meshy__").left(18)

func _select_clip(index: int) -> void:
	clips.select(index)
	player.stop()
	skeleton.reset_bone_poses()
	bind_pose_active = index == 0
	pause_button.disabled = bind_pose_active
	scrub.editable = not bind_pose_active
	if bind_pose_active:
		scrub.max_value = 1
		scrub.set_value_no_signal(0)
		_reset_physics()
		return
	var name := str(clips.get_item_metadata(index))
	var animation := player.get_animation(name)
	# Review-only loop setting; authored GLBs remain unchanged.
	animation.loop_mode = Animation.LOOP_LINEAR
	scrub.set_block_signals(true)
	scrub.max_value = animation.length
	scrub.value = 0
	scrub.set_block_signals(false)
	player.play(name, 0)
	player.seek(0, true)
	player.advance(0)
	_reset_physics()

func _step_model(offset: int) -> void:
	_select_model(posmod(model_index + offset, characters.size()))

func _step_clip(offset: int) -> void:
	_select_clip(posmod(clips.selected + offset, clips.item_count))

func _toggle_pause() -> void:
	if bind_pose_active:
		return
	if player.is_playing():
		player.pause()
	else:
		player.play()

func _process(_delta: float) -> void:
	if not is_instance_valid(skeleton):
		return
	var hips := skeleton.find_bone("Hips")
	var position_in_world := skeleton.to_global(skeleton.get_bone_global_pose(hips).origin)
	if is_instance_valid(physics):
		position_in_world = physics.root_body().global_position
	var target := Vector3(position_in_world.x, 0.9 if position_in_world.y > 0.7 else 0.45, position_in_world.z)
	camera.position = target + Vector3(sin(orbit.x) * cos(orbit.y), sin(orbit.y), cos(orbit.x) * cos(orbit.y)) * distance
	camera.look_at(target)
	# Reserve the left side for controls, keeping the face clear at any zoom.
	camera.h_offset = -distance * 0.19
	if not bind_pose_active:
		scrub.set_value_no_signal(player.current_animation_position)
		status.text = "%.2f / %.2f s · %.2f× · %s" % [player.current_animation_position, scrub.max_value, player.speed_scale, "spelar" if player.is_playing() else "pausad"]
	else:
		status.text = "Vilopose"
	if is_instance_valid(physics):
		physics_status.text = "%s · %.0f kg kropp · %d bollkontakter\n%s" % ["Slapp: motorer av" if physics.passive else "Aktiv: vridmoment + höftstöd", physics.total_mass, physics.ball_contacts, "Drar boll" if physics.dragging else "Balanshjälp är ett virtuellt höftstöd; ingen fot-IK"]
	else:
		physics_status.text = "Välj Aktiv fysik för boll och kroppskollisioner"

func _input(event: InputEvent) -> void:
	# Release even when the mouse ends over the UI, or focus leaves the window.
	if is_instance_valid(physics) and physics.dragging:
		if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
			physics.end_drag()
			get_viewport().set_input_as_handled()
		elif event is InputEventMouseMotion:
			physics.update_drag(event.position, camera)
			get_viewport().set_input_as_handled()

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and is_instance_valid(physics):
		physics.end_drag()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_Q: _step_model(-1)
			KEY_E: _step_model(1)
			KEY_LEFT: _step_clip(-1)
			KEY_RIGHT: _step_clip(1)
			KEY_SPACE: _toggle_pause()
			KEY_1: _set_physics_mode(0)
			KEY_2: _set_physics_mode(1)
			KEY_3: _set_physics_mode(2)
			KEY_R: _reset_physics()
			KEY_B:
				if is_instance_valid(physics): physics.reset_ball()
	if is_instance_valid(physics) and event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		if physics.begin_drag(event.position, camera):
			get_viewport().set_input_as_handled()
			return
	if event is InputEventMouseMotion and event.button_mask & MOUSE_BUTTON_MASK_LEFT != 0:
		orbit.x -= event.relative.x * 0.008
		orbit.y = clampf(orbit.y + event.relative.y * 0.006, -0.2, 1.0)
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance = maxf(1.3, distance - 0.2)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance = minf(6, distance + 0.2)

func _capture_snapshots(single := false) -> void:
	var saved: Array[String] = []
	for index in range(characters.size()):
		if single and index != model_index:
			continue
		_select_model(index)
		for name in ["Meshy_Unsteady_Walk", "Rodin_HumanZombieCrawl"]:
			for item in range(1, clips.item_count):
				if clips.get_item_metadata(item) == name:
					_select_clip(item)
			player.seek(scrub.max_value * 0.38, true)
			player.advance(0)
			player.pause()
			for frame in range(8):
				await get_tree().process_frame
			await RenderingServer.frame_post_draw
			var path := "res://../%s-%s.png" % [characters[index].id, name]
			var error := get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(path))
			assert(error == OK)
			saved.append(path)
	print("CHARACTER_REVIEW_SNAPSHOTS ", JSON.stringify(saved))
	get_tree().quit()

func _capture_physics_snapshots() -> void:
	for model in range(characters.size()):
		_select_model(model)
		_select_clip(0)
		_set_physics_mode(1)
		for frame in range(180):
			await get_tree().physics_frame
		await _save_physics_frame("active-physics")
		physics.launch_ball()
		for frame in range(25):
			await get_tree().physics_frame
		await _save_physics_frame("ball-hit")
		for item in range(1, clips.item_count):
			if clips.get_item_metadata(item) == "Meshy_Unsteady_Walk":
				_select_clip(item)
		for frame in range(180):
			await get_tree().physics_frame
		await _save_physics_frame("walking-physics")
		_select_clip(0)
		_set_physics_mode(2)
		for frame in range(420):
			await get_tree().physics_frame
		distance = 3.8
		orbit.y = 0.35
		await _save_physics_frame("passive-physics")
		distance = 3.1
		orbit = Vector2(0.25, 0.12)
	print("ACTIVE_PHYSICS_SNAPSHOTS_COMPLETE")
	get_tree().quit()

func _save_physics_frame(suffix: String) -> void:
	for frame in range(4):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var path := "res://../%s-%s.png" % [characters[model_index].id, suffix]
	var error := get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(path))
	assert(error == OK)
	# Return to the main frame before resetting/rebuilding physics for the next
	# shot; frame_post_draw is not a safe point for physics-server mutations.
	await get_tree().process_frame
