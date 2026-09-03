#!/bin/bash
echo "== claude (BASE_URL 8087) =="
timeout 150 claude -p "Reply with exactly the single word CLAUDE-OK" < /dev/null 2>&1 | tail -8
echo "[rc=${PIPESTATUS[0]}]"