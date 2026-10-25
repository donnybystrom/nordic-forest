extends SceneTree
const Model=preload("res://testground/damage_model.gd")
var world
var report: Dictionary={"cases":[],"performance":{},"renderer_geometry_checked":false}
func _initialize() -> void: call_deferred("run")
func frames(count: int) -> void:
	for i in range(count): await physics_frame
func snapshot(label: String) -> void:
	if DisplayServer.get_name()=="headless": return
	DirAccess.make_dir_recursive_absolute("res://../verification/damage")
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../verification/damage/"+label+".png")
func fresh(model: int) -> Node:
	world.models.select(model+1)
	world.spawn_group()
	await frames(120)
	return world.zombies[0]
func part(z: Node, name: String) -> Dictionary:
	return z.physics.by_bone[z.skeleton.find_bone(name)]
func hit(z: Node, name: String, profile: int) -> Dictionary:
	var body: RigidBody3D=part(z,name).body
	var origin:=body.global_position+Vector3(0,0,1.0)
	var exact: Dictionary=z.damage.refine_ray(origin,Vector3.FORWARD,2.0)
	if exact.is_empty(): return {}
	z.receive_hit(exact.collider,exact.position,Vector3.FORWARD,0.0,Model.projectile(profile),int(exact.cell))
	return exact
func run() -> void:
	create_timer(150).timeout.connect(func(): push_error("Damage smoke timed out");quit(1))
	world=load("res://testground/testground.tscn").instantiate()
	root.add_child(world)
	world.amount.value=1
	world.auto_recover=false
	world.motions.select(1)
	for model in range(2):
		var z=await fresh(model)
		# Compare CPU-skinned points to the actual SkeletonModifier output.
		z.damage.refresh_skin(true)
		var skin_error:=0.0
		for bind in range(z.damage.bind_bones.size()):
			var bone: int=z.damage.bind_bones[bind]
			if z.physics.by_bone.has(bone):
				var expected: Transform3D=part(z,str(z.skeleton.get_bone_name(bone))).body.global_transform*part(z,str(z.skeleton.get_bone_name(bone))).offset.affine_inverse()*z.damage.source.skin.get_bind_pose(bind)
				skin_error=maxf(skin_error,expected.origin.distance_to(z.damage.matrices[bind].origin))
		assert(skin_error<0.0001)
		world.menu.hide()
		world.player.weapon.hide()
		world.player.set_physics_process(false)
		var head_position: Vector3=part(z,"Head").body.global_position
		world.player.position=head_position+Vector3(0.18,-1.73,1.1)
		world.player.camera.look_at(head_position)
		await snapshot("model-%d-intact" % model)
		var head_origin: Vector3=part(z,"Head").body.global_position+Vector3.BACK
		var visible: Dictionary=z.damage.refine_ray(head_origin,Vector3.FORWARD,2.0)
		assert(not visible.is_empty())
		var short_ray: Dictionary=world.player.cast_shot(head_origin,Vector3.FORWARD,head_origin.distance_to(visible.position)+0.02)
		assert(not short_ray.is_empty(),"Short muzzle segment missed skin in front of its capsule")
		var exact:=hit(z,"Head",1)
		assert(not exact.is_empty(),"Head ray missed")
		z.damage.flush(true)
		print("DAMAGE_HEAD model=",model," report=",z.damage.report())
		await snapshot("model-%d-head-hole" % model)
		assert(z.state=="dead" and z.damage.removed.size()>0,"Heavy head hit must remove geometry and stop recovery")
		assert(z.damage.removed_volume<=z.damage.budget_volume+0.0000001)
		assert(str(exact.collider.get_meta("bone"))=="Head")
		# Every removed triangle is absent from the render index buffer.
		var indices: PackedInt32Array=z.damage.source.mesh.surface_get_arrays(0)[Mesh.ARRAY_INDEX]
		var cell: Dictionary=z.damage.data.cells[exact.cell]
		assert(z.damage.removed.has(exact.cell),"Entry cell was not removed")
		if DisplayServer.get_name()!="headless":
			report.renderer_geometry_checked=true
			for i in range(cell.index_offset,cell.index_offset+cell.indices.size()): assert(indices[i]==0,"Removed triangle still has area in the render buffer")
		var after: Dictionary=z.damage.refine_ray(exact.position+Vector3(0,0,0.005),Vector3.FORWARD,0.006)
		assert(after.is_empty(),"The entrance hole still intercepts bullets")
		await frames(90)
		assert(z.state=="dead" and z.physics.last_support_force==Vector3.ZERO)
		report.cases.append({"model":model,"test":"head_hole_and_collapse","skin_error":skin_error,"damage":z.damage.report()})
		z=await fresh(model)
		for pellet in range(8): hit(z,"Spine",2)
		z.damage.flush(true)
		print("DAMAGE_CHEST model=",model," report=",z.damage.report())
		await snapshot("model-%d-chest-hole" % model)
		assert(not z.damage.fatal and z.state!="dead","A chest hole must not be a generic HP death")
		assert(z.damage.rebuilds==1,"Pellets must share one mesh rebuild")
		assert(z.damage.removed.size()>0 and z.damage.removed_volume<=z.damage.budget_volume+0.0000001)
		report.cases.append({"model":model,"test":"chest_survives_and_pellets_batch","damage":z.damage.report()})
		for bone: String in ["LeftArm","RightForeArm","LeftHand","LeftUpLeg","RightLeg","LeftFoot","Head"]:
			z=await fresh(model)
			z.damage.refresh_skin(true)
			var before: Vector3=part(z,bone).body.global_position
			z.damage.sever(bone)
			z.damage._rebuild()
			assert(part(z,bone).detached and z.physics.part_strength(part(z,bone))==0.0)
			assert(part(z,bone).body.global_position.distance_to(before)<0.00001,"Sever teleported physical body")
			await frames(30)
			assert(not is_instance_valid(part(z,bone).joint),"Incoming joint remains after sever")
			if bone=="LeftArm": await snapshot("model-%d-detached-arm" % model)
			for entry: Dictionary in z.physics.bodies:
				assert(entry.body.global_position.is_finite())
			report.cases.append({"model":model,"test":"detach_"+bone,"mass":z.physics.total_mass})
		z=await fresh(model)
		# Damage a small limb through the full energy/cell/function path. The
		# direct sever cases above separately exercise every articulated branch.
		var disabled_while_attached:=false
		for shot in range(24):
			z.damage.refresh_skin(true)
			var target: Dictionary={}
			for id: int in z.damage.data.regions.LeftForeArm:
				if not z.damage.removed.has(id): target=z.damage.data.cells[id];break
			if target.is_empty(): break
			var body: RigidBody3D=part(z,"LeftForeArm").body
			z.receive_hit(body,z.damage.centers[target.id],Vector3.FORWARD,0.0,Model.projectile(1),target.id)
			z.damage.flush(true)
			if not part(z,"LeftForeArm").detached and z.physics.part_strength(part(z,"LeftForeArm"))<0.15: disabled_while_attached=true
			if part(z,"LeftForeArm").detached: break
		assert(part(z,"LeftForeArm").detached,"Repeated local damage did not release the limb")
		report.cases.append({"model":model,"test":"energy_driven_limb_sever","disabled_before_sever":disabled_while_attached,"damage":z.damage.report()})
		z=await fresh(model)
		z.physics.injure("LeftArm",0.0)
		assert(z.physics.part_strength(part(z,"LeftHand"))==0.0)
		assert(is_instance_valid(part(z,"LeftArm").joint) and not part(z,"LeftArm").detached,"Muscle injury must retain the joint")
		z=await fresh(model)
		world.auto_recover=true
		world.player.position=Vector3(z.root_position().x,0.0,z.root_position().z+3.0)
		world.player.camera.position=Vector3(0,1.65,0)
		world.player.camera.look_at(part(z,"Spine").body.global_position)
		world.select_profile(2)
		world.player.magazine=12;world.player.cooldown=0.0;world.player.reload_time=0.0
		world.player.fire()
		var fallen:=false
		for i in range(2000):
			await physics_frame
			fallen=fallen or z.state in ["downed","recovering"]
			if z.recovery_completed>0: break
		assert(z.damage.removed.size()>0 and not z.damage.fatal,"Shotgun chest wound lost survival rule")
		assert(fallen and z.recovery_completed>0,"Wounded torso could not get up again")
		report.cases.append({"model":model,"test":"shotgun_chest_recovers","getups":z.recovery_completed,"damage":z.damage.report(),"shot":world.player.last_shot.duplicate(true)})
		world.auto_recover=false
	# The high-end tissue control must change actual damage, not just its label.
	assert(world.tissue_slider.max_value==100.0 and world.tissue_slider.value==1.0 and world.tissue_slider.exp_edit)
	world.tissue_slider.value=100.0
	assert(world.tissue_multiplier==100.0)
	for model in range(2):
		for region: String in ["Head","LeftArm"]:
			var z=await fresh(model)
			var body: RigidBody3D=part(z,region).body
			# Side shoulder rays avoid the head occluding the upper arm.
			var offset:=Vector3.BACK if region=="Head" else Vector3.RIGHT
			var direction: Vector3=-offset
			var contact: Dictionary=z.damage.refine_ray(body.global_position+offset,direction,2.0)
			assert(not contact.is_empty() and contact.collider.get_meta("bone")==region)
			z.receive_hit(contact.collider,contact.position,direction,70.0,Model.projectile(1,world.tissue_multiplier),contact.cell)
			z.damage.flush(true)
			assert(z.damage.detached.has(region),"100x must remove the targeted head/shoulder in one shot")
			assert(z.damage.removed_volume<=z.damage.budget_volume+0.0000001)
			report.cases.append({"model":model,"test":"single_shot_100x_"+region,"damage":z.damage.report()})
	world.tissue_slider.value=1.0
	# Sustained ten-projectile-per-second work across the full crowd. This is
	# a CPU workload measurement, not an FPS claim from a headless renderer.
	world.models.select(0);world.amount.value=12;world.spawn_group()
	await frames(120)
	var times:=[]
	var removed:=0
	var hit_count:=0
	for shot in range(72):
		var z: Node=world.zombies[shot%world.zombies.size()]
		var began:=Time.get_ticks_usec()
		var contact:=hit(z,"Spine" if shot%2==0 else "LeftArm",3)
		if not contact.is_empty(): hit_count+=1
		z.damage.flush(true)
		times.append(float(Time.get_ticks_usec()-began)/1000.0)
		assert(world.debris.pieces.size()<=world.Debris.LIMIT)
		await frames(12)
	for z in world.zombies: removed+=z.damage.removed.size()
	times.sort()
	report.performance={"zombies":12,"shots":72,"body_hits":hit_count,"rate_hz":10,"cpu_p50_ms":times[times.size()/2],"cpu_p95_ms":times[int(times.size()*0.95)],"cpu_max_ms":times.back(),"removed_cells":removed,"debris_peak":world.debris.peak,"debris_limit":world.Debris.LIMIT}
	world.amount.value=1;world.spawn_group();await frames(2)
	assert(world.debris.pieces.is_empty(),"Respawn leaked debris")
	assert(get_nodes_in_group("testground_bodies").size()==17,"Respawn leaked detached limbs")
	report.status="pass"
	var file:=FileAccess.open("res://../damage-validation.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "));file.close()
	print("TESTGROUND_DAMAGE_PASS ",JSON.stringify(report.performance))
	quit()
