extends SceneTree
## Real-time rendering/physics workload. Do not use --fixed-fps or --headless
## when comparing frame pacing; software renderers are a separate environment.
const Model=preload("res://testground/damage_model.gd")
var world
func _initialize() -> void: call_deferred("run")
func sample(seconds: float, firing: bool) -> Dictionary:
	var samples:=[]
	var shot_times:=[]
	var began:=Time.get_ticks_usec()
	var previous:=began
	var next_shot:=0.0
	var shots:=0
	var hits:=0
	while float(Time.get_ticks_usec()-began)/1000000.0<seconds:
		await process_frame
		var now:=Time.get_ticks_usec()
		samples.append(float(now-previous)/1000.0)
		previous=now
		var elapsed:=float(now-began)/1000000.0
		if not firing or elapsed<next_shot: continue
		next_shot+=0.1
		var z: Node=world.zombies[shots%12]
		shots+=1
		var body: RigidBody3D=z.physics.by_bone[z.skeleton.find_bone("Spine")].body
		var origin:=body.global_position+Vector3.BACK
		var start:=Time.get_ticks_usec()
		var exact: Dictionary=z.damage.refine_ray(origin,Vector3.FORWARD,2.0)
		if not exact.is_empty():
			z.receive_hit(exact.collider,exact.position,Vector3.FORWARD,18.0,Model.projectile(3),exact.cell)
			hits+=1
		shot_times.append(float(Time.get_ticks_usec()-start)/1000.0)
	var total:=0.0
	for value: float in samples: total+=value
	samples.sort()
	return {"wall_seconds":float(Time.get_ticks_usec()-began)/1000000.0,"frames":samples.size(),"fps_mean":samples.size()*1000.0/total,"frame_p95_ms":samples[int(samples.size()*0.95)],"frame_max_ms":samples.back(),"shots":shots,"body_hits":hits,"debris":world.debris.pieces.size(),"debris_peak":world.debris.peak}
func run() -> void:
	world=load("res://testground/testground.tscn").instantiate()
	root.add_child(world)
	world.amount.value=12
	world.motions.select(1)
	world.spawn_group()
	world.menu.hide()
	world.player.set_physics_process(false)
	world.player.position=Vector3(0,0,3)
	world.player.camera.look_at(Vector3(0,1,-5))
	await sample(3.0,false)
	var baseline:=await sample(3.0,false)
	var firing:=await sample(6.0,true)
	var report: Dictionary={"godot":Engine.get_version_info().string,"display":DisplayServer.get_name(),"processor":OS.get_processor_name(),"zombies":12,"bodies":204,"baseline":baseline,"automatic_fire":firing,"limits":"Local real-time sample with other applications open; scripted close-range shots, not an input acceptance test or cross-device FPS guarantee."}
	var file:=FileAccess.open("res://../damage-benchmark.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"  "));file.close()
	print("DAMAGE_RENDER_BENCHMARK ",JSON.stringify(report))
	quit()
