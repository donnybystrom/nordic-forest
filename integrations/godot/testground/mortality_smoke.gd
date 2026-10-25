extends SceneTree
const Model = preload("res://testground/damage_model.gd")
var world
var report := {"cases":[],"corpses":[],"queue":{},"traversal":[]}
func _initialize() -> void: call_deferred("run")
func frames(count: int) -> void:
	for i in range(count): await physics_frame
func part(z: Node, bone: String) -> Dictionary:
	return z.physics.by_bone[z.skeleton.find_bone(bone)]
func fresh(model: int) -> Node:
	world.models.select(model+1)
	world.amount.value=1
	world.motions.select(1)
	world.muscle_strength=1.0
	world.spawn_group()
	await frames(90)
	return world.zombies[0]
func check_pose(z: Node) -> float:
	var error := 0.0
	for p: Dictionary in z.physics.bodies:
		var actual: Transform3D = z.skeleton.global_transform*z.skeleton.get_bone_global_pose(p.index)
		var expected: Transform3D = p.body.global_transform*p.offset.affine_inverse()
		error=maxf(error,actual.origin.distance_to(expected.origin))
	return error
func run() -> void:
	create_timer(120).timeout.connect(func(): push_error("Mortality smoke timed out");quit(1))
	world=load("res://testground/testground.tscn").instantiate()
	root.add_child(world)
	world.auto_recover=false
	for model in range(2):
		var z=await fresh(model)
		world.muscle_strength=0.0
		await frames(90)
		assert(not z.dead and z.physics.movement_capacity().best==1.0,"Temporary lab controls/rest/falling cannot cause injury death")
		report.cases.append({"model":model,"test":"no_false_death_when_passive_or_fallen"})
		z=await fresh(model)
		for bone: String in ["LeftFoot","RightFoot","LeftHand","RightHand"]: z.physics.injure(bone,0.0)
		assert(not z.dead and z.physics.movement_capacity().best>0.08,"Forearms/shins can still drag without extremities")
		report.cases.append({"model":model,"test":"extremity_loss_retains_drag_capacity"})
		z=await fresh(model)
		z.physics.injure("LeftUpLeg",0.0)
		z.physics.injure("RightUpLeg",0.0)
		await frames(2)
		assert(not z.dead and "Crawl" in z.clip and z.physics.movement_capacity().crawl>0.08)
		z.physics.injure("LeftArm",0.0)
		assert(not z.dead,"One working arm must retain a locomotion route")
		var transforms := {}
		for p: Dictionary in z.physics.bodies: transforms[p.index]=p.body.global_transform
		var reference = weakref(z.physics.target)
		var animation = weakref(z.player)
		z.physics.injure("RightArm",0.0)
		assert(z.dead and z.state=="dead" and z.death_capacity.best==0.0)
		for p: Dictionary in z.physics.bodies:
			assert(p.body.global_transform==transforms[p.index],"Death teleported the body")
		await frames(3)
		assert(reference.get_ref()==null and animation.get_ref()==null and z.recovery==null,"Dead animation/get-up resources were retained")
		var ticks: int=z.live_ticks
		var motor_ticks: int=z.physics.live_ticks
		await frames(60)
		assert(z.live_ticks==ticks and z.physics.live_ticks==motor_ticks,"Corpse still runs live controllers")
		assert(not z.is_physics_processing() and not z.physics.is_physics_processing())
		assert(z.physics.last_support_force==Vector3.ZERO and z.physics.max_drive_torque==0.0)
		assert(z.physics.joints.size()==16,"Death discarded passive joint constraints")
		await create_timer(0.0).timeout
		var pose_error:=check_pose(z)
		print("CORPSE_POSE_ERROR model=",model," error=",pose_error)
		assert(pose_error<0.0001,"Corpse skin jumped after releasing the modifier/reference")
		# Sleeping pose is permanent; an impulse wakes only the passive body/skin.
		for p: Dictionary in z.physics.bodies:
			p.body.linear_velocity=Vector3.ZERO
			p.body.angular_velocity=Vector3.ZERO
			p.body.sleeping=true
		await frames(5)
		var poses: int=z.physics.corpse_pose_updates
		await frames(30)
		assert(z.physics.corpse_pose_updates==poses,"Sleeping corpse still updates bone poses")
		var body: RigidBody3D=part(z,"Spine").body
		var before: Vector3=body.global_position
		z.receive_hit(body,body.global_position,Vector3.RIGHT,35.0)
		await frames(20)
		assert(z.dead and z.physics.live_ticks==motor_ticks and body.global_position.distance_to(before)>0.005)
		assert(z.physics.corpse_pose_updates>poses,"Woken corpse did not resume visual bone syncing")
		report.corpses.append({"model":model,"skin_error":pose_error,"live_ticks_after_death":z.live_ticks-ticks,"motor_ticks_after_death":z.physics.live_ticks-motor_ticks,"sleep_pose_updates":0,"wake_displacement":body.global_position.distance_to(before),"passive_joints":16})
		report.cases.append({"model":model,"test":"all_routes_lost_permanent_passive_corpse"})
		z=await fresh(model)
		z.physics.set_neural_strength(0.4)
		assert(not z.dead and absf(z.physics.movement_capacity().best-0.4)<0.00001)
		z.physics.set_neural_strength(0.05)
		await frames(20)
		assert(not z.dead,"Weakness skipped its confirmation period")
		await frames(30)
		assert(z.dead and absf(z.death_capacity.best-0.05)<0.00001)
		z.physics.set_neural_strength(1.0)
		z.set_motion("Meshy_Walking")
		z.start_lying("prone")
		world.auto_recover=true
		await frames(90)
		assert(z.dead and z.state=="dead" and z.recovery==null and z.physics.movement_capacity().best==0.0,"A corpse revived")
		world.auto_recover=false
		report.cases.append({"model":model,"test":"partial_neural_loss_and_irreversible_threshold_death","capacity_at_death":z.death_capacity})
		# Shoot off an already dead forearm using the actual energy/cell/function
		# path, without running the dead agent's physics callback or forced flush.
		z=await fresh(model)
		z.physics.set_neural_strength(0.0)
		await frames(90)
		var shots := 0
		for attempt in range(24):
			z.damage.refresh_skin(true)
			var cell: Dictionary={}
			for id: int in z.damage.data.regions.LeftForeArm:
				if not z.damage.removed.has(id): cell=z.damage.data.cells[id];break
			if cell.is_empty(): break
			body=part(z,"LeftForeArm").body
			z.receive_hit(body,z.damage.centers[cell.id],Vector3.FORWARD,0.0,Model.projectile(1),cell.id)
			shots+=1
			await frames(5)
			if part(z,"LeftForeArm").detached: break
		assert(z.dead and part(z,"LeftForeArm").detached,"Event-driven corpse shots did not sever the limb")
		await frames(2)
		assert(not is_instance_valid(part(z,"LeftForeArm").joint))
		assert(z.damage.pending.is_empty() and not z.is_physics_processing())
		assert(z.damage.removed_volume<=z.damage.budget_volume+0.0000001)
		report.cases.append({"model":model,"test":"postmortem_energy_damage_severs_forearm","shots":shots,"damage":z.damage.report()})
	# A delayed wound must rotate with the hit part. Reproduce a quarter-turn
	# between recording the bullet and processing damage, before advancing physics.
	for model in range(2):
		var z=await fresh(model)
		var head: RigidBody3D=part(z,"Head").body
		var contact: Dictionary=z.damage.refine_ray(head.global_position+Vector3.BACK,Vector3.FORWARD,2.0)
		assert(not contact.is_empty())
		z.receive_hit(contact.collider,contact.position,Vector3.FORWARD,70.0,Model.projectile(1),contact.cell)
		head.global_basis=Basis(Vector3.UP,PI*0.5)*head.global_basis
		z.damage.flush(true)
		assert(z.dead and z.damage.brain_energy_j>=400.0,"Queued head rotation changed the recorded brain intersection")
		report.cases.append({"model":model,"test":"delayed_channel_rotates_with_impact_body","brain_energy_j":z.damage.brain_energy_j})
	# Walk through the same low corpse pile with each body type. No collision
	# layers are disabled and neither body is teleported during the traversal.
	for model in range(2):
		print("MORTALITY_TRAVERSAL_START model=",model)
		var corpse=await fresh(model)
		corpse.start_lying("prone")
		corpse.physics.set_neural_strength(0.0)
		for step in range(2400):
			await physics_frame
			if step>120 and not corpse.physics.is_processing(): break
		var sleeping := 0
		for p: Dictionary in corpse.physics.bodies:
			if p.body.sleeping: sleeping+=1
		if sleeping!=17 or corpse.physics.is_processing():
			for p: Dictionary in corpse.physics.bodies: print("CORPSE_SLEEP_DIAGNOSTIC model=",model," bone=",p.name," position=",p.body.global_position," linear=",p.body.linear_velocity," angular=",p.body.angular_velocity)
		assert(sleeping==17 and not corpse.physics.is_processing(),"Settled corpse did not stop all body/pose work")
		var sleeping_updates: int=corpse.physics.corpse_pose_updates
		var walker=world.Agent.new()
		world.add_child(walker)
		walker.setup(world,world.next_id,model,Vector3(-1.2,0,-6.5),"Meshy_Walking")
		world.next_id+=1
		world.zombies.append(walker)
		world.player.set_physics_process(false)
		world.player.position=Vector3(-1.2,0,-0.8)
		world.follow_player=true
		world.auto_recover=true
		var contacts := 0
		var height := 0.0
		var start: Vector3=walker.root_position()
		for i in range(2400):
			await physics_frame
			contacts+=walker.physics.corpse_support_contacts
			height=maxf(height,walker.anchor.y)
			if walker.root_position().z>-2.5: break
		assert(walker.root_position().z>-2.5 and contacts>0 and height>0.10,"Living zombie did not cross/support on the physical corpse")
		assert(corpse.dead and corpse.physics.last_support_force==Vector3.ZERO)
		assert(corpse.physics.corpse_pose_updates>sleeping_updates,"Living-body contact did not wake the sleeping corpse")
		report.traversal.append({"model":model,"distance_m":walker.root_position().z-start.z,"corpse_support_samples":contacts,"max_floor_m":height,"naturally_sleeping_before_contact":sleeping})
		print("MORTALITY_TRAVERSAL_PASS model=",model," result=",report.traversal.back())
		if DisplayServer.get_name()!="headless":
			world.follow_player=false
			world.menu.hide();world.player.weapon.hide()
			world.player.camera.global_position=Vector3(1.8,2.2,-1.3)
			world.player.camera.look_at(Vector3(-1.2,0.7,-3.5))
			await process_frame
			RenderingServer.force_draw(false)
			DirAccess.make_dir_recursive_absolute("res://../verification/mortality")
			root.get_texture().get_image().save_png("res://../verification/mortality/corpse-traversal-%d.png" % model)
		world.follow_player=false
		world.auto_recover=false
	# A very light detached limb must not be frozen in flight just because
	# its energy is tiny relative to the corpse. This isolates the speed guard.
	var moving=await fresh(0)
	moving.physics.set_neural_strength(0.0)
	await frames(900)
	moving.physics.detach("LeftHand")
	await frames(3)
	var flying: RigidBody3D=part(moving,"LeftHand").body
	flying.mass=0.001
	flying.gravity_scale=0.0
	flying.global_position=Vector3(0,3,-4)
	PhysicsServer3D.body_set_state(flying.get_rid(),PhysicsServer3D.BODY_STATE_TRANSFORM,flying.global_transform)
	flying.linear_velocity=Vector3.RIGHT*2.0
	flying.angular_velocity=Vector3.ZERO
	flying.sleeping=false
	var launched: Vector3=flying.global_position
	await frames(200)
	assert(not flying.sleeping and moving.physics.is_processing() and flying.global_position.distance_to(launched)>2.0,"Low-energy thrown limb was slept while moving")
	report.cases.append({"test":"light_thrown_limb_keeps_passive_physics_awake","distance_m":flying.global_position.distance_to(launched)})
	# Burst work drains over rendered frames, not a callback on every corpse.
	var z=await fresh(0)
	z.physics.set_neural_strength(0.0)
	await frames(2)
	var body: RigidBody3D=part(z,"Spine").body
	var prior: int=z.damage.processed_projectiles
	for i in range(24): z.receive_hit(body,body.global_position,Vector3.FORWARD,0.0,Model.projectile(0))
	assert(z.damage.processed_projectiles==prior and z.damage.pending.size()==24)
	while z.damage.processed_projectiles==prior: await process_frame
	var first: int=z.damage.processed_projectiles-prior
	assert(first==8 and z.damage.pending.size()==16,"Burst was not bounded to one 8-projectile batch")
	for i in range(30):
		if z.damage.pending.is_empty(): break
		await process_frame
	assert(z.damage.pending.is_empty() and z.damage.processed_projectiles-prior==24)
	report.queue={"queued":24,"first_frame":first,"remaining_after_first":16,"processed":z.damage.processed_projectiles-prior}
	# Corpses do not use living spawn slots; normal respawn preserves them.
	world.amount.value=12;world.models.select(0);world.spawn_group()
	await frames(2)
	var retained: Array = world.zombies.duplicate()
	for dead_body: Node in retained: dead_body.physics.set_neural_strength(0.0)
	assert(world.living_count()==0 and world.zombies.size()==12)
	for i in range(12): assert(world.spawn_one()!=null)
	assert(world.living_count()==12 and world.zombies.size()==24 and world.spawn_one()==null)
	world.amount.value=2;world.spawn_group(false)
	await frames(3)
	assert(world.living_count()==2 and world.zombies.size()==14)
	for dead_body: Node in retained: assert(is_instance_valid(dead_body) and dead_body.dead)
	world.clear_corpses();await frames(3)
	assert(world.zombies.size()==2 and get_nodes_in_group("testground_bodies").size()==34,"Explicit corpse cleanup leaked bodies")
	report.cases.append({"test":"twelve_corpses_plus_twelve_living_and_explicit_cleanup"})
	report.status="pass"
	var file:=FileAccess.open("res://../mortality-validation.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "));file.close()
	print("TESTGROUND_MORTALITY_PASS ",JSON.stringify(report))
	quit()
