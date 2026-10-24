#!/usr/bin/env bash
set -euo pipefail
task_version=4.7.1
task_bin="${GODOT_CI_HOME:-$PWD/build/godot-ci}"
task_templates="${XDG_DATA_HOME:-$HOME/.local/share}/godot/export_templates/$task_version.stable"
mkdir -p "$task_bin" "$task_templates"
task_release="https://github.com/godotengine/godot-builds/releases/download/$task_version-stable"
if [[ ! -x "$task_bin/godot" ]]; then
  curl --fail --location --retry 3 "$task_release/Godot_v$task_version-stable_linux.x86_64.zip" -o "$task_bin/engine.zip"
  echo "c7ff14fd28472c8d4f193043de30278dcf7e5241a1dcf7566b02e27addaa33ba  $task_bin/engine.zip" | sha256sum -c -
  unzip -o "$task_bin/engine.zip" -d "$task_bin"
  mv "$task_bin/Godot_v$task_version-stable_linux.x86_64" "$task_bin/godot"
  chmod +x "$task_bin/godot"
  rm "$task_bin/engine.zip"
fi
if [[ ! -f "$task_templates/web_nothreads_release.zip" ]]; then
  curl --fail --location --retry 3 "$task_release/Godot_v$task_version-stable_export_templates.tpz" -o "$task_bin/templates.tpz"
  echo "86409db6200b6f8fd3230989c2d2002851f3dd18acf11d7bdbafddf5a0dd0f72  $task_bin/templates.tpz" | sha256sum -c -
  unzip -j -o "$task_bin/templates.tpz" templates/web_nothreads_release.zip -d "$task_templates"
  rm "$task_bin/templates.tpz"
fi
"$task_bin/godot" --version
