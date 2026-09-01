#!/bin/bash
# b5j_recon.sh — B5j 分片模型侦察: 分片清单 / llama-gguf-split 工具 / 磁盘空间
echo "===== $(hostname -s) B5j 分片侦察 @ $(date '+%F %T') ====="

echo "--- [1] llama-gguf-split 工具 ---"
ls -la /opt/llama.cpp/llama-gguf-split 2>/dev/null && /opt/llama.cpp/llama-gguf-split --help 2>&1 | head -8 || echo "工具不存在!"

echo ""
echo "--- [2] 分片模型清单 (repo 含多分片 gguf) ---"
find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | while read -r d; do
  # 统计分片式 gguf (xxx-00001-of-0000N.gguf)
  PARTS=$(find -L "$d" -name '*-00001-of-*.gguf' 2>/dev/null | wc -l)
  if [ "$PARTS" -ge 1 ]; then
    N=$(find -L "$d" -name '*.gguf' -size +1G 2>/dev/null | wc -l)
    SZ=$(du -shL "$d" 2>/dev/null | cut -f1)
    FIRST=$(find -L "$d" -name '*-00001-of-*.gguf' | head -1 | xargs basename 2>/dev/null)
    # 合并目标名: 去掉 -0000N-of-0000M 后缀
    MERGED=$(echo "$FIRST" | sed 's/-0000[0-9]*-of-0000[0-9]*\.gguf/.gguf/')
    echo "  ${SZ}  ${N}分片  $(basename $d)  →  ${MERGED}"
  fi
done

echo ""
echo "--- [3] 磁盘空间 ---"
df -h / | tail -1
