#!/bin/bash
echo "== B opencode cluster-local/gpt-oss =="
echo 'Reply with exactly the single word B-OC-LOCAL-OK' | timeout 120 opencode run -m cluster-local/gpt-oss 2>&1 | tail -4
echo "[rc=${PIPESTATUS[1]}]"