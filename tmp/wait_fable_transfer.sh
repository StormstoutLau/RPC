#!/bin/bash
# 等待 B->A fable scp 完成
SRC=/home/scott-lau/.lmstudio/models/autotrust/gpt-oss-120b-Fable-5-Distilled-GGUF/gpt-oss-120b-Fable-5-Distilled-Q5_0.gguf
DST_HOST=scott-lau@scott-lau-NEX.local
D=/home/scott-lau/.lmstudio/models/autotrust/gpt-oss-120b-Fable-5-Distilled-GGUF/gpt-oss-120b-Fable-5-Distilled-Q5_0.gguf
SIZE=$(stat -c%s "$SRC")
for i in $(seq 1 300); do
  SZ=$(ssh -o ConnectTimeout=6 "$DST_HOST" "stat -c%s '$D' 2>/dev/null || echo 0")
  PCT=$(( SZ * 100 / SIZE ))
  echo "[${i}x15s] ${SZ} / ${SIZE} bytes = ${PCT}%"
  if [ "$SZ" -ge "$SIZE" ]; then echo "TRANSFER_DONE"; break; fi
  sleep 15
done