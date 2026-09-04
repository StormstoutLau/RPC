#!/bin/bash
# bs2-runhelp.sh — 确认 opencode run 参数面 (只读帮助)
set -u
opencode run --help 2>&1 | head -40
echo "---- opencode --help(含 run 说明) ----"
opencode --help 2>&1 | grep -iE 'run|agent|-f |--fork|--continue|--session' | head -20
echo OK