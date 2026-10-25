extends SceneTree
var world
var report := {}

func _initialize() -> void:
	call_deferred("_run")

func frames(count: int) -> void:
	for i in range(count): await physics_frame

func snapshot(label: String) -> void:
	if DisplayServer.get_name() == "headless": return
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../testground-"+label+".png")

func _run() -> void:
	create_timer(120).timeout.connect(func(): push_error("Testground smoke timed out");quit(1))
	world = load("res://testground/testground.tscn").instantiate()
	root.add_child(world)
	world.damage_enabled=false
	await frames(300)
	assert(world.zombies.size()==4)
	var ids := {}
	var clips := {}
	var anchors := []
	for zombie in world.zombies:
		ids[zombie.characters[zombie.model_index].id]=true
		clips[zombie.clip]=true
		assert(zombie.physics.bodies.size()==17 and zombie.physics.joints.size()==16)
		assert(zombie.physics.ball==null,"Arena should not spawn review balls")
		assert(zombie.physics.max_skin_pose_error<0.001)
		assert(zombie.root_position().is_finite() and zombie.root_position().z<0.0,"Spawn transform lost")
		anchors.append(zombie.anchor)
	assert(ids.size()==2 and clips.size()==4)
	await frames(180)
	for zombie in world.zombies: assert(zombie.physics.desired_velocity==Vector3.ZERO,"Stationary group requested locomotion")
	world.set_menu(false)
	await snapshot("group")
	world.set_menu(true)
	world.follow_player=true
	var before: Vector3=world.zombies[0].root_position()
	var before_distance: float=before.distance_to(world.player.position)
	await frames(720)
	var after: Vector3=world.zombies[0].root_position()
	print("TESTGROUND_FOLLOW before=",before," after=",after)
	assert(after.distance_to(world.player.position)<before_distance-0.3,"Follower did not approach player")
	report["follow_distance_gained_m"]=before_distance-after.distance_to(world.player.position)
	world.follow_player=false
	world.amount.value=2
	world.motions.select(1)
	world.spawn_group()
	await frames(240)
	assert(get_nodes_in_group("testground_bodies").size()==34,"Respawn leaked old bodies")
	var hits := []
	for index in range(2):
		var zombie = world.zombies[index]
		var bone := "Head" if index==0 else "LeftForeArm"
		var part: RigidBody3D=zombie.physics.by_bone[zombie.skeleton.find_bone(bone)].body
		var point:=part.global_position+Vector3(0.025,0,0)
		var origin:=point+Vector3(0,0,2)
		var ray: Dictionary=world.player.cast_shot(origin,Vector3.FORWARD)
		assert(not ray.is_empty() and ray.collider==part,"Hitbox ray must select the requested body")
		var old_velocity:=part.linear_velocity
		var result: Dictionary=world.player.apply_shot(ray,Vector3.FORWARD)
		assert(result.bone==bone and result.impulse_ns==world.shot_impulse)
		assert(Vector3(result.angular_impulse[0],result.angular_impulse[1],result.angular_impulse[2]).length()>0.05,"Offset impact lost torque")
		await frames(3)
		assert(part.linear_velocity.distance_to(old_velocity)>0.05,"Impulse did not change physical velocity")
		hits.append(result)
		assert(zombie.state in ["stagger","downed"])
	report["point_impulses"]=hits
	# Cover is included in the same ray mask, so a body behind a wall is not hit.
	var cover: Dictionary=world.player.cast_shot(Vector3(-3.2,1.0,2),Vector3.FORWARD)
	assert(not cover.is_empty() and cover.collider is StaticBody3D)
	var cover_result: Dictionary=world.player.apply_shot(cover,Vector3.FORWARD)
	assert(cover_result.world and not cover_result.has("bone"))
	world.player.position=Vector3(-3.2,0.1,0.55)
	assert(world.player.cast_shot(world.player.camera.global_position,Vector3.FORWARD).is_empty(),"Camera should see over low cover in this test")
	world.player.fire()
	assert(world.player.last_shot.get("world",false),"Cover between camera and barrel must stop the shot")
	var shots: int=world.player.shots
	world.player.fire()
	assert(world.player.shots==shots,"Semi-auto cooldown failed")
	world.player.reload()
	assert(world.player.reload_time>0.0)
	await frames(180)
	assert(world.player.magazine==12 and world.player.reload_time<=0.0)
	report["cover_blocks_shots"]=true
	report["muzzle_obstruction"]=true
	report["cooldown_and_reload"]=true
	# A fall and recovery must use simulation; no reset_pose or body transform
	# writes occur in the agent state machine. Capture the observed transition.
	world.player.position=Vector3(0,0.1,7)
	world.spawn_group()
	await frames(200)
	var recovering=world.zombies[0]
	var leg: RigidBody3D=recovering.physics.by_bone[recovering.skeleton.find_bone("LeftUpLeg")].body
	world.shot_impulse=40.0
	recovering.receive_hit(leg,leg.global_position+Vector3(0.04,0,0),Vector3.FORWARD,40.0)
	var states := {}
	var minimum_height:=10.0
	for frame in range(1800):
		await physics_frame
		states[recovering.state]=true
		minimum_height=minf(minimum_height,recovering.root_position().y)
		assert(recovering.root_position().is_finite())
	print("TESTGROUND_RECOVERY ",states," min_y=",minimum_height," final_y=",recovering.root_position().y)
	assert(states.has("downed") and states.has("recovering"),"No physical knockdown/recovery observed")
	assert(recovering.state=="active" and recovering.root_position().y>0.65,"Assisted recovery did not stand")
	report["assisted_recovery"]={"states":states.keys(),"minimum_hips_y":minimum_height,"final_hips_y":recovering.root_position().y}
	world.player.position=Vector3(0,0.1,-1.0)
	world.amount.value=4
	world.motions.select(3)
	world.formation.select(1)
	world.spawn_group()
	await frames(180)
	world.follow_player=true
	var max_speed:=0.0
	for frame in range(1200):
		await physics_frame
		for zombie in world.zombies:
			for part: Dictionary in zombie.physics.bodies:
				assert(part.body.global_transform.is_finite())
				max_speed=maxf(max_speed,part.body.linear_velocity.length())
	var contacts:=0
	for zombie in world.zombies: contacts+=zombie.crowd_contacts
	print("TESTGROUND_CROWD contacts=",contacts," max_speed=",max_speed)
	assert(contacts>0,"Crowd bodies never collided")
	assert(max_speed<35.0,"Crowd physics became explosive")
	assert(get_nodes_in_group("testground_bodies").size()==68)
	world.set_menu(false)
	await snapshot("crowd")
	report["crowd_contacts"]=contacts
	report["maximum_crowd_speed_m_s"]=max_speed
	world.follow_player=false
	world.amount.value=12
	world.spawn_group()
	await frames(120)
	assert(world.zombies.size()==12 and get_nodes_in_group("testground_bodies").size()==204)
	for zombie in world.zombies:
		assert(zombie.root_position().is_finite() and zombie.physics.max_skin_pose_error<0.001)
	world.amount.value=1
	world.spawn_group()
	await frames(3)
	assert(get_nodes_in_group("testground_bodies").size()==17,"Maximum-size respawn leaked bodies")
	report["spawn_capacity_and_cleanup"]={"zombies":12,"bodies":204,"remaining_after_replace":17}
	report["models"]=ids.keys()
	report["status"]="pass"
	var file:=FileAccess.open("res://../testground-validation.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  ")+"\n")
	print("TESTGROUND_PHYSICS_PASS ",JSON.stringify(report))
	quit()
