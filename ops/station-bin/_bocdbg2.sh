#!/bin/bash
echo "== opencode debug (log-level DEBUG / print-logs) =="
echo 'Reply OK' | timeout 60 opencode run -m cluster-local/gpt-oss --print-logs 2>&1 | tail -40
echo "[rc=${PIPESTATUS[1]}]"