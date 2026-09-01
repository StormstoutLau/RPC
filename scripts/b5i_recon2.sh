#!/bin/bash
# b5i_recon2.sh — B5i 侦察 v2: 跟随软链枚举
echo "===== $(hostname -s) /data/models 侦察 v2 @ $(date '+%F %T') ====="
echo "--- [1] GGUF repo 列表 (含软链) ---"
find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sort | while read -r d; do
  N=$(find -L "$d" -name '*.gguf' 2>/dev/null | wc -l)
  SZ=$(du -sLh "$d" 2>/dev/null | cut -f1)
  echo "  ${SZ}  ${N}gguf  $d"
done
echo ""
echo "--- [2] GGUF 文件级 (多量化 repo 展开, 只列 >1G 的主权重) ---"
find -L /data/models/gguf -name '*.gguf' -size +1G 2>/dev/null | while read -r f; do
  SZ=$(du -hL "$f" 2>/dev/null | cut -f1)
  echo "  ${SZ}  $(echo $f | sed 's|/data/models/gguf/||')"
done
echo ""
echo "--- [3] 小文件 gguf (<1G, mmproj/tokenizer 等, 排除用) ---"
find -L /data/models/gguf -name '*.gguf' -size -1G 2>/dev/null | head -5
