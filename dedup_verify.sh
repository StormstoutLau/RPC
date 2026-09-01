#!/bin/bash
# dedup_verify.sh — B 站: 验证 /data/models 收编文件 vs .lmstudio 源的重复关系
# 方法: 对 /data/models/gguf 下每个 gguf, 按文件名在 .lmstudio 全树找同名文件,
#       size 相等则比 md5 首尾 8MB (大文件快速指纹), 全同 = 确认重复
echo "=== 逐对验证 (size+首尾块 md5) ==="
TOTAL_DUP=0
while IFS=$'\t' read -r size path; do
  name=$(basename "$path")
  # 在 .lmstudio 找同名
  src=$(sudo find /home/scott-lau/.lmstudio -name "$name" -not -path "*/junctions/*" 2>/dev/null | head -1)
  [ -z "$src" ] && continue
  srcsize=$(stat -c%s "$src" 2>/dev/null)
  [ "$srcsize" != "$size" ] && { echo "SIZE_DIFF $name"; continue; }
  # 首尾 8MB md5
  h1=$(head -c 8388608 "$path" | md5sum | cut -d' ' -f1)
  h2=$(head -c 8388608 "$src" | md5sum | cut -d' ' -f1)
  t1=$(tail -c 8388608 "$path" | md5sum | cut -d' ' -f1)
  t2=$(tail -c 8388608 "$src" | md5sum | cut -d' ' -f1)
  if [ "$h1" = "$h2" ] && [ "$t1" = "$t2" ]; then
    gb=$((size/1073741824))
    TOTAL_DUP=$((TOTAL_DUP+size))
    echo "DUP ${gb}G  $name"
    echo "     src: $src"
  else
    echo "HASH_DIFF $name (size 同但内容异!)"
  fi
done < <(sudo find /data/models -name "*.gguf" -type f -printf "%s\t%p\n" 2>/dev/null | sort -rn | head -40)
echo
echo "=== 确认重复总量: $((TOTAL_DUP/1073741824)) G ==="