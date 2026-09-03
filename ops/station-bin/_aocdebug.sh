#!/bin/bash
echo "== opencode 版本 =="
opencode --version 2>&1 | tail -2
echo "== opencode -m cluster-local/gpt-oss 短消息(带详细) =="
echo 'Reply OK' | timeout 60 opencode run -m cluster-local/gpt-oss --verbose 2>&1 | tail -30
echo "[rc=${PIPESTATUS[1]}]"