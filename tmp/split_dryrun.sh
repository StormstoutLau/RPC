#!/bin/bash
# 146G MXFP4 拆分 dry-run 计划（3 片）
MODEL=/data/models/gguf/lmstudio-community/DeepSeek-V4-Flash-0731-GGUF/DeepSeek-V4-Flash-0731-MXFP4.gguf
OUT=/data/models/gguf/lmstudio-community/DeepSeek-V4-Flash-0731-GGUF/v4f-split/
mkdir -p "$OUT"
echo "== dry-run: 3 片 (split-max-tensors 默认 128 观察) =="
/opt/llama.cpp/llama-gguf-split --split --dry-run --split-max-tensors 128 "$MODEL" "$OUT"split 2>&1 | head -30
echo
echo "== dry-run: 按 size 50G 分 =="
/opt/llama.cpp/llama-gguf-split --split --dry-run --split-max-size 50G "$MODEL" "$OUT"split2 2>&1 | head -30