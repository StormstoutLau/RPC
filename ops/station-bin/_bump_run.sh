#!/bin/bash
# _bump_run.sh — run _opencode_bump.py on target station (avoid PS quoting hell)
set -uo pipefail
CFG="$HOME/.config/opencode/opencode.jsonc"
[ -f "$CFG.bak.ctxfix" ] || cp "$CFG" "$CFG.bak.ctxfix"
echo "backup: $(ls -la "$CFG.bak.ctxfix")"
python3 /tmp/_opencode_bump.py "$CFG"
echo '--- verify (all context/input lines) ---'
grep -nE '"context"|"input"|"nemotron"|"gpt-oss"' "$CFG"