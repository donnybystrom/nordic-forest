extends Node3D
## The host never moves: only the hidden animation reference advances. All visible
## motion comes from the articulated bodies and the shared skeleton modifier.
const Ragdoll = preload("res://active_ragdoll.gd")
var arena: Node3D
var characters: Array
var model_index := 0
var skeleton: Skeleton3D
var player: AnimationPlayer
var camera: Camera3D
var physics
var character: Node3D
var clip := ""
var anchor := Vector3.ZERO
var heading := 0.0
var speed := 0.65
var state := "active"
var stagger_time := 0.0
var state_time := 0.0
var received_hits := 0
var crowd_contacts := 0
var travel := 0.0
var last_root := Vector3.ZERO
var last_hit := {}

func setup(world: Node3D, index: int, model: int, spawn: Vector3, motion: String) -> void:
	arena = world
	name = "Zombie_%02d" % index
	characters = world.catalog.characters
	model_index = model
	camera = world.player.camera
	anchor = spawn
	character = (load(str(characters[model].scene)) as PackedScene).instantiate()
	add_child(character)
	skeleton = character.find_children("*", "Skeleton3D", true, false)[0]
	player = character.find_children("*", "AnimationPlayer", true, false)[0]
	set_motion(motion, float(index) * 0.23)
	physics = Ragdoll.new()
	add_child(physics)
	physics.configure(self, {"push_ball":false, "reference_transform":Transform3D(Basis.IDENTITY, spawn)})
	for part: Dictionary in physics.bodies:
		var body: RigidBody3D = part.body
		body.collision_mask |= 8
		body.set_meta("zombie", self)
		body.set_meta("bone", part.name)
		body.add_to_group("testground_bodies")
		body.body_entered.connect(func(other: Node):
			if other.has_meta("zombie") and other.get_meta("zombie") != self:
				crowd_contacts += 1)
	last_root = physics.root_body().global_position

func selected_clip() -> String:
	return clip

func set_motion(motion: String, phase := 0.0) -> void:
	clip = motion
	player.stop()
	skeleton.reset_bone_poses()
	if not clip.is_empty() and player.has_animation(clip):
		player.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
		player.play(clip)
		player.seek(fmod(phase, player.get_animation(clip).length), true)
		player.advance(0)
	speed = 0.34 if "Crawl" in clip else (1.25 if "Running" in clip else 0.65)

func root_position() -> Vector3:
	return physics.root_body().global_position

func receive_hit(body: RigidBody3D, point: Vector3, direction: Vector3, magnitude: float) -> Dictionary:
	var impulse := direction.normalized() * magnitude
	var lever := point - body.global_position
	# apply_impulse expects a world-space offset from the body origin. Applying
	# centrally here would erase the requested dependence on the impact location.
	body.apply_impulse(impulse, lever)
	body.sleeping = false
	received_hits += 1
	var bone := str(body.get_meta("bone"))
	var duration := clampf(magnitude / 18.0, 0.25, 1.8)
	if "Leg" in bone or bone == "Head":
		duration *= 1.25
	stagger_time = maxf(stagger_time, duration)
	if state == "active":
		state = "stagger"
		state_time = 0.0
	anchor.x = root_position().x
	anchor.z = root_position().z
	last_hit = {"zombie":name, "model":characters[model_index].id, "bone":bone,
		"point":[point.x,point.y,point.z], "impulse":[impulse.x,impulse.y,impulse.z],
		"impulse_ns":magnitude, "lever":[lever.x,lever.y,lever.z],
		"angular_impulse":[lever.cross(impulse).x,lever.cross(impulse).y,lever.cross(impulse).z]}
	return last_hit

func _physics_process(delta: float) -> void:
	if not is_instance_valid(physics):
		return
	var root := physics.root_body() as RigidBody3D
	travel += Vector2(root.global_position.x-last_root.x,root.global_position.z-last_root.z).length()
	last_root = root.global_position
	state_time += delta
	stagger_time = maxf(0.0, stagger_time-delta)
	var expected: Transform3D = physics._target_body(physics.by_bone[physics.target_rig.find_bone("Hips")])
	var relative_height: float = root.global_position.y - arena.floor_height(root.global_position)
	var expected_height := expected.origin.y - anchor.y
	var fallen: bool = relative_height < maxf(0.20, expected_height * 0.48)
	if state in ["active", "stagger"] and fallen and state_time > 0.4:
		state = "downed"
		state_time = 0.0
	if state == "stagger" and stagger_time <= 0.0:
		state = "active"
		state_time = 0.0
	if state in ["stagger", "downed", "recovering"]:
		anchor.x = root.global_position.x
		anchor.z = root.global_position.z
	if state == "downed" and arena.auto_recover and state_time > 2.0 and stagger_time <= 0.0:
		state = "recovering"
		state_time = 0.0
	if state == "recovering" and state_time > 1.5 and relative_height > expected_height * 0.82:
		state = "active"
		state_time = 0.0
	physics.passive = state == "downed"
	physics.muscles = arena.muscle_strength
	physics.balance = arena.balance_strength
	if state == "stagger":
		physics.muscles *= 0.3
		physics.balance = 0.0
	elif state == "recovering":
		var ramp := clampf(state_time / 3.0, 0.0, 1.0)
		physics.muscles *= lerpf(0.25, 1.0, ramp)
		physics.balance *= lerpf(0.2, 1.0, ramp)
	physics.debug_shapes = arena.show_colliders
	if state == "active" and arena.follow_player:
		var destination: Vector3 = arena.steering_target(root.global_position)
		var offset := destination-root.global_position
		offset.y = 0.0
		var player_distance := Vector2(root.global_position.x-arena.player.position.x,root.global_position.z-arena.player.position.z).length()
		if offset.length() > 0.1 and player_distance > 1.2:
			var direction := offset.normalized()
			heading = lerp_angle(heading, atan2(direction.x,direction.z), minf(1.0,delta*2.2))
			anchor += direction * speed * delta
			# A blocked body cannot accumulate an arbitrarily distant spring target.
			var lead := Vector2(anchor.x-root.global_position.x,anchor.z-root.global_position.z).limit_length(0.55)
			anchor.x = root.global_position.x+lead.x
			anchor.z = root.global_position.z+lead.y
	anchor.x = clampf(anchor.x,-13.0,13.0)
	anchor.z = clampf(anchor.z,-13.0,13.0)
	anchor.y = arena.floor_height(Vector3(anchor.x,0.0,anchor.z))
	physics.target.global_transform = Transform3D(Basis(Vector3.UP, heading), anchor)

func dispose() -> void:
	physics.shutdown()
	queue_free()
