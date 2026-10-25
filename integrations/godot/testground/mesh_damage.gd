extends RefCounted
## Prebaked surface cells, CPU skinning only near hits, one mesh rebuild per batch.
## This is a textured shell prototype, not runtime solid Voronoi/Boolean cutting.
const FRAGMENTS_PER_BATCH := 4
const Data=preload("res://testground/fracture_data.gd")
const Model=preload("res://testground/damage_model.gd")
var agent: Node3D
var source: MeshInstance3D
var data: Dictionary
var material: Material
var flesh: StandardMaterial3D
var removed := {}
var detached := {}
var region_loss := {}
var original_region_volume := {}
var pending: Array[Dictionary] = []
var bind_bones: Array[int] = []
var matrices: Array[Transform3D] = []
var vertex_cache := {}
var inner_cache := {}
var centers: PackedVector3Array
var matrix_frame := -1
var coeff_override := {}
var live_arrays: Array
var last_wound := {}
var removed_volume := 0.0
var budget_volume := 0.0
var cpu_ms := 0.0
var sever_ms := 0.0
var rebuilds := 0
var render_removed := {}
var render_created := false
var weights_dirty := false
var severed: Array[String] = []
var fatal := false
var brain_energy_j := 0.0
var exact_tests := 0

func configure(owner_agent: Node3D) -> void:
	agent=owner_agent
	source=agent.character.find_children("*","MeshInstance3D",true,false)[0]
	data=Data.get_data(source,agent.skeleton,str(agent.characters[agent.model_index].id))
	material=source.get_active_material(0)
	flesh=StandardMaterial3D.new()
	flesh.albedo_color=Color("642d30")
	flesh.roughness=0.88
	flesh.cull_mode=BaseMaterial3D.CULL_DISABLED
	for bind in range(source.skin.get_bind_count()):
		var bone:=source.skin.get_bind_bone(bind)
		if bone<0: bone=agent.skeleton.find_bone(source.skin.get_bind_name(bind))
		bind_bones.append(bone)
	for cell: Dictionary in data.cells:
		original_region_volume[cell.region]=float(original_region_volume.get(cell.region,0.0))+cell.volume
	live_arrays=data.arrays.duplicate(true)

func refresh_skin(force := false) -> void:
	var frame:=Engine.get_physics_frames()
	if matrix_frame==frame and not force: return
	matrix_frame=frame
	vertex_cache.clear();inner_cache.clear()
	var poses: Array[Transform3D]=[]
	var rig: Skeleton3D=agent.physics.target_rig
	for bone in range(rig.get_bone_count()):
		if agent.physics.by_bone.has(bone):
			var part: Dictionary=agent.physics.by_bone[bone]
			poses.append(part.body.global_transform*part.offset.affine_inverse())
		else:
			var parent:=rig.get_bone_parent(bone)
			poses.append(poses[parent]*rig.get_bone_pose(bone) if parent>=0 else rig.global_transform*rig.get_bone_pose(bone))
	matrices.clear()
	for bind in range(bind_bones.size()): matrices.append(poses[bind_bones[bind]]*source.skin.get_bind_pose(bind))
	centers.resize(data.cells.size())
	for cell: Dictionary in data.cells:
		if removed.has(cell.id): continue
		var center:=Vector3.ZERO
		var coeff: Dictionary=coeff_override.get(cell.id,cell)
		for i in range(coeff.coeff_bones.size()):
			var transform: Transform3D=matrices[coeff.coeff_bones[i]]
			center+=transform.basis*coeff.coeff_positions[i]+transform.origin*coeff.coeff_weights[i]
		centers[cell.id]=center

func vertex(index: int, inside := false) -> Vector3:
	var cache: Dictionary=inner_cache if inside else vertex_cache
	if cache.has(index): return cache[index]
	var position: Vector3=data.inner[index] if inside else data.arrays[Mesh.ARRAY_VERTEX][index]
	var result:=Vector3.ZERO
	var influences: int=data.influences
	for i in range(influences):
		var k:=index*influences+i
		var weight: float=data.arrays[Mesh.ARRAY_WEIGHTS][k]
		if weight>0.00001: result+=(matrices[live_arrays[Mesh.ARRAY_BONES][k]]*position)*weight
	cache[index]=result
	return result

func refine_ray(origin: Vector3, direction: Vector3, limit: float) -> Dictionary:
	refresh_skin()
	var best: Dictionary={}
	var distance:=limit
	for cell: Dictionary in data.cells:
		if removed.has(cell.id): continue
		var offset: Vector3=centers[cell.id]-origin
		var along:=offset.dot(direction)
		var radius: float=cell.radius*2.0+0.025
		if along < -radius or along-radius>distance or (offset-direction*along).length_squared()>radius*radius: continue
		var indices: PackedInt32Array=cell.indices
		for i in range(0,indices.size(),3):
			exact_tests+=1
			var a:=vertex(indices[i]);var b:=vertex(indices[i+1]);var c:=vertex(indices[i+2])
			var hit: Variant=Geometry3D.ray_intersects_triangle(origin,direction,a,b,c)
			if hit==null: continue
			var t: float=(hit-origin).dot(direction)
			if t<0.00001 or t>=distance: continue
			distance=t
			var normal: Vector3=(b-a).cross(c-a).normalized()
			if normal.dot(direction)>0: normal=-normal
			best={"position":hit,"normal":normal,"collider":agent.physics.by_bone[agent.skeleton.find_bone(cell.region)].body,"cell":cell.id}
	return best

func queue_hit(body: RigidBody3D, point: Vector3, direction: Vector3, payload: Dictionary, cell := -1) -> void:
	if payload.is_empty() or not agent.arena.damage_enabled: return
	pending.append({"body":body,"local_point":body.to_local(point),"direction":direction.normalized(),"payload":payload,"cell":cell,"frame":Engine.get_physics_frames()+2})

func flush(force := false) -> void:
	if pending.is_empty(): return
	if not force and pending[0].frame>Engine.get_physics_frames(): return
	var began:=Time.get_ticks_usec()
	refresh_skin(true)
	var selected: Array[int]=[]
	var directions:=Vector3.ZERO
	while not pending.is_empty() and (force or pending[0].frame<=Engine.get_physics_frames()):
		var hit: Dictionary=pending.pop_front()
		var ids:=_select(hit)
		for id in ids:
			removed[id]=true
			selected.append(id)
		directions+=hit.direction
	if not selected.is_empty():
		_emit_cells(selected,directions.normalized())
		_update_function(selected)
		_rebuild()
	cpu_ms=float(Time.get_ticks_usec()-began)/1000.0
	if not last_wound.is_empty(): agent.arena.latest_wound=last_wound.duplicate(true)

func _select(hit: Dictionary) -> Array[int]:
	var point: Vector3=hit.body.to_global(hit.local_point)
	var direction: Vector3=hit.direction
	var payload: Dictionary=hit.payload
	var length:=0.35
	var region:=str(hit.body.get_meta("bone"))
	if region=="Head": length=0.20
	elif "Arm" in region or "Hand" in region or "Leg" in region or "Foot" in region: length=0.15
	var exit: Dictionary=refine_ray(point+direction*0.002,direction,0.65)
	if not exit.is_empty(): length=clampf(maxf(length*0.75,point.distance_to(exit.position)+0.015),0.05,0.65)
	var volume: float=payload.volume_m3
	budget_volume+=volume
	var radius:=Model.channel_radius(volume,length)
	var candidates:=[]
	var axis_start:=point-direction*0.025
	var axis_end:=point+direction*length
	for cell: Dictionary in data.cells:
		if removed.has(cell.id): continue
		var center: Vector3=centers[cell.id]
		var nearest:=Geometry3D.get_closest_point_to_segment(center,axis_start,axis_end)
		var dist:=center.distance_to(nearest)
		if dist>radius+minf(cell.radius,0.025): continue
		candidates.append([-1.0 if cell.id==hit.cell else dist,cell.id])
	candidates.sort_custom(func(a: Array,b: Array): return a[0]<b[0])
	var ids: Array[int]=[]
	var used:=0.0
	for candidate: Array in candidates:
		var cell: Dictionary=data.cells[candidate[1]]
		# Whole surface cells quantize the budget: never exceed the energy volume.
		if used+cell.volume>volume: continue
		ids.append(cell.id)
		used+=cell.volume
	if not ids.is_empty():
		removed_volume+=used
		last_wound={"region":region,"energy_j":payload.energy_j,"deposited_j":payload.deposited_j,"budget_cm3":volume*1000000.0,"removed_cm3":used*1000000.0,"cells":ids.size(),"radius_m":radius}
		# A zombie's brain is the functional kill rule. Torso loss alone isn't.
		if region=="Head":
			var head: RigidBody3D=hit.body
			var radii:=Vector3(0.06,0.075,0.07)
			var a:=head.to_local(point)/radii
			var b:=head.to_local(point+direction*maxf(length,0.30))/radii
			if Geometry3D.get_closest_point_to_segment(Vector3.ZERO,a,b).length_squared()<=1.0:
				brain_energy_j+=float(payload.deposited_j)
				if brain_energy_j>=400.0: fatal=true;agent.kill()
	return ids

func _update_function(selected: Array[int]) -> void:
	var touched: Dictionary={}
	for id in selected:
		var cell: Dictionary=data.cells[id]
		region_loss[cell.region]=float(region_loss.get(cell.region,0.0))+cell.volume
		touched[cell.region]=true
	for region: String in touched:
		var loss: float=region_loss[region]/original_region_volume[region]
		agent.physics.injure(region,clampf(1.0-loss*4.0,0.0,1.0))
		if region in ["Hips","Spine","Spine2","Neck"] or detached.has(region): continue
		if loss>=0.48: sever(region)

func sever(region: String) -> void:
	if detached.has(region): return
	var started:=Time.get_ticks_usec()
	var parts: Array=agent.physics.detach(region)
	for part: Dictionary in parts:
		detached[part.name]=true
		severed.append(part.name)
		var ids: Array[int]=[]
		for id: int in data.regions.get(part.name,PackedInt32Array()):
			if not removed.has(id): ids.append(id)
		if ids.is_empty(): continue
		var geometry:=_bake_piece(ids,part.body.global_transform.affine_inverse())
		var visual:=MeshInstance3D.new()
		visual.mesh=geometry
		part.body.add_child(visual)
		for id in ids: removed[id]=true
	_remap_remaining_weights()
	if region=="Head": fatal=true;agent.kill()
	sever_ms=float(Time.get_ticks_usec()-started)/1000.0

func _remap_remaining_weights() -> void:
	var bones: PackedInt32Array=data.arrays[Mesh.ARRAY_BONES].duplicate()
	var bind_by_bone: Dictionary={}
	var remap: Dictionary={}
	for i in range(bind_bones.size()): bind_by_bone[bind_bones[i]]=i
	for bind in range(bind_bones.size()):
		var bone: int=bind_bones[bind]
		var physical:=bone
		while physical>=0 and not agent.physics.by_bone.has(physical): physical=agent.skeleton.get_bone_parent(physical)
		if physical<0 or not agent.physics.by_bone[physical].get("detached",false): continue
		var parent:=physical
		while parent>=0 and agent.physics.by_bone.get(parent,{}).get("detached",true): parent=agent.skeleton.get_bone_parent(parent)
		if not bind_by_bone.has(parent): continue
		remap[bind]=bind_by_bone[parent]
		# Offline slot lists avoid scanning every vertex and its ancestry.
		for slot: int in data.bind_slots[bind]: bones[slot]=remap[bind]
	live_arrays[Mesh.ARRAY_BONES]=bones
	weights_dirty=true
	coeff_override.clear()
	for cell: Dictionary in data.cells:
		if removed.has(cell.id): continue
		var affected:=false
		for bind: int in cell.coeff_bones:
			if remap.has(bind): affected=true;break
		if not affected: continue
		var coefficients: Dictionary={}
		for i in range(cell.coeff_bones.size()):
			var bind: int=remap.get(cell.coeff_bones[i],cell.coeff_bones[i])
			if not coefficients.has(bind): coefficients[bind]=[Vector3.ZERO,0.0]
			coefficients[bind][0]+=cell.coeff_positions[i]
			coefficients[bind][1]+=cell.coeff_weights[i]
		var coeff: Dictionary={"coeff_bones":PackedInt32Array(),"coeff_positions":PackedVector3Array(),"coeff_weights":PackedFloat32Array()}
		for bind in coefficients:
			coeff.coeff_bones.append(bind);coeff.coeff_positions.append(coefficients[bind][0]);coeff.coeff_weights.append(coefficients[bind][1])
		coeff_override[cell.id]=coeff
	matrix_frame=-1
	vertex_cache.clear();inner_cache.clear()

func _emit_cells(ids: Array[int], direction: Vector3) -> void:
	# Bounded visual rigid bodies per batch, including multi-pellet hits.
	var buckets: Array=[]
	var largest: Array=ids.duplicate()
	largest.sort_custom(func(a: int,b: int): return data.cells[a].volume>data.cells[b].volume)
	# Actual individual surface cells; do not join disconnected pellet wounds
	# into a single stretched rigid mesh. Smaller excess cells have no debris.
	for i in range(mini(largest.size(),FRAGMENTS_PER_BATCH)): buckets.append([largest[i]])
	for id in ids:
		var region: String=data.cells[id].region
		var part: Dictionary=agent.physics.by_bone[agent.skeleton.find_bone(region)]
		part.body.mass=maxf(0.02,part.body.mass-float(data.cells[id].volume)*1000.0)
	for bucket: Array in buckets:
		var center:=Vector3.ZERO
		var volume:=0.0
		for id: int in bucket: center+=centers[id]/bucket.size();volume+=data.cells[id].volume
		var first: Dictionary=data.cells[bucket[0]]
		var part: Dictionary=agent.physics.by_bone[agent.skeleton.find_bone(first.region)]
		var body: RigidBody3D=part.body
		var mass:=minf(volume*1000.0,body.mass*0.15)
		# Current point velocity includes the parent's angular velocity.
		var inherited:=body.linear_velocity+body.angular_velocity.cross(center-body.global_position)
		var kick:=direction*3.0
		body.apply_impulse(-kick*mass,center-body.global_position)
		var local:=Transform3D(Basis.IDENTITY,-center)
		var geometry:=_bake_piece(bucket,local)
		agent.arena.debris.emit_piece(geometry,center,mass,inherited+kick,body.angular_velocity,0.025)
	agent.physics.recount_mass()

func _bake_piece(ids: Array, transform: Transform3D) -> ArrayMesh:
	var vertices:=PackedVector3Array()
	var normals:=PackedVector3Array()
	var uv:=PackedVector2Array()
	var outer:=PackedInt32Array()
	var inner:=PackedInt32Array()
	var lookup: Dictionary={}
	var included: Dictionary={}
	for id: int in ids: included[id]=true
	for id: int in ids:
		var cell: Dictionary=data.cells[id]
		for index: int in cell.indices:
			if not lookup.has(index):
				lookup[index]=vertices.size()
				var p:=transform*vertex(index)
				var q:=transform*vertex(index,true)
				vertices.append(p);vertices.append(q)
				var n: Vector3=(p-q).normalized()
				normals.append(n);normals.append(-n)
				uv.append(data.arrays[Mesh.ARRAY_TEX_UV][index]);uv.append(data.arrays[Mesh.ARRAY_TEX_UV][index])
			outer.append(lookup[index])
		for i in range(0,cell.indices.size(),3):
			inner.append_array(PackedInt32Array([lookup[cell.indices[i+2]]+1,lookup[cell.indices[i+1]]+1,lookup[cell.indices[i]]+1]))
	var borders: Dictionary={}
	for id: int in ids:
		for edge_id: int in data.cells[id].border_ids: borders[edge_id]=true
	for edge_id: int in borders:
		var edge: PackedInt32Array=data.boundaries[edge_id]
		var left: bool=included.has(edge[2]);var right: bool=included.has(edge[3])
		if left==right: continue
		for index: int in [edge[0],edge[1]]:
			if not lookup.has(index):
				lookup[index]=vertices.size()
				var p:=transform*vertex(index);var q:=transform*vertex(index,true)
				vertices.append(p);vertices.append(q)
				normals.append((p-q).normalized());normals.append((q-p).normalized())
				uv.append(data.arrays[Mesh.ARRAY_TEX_UV][index]);uv.append(data.arrays[Mesh.ARRAY_TEX_UV][index])
		var a: int=lookup[edge[0]];var b: int=lookup[edge[1]]
		inner.append_array(PackedInt32Array([a,b,b+1,a,b+1,a+1]))
	var arrays: Array=[]
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX]=vertices;arrays[Mesh.ARRAY_NORMAL]=normals;arrays[Mesh.ARRAY_TEX_UV]=uv;arrays[Mesh.ARRAY_INDEX]=outer
	var mesh:=ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	mesh.surface_set_material(0,material)
	arrays[Mesh.ARRAY_INDEX]=inner
	if not inner.is_empty(): mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays);mesh.surface_set_material(1,flesh)
	return mesh

func _create_render_mesh() -> void:
	var mesh:=ArrayMesh.new()
	var flags: int=Mesh.ARRAY_FLAG_USE_DYNAMIC_UPDATE | (Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS if data.influences==8 else 0)
	live_arrays[Mesh.ARRAY_INDEX]=data.render_outer
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,live_arrays,[],{},flags)
	mesh.surface_set_material(0,material)
	source.mesh=mesh
	render_removed.clear()
	render_created=true
	weights_dirty=false

func _rebuild() -> void:
	agent.arena.mesh_damage_present=true
	# Healthy characters keep their original shared GLB. A damaged character
	# gets one private outer index buffer, patched only where cells disappeared.
	if weights_dirty or not render_created: _create_render_mesh()
	var stride: int=data.index_stride
	var rid:=source.mesh.get_rid()
	for id: int in removed:
		if render_removed.has(id): continue
		var cell: Dictionary=data.cells[id]
		RenderingServer.mesh_surface_update_index_region(rid,0,cell.index_offset*stride,cell.zero_bytes)
		render_removed[id]=true
	_rebuild_wound_surface()
	rebuilds+=1

func _rebuild_wound_surface() -> void:
	# Compact skinned inner patches: do not skin a second full-body mesh just
	# to draw the rim of a small hole. No flesh is drawn on an intact character.
	var borders: Dictionary={}
	var inside: Dictionary={}
	for id: int in removed:
		var cell: Dictionary=data.cells[id]
		for edge_id: int in cell.border_ids: borders[edge_id]=true
		for neighbor: int in cell.neighbors:
			if not removed.has(neighbor): inside[neighbor]=true
	var global_indices:=PackedInt32Array()
	for id: int in inside: global_indices.append_array(data.cells[id].inside)
	var n: int=data.vertex_count
	for edge_id: int in borders:
		var edge: PackedInt32Array=data.boundaries[edge_id]
		if removed.has(edge[2])==removed.has(edge[3]): continue
		var a:=edge[0];var b:=edge[1]
		global_indices.append_array(PackedInt32Array([a,b,b+n,a,b+n,a+n]))
	var arrays: Array=[]
	arrays.resize(Mesh.ARRAY_MAX)
	var vertices:=PackedVector3Array();var normals:=PackedVector3Array()
	var bones:=PackedInt32Array();var weights:=PackedFloat32Array()
	var indices:=PackedInt32Array();var lookup: Dictionary={}
	for global_index: int in global_indices:
		if not lookup.has(global_index):
			lookup[global_index]=vertices.size()
			var index:=global_index%n
			var is_inner:=global_index>=n
			vertices.append(data.inner[index] if is_inner else data.arrays[Mesh.ARRAY_VERTEX][index])
			normals.append(data.arrays[Mesh.ARRAY_NORMAL][index]*(-1.0 if is_inner else 1.0))
			for influence in range(data.influences):
				var k: int=index*data.influences+influence
				bones.append(live_arrays[Mesh.ARRAY_BONES][k])
				weights.append(data.arrays[Mesh.ARRAY_WEIGHTS][k])
		indices.append(lookup[global_index])
	var mesh:=source.mesh as ArrayMesh
	if mesh.get_surface_count()>1: mesh.surface_remove(1)
	if indices.is_empty(): return
	arrays[Mesh.ARRAY_VERTEX]=vertices;arrays[Mesh.ARRAY_NORMAL]=normals
	arrays[Mesh.ARRAY_BONES]=bones;arrays[Mesh.ARRAY_WEIGHTS]=weights;arrays[Mesh.ARRAY_INDEX]=indices
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays,[],{},Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS if data.influences==8 else 0)
	mesh.surface_set_material(1,flesh)

func report() -> Dictionary:
	return {"cells_total":data.cells.size(),"removed_cells":removed.size(),"removed_cm3":removed_volume*1000000.0,"budget_cm3":budget_volume*1000000.0,"severed":severed.duplicate(),"fatal":fatal,"brain_energy_j":brain_energy_j,"wound":last_wound.duplicate(true),"cpu_ms":cpu_ms,"sever_ms":sever_ms,"rebuilds":rebuilds}
