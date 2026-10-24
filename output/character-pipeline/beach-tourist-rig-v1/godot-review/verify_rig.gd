extends SceneTree

var skeleton: Skeleton3D
var player: AnimationPlayer
var meshes := 0

func visit(node: Node) -> void:
    if node is MeshInstance3D:
        meshes += 1
    if node is Skeleton3D:
        skeleton = node
    if node is AnimationPlayer:
        player = node
    for child in node.get_children():
        visit(child)

func _initialize() -> void:
    call_deferred("verify")

func verify() -> void:
    var packed = load("res://character.glb") as PackedScene
    if packed == null:
        push_error("Rigged model import failed")
        quit(1)
        return
    var instance = packed.instantiate()
    root.add_child(instance)
    visit(instance)
    if skeleton == null or player == null:
        push_error("Missing skeleton or diagnostic animation")
        quit(1)
        return
    var clip: StringName = &""
    for name in player.get_animation_list():
        if "QA_RigRange" in name:
            clip = name
    if clip == &"":
        push_error("Diagnostic clip missing")
        quit(1)
        return
    var elbow = skeleton.find_bone("LeftForeArm")
    var knee = skeleton.find_bone("LeftLeg")
    if elbow < 0 or knee < 0:
        quit(1)
        return
    player.play(clip)
    player.seek(1.0/30.0, true)
    player.advance(0)
    var elbow_rest = skeleton.get_bone_pose_rotation(elbow)
    var knee_rest = skeleton.get_bone_pose_rotation(knee)
    player.seek(31.0/30.0, true)
    player.advance(0)
    var elbow_angle = rad_to_deg(elbow_rest.angle_to(skeleton.get_bone_pose_rotation(elbow)))
    player.seek(61.0/30.0, true)
    player.advance(0)
    var knee_angle = rad_to_deg(knee_rest.angle_to(skeleton.get_bone_pose_rotation(knee)))
    var passed = skeleton.get_bone_count() == 22 and meshes > 0 and abs(elbow_angle - 90.0) < 0.5 and abs(knee_angle - 85.0) < 0.5
    var report = {"status": "passed" if passed else "failed", "godot_version": Engine.get_version_info().string, "bones": skeleton.get_bone_count(), "mesh_instances": meshes, "animations": player.get_animation_list(), "diagnostic_clip": clip, "clip_duration_seconds": player.get_animation(clip).length, "time_mapping": "GLB source times retained; optimizer disabled for equivalence checking", "elbow_rotation_degrees": elbow_angle, "knee_rotation_degrees": knee_angle, "scope": "Rigged GLB import and diagnostic skeleton animation; no gameplay, foot contact or active-ragdoll acceptance"}
    FileAccess.open("res://rig-verification.json", FileAccess.WRITE).store_string(JSON.stringify(report, "  "))
    print("RIG_IMPORT_AND_ANIMATION ", JSON.stringify(report))
    quit(0 if passed else 1)
