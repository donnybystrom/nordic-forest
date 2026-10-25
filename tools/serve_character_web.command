#!/bin/zsh
set -eu
task_repo="${0:A:h:h}"
print 'FPS-testground: http://localhost:8010/?mode=arena'
exec python3 -m http.server 8010 --bind 127.0.0.1 --directory "$task_repo/build/character-web/site"
