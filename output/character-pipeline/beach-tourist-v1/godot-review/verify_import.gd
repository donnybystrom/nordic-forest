extends SceneTree

var report = {"mesh_instances": 0, "skeletons": 0, "animation_names": [], "scope": "static GLB import; no rig or gameplay acceptance"}

func visit(node: Node) -> void:
    if node is MeshInstance3D:
        report.mesh_instances += 1
    if node is Skeleton3D:
        report.skeletons += 1
    if node is AnimationPlayer:
        for clip in node.get_animation_list():
            report.animation_names.append(clip)
    for child in node.get_children():
        visit(child)

func _initialize() -> void:
    var packed = load("res://character.glb") as PackedScene
    if packed == null:
        push_error("Generated character import failed")
        quit(1)
        return
    var instance = packed.instantiate()
    root.add_child(instance)
    visit(instance)
    report["godot_version"] = Engine.get_version_info().string
    report["status"] = "passed" if report.mesh_instances > 0 else "failed"
    var output = FileAccess.open("res://import-verification.json", FileAccess.WRITE)
    output.store_string(JSON.stringify(report, "  "))
    print("CHARACTER_IMPORT_VERIFIED ", JSON.stringify(report))
    quit(0 if report.mesh_instances > 0 else 1)
