#!/bin/bash
# b5m1_recon.sh — B5m1 资产盘点: 只读侦察 (两站通用)
# 覆盖: LM Studio 模型目录 (新旧两代) + 统一模型根 + 磁盘余量 + 下载任务 json
# 用法: 经主控站 scp 到 /tmp 后 ssh 执行: bash /tmp/b5m1_recon.sh
# 只读, 不动任何文件

DIRS=(
  "$HOME/.lmstudio/models"
  "$HOME/.cache/lm-studio/models"
  "/data/models"
  "$HOME/models"
  "/data/rpccache"
)

echo "=== HOST ==="
hostname

echo "=== DF (根 + /data) ==="
df -h / /data 2>/dev/null | awk '!seen[$1]++'

echo "=== MODEL DIRS (存在性 + 总量) ==="
for d in "${DIRS[@]}"; do
  if [ -d "$d" ]; then
    # 目录总大小 (sudo 不可用则容忍权限洞)
    sz=$(du -sh "$d" 2>/dev/null | cut -f1)
    n=$(find "$d" -type f 2>/dev/null | wc -l)
    echo "EXISTS|$d|du=$sz|files=$n"
  else
    echo "ABSENT|$d"
  fi
done

echo "=== LARGE FILES (>100MB) : bytes|path ==="
for d in "${DIRS[@]}"; do
  [ -d "$d" ] || continue
  find "$d" -type f -size +100M -printf '%s|%p\n' 2>/dev/null | sort -t'|' -k2
done

echo "=== MEDIUM FILES (1MB-100MB) 汇总: 每目录 count+bytes ==="
for d in "${DIRS[@]}"; do
  [ -d "$d" ] || continue
  find "$d" -type f -size +1M -size -100M -printf '%s\n' 2>/dev/null \
    | awk -v dir="$d" '{t+=$1; n++} END{printf "MED|%s|count=%d|bytes=%d\n", dir, n, t+0}'
done

echo "=== LM STUDIO 下载任务 json ==="
J="$HOME/.lmstudio/.internal/download-jobs-info.json"
if [ -f "$J" ]; then
  JN=$(python3 -c "import json;d=json.load(open('$J'));print(len(d.get('jobs',d) if isinstance(d,dict) else d))" 2>/dev/null || echo parse_fail)
  echo "JOBS_JSON|exists|jobs=$JN"
else
  echo "JOBS_JSON|absent"
fi

echo "=== B5M1_RECON_DONE ==="
