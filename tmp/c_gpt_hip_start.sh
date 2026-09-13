#!/bin/bash
# C 站 gpt-oss-120b HIP 启动 — 按 A/B 站成功基准 (文档 §2.3 同参数)
set +e
ENGINE=~/.unsloth/llama.cpp/build/bin/llama-server
MODEL=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf
LOG=/tmp/c_gpt_hip.log

echo '=== 0. load-gate 预检 (need 60G) ==='
bash /tmp/load-gate 60 || { echo 'GATE FAIL'; exit 1; }

echo '=== 1. 清理旧实例 ==='
pkill -9 -f 'gpt-oss-120b' 2>/dev/null
sleep 3
pgrep -af 'llama-server' || echo '(无 llama-server)'
ss -tlnp 2>/dev/null | grep 18081 || echo '(18081 已释放)'

echo '=== 2. 启动 (A/B 基准参数: -ngl -1 --fit off --load-mode none) ==='
setsid nohup "$ENGINE" -m "$MODEL" --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none -c 4096 -t 16 --flash-attn on > "$LOG" 2>&1 &
echo "pid=$!"
sleep 25
echo '=== 日志头部 ==='
head -25 "$LOG"
echo '=== GPU/内存 ==='
cat /sys/class/drm/card1/device/gpu_busy_percent 2>/dev/null | xargs echo "gpu_busy=%"
free -g | head -2
echo '=== 端口 ==='
ss -tlnp 2>/dev/null | grep 18081 || echo 'not listening yet'