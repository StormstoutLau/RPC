#!/bin/bash
# 查 repo 真实结构: 软链 or 目录 + 物理库 + 大小 (B 站)
set -u
REPO=/data/models/gguf/mradermacher/Qwen3.5-122B-A10B-Claude-Distill-v2-i1-GGUF
echo "=== repo 本体 ==="
ls -la /data/models/gguf/mradermacher/ | grep -i claude
echo "=== repo 内容 ==="
ls -la $REPO/ 2>/dev/null | head -8
echo "=== 真实大小 (跟随软链) ==="
sudo du -smL $REPO 2>/dev/null
echo "=== .lmstudio 物理库搜索 (修正 find) ==="
sudo find /home/scott-lau/.lmstudio/models -maxdepth 2 -type d -iname "*Qwen3.5-122B*" 2>/dev/null
echo "=== 分片文件与大小 ==="
sudo find $REPO/ -name "*.gguf" -exec ls -la {} \; 2>/dev/null | awk '{printf "%.1fG\t%s\n", $5/1073741824, $NF}' | head -5
echo DONE
