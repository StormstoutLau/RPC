#!/bin/bash
# B 站对照: 同命令加载 gpt-oss HIP (若 B 有模型)
set +e
MODEL=/data/models/gguf/lmstudio-community/gpt-oss-120b-GGUF/gpt-oss-120b-MXFP4.gguf
echo "=== 0. B 模型是否存在 ==="
ls -la "$MODEL" 2>/dev/null || { echo 'B 无此模型，尝试其他路径'; find /data/models -maxdepth 4 -name '*gpt-oss*'.gguf 2>/dev/null | head -5; }
echo "=== 1. load-gate ==="
bash /tmp/load-gate 60 || { echo GATE FAIL; exit 1; }
echo "=== 2. 启动 ==="
pkill -9 -f 'gpt-oss' 2>/dev/null; sleep 2
setsid nohup ~/.unsloth/llama.cpp/build/bin/llama-server -m "$MODEL" --port 18081 --device ROCm0 -ngl -1 --fit off --load-mode none -c 4096 -t 16 --flash-attn on > /tmp/b_gpt_hip.log 2>&1 &
echo "pid=$!"
sleep 55
echo "=== 3. 日志尾 ==="
tail -12 /tmp/b_gpt_hip.log
echo "=== 4. 端口 ==="
ss -tlnp 2>/dev/null | grep 18081 || echo 'not yet'
echo "=== 5. 进程 ==="
ps -o pid,stat,%cpu,time,rss -p $! 2>/dev/null
echo "=== 6. 新增 fault ==="
sudo -n dmesg 2>/dev/null | tail -3 | grep -i fault || echo '(无新 fault)'
echo "=== 7. 内存 ==="
free -g | head -2