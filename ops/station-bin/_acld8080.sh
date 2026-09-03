#!/bin/bash
echo "== A 站 claude (8080) =="
timeout 120 claude -p "Reply with exactly the single word A-CLD-8080-OK" < /dev/null 2>&1 | tail -4
echo "[rc=${PIPESTATUS[0]}]"