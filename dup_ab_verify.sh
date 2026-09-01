#!/bin/bash
# dup_ab_verify.sh — 站间重复精确校验 (A 站 16 repo vs B 站三源)
# 逻辑: A 站每个 GGUF (repo/file/size) 在 B 站 .lmstudio + /data/models/gguf(含软链解析) 找同名文件
# 输出: 逐文件 VERDICT (DUP=同文件同大小 / FORM=repo在B但文件形态不同 / AONLY=B无)

A="scott-lau@10.10.10.1"

# B 站三源合一的 GGUF 清单 (真实路径+大小; -L 解析软链)
find -L /data/models/gguf -name "*.gguf" -printf "%s\t%f\n" 2>/dev/null | sort -u > /tmp/b_gguf_all.txt
find ~/.lmstudio/models -name "*.gguf" -printf "%s\t%f\n" 2>/dev/null | sort -u >> /tmp/b_gguf_all.txt
sort -u /tmp/b_gguf_all.txt -o /tmp/b_gguf_all.txt
echo "B 站 GGUF 唯一文件数: $(wc -l < /tmp/b_gguf_all.txt)"
echo

# A 站 GGUF 清单 (repo|file|size)
ssh -o ConnectTimeout=10 $A 'find ~/.lmstudio/models -name "*.gguf" -printf "%s\t%f\t%h\n" 2>/dev/null' > /tmp/a_gguf.txt
echo "A 站 GGUF 文件数: $(wc -l < /tmp/a_gguf.txt)"
echo
echo "=== 逐文件判定 (DUP 同名同大小 / MISS B无同名 / SIZE 同名不同大小!) ==="
while IFS=$'\t' read -r size fname dir; do
  repo=$(echo "$dir" | sed 's|.*/models/||')
  # B 侧查同名文件
  bmatch=$(grep -P "\t${fname}$" /tmp/b_gguf_all.txt | head -1)
  if [ -z "$bmatch" ]; then
    verdict="MISS"
    binfo="-"
  else
    bsize=$(echo "$bmatch" | cut -f1)
    if [ "$bsize" = "$size" ]; then verdict="DUP"; binfo="B有同大小"
    else verdict="SIZE-MISMATCH"; binfo="B=$bsize A=$size"; fi
  fi
  printf "%-10s %-60s %8.1fG  %s\n" "$verdict" "$repo/$fname" "$(echo "$size/1073741824" | bc -l)" "$binfo"
done < /tmp/a_gguf.txt | sort
echo
echo "=== 汇总 ==="
echo "A 站总 GGUF 体积: $(awk -F'\t' '{s+=$1} END {printf "%.0fG", s/1073741824}' /tmp/a_gguf.txt)"
DUPG=$(grep -v unsloth /tmp/a_gguf.txt | awk -F'\t' '{s+=$1} END {print s}')
echo "(去 unsloth/GLM 后, 即可对 B 校验的部分)"
