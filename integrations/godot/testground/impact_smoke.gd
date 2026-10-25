extends SceneTree
## Behavioral measurements of physical response, independent of hit animations.
var world
var report := {}
func _initialize() -> void: call_deferred("run")
func frames(count: int) -> void:
	for i in range(count): await physics_frame
func part(zombie: Node, bone: String) -> RigidBody3D:
	return zombie.physics.by_bone[zombie.skeleton.find_bone(bone)].body
func angular_momentum(zombie: Node) -> Vector3:
	var result := Vector3.ZERO
	var center: Vector3 = zombie.physics.center_of_mass
	for entry: Dictionary in zombie.physics.bodies:
		var body: RigidBody3D = entry.body
		var inverse := body.get_inverse_inertia_tensor()
		if absf(inverse.determinant())>0.000001: result += inverse.inverse()*body.angular_velocity
		result += (body.global_position-center).cross(body.linear_velocity*body.mass)
	return result
func fresh(model: int, airborne := false) -> Node:
	world.models.select(model+1)
	world.spawn_group()
	var zombie = world.zombies[0]
	if airborne:
		# Spawn a new articulated body above the floor, rather than moving an
		# already simulated body's parent or resetting velocities during impact.
		zombie.dispose()
		world.zombies.clear()
		zombie = world.Agent.new()
		world.add_child(zombie)
		zombie.setup(world,100,model,Vector3(0,5,-5),"")
		world.zombies.append(zombie)
		await frames(12)
	else:
		await frames(300)
	return zombie
func impact(model: int, bone: String, impulse: float, direct := false) -> Dictionary:
	var zombie = await fresh(model)
	assert(zombie.state=="active" and zombie.root_position().y>0.75,"Unhit rest pose must stand")
	var start: Vector3 = zombie.physics.center_of_mass
	var body := part(zombie,bone)
	var point := body.global_position+Vector3(0.015,0.02,0.03)
	var before := angular_momentum(zombie)
	if direct: body.apply_impulse(Vector3.FORWARD*impulse,point-body.global_position)
	else: zombie.receive_hit(body,point,Vector3.FORWARD,impulse)
	var minimum := 10.0
	var minimum_stability := 1.0
	var states := {}
	var early_yaw_momentum := 0.0
	var maximum_displacement := 0.0
	for i in range(360):
		await physics_frame
		if i==2: early_yaw_momentum = (angular_momentum(zombie)-before).y
		minimum = minf(minimum,zombie.root_position().y)
		minimum_stability = minf(minimum_stability,zombie.physics.stability)
		states[zombie.state]=true
		var offset: Vector3 = zombie.physics.center_of_mass-start
		maximum_displacement = maxf(maximum_displacement,-offset.z)
		assert(is_equal_approx(zombie.physics.muscles,world.muscle_strength),"Impact must not disable muscles")
		assert(not zombie.physics.passive,"Falling must retain the internal joint motors")
		assert(zombie.physics.max_skin_pose_error<0.001)
	var final_offset: Vector3 = zombie.physics.center_of_mass-start
	var result := {"final_backward_displacement_m":-final_offset.z,"model":model,"bone":bone,"impulse_ns":impulse,"direct_external_impulse":direct,
		"backward_displacement_m":maximum_displacement,"minimum_hips_y":minimum,
		"early_yaw_momentum":early_yaw_momentum,"minimum_stability":minimum_stability,"states":states.keys()}
	print("IMPACT_MEASURE ",JSON.stringify(result))
	return result
func run() -> void:
	create_timer(120).timeout.connect(func(): push_error("Impact test timeout");quit(1))
	world = load("res://testground/testground.tscn").instantiate()
	root.add_child(world)
	world.amount.value=1
	world.motions.select(1)
	world.auto_recover=false
	var results := []
	for model in range(2):
		var weak := await impact(model,"Spine",14.0)
		var strong := await impact(model,"Spine",100.0)
		var left := await impact(model,"LeftArm",70.0)
		var right := await impact(model,"RightArm",70.0)
		var external := await impact(model,"Spine2",120.0,true)
		results.append_array([weak,strong,left,right,external])
		assert(strong.backward_displacement_m>weak.backward_displacement_m+0.15,"Stronger torso hit must move the body farther")
		assert(strong.final_backward_displacement_m>0.5,"Body was pulled back to its original anchor")
		assert(strong.states.has("downed") and strong.minimum_hips_y<0.5,"Strong torso hit must topple the body")
		assert(left.early_yaw_momentum*right.early_yaw_momentum<0.0,"Opposite shoulders must twist in opposite directions")
		assert(left.states.has("downed") and right.states.has("downed"),"Heavy shoulder shots must cause a physical fall")
		assert(external.minimum_stability<0.1 and external.states.has("downed"),"A non-weapon force must also defeat support")
	# No floor contact => no virtual support. Relative motors must preserve
	# whole-body angular momentum, subject only to the configured damping.
	var flying = await fresh(0,true)
	var body := part(flying,"LeftArm")
	var point := body.global_position+Vector3(0.02,0.02,0)
	var before := angular_momentum(flying)
	var expected: Vector3 = before+(point-flying.physics.center_of_mass).cross(Vector3.FORWARD*40.0)
	body.apply_impulse(Vector3.FORWARD*40.0,point-body.global_position)
	await frames(48)
	var observed := angular_momentum(flying)
	var error: float = observed.distance_to(expected)/expected.length()
	print("IMPACT_AIRBORNE error=",error," expected=",expected," observed=",observed)
	assert(flying.physics.last_support_force.length()<0.001,"Airborne character has phantom support")
	assert(error<0.22,"Joint motors removed whole-body impact rotation in flight")
	# Real firing path: eight separate collision queries share one budget.
	var target = await fresh(1)
	world.player.position=Vector3(target.root_position().x,0.1,-1.5)
	var chest := part(target,"Spine").global_position
	world.player.rotation.y=0.0
	world.player.camera.look_at(chest)
	world.select_profile(2)
	world.player.cooldown=0.0
	world.player.fire()
	var shot: Dictionary = world.player.last_shot
	assert(shot.pellets.size()==8 and shot.body_hits>1,"Buckshot must hit through separate rays")
	assert(shot.delivered_ns<=shot.budget_ns+0.001,"Buckshot multiplied the impulse budget")
	for pellet: Dictionary in shot.pellets:
		if pellet.has("bone"): assert(is_equal_approx(pellet.impulse_ns,12.5))
	report={"status":"pass","impacts":results,"airborne_angular_momentum_relative_error":error,"buckshot":shot}
	FileAccess.open("res://../impact-validation.json",FileAccess.WRITE).store_string(JSON.stringify(report,"\t")+"\n")
	print("TESTGROUND_IMPACT_PASS ",JSON.stringify(report))
	quit()
