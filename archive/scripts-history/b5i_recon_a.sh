#!/bin/bash
# b5i_recon_a.sh — B5i A 站 GGUF 枚举 + 两站差异
echo "===== $(hostname -s) A 站 /data/models/gguf @ $(date '+%F %T') ====="
find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sort | while read -r d; do
  N=$(find -L "$d" -name '*.gguf' -size +1G 2>/dev/null | wc -l)
  SZ=$(du -sLh "$d" 2>/dev/null | cut -f1)
  echo "  ${SZ}  ${N}gguf  $(echo $d | sed 's|/data/models/gguf/||')"
done
echo ""
echo "--- A 站 rpccache ---"
du -sh /data/rpccache/* 2>/dev/null
echo ""
df -h /data | tail -1
