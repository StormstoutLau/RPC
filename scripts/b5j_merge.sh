#!/bin/bash
# b5j_merge.sh — B5j 合并分片 GGUF: 用法 bash b5j_merge.sh <repo目录名前缀|all> [--keep]
# llama-gguf-split --merge <首分片> <输出>
# 默认: 验证合并文件大小合理后删除原分片; --keep 保留分片
set -uo pipefail
TARGET="${1:?用法: b5j_merge.sh <repo前缀|all> [--keep]}"
KEEP="${2:-}"
SPLIT=/opt/llama.cpp/llama-gguf-split

log() { echo "[b5j-merge] $(date '+%H:%M:%S') $*"; }

merge_repo() {  # $1 = repo 目录 (软链路径)
  local REPO="$1"
  local FIRST=$(find -L "$REPO" -name '*-00001-of-*.gguf' 2>/dev/null | head -1)
  [ -z "$FIRST" ] && { log "跳过 (无分片): $REPO"; return 0; }
  local BASE=$(basename "$FIRST")
  local MERGED_NAME=$(echo "$BASE" | sed 's/-0000[0-9]*-of-0000[0-9]*\.gguf/.gguf/')
  local MERGED="${REPO}/${MERGED_NAME}"
  if [ -f "$MERGED" ]; then
    log "已存在合并文件, 跳过: $MERGED"
    return 0
  fi
  # 分片总大小 (排除 mmproj 等非分片文件)
  local PARTS_SZ=$(find -L "$REPO" -name '*-of-0000*.gguf' -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {print s+0}')
  local AVAIL=$(df --output=avail -B1 / | tail -1 | tr -d ' ')
  if [ "$AVAIL" -lt $(( PARTS_SZ + 10737418240 )) ]; then
    log "空间不足: 需 ${PARTS_SZ}B + 10G 余量, 可用 ${AVAIL}B — 跳过"
    return 1
  fi
  log "合并: $BASE → $MERGED_NAME (分片总 ${PARTS_SZ}B)"
  local T0=$(date +%s)
  if "$SPLIT" --merge "$FIRST" "$MERGED"; then
    local T1=$(date +%s)
    local M_SZ=$(stat -c%s "$MERGED")
    # 验证: 合并文件 ≥ 分片总大小 - 10MB (header 重建允许微小差异, 不应更小)
    if [ "$M_SZ" -ge $(( PARTS_SZ - 10485760 )) ]; then
      log "合并 OK: ${M_SZ}B (期望~${PARTS_SZ}B), 耗时 $((T1-T0))s"
      if [ "$KEEP" != "--keep" ]; then
        log "删原分片..."
        find -L "$REPO" -name '*-of-0000*.gguf' -delete
        log "分片已删, 回收 ${PARTS_SZ}B"
      fi
      return 0
    else
      log "大小异常: 合并 ${M_SZ}B vs 分片总 ${PARTS_SZ}B — 保留分片, 删合并文件排查"
      rm -f "$MERGED"
      return 1
    fi
  else
    log "合并命令失败 — 清理残留"
    rm -f "$MERGED"
    return 1
  fi
}

if [ "$TARGET" = "all" ]; then
  for REPO in $(find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sort); do
    find -L "$REPO" -name '*-00001-of-*.gguf' 2>/dev/null | grep -q . && merge_repo "$REPO"
  done
else
  REPO=$(find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | grep -i "$TARGET" | head -1)
  [ -z "$REPO" ] && { echo "ERROR: repo 未找到: $TARGET"; exit 1; }
  merge_repo "$REPO"
fi
log "完成"
