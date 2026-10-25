extends Node3D
## Hard global budget, finite lifetime. Debris collides with the world only;
## character knockback remains the original point impulse, not this visual kick.
const LIMIT := 32
const LIFETIME := 7.0
var pieces: Array[Dictionary] = []
var peak := 0
var emitted := 0
func emit_piece(mesh: ArrayMesh, at: Vector3, mass: float, velocity: Vector3, spin: Vector3, radius: float) -> void:
	while pieces.size()>=LIMIT: _remove(0)
	var body:=RigidBody3D.new()
	body.mass=maxf(mass,0.002)
	body.collision_layer=16
	body.collision_mask=1
	body.continuous_cd=true
	body.linear_damp=0.12
	body.angular_damp=0.4
	var shape:=CollisionShape3D.new()
	var sphere:=SphereShape3D.new()
	sphere.radius=clampf(radius,0.008,0.065)
	shape.shape=sphere
	body.add_child(shape)
	var visual:=MeshInstance3D.new()
	visual.mesh=mesh
	visual.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	body.add_child(visual)
	add_child(body)
	body.global_position=at
	body.linear_velocity=velocity
	body.angular_velocity=spin
	pieces.append({"body":body,"time":LIFETIME})
	emitted+=1
	peak=maxi(peak,pieces.size())
func _physics_process(delta: float) -> void:
	for i in range(pieces.size()-1,-1,-1):
		pieces[i].time-=delta
		if pieces[i].time<=0.0: _remove(i)
func _remove(index: int) -> void:
	var body: RigidBody3D=pieces[index].body
	body.collision_layer=0
	body.collision_mask=0
	body.queue_free()
	pieces.remove_at(index)
func clear() -> void:
	while not pieces.is_empty(): _remove(pieces.size()-1)
