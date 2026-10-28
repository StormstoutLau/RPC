#!/bin/bash
echo "== opencode --pure (禁插件) cluster-local/gpt-oss =="
echo 'Reply with exactly the single word PURE-OK' | timeout 90 opencode run -m cluster-local/gpt-oss --pure 2>&1 | tail -6
echo "[rc=${PIPESTATUS[1]}]"