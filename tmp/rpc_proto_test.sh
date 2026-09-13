#!/bin/bash
# RPC 协议兼容性实测: 9859 client -> master rpc-server (A via WiFi)
set +e
SSHPORT=18099
# 清理残留(仅匹配 llama-server 18099)
for pid in $(ss -tlnp 2>/dev/null | grep 18099 | grep -oP 'pid=\K[0-9]+'); do kill "$pid" 2>/dev/null; done
sleep 1
nohup /opt/llama.cpp-9859/llama-server \
  -m /data/models/gguf/lmstudio-community/Qwen2.5-7B-Instruct-GGUF/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  --rpc 192.168.1.33:50052 \
  -c 4096 -ngl 99 --port 18099 \
  > /tmp/rpc-proto-test.log 2>&1 &
sleep 15
echo "=== KEY LOG (rpc/backend/error) ==="
grep -iE "rpc|error|fail|backend|load|version|handshake" /tmp/rpc-proto-test.log | head -30
echo "=== LISTEN CHECK ==="
ss -tlnp 2>/dev/null | grep 18099