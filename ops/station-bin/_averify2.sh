#!/bin/bash
# 铁律：opencode 必须 stdin 管道形式
echo "== 1) opencode stdin 管道 =="
echo 'Reply with exactly the single word OPENCODE-OK' | timeout 150 opencode run -m cluster-local/gpt-oss 2>&1 | tail -8
echo "[rc=${PIPESTATUS[1]}]"