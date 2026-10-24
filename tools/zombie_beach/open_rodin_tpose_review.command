#!/bin/zsh
set -eu
task_repo="${0:A:h:h:h}"
exec "$task_repo/tools/open_character_review.command" "$@"
