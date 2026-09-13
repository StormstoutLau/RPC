#!/bin/bash
# C 站: Auto 档(64G carveout) 下 qwen3.8-27B HIP 验证 — 用小模型隔离变量
set +e
MODEL=/home/scott-lau/models/qwen3.8-27b-mtp/Qwen3.8-27B-MTP-Q8_0.gguf
echo "=== 0. load-gate 30G (27B 模型) ==="
bash /tmp/load-gate 30 || { echo GATE FAIL; exit 1; }
echo "=== 1. 清理 ==="
pkill -9 -f 'llama-server.*gpt-oss' 2>/dev/null
pkill -9 -f 'qwen3.8-27b' 2>/dev/null
sleep 2
echo "=== 2. 启动 qwen3.8 HIP (ROCm0, Auto 档) ==="
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server -m $MODEL --port 18082 --device ROCm0 -ngl -1 --fit off --load-mode none -c 4096 -t 16 --flash-attn on > /tmp/c_qwen_hip_auto.log 2>&1 &
PID=$!
echo "pid=$PID"
sleep 50
echo "=== 3. 日志尾 ==="
tail -12 /tmp/c_qwen_hip_auto.log
echo "=== 4. 端口 ==="
ss -tlnp 2>/dev/null | grep 18082 || echo 'not yet'
echo "=== 5. 进程 ==="
ps -o pid,stat,%cpu,time,rss -p $PID 2>/dev/null
echo "=== 6. 新 fault ==="
sudo -n dmesg 2>/dev/null | grep 'gfxhub. page fault' | tail -2 || echo '(无)'
echo "=== 7. 内存 ==="
free -g | head -2