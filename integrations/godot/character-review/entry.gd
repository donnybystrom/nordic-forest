extends Node

func _ready() -> void:
	var arena := "--testground" in OS.get_cmdline_user_args()
	var scene := "res://testground/testground.tscn" if arena else "res://review.tscn"
	add_child(load(scene).instantiate())
