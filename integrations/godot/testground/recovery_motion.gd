extends RefCounted
## Authored get-up keyframes retargeted by limb lengths, sampled with smooth
## interpolation. These are pose targets for joint motors, never body teleports.
const PRONE := [[0.0,"handstöd"],[0.8,"trycker upp bålen"],[1.8,"drar in knäna"],[2.7,"sätter fram foten"],[3.7,"reser sig"],[4.6,"står"]]
const SUPINE := [[0.0,"på rygg"],[0.9,"rullar åt sidan"],[1.8,"sätter sig"],[2.8,"vänder upp på knä"],[3.8,"reser sig"],[4.9,"står"]]
const PRONE_CLIP = preload("res://testground/get_up_prone.tres")
const SUPINE_CLIP = preload("res://testground/get_up_supine.tres")
var controller: Node
var rests := {}
var height := 1.0
var animations := {}
var kind := ""
var stage := ""
var time := 0.0
var running := false
var origin := Vector3.ZERO
var heading := 0.0
var captured := {}
var blend_out := 0.8
var entry_blend := 0.65
var last_weight := 0.0

func configure(ragdoll: Node) -> void:
	controller = ragdoll
	for part: Dictionary in controller.bodies:
		rests[part.name] = controller.target_rig.get_bone_global_rest(part.index)
	height = rests.Hips.origin.y
	animations = {"prone":PRONE_CLIP,"supine":SUPINE_CLIP}

func choose() -> String:
	var chest: RigidBody3D = controller.by_bone[controller.target_rig.find_bone("Spine2")].body
	var rotation: Basis = chest.global_basis * rests.Spine2.basis.inverse()
	return "supine" if (rotation*Vector3(0,0,1)).dot(Vector3.UP)>0.0 else "prone"

func begin() -> void:
	# Hold a consistent locomotion entry pose while planting the feet. Resume
	# the clip only after blending, rather than chasing a moving stride target.
	if not controller.view.clip.is_empty():
		controller.view.player.pause()
		controller.view.player.seek(0.0,true)
		controller.view.player.advance(0.0)
	kind = choose()
	var chest: RigidBody3D = controller.by_bone[controller.target_rig.find_bone("Spine2")].body
	var rotation: Basis = chest.global_basis * rests.Spine2.basis.inverse()
	var along: Vector3 = rotation*Vector3.UP
	along.y=0.0
	if kind=="supine": along = -along
	if along.length()<0.1:
		along=rotation*Vector3(0,0,1)
		along.y=0.0
	heading = atan2(along.x,along.z) if along.length()>0.1 else controller.view.heading
	origin = controller.root_body().global_position
	origin.y = controller.view.arena.floor_height(origin)
	captured.clear()
	for part: Dictionary in controller.bodies: captured[part.index] = part.body.global_transform
	time=0.0
	running=true

func duration() -> float:
	return animations[kind].length+entry_blend+blend_out

func sample(name: String, at: float, base: Vector3, yaw: float) -> Dictionary:
	var keys: Array = PRONE if name=="prone" else SUPINE
	var before: Array = keys[0]
	var after: Array = keys.back()
	for i in range(keys.size()-1):
		if at<=float(keys[i+1][0]):
			before=keys[i];after=keys[i+1];break
	stage=str(before[1])
	var weight := smoothstep(float(before[0]),float(after[0]),at)
	var p := []
	var eased_time := lerpf(float(before[0]),float(after[0]),weight)
	for channel in range(2,10): p.append(float(animations[name].value_track_interpolate(channel-2,eased_time)))
	var global_basis := Basis(Vector3.UP,yaw)
	var pelvis := Basis(Vector3(0,0,1),deg_to_rad(float(p[3])))*Basis(Vector3.RIGHT,deg_to_rad(float(p[1])))
	var chest := Basis(Vector3(0,0,1),deg_to_rad(float(p[3])))*Basis(Vector3.RIGHT,deg_to_rad(float(p[2])))
	var result := {}
	for part: Dictionary in controller.bodies:
		var rest: Transform3D = rests[part.name]
		var basis: Basis = (pelvis if part.name=="Hips" else chest)*rest.basis
		if part.name=="Hips":
			result[part.index] = Transform3D(global_basis*basis,base+global_basis*(Vector3(0,float(p[0])*height,0)+basis*part.offset.origin))
		elif part.name in ["Spine","Spine2","Neck","Head"]:
			result[part.index] = _connected(part,global_basis*basis,result)
	# Solve legs and arms as two-link chains towards authored foot/hand goals.
	for side in ["Left","Right"]:
		var sign_x := 1.0 if side=="Left" else -1.0
		var foot_z: float = p[4] if side=="Left" else p[5]
		var foot_rest: Transform3D = rests[side+"Foot"]
		var ankle := base+global_basis*Vector3(sign_x*0.16*height,foot_rest.origin.y,foot_z*height)
		_chain(side+"UpLeg",side+"Leg",side+"Foot",ankle,global_basis*pelvis*Vector3(0,0,1),global_basis,result)
		var hand := base+global_basis*Vector3(sign_x*0.32*height,float(p[6])*height,float(p[7])*height)
		if name=="supine":
			var roll_weight := smoothstep(0.15,0.6,at)*(1.0-smoothstep(1.2,1.85,at))
			hand += global_basis*Vector3(-0.12*height,0.12*height if side=="Left" else 0.0,0)*roll_weight
		_chain(side+"Arm",side+"ForeArm",side+"Hand",hand,global_basis*Vector3(sign_x,-0.2,-0.35),global_basis,result)
	# Prevent any authored collision capsule from being below the floor.
	var lowest := 100.0
	for part: Dictionary in controller.bodies:
		var pose: Transform3D = result[part.index]
		var half_segment := maxf(float(part.height)*0.5-float(part.radius),0.0)
		lowest = minf(lowest,pose.origin.y-absf((pose.basis*part.axis).y)*half_segment-float(part.radius))
	var lift := maxf(0.0,base.y+0.012-lowest)
	for index in result:
		var pose: Transform3D = result[index]
		pose.origin.y += lift
		result[index] = pose
	return result

func _connected(part: Dictionary, basis: Basis, poses: Dictionary) -> Transform3D:
	var parent: Transform3D = poses[part.parent_index]
	return Transform3D(basis,parent*part.anchor_a-basis*part.anchor_b)

func _chain(upper: String, lower: String, end: String, goal: Vector3, pole: Vector3, frame: Basis, poses: Dictionary) -> void:
	var a: Dictionary = controller.by_bone[controller.target_rig.find_bone(upper)]
	var b: Dictionary = controller.by_bone[controller.target_rig.find_bone(lower)]
	var c: Dictionary = controller.by_bone[controller.target_rig.find_bone(end)]
	var joint: Vector3 = poses[a.parent_index]*a.anchor_a
	var length_a: float = rests[upper].origin.distance_to(rests[lower].origin)
	var length_b: float = rests[lower].origin.distance_to(rests[end].origin)
	var offset := goal-joint
	var distance := clampf(offset.length(),absf(length_a-length_b)+0.005,length_a+length_b-0.005)
	var direction := offset.normalized()
	var along := (length_a*length_a-length_b*length_b+distance*distance)/(2.0*distance)
	var bend := (pole-direction*pole.dot(direction)).normalized()
	if bend.length()<0.1: bend=frame*Vector3.RIGHT
	var elbow := joint+direction*along+bend*sqrt(maxf(0.0,length_a*length_a-along*along))
	var actual_end := joint+direction*distance
	for pair: Array in [[a,elbow-joint],[b,actual_end-elbow]]:
		var part: Dictionary = pair[0]
		var rest: Transform3D = rests[part.name]
		var rest_direction: Vector3 = rest.basis*part.axis
		var basis := Basis(Quaternion(rest_direction.normalized(),(frame.inverse()*pair[1]).normalized()))*rest.basis
		poses[part.index] = _connected(part,frame*basis,poses)
	poses[c.index] = _connected(c,frame*rests[end].basis,poses)

func advance(delta: float) -> bool:
	time += delta
	var animation: Animation = animations[kind]
	var at := clampf(time-entry_blend,0.0,animation.length)
	var wanted := sample(kind,at,origin,heading)
	var entering := smoothstep(0.0,entry_blend,time)
	var leaving := smoothstep(entry_blend+animation.length,duration(),time)
	last_weight = entering*(1.0-leaving)
	controller.recovery_pose.clear()
	for part: Dictionary in controller.bodies:
		var pose: Transform3D = captured[part.index].interpolate_with(wanted[part.index],entering)
		if leaving>0.0: pose=pose.interpolate_with(controller._animation_body(part),leaving)
		controller.recovery_pose[part.index]=pose
	stage = "blandar till rörelse" if leaving>0.0 else ("anpassar fallposen" if entering<1.0 else stage)
	return time>=duration()

func stop() -> void:
	if running and not controller.view.clip.is_empty(): controller.view.player.play(controller.view.clip)
	running=false
	controller.recovery_pose.clear()
