extends RefCounted
## Deterministic surface Voronoi assignment at existing triangle resolution.
## Generated once by the exporter. No runtime Boolean/fracture of the whole mesh.
const VERSION := 7
const PARTS := ["Hips","Spine","Spine2","Neck","Head","LeftArm","LeftForeArm","LeftHand","RightArm","RightForeArm","RightHand","LeftUpLeg","LeftLeg","LeftFoot","RightUpLeg","RightLeg","RightFoot"]
static var cached := {}

static func get_data(mesh: MeshInstance3D, rig: Skeleton3D, id: String) -> Dictionary:
	if cached.has(id): return cached[id]
	var path := "res://damage/"+id+".dbin"
	var file := FileAccess.open_compressed(path,FileAccess.READ) if FileAccess.file_exists(path) else null
	var data: Dictionary = file.get_var() if file else build(mesh,rig)
	assert(data.version==VERSION)
	cached[id]=data
	return data

static func build(mesh: MeshInstance3D, rig: Skeleton3D) -> Dictionary:
	assert(mesh.mesh.get_surface_count()==1,"Review multi-material assets before adding them")
	var arrays: Array = mesh.mesh.surface_get_arrays(0)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
	var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
	var influences := bones.size()/vertices.size()
	var bind_slots:=[]
	for bind in range(mesh.skin.get_bind_count()): bind_slots.append(PackedInt32Array())
	for slot in range(bones.size()): bind_slots[bones[slot]].append(slot)
	var bind_regions := []
	for bind in range(mesh.skin.get_bind_count()):
		var bone := mesh.skin.get_bind_bone(bind)
		if bone<0: bone=rig.find_bone(mesh.skin.get_bind_name(bind))
		while bone>=0 and not PARTS.has(str(rig.get_bone_name(bone))): bone=rig.get_bone_parent(bone)
		bind_regions.append(str(rig.get_bone_name(bone)) if bone>=0 else "Hips")
	var cells := []
	var lookup := {}
	var sites := {}
	var regions := {}
	var tri_cell := PackedInt32Array()
	for tri in range(indices.size()/3):
		var scores := {}
		var center := Vector3.ZERO
		for corner in range(3):
			var v := indices[tri*3+corner]
			center+=vertices[v]/3.0
			for influence in range(influences):
				var k := v*influences+influence
				var region: String=bind_regions[bones[k]]
				scores[region]=float(scores.get(region,0.0))+weights[k]
		var region := "Hips"
		var best := -1.0
		for name in scores:
			if scores[name]>best: best=scores[name];region=name
		var spacing := 0.025 if region=="Head" else (0.035 if "Hand" in region or "Foot" in region else 0.05)
		var grid := Vector3i((center/spacing).floor())
		var winner := grid
		var distance := INF
		for x in range(-1,2):
			for y in range(-1,2):
				for z in range(-1,2):
					var key := grid+Vector3i(x,y,z)
					var site_key := str(spacing)+str(key)
					if not sites.has(site_key):
						var rng := RandomNumberGenerator.new()
						rng.seed=absi(key.x*73856093 ^ key.y*19349663 ^ key.z*83492791)
						sites[site_key]=(Vector3(key)+Vector3(0.5+rng.randf_range(-0.28,0.28),0.5+rng.randf_range(-0.28,0.28),0.5+rng.randf_range(-0.28,0.28)))*spacing
					var d: float=center.distance_squared_to(sites[site_key])
					if d<distance: distance=d;winner=key
		var key := region+str(winner)
		if not lookup.has(key):
			lookup[key]=cells.size()
			cells.append({"id":cells.size(),"region":region,"indices":PackedInt32Array(),"vertices":{},"area":0.0,"neighbors":{},"edges":PackedInt32Array(),"border_ids":PackedInt32Array()})
			if not regions.has(region): regions[region]=PackedInt32Array()
			regions[region].append(lookup[key])
		var cell: Dictionary=cells[lookup[key]]
		for corner in range(3):
			var v := indices[tri*3+corner]
			cell.indices.append(v)
			cell.vertices[v]=true
		var a: Vector3=vertices[indices[tri*3]]
		var b: Vector3=vertices[indices[tri*3+1]]
		var c: Vector3=vertices[indices[tri*3+2]]
		cell.area+=(b-a).cross(c-a).length()*0.5
		tri_cell.append(cell.id)
	# Weld UV/normal seams for adjacency, retaining original textured vertices.
	var weld := {}
	var weld_ids := PackedInt32Array()
	for v in vertices:
		var key := Vector3i((v*100000.0).round())
		if not weld.has(key): weld[key]=weld.size()
		weld_ids.append(weld[key])
	var edges := {}
	for tri in range(indices.size()/3):
		for corner in range(3):
			var a := indices[tri*3+corner]
			var b := indices[tri*3+(corner+1)%3]
			var wa := weld_ids[a]
			var wb := weld_ids[b]
			var key := Vector2i(mini(wa,wb),maxi(wa,wb))
			if not edges.has(key): edges[key]=[a,b,tri_cell[tri],-1]
			else: edges[key][3]=tri_cell[tri]
	var boundaries := []
	for edge: Array in edges.values():
		var a: int=edge[2]
		var b: int=edge[3]
		if a==b: continue
		cells[a].border_ids.append(boundaries.size())
		if b>=0: cells[b].border_ids.append(boundaries.size())
		boundaries.append(PackedInt32Array(edge))
		cells[a].edges.append_array(PackedInt32Array([edge[0],edge[1]]))
		if b>=0:
			cells[a].neighbors[b]=true
			cells[b].neighbors[a]=true
			cells[b].edges.append_array(PackedInt32Array([edge[1],edge[0]]))
	var inner := PackedVector3Array()
	for i in range(vertices.size()): inner.append(vertices[i]-normals[i]*0.024)
	for cell: Dictionary in cells:
		var coeff := {}
		var center := Vector3.ZERO
		for v in cell.vertices:
			center+=vertices[v]/cell.vertices.size()
			for influence in range(influences):
				var k: int=v*influences+influence
				var bind := bones[k]
				var w: float=weights[k]/cell.vertices.size()
				if w<0.00001: continue
				if not coeff.has(bind): coeff[bind]=[Vector3.ZERO,0.0]
				coeff[bind][0]+=vertices[v]*w
				coeff[bind][1]+=w
		cell.center=center
		cell.radius=0.0
		for v in cell.vertices: cell.radius=maxf(cell.radius,center.distance_to(vertices[v]))
		cell.coeff_bones=PackedInt32Array()
		cell.coeff_positions=PackedVector3Array()
		cell.coeff_weights=PackedFloat32Array()
		for bind in coeff:
			cell.coeff_bones.append(bind)
			cell.coeff_positions.append(coeff[bind][0])
			cell.coeff_weights.append(coeff[bind][1])
		cell.inside=PackedInt32Array()
		for i in range(0,cell.indices.size(),3): cell.inside.append_array(PackedInt32Array([cell.indices[i+2]+vertices.size(),cell.indices[i+1]+vertices.size(),cell.indices[i]+vertices.size()]))
		cell.volume=cell.area*0.024
		cell.neighbors=PackedInt32Array(cell.neighbors.keys())
		cell.erase("vertices")
	var render_outer:=PackedInt32Array()
	var stride:=2 if vertices.size()<=65536 else 4
	for cell: Dictionary in cells:
		cell.index_offset=render_outer.size()
		render_outer.append_array(cell.indices)
		var zero:=PackedByteArray()
		zero.resize(cell.indices.size()*stride)
		cell.zero_bytes=zero
	return {"render_outer":render_outer,"index_stride":stride,"bind_slots":bind_slots,"version":VERSION,"arrays":arrays,"inner":inner,"influences":influences,"cells":cells,"regions":regions,"boundaries":boundaries,"triangle_cells":tri_cell,"vertex_count":vertices.size(),"triangles":indices.size()/3}
