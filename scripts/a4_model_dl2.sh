#!/bin/bash
# a4_model_dl2.sh — A4: 模型下载 v2 (标准下载器, 不用 hf_transfer — 其在 mirror 断连时会卡死)
# 用法: bash a4_model_dl2.sh <local_dir>
set -x
DIR=${1:?usage: a4_model_dl2.sh <local_dir>}
mkdir -p "$DIR"
export HF_ENDPOINT=https://hf-mirror.com
unset HF_HUB_ENABLE_HF_TRANSFER
export HF_HUB_DOWNLOAD_TIMEOUT=60
HF=$(command -v hf || echo "$HOME/.local/bin/hf")
pkill -f 'hf downloa[d]' 2>/dev/null; sleep 1
nohup "$HF" download ayysasha/MiniMax-M2.7-AWQ-G32-STRIX-2H \
  --local-dir "$DIR" > "$DIR/hf_download2.log" 2>&1 &
echo "MODEL_DL_PID=$! LOG=$DIR/hf_download2.log"
