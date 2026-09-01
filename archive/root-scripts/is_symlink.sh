#!/bin/bash
# is_symlink.sh — /data/models/gguf 各属主目录是软链还是真目录
echo "=== gguf 属主层 ==="
ls -la /data/models/gguf/
echo
echo "=== 抽查 GLM 目录内容 (软链目标) ==="
ls -la /data/models/gguf/unsloth/ 2>/dev/null | head -4
echo
echo "=== 物理占用复测: du 不跟软链 (-x 不含外挂) vs 跟随 (-L) ==="
sudo du -sh /data/models 2>/dev/null
sudo du -shL /data/models 2>/dev/null
echo
echo "=== /data/models/gguf 下真文件 (非软链) 的物理量 ==="
sudo find /data/models/gguf -type f -name "*.gguf" -printf "%s\n" 2>/dev/null | awk '{s+=$1} END {printf "真文件: %.0fG\n", s/1073741824}'
sudo find /data/models/gguf -type l 2>/dev/null | wc -l | xargs echo "软链数:"
echo
echo "=== .lmstudio 内部: junctions? ==="
ls -la /home/scott-lau/.lmstudio/ 2>/dev/null | head -6
ls -la /home/scott-lau/.lmstudio/models/ 2>/dev/null | head -5