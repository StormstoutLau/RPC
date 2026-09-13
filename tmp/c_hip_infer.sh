#!/bin/bash
# C 站 unsloth HIP 推理验证: load-gate -> 启动 gpt-oss-120b (HIP/ROCm0) -> 冒烟
set +e
MODEL=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf
ENGINE=~/.unsloth/llama.cpp/build/bin/llama-server
LOG=/tmp/c_gpt_hip.log

echo "=== 0. load-gate 预检 (need 72G: 模型60 + 余量) ==="
bash /tmp/load-gate 72
RC=$?
if [ $RC -ne 0 ]; then echo "GATE FAIL"; exit 1; fi
echo ""
echo "=== 1. 引擎与设备 ==="
$ENGINE --version 2>&1 | head -1
$ENGINE --list-devices 2>&1 | head -3
echo ""
echo "=== 2. 启动 (HIP/ROCm0, 单实例) ==="
pkill -f 'llama-server.*gpt-oss-120b' 2>/dev/null; sleep 2
setsid nohup "$ENGINE" -m "$MODEL" --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none -c 4096 -t 8 --flash-attn on > "$LOG" 2>&1 &
echo "pid=$!"
sleep 20
echo "=== log 头部 ==="
head -15 "$LOG" 2>/dev/null
echo "=== 内存 ==="
free -g | head -2
echo "=== 18081 ==="
ss -tlnp 2>/dev/null | grep 18081 || echo "not listening yet"