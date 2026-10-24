extends Node
## Minimal browser readiness event, with opt-in read-only state for WebGL tests.
var view: Node
var probe_enabled := false

func _ready() -> void:
	if not OS.has_feature("web"):
		return
	probe_enabled = bool(JavaScriptBridge.eval("new URLSearchParams(location.search).has('test')", true))
	JavaScriptBridge.eval("window.__ragdollReady=true; window.dispatchEvent(new Event('nordic-ragdoll-ready'));", true)
	if probe_enabled:
		var timer := Timer.new()
		timer.wait_time = 0.2
		timer.timeout.connect(_publish)
		add_child(timer)
		timer.start()
		_publish()

func _center(control: Control) -> Array:
	var point := control.get_global_rect().get_center()
	return [point.x, point.y]

func _rect(control: Control) -> Array:
	var rect := control.get_global_rect()
	return [rect.position.x, rect.position.y, rect.size.x, rect.size.y]

func _publish() -> void:
	var state := {"model":view.characters[view.model_index].id, "models":view.models.item_count,
		"clips":view.clips.item_count - 1, "clip":view.selected_clip(), "playing":view.player.is_playing(),
		"mode":view.physics_mode.selected, "viewport":[view.get_viewport().get_visible_rect().size.x,view.get_viewport().get_visible_rect().size.y],
		"controls":{"push":_center(view.push_button), "mode":_center(view.physics_mode), "models":_center(view.models),
			"clips":_center(view.clips), "muscles":_center(view.muscle_slider), "balance":_center(view.balance_slider), "ball_mass":_center(view.ball_mass)}}
	state["slider_rects"] = {"muscles":_rect(view.muscle_slider), "balance":_rect(view.balance_slider), "ball_mass":_rect(view.ball_mass)}
	if is_instance_valid(view.physics):
		var sandbox = view.physics
		var hips: Vector3 = sandbox.root_body().global_position
		var ball_point: Vector2 = view.camera.unproject_position(sandbox.ball.global_position)
		var ball_position: Vector3 = sandbox.ball.global_position
		state.merge({"hips":[hips.x,hips.y,hips.z], "ball_contacts":sandbox.ball_contacts, "bodies":sandbox.bodies.size(), "joints":sandbox.joints.size(),
			"dragging":sandbox.dragging, "ball_screen":[ball_point.x,ball_point.y], "mass":sandbox.ball.mass,
			"ball_position":[ball_position.x,ball_position.y,ball_position.z],
			"skin_samples":sandbox.modifier_samples, "skin_error":sandbox.max_skin_pose_error,
			"muscles":sandbox.muscles, "balance":sandbox.balance, "support_force":sandbox.last_support_force.length()})
	JavaScriptBridge.eval("window.__ragdollDemo=" + JSON.stringify(state) + ";", true)
