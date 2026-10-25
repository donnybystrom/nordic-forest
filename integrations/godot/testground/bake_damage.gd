extends SceneTree
const Data=preload("res://testground/fracture_data.gd")
func _initialize() -> void: call_deferred("run")
func run() -> void:
	var catalog: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://characters.json"))
	DirAccess.make_dir_recursive_absolute("res://damage")
	for entry: Dictionary in catalog.characters:
		var model=(load(entry.scene) as PackedScene).instantiate()
		root.add_child(model)
		var mesh: MeshInstance3D=model.find_children("*","MeshInstance3D",true,false)[0]
		var rig: Skeleton3D=model.find_children("*","Skeleton3D",true,false)[0]
		var data:=Data.build(mesh,rig)
		data.source_sha256=entry.sha256
		var file:=FileAccess.open_compressed("res://damage/"+entry.id+".dbin",FileAccess.WRITE)
		file.store_var(data)
		file.close()
		print("FRACTURE_BAKE ",entry.id," cells=",data.cells.size()," triangles=",data.triangles," vertices=",data.vertex_count)
		model.queue_free()
	quit()
