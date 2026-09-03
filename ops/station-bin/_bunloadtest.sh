#!/bin/bash
echo "== infer-unload 测试 (应停掉 unsloth gpt-oss-120b) =="
infer-unload 2>&1 | head -15
echo "[rc=${PIPESTATUS[0]}]"
echo "== 卸载后残留 =="
ps -eo pid,cmd | grep -E "[u]nsloth studio run|[l]lama-server" | grep -v defunct | grep -v grep | head || echo "(无残留)"
echo "== 内存 =="
free -g | head -2