#!/bin/bash
# 读取 nemotron 元数据 (KV 预算关键字段)
set +e
M=/data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF/NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M-00001-of-00003.gguf
echo "=== llama-gguf -r 输出 (关键字段) ==="
/opt/llama.cpp/llama-gguf r "$M" 2>/dev/null | grep -iE 'block_count|head_count|embedding|attention|expert|layer|kv|rope|arch' | head -25
echo ""
echo "=== 若 -r 失败, 尝试直接读 KV 段 ==="
/opt/llama.cpp/llama-gguf --help 2>&1 | head -15
echo ""
echo "=== 文件大小确认 (三片) ==="
ls -la /data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Super-120B-A12B-GGUF/*.gguf 2>/dev/null | cut -c1-80
echo "DONE"