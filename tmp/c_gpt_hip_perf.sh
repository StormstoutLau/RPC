#!/bin/bash
# C 站: 启动 gpt-oss HIP 并长窗观察 (120s), 抓取 dmesg fault 与 perf 热点
set +e
ENGINE=~/.unsloth/llama.cpp/build/bin/llama-server
MODEL=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf
LOG=/tmp/c_gpt_hip.log
DCNT_BEFORE=$(sudo -n dmesg 2>/dev/null | grep -c 'gfxhub. page fault')

echo "=== 0. 清理 ==="
pkill -9 -f 'gpt-oss-120b' 2>/dev/null
sleep 2
echo "fault_before=$DCNT_BEFORE"

echo "=== 1. 启动 ==="
setsid nohup "$ENGINE" -m "$MODEL" --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none -c 4096 -t 16 --flash-attn on > "$LOG" 2>&1 &
PID=$!
echo "pid=$PID"
sleep 30
echo "=== 2. 进程状态 ==="
ps -o pid,stat,%cpu,time,rss -p $PID 2>/dev/null
echo "=== 3. 采样栈 (3 次) ==="
for i in 1 2 3; do
  cat /proc/$PID/stack 2>/dev/null | head -3
  y=$(cat /proc/$PID/*/stack 2>/dev/null | head -3)
  [ -n "$y" ] && echo "t$i: $y"
  sleep 2
done
echo "=== 4. 日志尾 ==="
tail -8 "$LOG"
echo "=== 5. fault 计数对比 ==="
sudo -n dmesg 2>/dev/null | grep -c 'gfxhub. page fault'
echo "=== 6. 尝试 gdb 附加 (允许则取 backtrace) ==="
gdb -batch -p $PID -ex 'bt 12' 2>/dev/null | grep -E '^#' | head -12 || echo '(gdb 不可用或受限)'