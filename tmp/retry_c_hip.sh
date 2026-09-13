#!/bin/bash
# C 站 gpt-oss 重试: 默认 load-mode (mmap) + 观察
set +e
MODEL=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf
ENGINE=~/.unsloth/llama.cpp/build/bin/llama-server
LOG=/tmp/c_gpt_hip2.log
pkill -f 'llama-server.*gpt-oss-120b' 2>/dev/null
sleep 2
echo "=== 内存前 ==="
free -g | head -2
setsid nohup "$ENGINE" -m "$MODEL" --port 18087 --device ROCm0 -ngl -1 --fit off -c 2048 -t 4 --flash-attn on > "$LOG" 2>&1 &
echo "pid=$!"
for i in 1 2 3 4 5 6; do
  sleep 10
  echo "[$i] $(ps -o state,%cpu,rss -p $! 2>/dev/null | tail -1)"
  grep -c 'model loaded' "$LOG" 2>/dev/null | xargs echo "  loaded_cnt="
done
tail -4 "$LOG" | cut -c1-90
echo "DONE"