#!/bin/bash
# a4_model_dl3.sh — A4: 模型下载 v3 (关键修复: HF_HUB_DISABLE_XET=1)
# 根因: huggingface_hub 1.29 默认 Xet 协议直连 cas-server.xethub.hf.co (绕过 mirror) -> 401 崩溃
# v1 (hf_transfer) 在 mirror 断连时 Rust 线程 hang; v3 走标准 CDN 路径 + timeout 重试
# 用法: bash a4_model_dl3.sh <local_dir>
set -x
DIR=${1:?usage: a4_model_dl3.sh <local_dir>}
mkdir -p "$DIR"
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1
unset HF_HUB_ENABLE_HF_TRANSFER
export HF_HUB_DOWNLOAD_TIMEOUT=60
HF=$(command -v hf || echo "$HOME/.local/bin/hf")
pkill -f 'hf downloa[d]' 2>/dev/null; sleep 1
nohup "$HF" download ayysasha/MiniMax-M2.7-AWQ-G32-STRIX-2H \
  --local-dir "$DIR" >> "$DIR/hf_download3.log" 2>&1 &
echo "MODEL_DL_PID=$! LOG=$DIR/hf_download3.log"
