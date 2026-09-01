#!/bin/bash
# a4_model_dl.sh — A4: MiniMax-M2.7-AWQ-G32-STRIX-2H 模型下载 (hf-mirror, 后台)
# 用法: bash a4_model_dl.sh <local_dir>   (两站通用, 参数化模型目录)
set -x
DIR=${1:?usage: a4_model_dl.sh <local_dir>}
mkdir -p "$DIR"
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_ENABLE_HF_TRANSFER=1
HF=$(command -v hf || echo "$HOME/.local/bin/hf")
nohup "$HF" download ayysasha/MiniMax-M2.7-AWQ-G32-STRIX-2H \
  --local-dir "$DIR" > "$DIR/hf_download.log" 2>&1 &
echo "MODEL_DL_PID=$! LOG=$DIR/hf_download.log"
