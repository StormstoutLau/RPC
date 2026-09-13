#!/bin/bash
# 网络/下载工具预检脚本 (B 站执行, 可参数化 host)
set -u
HOST_ARG="${1:-scott-lau@scott-lau-GTR-Pro.local}"
echo "=== hf tooling ==="
which hf 2>/dev/null || echo "no hf cli"
python3 -c "import huggingface_hub; print('huggingface_hub', huggingface_hub.__version__)" 2>/dev/null || echo "no huggingface_hub"
echo "=== HF env ==="
env | grep -iE "HF_|huggingface" || echo "no hf env"
echo "=== HF dns ==="
timeout 10 getent hosts huggingface.co 2>/dev/null | head -2 || echo "dns fail"
echo "=== HF https (5s) ==="
timeout 8 curl -sI https://huggingface.co 2>&1 | head -3 || echo "curl fail"
echo "=== hf-mirror https (5s) ==="
timeout 8 curl -sI https://hf-mirror.com 2>&1 | head -3 || echo "mirror fail"
echo "=== disk ==="
df -h /data | tail -1
echo "=== mem ==="
free -g | head -2