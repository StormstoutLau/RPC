#!/bin/bash
# B5q §4: b5k_sync --go --verify 双端校验 (CHECKLIST §4; 目标: A-only 最小模型 Nemotron-4B 2.7G)
set -uo pipefail

echo '--- 1. 同步 + 校验 (走管理网; 2.7G 预计 1-2min) ---'
START=$(date +%s)
bash ~/scripts/b5k_sync.sh --go --verify 2>&1 | tail -25
RC=$?
ELAPSED=$(( $(date +%s) - START ))
echo "=== b5k rc=${RC} elapsed=${ELAPSED}s ==="

echo '--- 2. manifest 存在性 + 兼容 sha256sum -c ---'
M=/data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Nano-4B-GGUF/.sha256
ls -la "$M" 2>/dev/null && wc -l "$M"
cd /data/models/gguf/lmstudio-community/NVIDIA-Nemotron-3-Nano-4B-GGUF && sha256sum -c .sha256

echo '--- 3. 传输速度回填素材 ---'
SZ=2706  # MB (du -smL A 站)
echo "size=${SZ}MB elapsed=${ELAPSED}s -> $((SZ/ELAPSED>0 ? SZ/ELAPSED : 1)) MB/s (含校验)"
