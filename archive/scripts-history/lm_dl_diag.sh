#!/bin/bash
# lm_dl_diag.sh — LM Studio 下载瓶颈诊断: HF 直连 vs hf-mirror 镜像 (两站通用)
# 30MB Range 请求, 测真实吞吐; 只读, 零风险
set -u
URL_PATH="Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
echo "=== $(hostname -s) @ $(date '+%H:%M:%S') ==="
for host in https://huggingface.co https://hf-mirror.com https://search.lmstudio.ai; do
  printf '%-28s' "$host:"
  curl -sL -o /dev/null -w "speed: %{speed_download} B/s | http: %{http_code} | got: %{size_download}B | time: %{time_total}s\n" \
    --max-time 20 -r 0-30000000 "$host/$URL_PATH" || echo "FAILED"
done
