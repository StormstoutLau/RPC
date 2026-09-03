#!/bin/bash
echo "== A 站 claude 长时测 (180s) =="
timeout 180 claude -p "Reply with exactly the single word A-CLD-OK" < /dev/null 2>&1 | tail -4
echo "[rc=${PIPESTATUS[0]}]"