#!/bin/bash
echo "== claude 长时测 (240s) =="
timeout 240 claude -p "Reply with exactly the single word CLAUDE-OK" < /dev/null 2>&1 | tail -12
echo "[rc=${PIPESTATUS[0]}]"