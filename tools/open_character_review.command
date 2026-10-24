#!/bin/zsh
set -eu
task_repo="${0:A:h:h}"
task_project="$task_repo/output/zombie-beach/rodin-tpose-v1/godot-review"
if command -v godot >/dev/null 2>&1; then
  task_engine="$(command -v godot)"
else
  task_engine="/Applications/Godot.app/Contents/MacOS/Godot"
fi
python3 "$task_repo/tools/build_character_review.py"
"$task_engine" --headless --path "$task_project" --editor --import --log-file "$task_project/../godot-import.log"
exec "$task_engine" --path "$task_project" --log-file "$task_project/../godot-viewer.log" -- --physics "$@"
