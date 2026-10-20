#!/bin/zsh
cd "${0:A:h:h}" || exit 1
exec /opt/miniconda3/bin/python3 tools/manage_bridge.py start
