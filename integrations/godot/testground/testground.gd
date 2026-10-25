extends Node3D
const Agent = preload("res://testground/zombie_agent.gd")
const Player = preload("res://testground/fps_player.gd")
const MOTIONS := ["Meshy_Unsteady_Walk","Meshy_Walking","Meshy_Running","Rodin_HumanZombieCrawl"]
var catalog: Dictionary
var player: CharacterBody3D
var zombies: Array[Node3D] = []
var follow_player := false
var auto_recover := true
var show_colliders := false
var shot_impulse := 14.0
var shot_profile := 0
var profile: OptionButton
var muscle_strength := 1.0
var balance_strength := 1.0
var menu: PanelContainer
var amount: SpinBox
var models: OptionButton
var motions: OptionButton
var formation: OptionButton
var follow: CheckBox
var respawn_button: Button
var add_button: Button
var impulse_slider: HSlider
var play_button: Button
var colliders_check: CheckBox
var info: Label
var ammo: Label
var hit_label: Label
var hint: Label
var crosshair: Label
var hit_flash := 0.0
var generation := 0
var probe_enabled := false
var probe_elapsed := 0.0
var next_id := 0
var impacts: Array[Node3D] = []

func _ready() -> void:
	catalog = JSON.parse_string(FileAccess.get_file_as_string("res://characters.json"))
	_build_world()
	player = Player.new()
	add_child(player)
	player.position = Vector3(0,0.1,7)
	player.setup(self)
	_build_ui()
	spawn_group()
	if OS.has_feature("web"):
		probe_enabled = bool(JavaScriptBridge.eval("new URLSearchParams(location.search).has('test')",true))
		JavaScriptBridge.eval("window.__ragdollReady=true;window.dispatchEvent(new Event('nordic-ragdoll-ready'));",true)
	print("TESTGROUND_READY zombies=",zombies.size()," models=",catalog.characters.size())

func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.94
	return material

func block(at: Vector3, size: Vector3, color: Color, solid := true, walkable := false) -> Node3D:
	var body: Node3D = StaticBody3D.new() if solid else Node3D.new()
	add_child(body)
	body.position = at
	if solid:
		body.collision_layer = 1
		body.collision_mask = 2|8
		body.set_meta("walkable",walkable)
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = size
		shape.shape = box
		body.add_child(shape)
	var visual := MeshInstance3D.new()
	visual.name = "Surface"
	var mesh := BoxMesh.new()
	mesh.size = size
	visual.mesh = mesh
	visual.material_override = _material(color)
	if not solid:
		visual.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	body.add_child(visual)
	return body

func _build_world() -> void:
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("aabcb7")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color("cbd9d3")
	environment.environment.ambient_light_energy = 0.65
	add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48,-28,0)
	sun.light_color = Color("fff0d8")
	sun.light_energy = 0.85
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 35.0
	add_child(sun)
	var ground := block(Vector3(0,-0.1,0),Vector3(30,0.2,30),Color("53645b"),true,true)
	ground.get_node("Surface").cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for i in range(-7,8):
		block(Vector3(i*2,0.003,0),Vector3(0.025,0.005,28),Color("718075"),false)
		block(Vector3(0,0.003,i*2),Vector3(28,0.005,0.025),Color("718075"),false)
	for edge in [-1,1]:
		block(Vector3(edge*14.5,0.4,0),Vector3(0.5,0.8,29),Color("34473f"))
		block(Vector3(0,0.4,edge*14.5),Vector3(29,0.8,0.5),Color("34473f"))
	# Two solid shoulders form a crowd bottleneck. A small side stair lets us
	# inspect collisions on different heights; no scripted climb/foot IK is used.
	block(Vector3(-3.2,0.85,0),Vector3(4.2,1.7,0.5),Color("7c8b7f"))
	block(Vector3(3.2,0.85,0),Vector3(4.2,1.7,0.5),Color("7c8b7f"))
	for step in range(3):
		var height := 0.15*float(step+1)
		block(Vector3(7,height*0.5,-2-step*0.6),Vector3(2,height,0.6),Color("8b9482"),true,true)
	block(Vector3(7,0.225,-4.1),Vector3(2,0.45,1.4),Color("8b9482"),true,true)
	for side in [-1,1]:
		for index in range(5):
			var tree := MeshInstance3D.new()
			var cone := CylinderMesh.new()
			cone.top_radius = 0.0
			cone.bottom_radius = 1.8
			cone.height = 6.0+index*0.3
			cone.radial_segments = 8
			tree.mesh = cone
			tree.position = Vector3(side*(18+index%2),3.5,-12+index*6)
			tree.material_override = _material(Color("354d40"))
			add_child(tree)
	var sign := Label3D.new()
	sign.text = "NORDIC FOREST\nPHYSICS TESTGROUND"
	sign.font_size = 75
	sign.pixel_size = 0.008
	sign.position = Vector3(0,3.5,-13.9)
	sign.modulate = Color("d9e5c6")
	add_child(sign)

func floor_height(at: Vector3) -> float:
	var query := PhysicsRayQueryParameters3D.create(Vector3(at.x,3.0,at.z),Vector3(at.x,-1.0,at.z),1)
	var result := get_world_3d().direct_space_state.intersect_ray(query)
	if not result.is_empty() and result.collider.get_meta("walkable",false):
		return float(result.position.y)
	return 0.0

func steering_target(at: Vector3) -> Vector3:
	var destination := player.global_position
	if at.z < -0.5 and destination.z > 0.5 and absf(at.x)>0.85 and absf(at.x)<5.5:
		return Vector3(0,0,-1.1)
	if at.z > 0.5 and destination.z < -0.5 and absf(at.x)>0.85 and absf(at.x)<5.5:
		return Vector3(0,0,1.1)
	return destination

func _label(parent: Node, text: String, size := 16) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size",size)
	label.add_theme_color_override("font_outline_color",Color("14221c"))
	label.add_theme_constant_override("outline_size",3)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label

func _button(parent: Node, text: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.pressed.connect(callback)
	parent.add_child(button)
	return button

func _slider(parent: Node, text: String, low: float, high: float, initial: float, callback: Callable) -> HSlider:
	_label(parent,text)
	var row := HBoxContainer.new()
	parent.add_child(row)
	var slider := HSlider.new()
	slider.min_value = low
	slider.max_value = high
	slider.step = 1.0 if high > 2.0 else 0.05
	slider.value = initial
	slider.custom_minimum_size.x = 245
	slider.focus_mode = Control.FOCUS_NONE
	row.add_child(slider)
	var value := _label(row,"%.2f" % initial)
	slider.value_changed.connect(func(n: float): value.text = "%.2f" % n; callback.call(n))
	return slider

func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	menu = PanelContainer.new()
	menu.position = Vector2(18,18)
	menu.custom_minimum_size.x = 350
	layer.add_child(menu)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation",7)
	menu.add_child(box)
	_label(box,"FPS / TESTGROUND",22)
	_label(box,"Grupp och rörelse",16)
	var row := HBoxContainer.new()
	box.add_child(row)
	_label(row,"Antal  ")
	amount = SpinBox.new()
	amount.min_value = 1
	amount.max_value = 12
	amount.value = 4
	row.add_child(amount)
	models = OptionButton.new()
	models.focus_mode = Control.FOCUS_NONE
	for text in ["Båda zombietyperna","Strandzombie · kvinna","Strandzombie · man"]:
		models.add_item(text)
	box.add_child(models)
	motions = OptionButton.new()
	motions.focus_mode = Control.FOCUS_NONE
	for text in ["Blandat: gång, löpning, krypning","Vilopose","Ostadig gång","Gång","Löpning","Krypning","Uppresningsprov · mage","Uppresningsprov · rygg"]:
		motions.add_item(text)
	box.add_child(motions)
	formation = OptionButton.new()
	formation.focus_mode = Control.FOCUS_NONE
	formation.add_item("Spridd grupp")
	formation.add_item("Trångt led")
	box.add_child(formation)
	var buttons := HBoxContainer.new()
	box.add_child(buttons)
	respawn_button = _button(buttons,"Spawna om grupp",spawn_group)
	add_button = _button(buttons,"Lägg till en",func(): spawn_one())
	follow = CheckBox.new()
	follow.text = "Följ spelaren (annars stå kvar)"
	follow.focus_mode = Control.FOCUS_NONE
	follow.toggled.connect(func(enabled: bool): follow_player = enabled)
	box.add_child(follow)
	var recovery := CheckBox.new()
	recovery.text = "Res dig med animation och stöd"
	recovery.button_pressed = true
	recovery.focus_mode = Control.FOCUS_NONE
	recovery.toggled.connect(func(enabled: bool): auto_recover = enabled)
	box.add_child(recovery)
	profile = OptionButton.new()
	profile.focus_mode = Control.FOCUS_NONE
	for text in ["1 · Pistol", "2 · Tung kula", "3 · Hagelsvärm (8 hagel)"]: profile.add_item(text)
	profile.item_selected.connect(select_profile)
	box.add_child(profile)
	impulse_slider = _slider(box,"Total skottimpuls · N s",2.0,180.0,14.0,func(n: float): shot_impulse=n)
	_slider(box,"Muskelkraft",0.0,1.5,1.0,func(n: float): muscle_strength=n)
	_slider(box,"Höftstöd",0.0,1.0,1.0,func(n: float): balance_strength=n)
	colliders_check = CheckBox.new()
	colliders_check.text = "Visa träff- och kollisionskroppar (F2)"
	colliders_check.focus_mode = Control.FOCUS_NONE
	colliders_check.toggled.connect(func(enabled: bool): show_colliders=enabled)
	box.add_child(colliders_check)
	_label(box,"Impulsen är ett provvärde.\nHagel delar totalimpulsen mellan 8 strålar.\nBalanshjälpen ger efter vid störning.\nFotarbete och självbärande balans återstår.",13)
	play_button = _button(box,"Spela · fånga musen",func(): set_menu(false))
	crosshair = _label(layer,"+",26)
	crosshair.position = Vector2(542,405)
	ammo = _label(layer,"",20)
	ammo.position = Vector2(730,775)
	info = _label(layer,"",16)
	info.position = Vector2(18,750)
	hit_label = _label(layer,"",17)
	hit_label.position = Vector2(370,56)
	hint = _label(layer,"",15)
	hint.position = Vector2(365,18)
	set_menu(true)

func select_profile(index: int) -> void:
	shot_profile = index
	profile.select(index)
	impulse_slider.value = [14.0,70.0,100.0][index]

func set_menu(open: bool) -> void:
	menu.visible = open
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if open else Input.MOUSE_MODE_CAPTURED
	player.aiming = false

func spawn_group() -> void:
	for zombie in zombies:
		zombie.dispose()
	zombies.clear()
	for i in range(int(amount.value)):
		spawn_one()
	generation += 1

func spawn_one() -> Node3D:
	if zombies.size() >= 12:
		return null
	var model: int = zombies.size()%catalog.characters.size() if models.selected == 0 else models.selected-1
	var motion := ""
	if motions.selected == 0:
		motion = MOTIONS[zombies.size()%MOTIONS.size()]
	elif motions.selected >= 6:
		motion = MOTIONS[0]
	elif motions.selected >= 2:
		motion = MOTIONS[motions.selected-2]
	var index := zombies.size()
	var spacing := 1.45 if formation.selected == 1 else 2.4
	var spawn := Vector3((float(index%2)-0.5)*spacing,0,-3.8-float(index/2)*2.0)
	var zombie := Agent.new()
	add_child(zombie)
	zombie.setup(self,next_id,model,spawn,motion)
	if motions.selected>=6: zombie.start_lying("prone" if motions.selected==6 else "supine")
	next_id += 1
	zombies.append(zombie)
	return zombie

func mark_impact(at: Vector3, normal: Vector3, wall: bool) -> void:
	var node := MeshInstance3D.new()
	var mesh := SphereMesh.new()
	mesh.radius = 0.025
	mesh.height = 0.05
	mesh.radial_segments = 8
	mesh.rings = 4
	node.mesh = mesh
	var material := _material(Color("e7c179") if wall else Color("dbefae"))
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	node.material_override = material
	add_child(node)
	node.global_position = at+normal*0.012
	impacts.append(node)
	if impacts.size()>20:
		var oldest := impacts.pop_front() as Node3D
		if is_instance_valid(oldest): oldest.queue_free()
	get_tree().create_timer(0.7).timeout.connect(func():
		impacts.erase(node)
		if is_instance_valid(node): node.queue_free())

func _process(delta: float) -> void:
	if not is_instance_valid(player): return
	hit_flash = maxf(0.0,hit_flash-delta)
	crosshair.modulate = Color("ddedab") if hit_flash>0.0 else Color.WHITE
	ammo.text = "Laddar om..." if player.reload_time>0 else "%02d / 12  ·  R: ladda om" % player.magazine
	var fallen := 0
	var contacts := 0
	for zombie in zombies:
		if zombie.state in ["downed","recovering"]: fallen += 1
		contacts += zombie.crowd_contacts
	info.text = "%d zombier · %d fysikkroppar\n%s · %d nere/återhämtar · %d kroppskontakter\nWASD: gå · Shift: spring · Space: hoppa" % [zombies.size(),zombies.size()*17,"Följer dig" if follow_player else "Står kvar",fallen,contacts]
	hint.text = "Tab: inställningar · 1/2/3: impulsprofil · högerklick: sikta"
	if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED and not menu.visible:
		hint.text = "Klicka i banan för att spela · Tab: inställningar"
	if not player.last_shot.is_empty():
		var hit: Dictionary = player.last_shot
		if hit.has("bone"):
			hit_label.text = "%s · %s · %.1f N s" % [hit.zombie,hit.bone,hit.get("delivered_ns",hit.impulse_ns)]
			if hit.get("profile",0)==2: hit_label.text += " · %d/8 hagel" % hit.body_hits
		else:
			hit_label.text = "Träff i banan" if hit.get("hit",false) else "Miss"
	for zombie in zombies:
		if zombie.state=="recovering":
			info.text += "\n%s · %s" % ["Mage" if zombie.recovery.kind=="prone" else "Rygg",zombie.recovery.stage]
			break
	add_button.disabled = zombies.size()>=12
	colliders_check.set_pressed_no_signal(show_colliders)
	if probe_enabled:
		probe_elapsed += delta
		if probe_elapsed>0.2:
			probe_elapsed=0.0
			_publish_probe()

func _center(control: Control) -> Array:
	var p := control.get_global_rect().get_center()
	return [p.x,p.y]

func _publish_probe() -> void:
	var agents := []
	for zombie in zombies:
		var root: Vector3 = zombie.root_position()
		var parts := {}
		for part: Dictionary in zombie.physics.bodies:
			var p: Vector3 = part.body.global_position
			var screen: Vector2 = player.camera.unproject_position(p)
			parts[part.name] = {"position":[p.x,p.y,p.z],"screen":[screen.x,screen.y]}
		agents.append({"id":zombie.name,"model":zombie.characters[zombie.model_index].id,"clip":zombie.clip,
			"root":[root.x,root.y,root.z],"anchor":[zombie.anchor.x,zombie.anchor.y,zombie.anchor.z],
			"recovery_kind":zombie.recovery.kind,"recovery_stage":zombie.recovery.stage,
			"recovery_time":zombie.recovery.time,"recovery_duration":zombie.recovery.duration() if not zombie.recovery.kind.is_empty() else 0,
			"recovery_attempts":zombie.recovery_attempts,"recovery_completed":zombie.recovery_completed,"recovery_interruptions":zombie.recovery_interruptions,
			"state":zombie.state,"hits":zombie.received_hits,"contacts":zombie.crowd_contacts,
			"stability":zombie.physics.stability,"support_distance":zombie.physics.support_distance,
			"support_force":[zombie.physics.last_support_force.x,zombie.physics.last_support_force.y,zombie.physics.last_support_force.z],
			"muscles":zombie.physics.muscles,"travel":zombie.travel,"skin_error":zombie.physics.max_skin_pose_error,"parts":parts})
	var at := player.global_position
	var popup := motions.get_popup()
	var state := {"generation":generation,"zombies":agents,"follow":follow_player,"menu":menu.visible,
		"player":[at.x,at.y,at.z],"yaw":player.rotation.y,"pitch":player.pitch,"sensitivity":player.sensitivity,
		"player_speed":Vector2(player.velocity.x,player.velocity.z).length(),
		"captured":Input.mouse_mode==Input.MOUSE_MODE_CAPTURED,"fov":player.camera.fov,"shots":player.shots,"ammo":player.magazine,
		"motion_count":motions.item_count,"selected_motion":motions.selected,"motions_open":motions.get_popup().visible,
		"motion_popup":[popup.position.x,popup.position.y,popup.size.x,popup.size.y],
		"selected_count":amount.value,"count_focused":amount.get_line_edit().has_focus(),
		"profile":shot_profile,"reloading":player.reload_time>0.0,"last_shot":player.last_shot,"impulse":shot_impulse,
		"viewport":[1100,850],"controls":{"play":_center(play_button),"follow":_center(follow),"spawn":_center(respawn_button),"add":_center(add_button),"amount":_center(amount),"models":_center(models),"motions":_center(motions),"formation":_center(formation),"impulse":_center(impulse_slider),"profile":_center(profile)}}
	JavaScriptBridge.eval("window.__testgroundDemo="+JSON.stringify(state)+";",true)
