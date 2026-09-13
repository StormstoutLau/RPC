#!/usr/bin/env bash
# check_llama_version.sh — 三站 A/B/C llama.cpp 引擎版本一致性巡检
# 依据: spec/vulkan-version-control/IMPLEMENTATION.md §4.3（由 IMPl 单/双机版扩展为三站）
# 用法: bash check_llama_version.sh [--deep]
# 退出: 0 一致 / 1 不一致 / 2 SSH 不可达
# 指纹: <symlink 目标>|<version>|<commit>|<md5 全量自校验通过数>
set -uo pipefail

HOSTS=(
  "scott-lau@scott-lau-GTR-Pro.local"   # B (master, GTR-Pro)
  "scott-lau@scott-lau-NEX.local"       # A (NEX)
  "scott-lau@192.168.1.24"              # C (seaviv, WiFi 动态 IP)
)
DEEP=false
[[ "${1:-}" == "--deep" ]] && DEEP=true

declare -A FP
SSH_OPTS="-o ConnectTimeout=8 -o BatchMode=yes"

for h in "${HOSTS[@]}"; do
  fp=$(ssh $SSH_OPTS "$h" '
    D=/opt/llama.cpp
    L=$(readlink "$D" 2>/dev/null || echo "NO_SYMLINK")
    M=$(readlink -f "$D")/MANIFEST
    V=$(grep "^version" "$M" 2>/dev/null | cut -d= -f2 | tr -d " " || echo "NO_MANIFEST")
    C=$(grep "^commit" "$M" 2>/dev/null | cut -d= -f2 | tr -d " " || echo "?")
    R=$(grep "^rpc_protocol" "$M" 2>/dev/null | cut -d= -f2 | tr -d " " || echo "?")
    MD=$(cd "$(readlink -f "$D")" 2>/dev/null && tail -n +10 MANIFEST 2>/dev/null | md5sum -c 2>&1 | grep -c "成功" || echo 0)
    echo "$L|$V|$C|$R|md5ok=$MD"
  ' 2>/dev/null)
  if [[ -z "$fp" ]]; then echo "❌ $h SSH 不可达"; exit 2; fi
  FP[$h]="$fp"
  echo "$h → $fp"
done

# 指纹比对（忽略 md5ok 数值差异导致的误报，仅比 symlink/version/commit/rpc 四段）
declare -A KEY
for h in "${HOSTS[@]}"; do
  KEY[$h]=$(echo "${FP[$h]}" | cut -d'|' -f1-4)
done
base="${KEY[${HOSTS[0]}]}"
ok=true
for h in "${HOSTS[@]}"; do
  if [[ "${KEY[$h]}" != "$base" ]]; then
    echo "❌ 不一致: $h = ${KEY[$h]} vs base = $base"
    ok=false
  fi
done
$ok || exit 1
echo "✅ 三站指纹一致: $base"

# --deep 全量 MD5 比对
if $DEEP; then
  echo "== 深度模式: 三站 md5 集合比对 =="
  declare -A HASH
  for h in "${HOSTS[@]}"; do
    hostk=$(echo "$h" | md5sum | cut -c1-8)
    ssh $SSH_OPTS "$h" 'cd /opt/llama.cpp && md5sum llama-* ggml-rpc-server libggml*.so* libllama*.so* libmtmd*.so* 2>/dev/null | sort' > "/tmp/md5_${hostk}.txt" 2>/dev/null
    HASH[$h]=$(md5sum "/tmp/md5_${hostk}.txt" | cut -d' ' -f1)
    echo "$h md5集合指纹: ${HASH[$h]} ($(wc -l < /tmp/md5_${hostk}.txt) 文件)"
  done
  mismatch=false
  for h in "${HOSTS[@]:1}"; do
    if [[ "${HASH[$h]}" != "${HASH[${HOSTS[0]}]}" ]]; then
      echo "❌ $h 与 ${HOSTS[0]} 文件集不一致"
      diff <(sort /tmp/md5_$(echo "${HOSTS[0]}" | md5sum | cut -c1-8).txt) <(sort /tmp/md5_$(echo "$h" | md5sum | cut -c1-8).txt) | head -10
      mismatch=true
    fi
  done
  $mismatch && exit 1
  echo "✅ 三站文件集 md5 完全一致"
fi

exit 0