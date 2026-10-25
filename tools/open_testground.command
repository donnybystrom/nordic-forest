#!/bin/zsh
set -eu
task_repo="${0:A:h:h}"
if command -v godot >/dev/null 2>&1; then
  task_engine="$(command -v godot)"
else
  task_engine="/Applications/Godot.app/Contents/MacOS/Godot"
fi
python3 "$task_repo/tools/build_character_web.py" --prepare-only
"$task_engine" --headless --path "$task_repo/build/character-web/project" --editor --import --log-file /tmp/nordic-testground-import.log
"$task_engine" --headless --path "$task_repo/build/character-web/project" --script res://testground/bake_damage.gd --log-file /tmp/nordic-fracture-bake.log
exec "$task_engine" --path "$task_repo/build/character-web/project" --log-file /tmp/nordic-testground.log -- --testground "$@"
