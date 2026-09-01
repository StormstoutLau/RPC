#!/bin/bash
# check_llama_version.sh — A/B 两站 llama.cpp 版本一致性巡检
# 用法: bash check_llama_version.sh [--deep]
# 运行位置: 主控站 Git Bash（内部 ssh 两站）；
#           保底模式（DR-2）: scp 到 B 站后执行（B→A 免密实测可达）
# 退出码: 0 一致 / 1 不一致 / 2 SSH 不可达
set -uo pipefail
HOSTS=("scott-lau@scott-lau-NEX.local" "scott-lau@scott-lau-GTR-Pro.local")
DEEP=false
[[ "${1:-}" == "--deep" ]] && DEEP=true

declare -A FP
for h in "${HOSTS[@]}"; do
  fp=$(ssh -o ConnectTimeout=8 -o BatchMode=yes "$h" \
    'L=$(readlink /opt/llama.cpp 2>/dev/null || echo "NO_LINK");
     M=/opt/llama.cpp/MANIFEST;
     V=$(grep "^version" "$M" 2>/dev/null | head -1 | cut -d= -f2 | tr -d " ");
     C=$(grep "^commit" "$M" 2>/dev/null | head -1 | cut -d= -f2 | tr -d " ");
     echo "${L}|${V:-NO_MANIFEST}|${C:-?}"' 2>/dev/null)
  if [[ -z "${fp}" ]]; then
    echo "❌ $h SSH 不可达"
    exit 2
  fi
  FP[$h]="$fp"
  echo "$h → $fp"
done

a="${FP[${HOSTS[0]}]}"
b="${FP[${HOSTS[1]}]}"
if [[ "$a" != "$b" ]]; then
  echo "❌ 两站指纹不一致"
  echo "  A站: $a"
  echo "  B站: $b"
  exit 1
fi
echo "✅ 指纹一致: $a"

if $DEEP; then
  echo "--- 深度比对 (全量 MD5) ---"
  T1=$(mktemp); T2=$(mktemp)
  ssh -o BatchMode=yes "${HOSTS[0]}" 'cd /opt/llama.cpp && md5sum llama-* libggml*.so* libllama*.so* libmtmd.so* 2>/dev/null | sort' > "$T1" 2>/dev/null
  ssh -o BatchMode=yes "${HOSTS[1]}" 'cd /opt/llama.cpp && md5sum llama-* libggml*.so* libllama*.so* libmtmd.so* 2>/dev/null | sort' > "$T2" 2>/dev/null
  if diff -q "$T1" "$T2" > /dev/null; then
    echo "✅ 深度比对: 全部 $(wc -l < "$T1") 个文件 MD5 一致"
    rm -f "$T1" "$T2"
  else
    echo "❌ 深度比对差异:"
    diff "$T1" "$T2" || true
    rm -f "$T1" "$T2"
    exit 1
  fi
fi
exit 0
