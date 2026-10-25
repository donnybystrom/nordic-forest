extends Node3D
## Articulated rigid bodies, pose torques, bounded pelvis support and a drag spring.
## Layer 1: ground; layer 2: body; layer 4: ball. Nearby joint neighbors exempt.
const PoseModifier = preload("res://physical_pose.gd")
const SEGMENTS := [
	["Hips", "Spine", 0.14, 0.13], ["Spine", "Spine2", 0.20, 0.145],
	["Spine2", "Neck", 0.17, 0.16], ["Neck", "Head", 0.02, 0.065],
	["Head", "", 0.07, 0.10],
	["LeftArm", "LeftForeArm", 0.025, 0.065], ["LeftForeArm", "LeftHand", 0.015, 0.05], ["LeftHand", "", 0.01, 0.055],
	["RightArm", "RightForeArm", 0.025, 0.065], ["RightForeArm", "RightHand", 0.015, 0.05], ["RightHand", "", 0.01, 0.055],
	["LeftUpLeg", "LeftLeg", 0.10, 0.085], ["LeftLeg", "LeftFoot", 0.045, 0.06], ["LeftFoot", "LeftToeBase", 0.015, 0.06],
	["RightUpLeg", "RightLeg", 0.10, 0.085], ["RightLeg", "RightFoot", 0.045, 0.06], ["RightFoot", "RightToeBase", 0.015, 0.06]]

var view: Node
var target: Node3D
var target_rig: Skeleton3D
var target_player: AnimationPlayer
var modifier: SkeletonModifier3D
var bodies: Array[Dictionary] = []
var by_bone: Dictionary = {}
var joints: Array[Generic6DOFJoint3D] = []
var ball: RigidBody3D
var ball_mesh: MeshInstance3D
var total_mass := 80.0
var muscles := 1.0
var balance := 1.0
var passive := false
var debug_shapes := false
var ground_lift := 0.0
var dragging := false
var drag_target := Vector3.ZERO
var drag_plane := Plane()
var last_clip := "!"
var ball_contacts := 0
var ground_contacts := 0
var max_drive_torque := 0.0
var last_support_force := Vector3.ZERO
var max_joint_gap := 0.0
var elapsed := 0.0
var modifier_samples := 0
var max_skin_pose_error := 0.0
var joint_gap_peak := {}
var ball_resets := 0
# The review lab retains its explicit fixed support. Arena mode instead uses
# internal joint motors and a yielding support at the body's current location.
var free_balance := false
var desired_velocity := Vector3.ZERO
var assistance_scale := 1.0
var recovery_support := false
var center_of_mass := Vector3.ZERO
var com_velocity := Vector3.ZERO
var support_points: Array[Vector3] = []
var support_distance := 0.0
var stability := 1.0
var upright := 1.0
var support_grace := 0.0
var recovery_pose := {}
var recovery_reach := 0.0

func configure(owner_view: Node, options: Dictionary = {}) -> void:
	view = owner_view
	free_balance = options.get("free_balance", false)
	total_mass = float(view.characters[view.model_index].get("physics_mass_kg", 80.0))
	target = (load(str(view.characters[view.model_index].scene)) as PackedScene).instantiate()
	target.name = "AnimationReference"
	target.visible = false
	add_child(target)
	target.global_transform = options.get("reference_transform", Transform3D.IDENTITY)
	target_rig = target.find_children("*", "Skeleton3D", true, false)[0]
	target_player = target.find_children("*", "AnimationPlayer", true, false)[0]
	target_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	_sync_reference()
	_build_bodies()
	_build_joints()
	_exclude_joint_neighbors()
	if options.get("push_ball", true):
		_build_ball()
	modifier = PoseModifier.new()
	modifier.controller = self
	view.skeleton.add_child(modifier)
	modifier.modification_processed.connect(_check_skin_pose)
	reset_pose()

func _sync_reference() -> void:
	var clip: String = view.selected_clip()
	if clip != last_clip:
		target_player.stop()
		target_rig.reset_bone_poses()
		if not clip.is_empty():
			target_player.play(clip)
		last_clip = clip
	if not clip.is_empty():
		target_player.seek(view.player.current_animation_position, true)
		target_player.advance(0)

func _build_bodies() -> void:
	var fraction_sum := 0.0
	for segment: Array in SEGMENTS:
		fraction_sum += float(segment[2])
	for segment: Array in SEGMENTS:
		var index := target_rig.find_bone(segment[0])
		assert(index >= 0, "Missing required physics bone " + str(segment[0]))
		var rest := target_rig.get_bone_global_rest(index)
		var tip: Vector3
		if segment[1] != "":
			tip = target_rig.get_bone_global_rest(target_rig.find_bone(segment[1])).origin
		elif segment[0] == "Head":
			tip = rest.origin + Vector3.UP * 0.18
		else:
			var parent := target_rig.get_bone_parent(index)
			tip = rest.origin + (rest.origin - target_rig.get_bone_global_rest(parent).origin).normalized() * 0.12
		var length := rest.origin.distance_to(tip)
		var radius: float = segment[3]
		var local_tip := rest.basis.inverse() * (tip - rest.origin)
		var offset := Transform3D(Basis.IDENTITY, local_tip * 0.5)
		var body := RigidBody3D.new()
		body.name = str(segment[0])
		body.mass = total_mass * float(segment[2]) / fraction_sum
		body.collision_layer = 2
		body.collision_mask = 1 | 2 | 4
		body.can_sleep = false
		body.continuous_cd = true
		body.linear_damp = 0.12
		body.angular_damp = 0.25
		body.contact_monitor = true
		body.max_contacts_reported = 8
		body.body_entered.connect(func(other: Node):
			if other is StaticBody3D:
				ground_contacts += 1)
		var material := PhysicsMaterial.new()
		material.friction = 0.85
		material.bounce = 0.02
		body.physics_material_override = material
		add_child(body)
		var shape := CollisionShape3D.new()
		var capsule := CapsuleShape3D.new()
		capsule.radius = radius
		capsule.height = maxf(length, radius * 2.0)
		shape.shape = capsule
		shape.basis = Basis(Quaternion(Vector3.UP, local_tip.normalized()))
		body.add_child(shape)
		var visual := MeshInstance3D.new()
		var capsule_mesh := CapsuleMesh.new()
		capsule_mesh.radius = radius
		capsule_mesh.height = capsule.height
		visual.mesh = capsule_mesh
		visual.basis = shape.basis
		var wire := StandardMaterial3D.new()
		wire.albedo_color = Color(0.15, 0.85, 0.95, 0.35)
		wire.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		wire.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		visual.material_override = wire
		visual.visible = false
		body.add_child(visual)
		var entry := {"index":index, "name":str(segment[0]), "body":body, "offset":offset,
			"radius":radius, "length":length, "axis":local_tip.normalized(), "height":capsule.height, "visual":visual}
		bodies.append(entry)
		by_bone[index] = entry

func _build_joints() -> void:
	for entry in bodies:
		var parent := target_rig.get_bone_parent(entry.index)
		while parent >= 0 and not by_bone.has(parent):
			parent = target_rig.get_bone_parent(parent)
		if parent < 0:
			continue
		var joint := Generic6DOFJoint3D.new()
		joint.name = "Joint_" + str(entry.name)
		add_child(joint)
		# Establish constraints in the reference rest frames, then reset the bodies
		# to the selected animation pose together. These are broad prototype limits.
		joint.global_transform = target_rig.global_transform * target_rig.get_bone_global_rest(entry.index)
		var limit := 130.0 if "Arm" in entry.name or "Leg" in entry.name else 70.0
		for axis in ["x", "y", "z"]:
			joint.set("linear_limit_" + axis + "/enabled", true)
			joint.set("linear_limit_" + axis + "/lower_distance", 0.0)
			joint.set("linear_limit_" + axis + "/upper_distance", 0.0)
			joint.set("angular_limit_" + axis + "/enabled", true)
			joint.set("angular_limit_" + axis + "/lower_angle", deg_to_rad(-limit))
			joint.set("angular_limit_" + axis + "/upper_angle", deg_to_rad(limit))
		# Bodies must be in their rest frames while joint-local anchors are captured.
		for bone_index in [parent, int(entry.index)]:
			var part: Dictionary = by_bone[bone_index]
			part.body.global_transform = target_rig.global_transform * target_rig.get_bone_global_rest(bone_index) * part.offset
		joint.node_a = joint.get_path_to(by_bone[parent].body)
		joint.node_b = joint.get_path_to(entry.body)
		joint.exclude_nodes_from_collision = true
		entry["parent_index"] = parent
		entry["anchor_a"] = by_bone[parent].body.to_local(joint.global_position)
		entry["anchor_b"] = entry.body.to_local(joint.global_position)
		joints.append(joint)

func _exclude_joint_neighbors() -> void:
	# Adjacent and second-neighbor proxies can overlap around real joints.
	# All more distant body pairs still collide (e.g. hands versus pelvis).
	for first in range(bodies.size()):
		var ancestors_a := _ancestors(bodies[first].index)
		for second in range(first + 1, bodies.size()):
			var ancestors_b := _ancestors(bodies[second].index)
			var distance := 100
			for step in range(ancestors_a.size()):
				var other_step := ancestors_b.find(ancestors_a[step])
				if other_step >= 0:
					distance = mini(distance, step + other_step)
			if distance <= 2:
				bodies[first].body.add_collision_exception_with(bodies[second].body)
				bodies[second].body.add_collision_exception_with(bodies[first].body)

func _ancestors(index: int) -> Array[int]:
	var result: Array[int] = [index]
	while by_bone[index].has("parent_index"):
		index = by_bone[index].parent_index
		result.append(index)
	return result

func _build_ball() -> void:
	ball = RigidBody3D.new()
	ball.name = "PushBall"
	ball.mass = 8.0
	ball.collision_layer = 4
	ball.collision_mask = 1 | 2
	ball.continuous_cd = true
	ball.contact_monitor = true
	ball.max_contacts_reported = 12
	ball.linear_damp = 0.18
	ball.angular_damp = 0.15
	ball.body_entered.connect(func(other: Node):
		if other is RigidBody3D and other.collision_layer == 2:
			ball_contacts += 1)
	var material := PhysicsMaterial.new()
	material.friction = 0.7
	material.bounce = 0.25
	ball.physics_material_override = material
	add_child(ball)
	var collider := CollisionShape3D.new()
	var sphere := SphereShape3D.new()
	sphere.radius = 0.17
	collider.shape = sphere
	ball.add_child(collider)
	ball_mesh = MeshInstance3D.new()
	var mesh := SphereMesh.new()
	mesh.radius = 0.17
	mesh.height = 0.34
	ball_mesh.mesh = mesh
	var orange := StandardMaterial3D.new()
	orange.albedo_color = Color("ef8528")
	orange.roughness = 0.5
	ball_mesh.material_override = orange
	ball.add_child(ball_mesh)

func reset_pose() -> void:
	_sync_reference()
	ground_lift = 0.0
	var initial_poses := {}
	for entry in bodies:
		var pose := _target_body(entry)
		if entry.has("parent_index"):
			# Preserve the joint anchors even when an animation rotates skipped
			# shoulder/spine bones. Do not start a reset with stretched joints.
			var parent_pose: Transform3D = initial_poses[entry.parent_index]
			pose.origin = parent_pose * entry.anchor_a - pose.basis * entry.anchor_b
		initial_poses[entry.index] = pose
	# Place the initial approximate collision hull above the floor. Subsequent
	# motion is simulated; there is no per-frame transform correction or foot IK.
	var lowest := 0.0
	for entry in bodies:
		var pose: Transform3D = initial_poses[entry.index]
		var center := pose.origin
		var half_segment := maxf(float(entry.height) * 0.5 - float(entry.radius), 0.0)
		var direction: Vector3 = pose.basis * entry.axis
		lowest = minf(lowest, center.y - absf(direction.y) * half_segment - float(entry.radius))
	ground_lift = -lowest + 0.015
	for entry in bodies:
		var body := entry.body as RigidBody3D
		var pose: Transform3D = initial_poses[entry.index]
		pose.origin.y += ground_lift
		body.global_transform = pose
		PhysicsServer3D.body_set_state(body.get_rid(), PhysicsServer3D.BODY_STATE_TRANSFORM, pose)
		body.linear_velocity = Vector3.ZERO
		body.angular_velocity = Vector3.ZERO
		body.sleeping = false
	reset_ball()

func reset_ball() -> void:
	if not is_instance_valid(ball):
		return
	ball_resets += 1
	end_drag()
	ball.global_position = root_body().global_position - view.camera.global_basis.x * 0.85 + view.camera.global_basis.z * 0.05 + Vector3.DOWN * 0.3
	ball.global_position.y = maxf(ball.global_position.y, 0.35)
	PhysicsServer3D.body_set_state(ball.get_rid(), PhysicsServer3D.BODY_STATE_TRANSFORM, ball.global_transform)
	ball.linear_velocity = Vector3.ZERO
	ball.angular_velocity = Vector3.ZERO
	ball.sleeping = false

func launch_ball() -> void:
	reset_ball()
	var direction: Vector3 = view.camera.global_basis.x
	ball.global_position = root_body().global_position - direction * 0.9 + Vector3.UP * 0.05
	PhysicsServer3D.body_set_state(ball.get_rid(), PhysicsServer3D.BODY_STATE_TRANSFORM, ball.global_transform)
	ball.apply_central_impulse(direction * ball.mass * 6.0)

func _check_skin_pose() -> void:
	# SkeletonModifier poses are transient. Inspect while the processed signal
	# is emitted to verify that skinning follows the simulated body transforms.
	modifier_samples += 1
	var rig: Skeleton3D = view.skeleton
	for entry in bodies:
		var expected: Transform3D = entry.body.global_transform * entry.offset.affine_inverse()
		var observed := rig.global_transform * rig.get_bone_global_pose(entry.index)
		max_skin_pose_error = maxf(max_skin_pose_error, expected.origin.distance_to(observed.origin))

func root_body() -> RigidBody3D:
	return by_bone[target_rig.find_bone("Hips")].body

func _target_body(entry: Dictionary) -> Transform3D:
	if recovery_pose.has(entry.index): return recovery_pose[entry.index]
	return _animation_body(entry)

func _animation_body(entry: Dictionary) -> Transform3D:
	var pose: Transform3D = target_rig.global_transform * target_rig.get_bone_global_pose(entry.index) * entry.offset
	# Keep the sandbox near the origin across locomotion loops. Animated vertical
	# movement and rotations remain targets; horizontal root motion is in-place.
	var hips_index := target_rig.find_bone("Hips")
	var animated_hips := target_rig.global_transform * target_rig.get_bone_global_pose(hips_index).origin
	var rest_hips := target_rig.global_transform * target_rig.get_bone_global_rest(hips_index).origin
	pose.origin.x -= animated_hips.x - rest_hips.x
	pose.origin.z -= animated_hips.z - rest_hips.z
	pose.origin.y += ground_lift
	return pose

func _physics_process(delta: float) -> void:
	if not is_instance_valid(view) or bodies.is_empty():
		return
	elapsed += delta
	_sync_reference()
	max_drive_torque = 0.0
	if free_balance:
		_measure_support(delta)
	for entry in bodies:
		var body := entry.body as RigidBody3D
		if not passive and muscles > 0.0 and (not free_balance or entry.has("parent_index")):
			var desired := _target_body(entry).basis.get_rotation_quaternion()
			var current := body.global_basis.get_rotation_quaternion()
			var relative_velocity := body.angular_velocity
			var parent_body: RigidBody3D
			if free_balance:
				var parent: Dictionary = by_bone[entry.parent_index]
				parent_body = parent.body
				# Preserve the animated child-to-parent rotation, allowing the whole
				# body to rotate freely. Each motor has an equal opposite reaction.
				var relative_target := _target_body(parent).basis.inverse() * _target_body(entry).basis
				desired = (parent_body.global_basis * relative_target).get_rotation_quaternion()
				relative_velocity -= parent_body.angular_velocity
			var error := (desired * current.inverse()).normalized()
			if error.w < 0:
				error = -error
			var angle := error.get_angle()
			# Implicit PD gains and the actual world-space inertia avoid overdriving
			# the light twist axis of a long capsule with its bending-axis inertia.
			var kp := (6000.0 if free_balance else 2200.0) * muscles
			var kd := (120.0 if free_balance else 90.0) * sqrt(muscles)
			var gain := 1.0 / (1.0 + kd * delta + kp * delta * delta)
			var acceleration := (error.get_axis() * angle * kp - relative_velocity * (kd + kp * delta)) * gain
			var inverse_inertia := body.get_inverse_inertia_tensor()
			if free_balance:
				var parent_inverse := parent_body.get_inverse_inertia_tensor()
				inverse_inertia = Basis(inverse_inertia.x+parent_inverse.x,inverse_inertia.y+parent_inverse.y,inverse_inertia.z+parent_inverse.z)
			var torque := Vector3.ZERO
			if absf(inverse_inertia.determinant()) > 0.000001:
				torque = inverse_inertia.inverse() * acceleration
			torque = torque.limit_length(body.mass * 12.0 * muscles)
			body.apply_torque(torque)
			if free_balance:
				parent_body.apply_torque(-torque)
			max_drive_torque = maxf(max_drive_torque, torque.length())
		entry.visual.visible = debug_shapes
		if entry.has("parent_index"):
			var parent_body: RigidBody3D = by_bone[entry.parent_index].body
			var gap := parent_body.to_global(entry.anchor_a).distance_to(body.to_global(entry.anchor_b))
			if gap > max_joint_gap:
				max_joint_gap = gap
				joint_gap_peak = {"bone":entry.name, "clip":last_clip, "elapsed_s":elapsed, "passive":passive}
	last_support_force = Vector3.ZERO
	if free_balance:
		_apply_free_support(delta)
	elif not passive and balance > 0.0:
		var hips := root_body()
		var destination := _target_body(by_bone[target_rig.find_bone("Hips")]).origin
		# A visible, bounded virtual pelvis support, NOT a self-balancing controller.
		last_support_force = ((destination - hips.global_position) * 1800.0 - hips.linear_velocity * 320.0 + Vector3.UP * total_mass * 9.8) * balance
		last_support_force = last_support_force.limit_length(total_mass * 9.8 * 2.0 * balance)
		hips.apply_central_force(last_support_force)
	if dragging:
		var force := ((drag_target - ball.global_position) * 950.0 - ball.linear_velocity * 75.0).limit_length(850.0)
		ball.apply_central_force(force)
		ball.sleeping = false

func _measure_support(delta: float) -> void:
	center_of_mass = Vector3.ZERO
	com_velocity = Vector3.ZERO
	var contacts: Array[Vector3] = []
	for entry in bodies:
		var body: RigidBody3D = entry.body
		center_of_mass += body.global_position * body.mass / total_mass
		com_velocity += body.linear_velocity * body.mass / total_mass
		# Feet for standing; hands/knees can support the crawl reference too.
		var crawl := "Crawl" in last_clip
		if "Foot" not in entry.name and not (crawl and ("Hand" in entry.name or "Leg" in entry.name)):
			continue
		var state := PhysicsServer3D.body_get_direct_state(body.get_rid())
		if state == null: continue
		for i in range(state.get_contact_count()):
			var other := state.get_contact_collider_object(i)
			var point := state.get_contact_local_position(i)
			# Reject wall contacts and other characters as a standing platform.
			if other is StaticBody3D and other.get_meta("walkable", false) and point.y < body.global_position.y:
				contacts.append(point)
		# Animation can lift a foot briefly. Allow a short leg-reach margin, but
		# expire the support once the feet leave this ground-reach margin.
		var half_segment := maxf(float(entry.height)*0.5-float(entry.radius),0.0)
		var bottom := body.global_position.y-absf((body.global_basis*entry.axis).y)*half_segment-float(entry.radius)
		var query := PhysicsRayQueryParameters3D.create(body.global_position+Vector3.UP*0.3,body.global_position-Vector3.UP*0.7,1)
		var floor_hit := get_world_3d().direct_space_state.intersect_ray(query)
		if not floor_hit.is_empty() and floor_hit.collider.get_meta("walkable",false) and bottom-floor_hit.position.y<0.20:
			contacts.append(floor_hit.position)
	if not contacts.is_empty():
		support_points = contacts
		support_grace = 0.16
	else:
		support_grace = maxf(0.0, support_grace-delta)
		if support_grace <= 0.0: support_points.clear()
	var hips_entry: Dictionary = by_bone[target_rig.find_bone("Hips")]
	var rotation_error := root_body().global_basis * _target_body(hips_entry).basis.inverse()
	upright = (rotation_error * Vector3.UP).dot(Vector3.UP)
	# Velocity shifts the projected COM towards the place it would need a new
	# step. This is a broad capsule footprint, not a foot-placement controller.
	var projected := center_of_mass + Vector3(com_velocity.x-desired_velocity.x,0,com_velocity.z-desired_velocity.z)*0.30
	projected.y = 0.0
	support_distance = 10.0
	for a in support_points:
		a.y = 0.0
		for b in support_points:
			b.y = 0.0
			var closest := a
			if a.distance_squared_to(b)>0.00001:
				closest = Geometry3D.get_closest_point_to_segment(projected,a,b)
			support_distance = minf(support_distance,projected.distance_to(closest))
	var footprint := 1.0-smoothstep(0.20,0.55,support_distance)
	var tilt := smoothstep(0.35,0.85,upright)
	stability = footprint * tilt if not support_points.is_empty() else 0.0

func _apply_free_support(delta: float) -> void:
	if passive or balance <= 0.0: return
	var hips := root_body()
	var entry: Dictionary = by_bone[target_rig.find_bone("Hips")]
	var desired := _target_body(entry)
	var gain := stability * assistance_scale * balance
	# Recovery is deliberately an optional virtual lifting aid, never a reset.
	if recovery_support: gain = assistance_scale * balance
	if gain <= 0.001: return
	var height_error := desired.origin.y-hips.global_position.y
	last_support_force.y = clampf(total_mass*9.8+height_error*1800.0-hips.linear_velocity.y*240.0,0.0,total_mass*9.8*1.8)*gain
	# Velocity control at the current location: no horizontal position spring,
	# no stored spawn target, and no braking while the support has yielded.
	var velocity_error := desired_velocity-Vector3(com_velocity.x,0,com_velocity.z)
	if recovery_support:
		var placement := desired.origin-hips.global_position
		placement.y=0.0
		velocity_error += placement*2.5
	var horizontal := (velocity_error * total_mass * 3.0).limit_length(total_mass*2.0)*gain
	last_support_force += horizontal
	hips.apply_central_force(last_support_force)
	if recovery_support and recovery_reach>0.0:
		# Bounded virtual hand/foot placement during this authored manoeuvre.
		# Collision response remains active; no limb transform is overwritten.
		for bone in ["LeftHand","RightHand","LeftFoot","RightFoot"]:
			var limb: Dictionary = by_bone[target_rig.find_bone(bone)]
			var body: RigidBody3D = limb.body
			var error := _target_body(limb).origin-body.global_position
			var force := (error*80.0-body.linear_velocity*10.0)*body.mass
			body.apply_central_force(force.limit_length(total_mass*9.8*0.12)*recovery_reach*balance)
	# Distributed virtual upright assistance. Joint motors above still act in
	# equal opposite pairs; only this explicitly named support rights the body.
	for part in bodies:
		var core: bool = part.name in ["Hips","Spine","Spine2"]
		var pose_gain := 1.0 if core else (recovery_reach if recovery_support else 0.0)
		if pose_gain<=0.0: continue
		var body: RigidBody3D = part.body
		var error := (_target_body(part).basis.get_rotation_quaternion()*body.global_basis.get_rotation_quaternion().inverse()).normalized()
		if error.w<0: error = -error
		var acceleration := (error.get_axis()*error.get_angle()*2200.0-body.angular_velocity*(90.0+2200.0*delta))/(1.0+90.0*delta+2200.0*delta*delta)
		var inverse_inertia := body.get_inverse_inertia_tensor()
		if absf(inverse_inertia.determinant())>0.000001:
			body.apply_torque((inverse_inertia.inverse()*acceleration).limit_length(body.mass*12.0)*gain*pose_gain)

func begin_drag(point: Vector2, camera: Camera3D) -> bool:
	var from := camera.project_ray_origin(point)
	var to := from + camera.project_ray_normal(point) * 100.0
	var query := PhysicsRayQueryParameters3D.create(from, to, 4)
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty() or hit.collider != ball:
		return false
	dragging = true
	drag_target = ball.global_position
	drag_plane = Plane(-camera.global_basis.z, ball.global_position)
	return true

func update_drag(point: Vector2, camera: Camera3D) -> void:
	var hit: Variant = drag_plane.intersects_ray(camera.project_ray_origin(point), camera.project_ray_normal(point))
	if hit is Vector3:
		drag_target = hit
		drag_target.y = clampf(drag_target.y, 0.2, 3.0)

func end_drag() -> void:
	dragging = false

func shutdown() -> void:
	set_physics_process(false)
	end_drag()
	if is_instance_valid(modifier):
		modifier.active = false
		modifier.queue_free()
	for entry in bodies:
		entry.body.collision_layer = 0
		entry.body.collision_mask = 0
		entry.body.freeze = true
	if is_instance_valid(ball):
		ball.collision_layer = 0
		ball.collision_mask = 0
		ball.freeze = true
