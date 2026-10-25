extends CharacterBody3D
## Semi-automatic hitscan pistol: camera aim, muzzle obstruction, point impulse.
var arena: Node3D
var camera: Camera3D
var weapon: Node3D
var slide: MeshInstance3D
var muzzle: Node3D
var flash: MeshInstance3D
var flash_light: OmniLight3D
var sound: AudioStreamPlayer
var magazine := 12
var reload_time := 0.0
var cooldown := 0.0
var recoil := 0.0
var flash_time := 0.0
var bob_time := 0.0
var aiming := false
var sensitivity := 0.0022
var shots := 0
var last_shot := {}
var pitch := 0.0

func setup(world: Node3D) -> void:
	arena = world
	collision_layer = 8
	collision_mask = 1 | 2
	floor_snap_length = 0.2
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.3
	capsule.height = 1.8
	shape.shape = capsule
	shape.position.y = 0.9
	add_child(shape)
	camera = Camera3D.new()
	camera.position.y = 1.65
	camera.fov = 74.0
	camera.near = 0.025
	camera.far = 80.0
	add_child(camera)
	camera.make_current()
	_build_weapon()

func _piece(parent: Node3D, dimensions: Vector3, at: Vector3, color: Color) -> MeshInstance3D:
	var part := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = dimensions
	part.mesh = mesh
	part.position = at
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.55
	part.material_override = material
	part.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(part)
	return part

func _build_weapon() -> void:
	weapon = Node3D.new()
	camera.add_child(weapon)
	_piece(weapon, Vector3(0.085,0.08,0.29), Vector3(0,0,0), Color("303b43"))
	slide = _piece(weapon, Vector3(0.078,0.055,0.31), Vector3(0,0.05,-0.015), Color("6e7d83"))
	var grip := _piece(weapon, Vector3(0.07,0.17,0.08), Vector3(0,-0.1,0.075), Color("1b2429"))
	grip.rotation.x = -0.23
	_piece(weapon, Vector3(0.02,0.025,0.025), Vector3(0,0.09,-0.13), Color("ccdfb5"))
	_piece(weapon, Vector3(0.065,0.03,0.025), Vector3(0,0.085,0.12), Color("202a2e"))
	_piece(weapon, Vector3(0.08,0.075,0.1), Vector3(0,-0.09,0.08), Color("6f7963"))
	var right := _piece(weapon,Vector3(0.09,0.1,0.37),Vector3(0.03,-0.17,0.23),Color("8b977e"))
	right.rotation.x = -0.25
	var left := _piece(weapon,Vector3(0.085,0.085,0.35),Vector3(-0.13,-0.16,0.18),Color("76866c"))
	left.rotation.y = -0.7
	muzzle = Node3D.new()
	muzzle.position = Vector3(0,0.035,-0.185)
	weapon.add_child(muzzle)
	flash = _piece(muzzle,Vector3(0.13,0.02,0.11),Vector3(0,0,-0.04),Color("ffde85"))
	var material := flash.material_override as StandardMaterial3D
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	flash.visible = false
	flash_light = OmniLight3D.new()
	flash_light.light_color = Color("ffc17b")
	flash_light.omni_range = 3.0
	flash_light.light_energy = 0.0
	muzzle.add_child(flash_light)
	sound = AudioStreamPlayer.new()
	sound.volume_db = -17.0
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = 22050
	var samples := PackedByteArray()
	samples.resize(4410)
	var rng := RandomNumberGenerator.new()
	rng.seed = 25
	for i in range(2205):
		var t := float(i)/22050.0
		var value := (rng.randf_range(-1.0,1.0)*0.75+sin(t*600.0)*0.25)*exp(-t*65.0)
		samples.encode_s16(i*2,int(value*28000.0))
	wav.data = samples
	sound.stream = wav
	add_child(sound)

func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotation.y -= event.screen_relative.x * sensitivity
		pitch = clampf(pitch-event.screen_relative.y*sensitivity, -1.4,1.4)
		camera.rotation.x = pitch

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_TAB:
			arena.set_menu(not arena.menu.visible)
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_ESCAPE:
			arena.set_menu(true)
		elif event.keycode == KEY_R:
			reload()
		elif event.keycode == KEY_F2:
			arena.show_colliders = not arena.show_colliders
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
			if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
				arena.set_menu(false)
			else:
				fire()
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			aiming = event.pressed and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		aiming = false

func reload() -> void:
	if reload_time <= 0.0 and magazine < 12:
		reload_time = 1.3

func _physics_process(delta: float) -> void:
	cooldown = maxf(0.0,cooldown-delta)
	if reload_time > 0.0:
		reload_time -= delta
		if reload_time <= 0.0:
			magazine = 12
	var walking: bool = Input.mouse_mode == Input.MOUSE_MODE_CAPTURED and not arena.menu.visible
	var input := Vector2.ZERO
	if walking:
		input = Vector2(float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A)),float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W))).limit_length(1.0)
	var direction := global_basis * Vector3(input.x,0,input.y)
	var speed := 6.0 if walking and Input.is_physical_key_pressed(KEY_SHIFT) else 3.8
	velocity.x = move_toward(velocity.x,direction.x*speed,delta*22.0)
	velocity.z = move_toward(velocity.z,direction.z*speed,delta*22.0)
	velocity.y -= 9.8*delta
	if walking and Input.is_physical_key_pressed(KEY_SPACE) and is_on_floor():
		velocity.y = 4.5
	move_and_slide()
	if position.y < -5.0:
		position = Vector3(0,0.1,7)
		velocity = Vector3.ZERO

func _process(delta: float) -> void:
	if not is_instance_valid(weapon):
		return
	recoil = move_toward(recoil,0.0,delta*5.5)
	flash_time = maxf(0.0,flash_time-delta)
	flash.visible = flash_time > 0.0
	flash_light.light_energy = 1.7 if flash.visible else 0.0
	bob_time += delta * Vector2(velocity.x,velocity.z).length() * 2.4
	var bob := minf(Vector2(velocity.x,velocity.z).length()*0.002,0.012)
	var ads := aiming and reload_time <= 0.0 and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
	var aim_position := Vector3(0.0,-0.09,-0.52) if ads else Vector3(0.22,-0.20,-0.62)
	weapon.position = weapon.position.lerp(aim_position, minf(1.0,delta*15.0))
	weapon.position += Vector3(sin(bob_time)*bob,absf(cos(bob_time))*bob,recoil*0.055)
	weapon.rotation = Vector3(recoil*0.17+(0.55 if reload_time>0 else 0.0),0.0,0.0)
	slide.position.z = -0.015+recoil*0.065
	camera.fov = lerpf(camera.fov,55.0 if ads else 74.0,minf(1.0,delta*12.0))

func cast_shot(origin: Vector3, direction: Vector3, maximum_distance := 80.0) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(origin,origin+direction.normalized()*maximum_distance,1|2)
	query.exclude = [get_rid()]
	query.hit_from_inside = true
	return get_world_3d().direct_space_state.intersect_ray(query)

func apply_shot(hit: Dictionary, direction: Vector3) -> Dictionary:
	if hit.is_empty():
		return {"hit":false}
	var collider: Node = hit.collider
	var result := {"hit":true,"world":true,"point":[hit.position.x,hit.position.y,hit.position.z]}
	if collider.has_meta("zombie"):
		var zombie: Node3D = collider.get_meta("zombie")
		result = zombie.receive_hit(collider,hit.position,direction,arena.shot_impulse)
		result["hit"] = true
		result["world"] = false
	arena.mark_impact(hit.position,hit.normal,result.get("world",true))
	return result

func fire() -> void:
	if cooldown > 0.0 or reload_time > 0.0:
		return
	if magazine == 0:
		reload()
		return
	magazine -= 1
	shots += 1
	cooldown = 0.22
	recoil = 1.0
	flash_time = 0.055
	sound.play()
	var direction := -camera.global_basis.z
	var aim := cast_shot(camera.global_position,direction)
	var destination: Vector3 = aim.position if not aim.is_empty() else camera.global_position+direction*80.0
	# Check the segment to the muzzle as well: the barrel can poke through cover
	# while the camera remains outside it, or below a wall the camera sees over.
	var to_muzzle := muzzle.global_position-camera.global_position
	var obstruction := cast_shot(camera.global_position,to_muzzle,to_muzzle.length())
	var barrel_direction := (destination-muzzle.global_position).normalized()
	var hit := obstruction if not obstruction.is_empty() else cast_shot(muzzle.global_position,barrel_direction,minf(80.0,muzzle.global_position.distance_to(destination)+0.02))
	last_shot = apply_shot(hit,direction if not obstruction.is_empty() else barrel_direction)
	last_shot["sequence"] = shots
	arena.hit_flash = 0.18 if last_shot.get("hit",false) and not last_shot.get("world",true) else 0.0
