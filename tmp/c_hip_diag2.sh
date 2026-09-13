#!/bin/bash
# C 站: A) CPU-only 加载 qwen3.8 (判断 HIP 通路整体性)  B) HSA_XNACK 变体
set +e
MODEL=/home/scott-lau/models/qwen3.8-27b-mtp/Qwen3.8-27B-MTP-Q8_0.gguf
echo "=== A. 清理 ==="
pkill -9 -f llama-server 2>/dev/null; sleep 2

echo "=== A.1 CPU-only 加载 (无 --device) ==="
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server -m $MODEL --port 18083 --no-kv-offload -c 4096 -t 16 > /tmp/c_cpu_qwen.log 2>&1 &
PID=$!
echo "pid=$PID"
sleep 40
echo "--- 日志尾 ---"
tail -8 /tmp/c_cpu_qwen.log
echo "--- 端口 ---"
ss -tlnp 2>/dev/null | grep 18083 || echo 'not yet'
echo "--- 新 fault? ---"
sudo -n dmesg 2>/dev/null | grep -c 'gfxhub. page fault'
echo "--- 内存 ---"
free -g | head -2

echo ""
echo "=== B. HSA_XNACK=0 + HIP ==="
pkill -9 -f llama-server 2>/dev/null; sleep 2
HSA_XNACK=0 setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server -m $MODEL --port 18084 --device ROCm0 -ngl -1 --fit off -c 4096 -t 16 --flash-attn on > /tmp/c_xnack_qwen.log 2>&1 &
PID2=$!
echo "pid=$PID2"
sleep 40
echo "--- 日志尾 ---"
tail -8 /tmp/c_xnack_qwen.log
echo "--- 端口 ---"
ss -tlnp 2>/dev/null | grep 18084 || echo 'not yet'
echo "--- 新 fault? ---"
sudo -n dmesg 2>/dev/null | grep 'gfxhub. page fault' | tail -1
echo "--- 内存 ---"
free -g | head -2
pkill -9 -f llama-server 2>/dev/null