#!/bin/bash
# C 站: CPU-only 完整加载确认 + BIOS 信息
set +e
MODEL=/home/scott-lau/models/qwen3.8-27b-mtp/Qwen3.8-27B-MTP-Q8_0.gguf
echo "=== A. CPU-only 加载计时 (最长 90s) ==="
pkill -9 -f llama-server 2>/dev/null; sleep 2
/usr/bin/time -v setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server -m $MODEL --port 18083 --no-kv-offload -c 4096 -t 16 > /tmp/c_cpu_qwen.log 2>&1 &
PID=$!
# 轮询直到 model loaded 或超时
for i in $(seq 1 18); do
  sleep 5
  if grep -q 'model loaded' /tmp/c_cpu_qwen.log 2>/dev/null; then
    echo "model loaded at ~$((i*5))s"; break
  fi
  if ! kill -0 $PID 2>/dev/null; then echo "进程退出 at ~$((i*5))s"; break; fi
done
echo "--- 日志尾 ---"
grep -E 'model loaded|listening|error|fail' /tmp/c_cpu_qwen.log | tail -5
echo "--- 进程 ---"
ps -o pid,stat,%cpu,time,rss -p $PID 2>/dev/null
pkill -9 -f llama-server 2>/dev/null

echo ""
echo "=== B. BIOS/UMA 信息 ==="
sudo -n dmidecode -t bios 2>/dev/null | grep -E 'Vendor|Version|Release' | head -3
sudo -n dmidecode -t memory 2>/dev/null | grep -E 'Size:|Speed:|Type:' | head -8
echo "=== C. svm/umc 相关 dmesg ==="
sudo -n dmesg 2>/dev/null | grep -iE 'svm|uma|carveout|VRAM' | head -8
echo "=== D. mem_info_vram_total 三站对照确认 ==="
cat /sys/class/drm/card1/device/mem_info_vram_total 2>/dev/null | xargs echo 'C vram_total='