extends SceneTree
## Exercise both retargeted get-up clips, physics transitions and interruptions.
var world
var report := {"cases":[]}
func _initialize() -> void: call_deferred("run")
func frames(count: int) -> void:
	for i in range(count): await physics_frame
func reset_case(model: int, choice: int) -> Node:
	world.follow_player=false
	world.auto_recover=true
	world.models.select(model+1)
	world.motions.select(choice)
	world.spawn_group()
	await frames(1)
	return world.zombies[0]
func run() -> void:
	create_timer(150).timeout.connect(func(): push_error("Recovery test timed out");quit(1))
	world=load("res://testground/testground.tscn").instantiate()
	root.add_child(world)
	world.amount.value=1
	for model in range(2):
		for choice in [6,7]:
			var zombie=await reset_case(model,choice)
			var wanted: String = "prone" if choice==6 else "supine"
			assert(zombie.recovery.choose()==wanted,"Wrong face-up/face-down selection")
			var stages := {}
			var previous := zombie.root_position() as Vector3
			var max_step := 0.0
			var max_speed := 0.0
			var maximum_target_step := 0.0
			var old_targets := {}
			var old_state := "downed"
			var transitions := []
			var done := false
			for frame in range(1800):
				await physics_frame
				if frame%240==0: print("GETUP_PROGRESS model=",model," choice=",choice," state=",zombie.state," position=",zombie.root_position()," time=",zombie.recovery.time," heading=",zombie.recovery.heading," attempts=",zombie.recovery_attempts," done=",zombie.recovery_completed)
				if zombie.state!=old_state:
					transitions.append([old_state,zombie.state])
					old_state=zombie.state
				if zombie.state=="recovering":
					assert(zombie.recovery.kind==wanted)
					stages[zombie.recovery.stage]=true
					for part: Dictionary in zombie.physics.bodies:
						var pose: Transform3D = zombie.physics._target_body(part)
						if old_targets.has(part.index): maximum_target_step=maxf(maximum_target_step,pose.basis.get_rotation_quaternion().angle_to(old_targets[part.index]))
						old_targets[part.index]=pose.basis.get_rotation_quaternion()
				max_step=maxf(max_step,zombie.root_position().distance_to(previous))
				previous=zombie.root_position()
				for part: Dictionary in zombie.physics.bodies:
					max_speed=maxf(max_speed,part.body.linear_velocity.length())
					assert(part.body.global_transform.is_finite())
				assert(zombie.physics.muscles==world.muscle_strength and not zombie.physics.passive)
				if zombie.recovery_completed>0:
					done=true
					break
			assert(done,"Get-up did not finish")
			assert(zombie.state=="active" and zombie.root_position().y>0.75)
			assert(stages.size()>=6 and stages.has("blandar till rörelse"),"Missing authored phases or exit blend")
			assert(zombie.physics.recovery_pose.is_empty() and not zombie.recovery.running)
			assert(zombie.player.current_animation==zombie.clip,"Original locomotion clip was lost")
			assert(max_step<0.10 and max_speed<18.0,"Get-up caused a pop or unstable motion")
			assert(maximum_target_step<0.4,"Pose targets jumped between recovery stages")
			assert(zombie.physics.max_skin_pose_error<0.001)
			world.follow_player=true
			var before: float = zombie.root_position().distance_to(world.player.position)
			await frames(240)
			assert(zombie.root_position().distance_to(world.player.position)<before-0.1,"Following did not resume")
			var result := {"model":model,"kind":wanted,"stages":stages.keys(),"transitions":transitions,"maximum_root_step_m":max_step,"maximum_body_speed_m_s":max_speed,"maximum_target_rotation_step_rad":maximum_target_step,"attempts":zombie.recovery_attempts,"following_resumed":true}
			report.cases.append(result)
			print("GETUP_CASE ",JSON.stringify(result))
	# A second hit must interrupt immediately without moving bodies or erasing
	# their existing momentum. A subsequent settled attempt chooses afresh.
	var interrupted=await reset_case(1,7)
	while interrupted.state!="recovering": await physics_frame
	await frames(150)
	var part: RigidBody3D=interrupted.physics.root_body()
	var at:=part.global_transform
	var velocity:=part.linear_velocity
	interrupted.receive_hit(part,part.global_position+Vector3(0.03,0,0.03),Vector3.FORWARD,70.0)
	assert(interrupted.state=="downed" and not interrupted.recovery.running)
	assert(part.global_transform==at and part.linear_velocity==velocity,"Interruption teleported or cleared velocities")
	await frames(3)
	assert(part.linear_velocity.distance_to(velocity)>0.05)
	assert(interrupted.recovery_interruptions==1)
	world.auto_recover=false
	await frames(480)
	assert(interrupted.state=="downed","Disabled recovery restarted itself")
	world.auto_recover=true
	var complete := false
	for i in range(2400):
		await physics_frame
		if interrupted.recovery_completed>0:
			complete=true
			break
	assert(complete and interrupted.recovery_attempts>=2,"Interrupted get-up did not retry")
	report.interruption_and_retry=true
	# Insufficient headroom must fail and yield rather than instantly switching
	# to active, tunnelling through cover or applying unbounded lifting forces.
	var blocked=await reset_case(0,6)
	var ceiling: Node3D=world.block(Vector3(-1.2,0.72,-3.8),Vector3(2.2,0.22,2.6),Color.GRAY)
	var saw_recovering := false
	var saw_failure := false
	for i in range(1700):
		await physics_frame
		if blocked.state=="recovering": saw_recovering=true
		if saw_recovering and blocked.state=="downed": saw_failure=true;break
		assert(blocked.root_position().y<0.7,"Get-up went through the overhead obstacle")
	assert(saw_failure,"Blocked attempt did not time out safely")
	ceiling.queue_free()
	report.blocked_attempt_yields=true
	report.status="pass"
	FileAccess.open("res://../recovery-validation.json",FileAccess.WRITE).store_string(JSON.stringify(report,"\t")+"\n")
	print("TESTGROUND_RECOVERY_PASS ",JSON.stringify(report))
	quit()
