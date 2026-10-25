extends Node3D
## The host never moves: only the hidden animation reference advances. All visible
## motion comes from the articulated bodies and the shared skeleton modifier.
const Recovery = preload("res://testground/recovery_motion.gd")
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
var support_pause := 0.0
var impact_momentum := Vector3.ZERO
var imbalance_time := 0.0
var recovery
var recovery_attempts := 0
var recovery_interruptions := 0
var recovery_completed := 0
var resting_time := 0.0
var upright_time := 0.0

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
	physics.configure(self, {"push_ball":false, "free_balance":true, "reference_transform":Transform3D(Basis.IDENTITY, spawn)})
	for part: Dictionary in physics.bodies:
		var body: RigidBody3D = part.body
		body.collision_mask |= 8
		body.set_meta("zombie", self)
		body.set_meta("bone", part.name)
		body.add_to_group("testground_bodies")
		body.body_entered.connect(func(other: Node):
			if other.has_meta("zombie") and other.get_meta("zombie") != self:
				crowd_contacts += 1)
	recovery = Recovery.new()
	recovery.configure(physics)
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
	if state=="recovering":
		recovery_interruptions += 1
		_enter_downed()
	var bone := str(body.get_meta("bone"))
	impact_momentum += impulse
	var duration := clampf(impact_momentum.length() / physics.total_mass * 1.2, 0.12, 0.9)
	if "Leg" in bone or bone == "Head":
		duration *= 1.25
	stagger_time = maxf(stagger_time, duration + 0.45)
	support_pause = maxf(support_pause, duration)
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
	support_pause = maxf(0.0, support_pause-delta)
	impact_momentum = impact_momentum.move_toward(Vector3.ZERO,physics.total_mass*1.5*delta)
	var disturbed: bool = physics.stability<0.2 and (physics.upright<0.6 or (physics.com_velocity-physics.desired_velocity).length()>0.6)
	imbalance_time = imbalance_time+delta if disturbed else 0.0
	if state=="active" and imbalance_time>0.12 and state_time>0.5:
		state="stagger"
		state_time=0.0
		stagger_time=0.6
	var expected: Transform3D = physics._animation_body(physics.by_bone[physics.target_rig.find_bone("Hips")])
	var relative_height: float = root.global_position.y - arena.floor_height(root.global_position)
	var expected_height := expected.origin.y - anchor.y
	var fallen: bool = relative_height < maxf(0.10 if "Crawl" in clip else 0.20, expected_height * 0.40)
	if state in ["active", "stagger"] and fallen and state_time > 0.4:
		_enter_downed()
	if state == "stagger" and stagger_time <= 0.0:
		state = "active"
		state_time = 0.0
	var quiet: bool = physics.com_velocity.length()<0.65 and root.angular_velocity.length()<2.5
	resting_time = resting_time+delta if quiet and support_pause<=0.0 else 0.0
	if state=="downed" and arena.auto_recover and state_time>2.0 and resting_time>0.25:
		state="recovering"
		state_time=0.0
		recovery_attempts += 1
		recovery.begin()
		heading=recovery.heading
	if state=="recovering":
		if not arena.auto_recover:
			_enter_downed()
		else:
			var complete: bool = recovery.advance(delta)
			upright_time = upright_time+delta if relative_height>expected_height*0.78 and physics.upright>0.65 else 0.0
			if complete and upright_time>0.25:
				recovery.stop()
				state="active"
				state_time=0.0
				recovery_completed += 1
			elif state_time>recovery.duration()+2.5:
				_enter_downed()
	physics.passive = false
	physics.muscles = arena.muscle_strength
	physics.balance = arena.balance_strength
	physics.assistance_scale = 0.0 if support_pause>0.0 or state=="downed" else 1.0
	physics.recovery_support = state=="recovering"
	physics.recovery_reach = recovery.last_weight if state=="recovering" else 0.0
	physics.desired_velocity = Vector3.ZERO
	if state == "recovering":
		var ramp := smoothstep(0.0,1.0,state_time)
		physics.assistance_scale = lerpf(0.15,1.0,ramp)
	physics.debug_shapes = arena.show_colliders
	if state == "active" and arena.follow_player:
		var destination: Vector3 = arena.steering_target(root.global_position)
		var offset := destination-root.global_position
		offset.y = 0.0
		var player_distance := Vector2(root.global_position.x-arena.player.position.x,root.global_position.z-arena.player.position.z).length()
		if offset.length() > 0.1 and player_distance > 1.2:
			var direction := offset.normalized()
			heading = lerp_angle(heading, atan2(direction.x,direction.z), minf(1.0,delta*2.2))
			physics.desired_velocity = direction * speed
	anchor.x = root.global_position.x
	anchor.z = root.global_position.z
	anchor.y = arena.floor_height(Vector3(anchor.x,0.0,anchor.z))
	physics.target.global_transform = Transform3D(Basis(Vector3.UP, heading), anchor)

func _enter_downed() -> void:
	if recovery.running: recovery.stop()
	state="downed"
	state_time=0.0
	resting_time=0.0
	upright_time=0.0
	# Hold the settled joint relationships until a get-up starts. This avoids
	# chasing the walk pose while lying down, with all muscles still available.
	physics.recovery_pose.clear()
	for part: Dictionary in physics.bodies: physics.recovery_pose[part.index]=part.body.global_transform

func start_lying(kind: String) -> void:
	# Spawn-only placement for repeatable menu tests. During a real fall/get-up,
	# the state machine never writes transforms or clears physical velocities.
	var poses: Dictionary = recovery.sample(kind,0.0,anchor,heading)
	for part: Dictionary in physics.bodies:
		part.body.global_transform=poses[part.index]
		PhysicsServer3D.body_set_state(part.body.get_rid(),PhysicsServer3D.BODY_STATE_TRANSFORM,poses[part.index])
		part.body.linear_velocity=Vector3.ZERO
		part.body.angular_velocity=Vector3.ZERO
	last_root=root_position()
	_enter_downed()

func dispose() -> void:
	physics.shutdown()
	queue_free()
