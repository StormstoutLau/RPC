#!/bin/bash
# dl_ms_enhanced.sh — ModelScope 两模型 UD-IQ4_XS 全量下载 (增强版, 持久部署 ~/bin)
# 特性:
#  1. setsid 独立驻留 (SSH 断开/主控不查仍继续)
#  2. wget -c 断点续传 (断电/中断后重跑幂等续传)
#  3. 每分片完成后校验 size==目标, 失败自动重试
#  4. 分片自动串行
#  5. 进度状态文件 (~/dl-ms-status.txt + ~/dl-ms-progress.txt)
# 用法: bash ~/bin/dl_ms_enhanced.sh  (幂等续传)
set -u

MS=https://modelscope.cn/models/unsloth
M_ROOT=~/.lmstudio/models/lmstudio-community
STATUS=~/dl-ms-status.txt
mkdir -p "$M_ROOT/MiniMax-M2.7-GGUF/UD-IQ4_XS"
mkdir -p "$M_ROOT/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS"

# 目标分片:  repo|file|expected_size
SHARDS=(
  "Qwen3.8-Flash-Next-GGUF|Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf|10946624"
  "Qwen3.8-Flash-Next-GGUF|Qwen3.8-Flash-Next-UD-IQ4_XS-00002-of-00003.gguf|49835229856"
  "Qwen3.8-Flash-Next-GGUF|Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf|43836407744"
  "MiniMax-M2.7-GGUF|MiniMax-M2.7-UD-IQ4_XS-00001-of-00004.gguf|8237824"
  "MiniMax-M2.7-GGUF|MiniMax-M2.7-UD-IQ4_XS-00002-of-00004.gguf|49638761280"
  "MiniMax-M2.7-GGUF|MiniMax-M2.7-UD-IQ4_XS-00003-of-00004.gguf|49598675552"
  "MiniMax-M2.7-GGUF|MiniMax-M2.7-UD-IQ4_XS-00004-of-00004.gguf|9168106656"
)

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$STATUS"; }

# 防重复驻留: PID 文件方式 (pgrep 会匹配自身, 不可用)
PIDF=~/dl-ms.pid
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF" 2>/dev/null)" 2>/dev/null; then
  echo "已有实例在跑 (pid=$(cat "$PIDF")), 退出"; exit 0
fi
echo "$$" > "$PIDF"

echo "=== ModelScope 下载状态 $(date '+%F %T') (重启恢复) ===" >> "$STATUS"
log "进程 pid=$$ (setsid 独立驻留, ~/bin 持久)"

total_done=0; total_all=0
for s in "${SHARDS[@]}"; do
  repo="${s%%|*}"; rest="${s#*|}"
  file="${rest%%|*}"; expect="${rest##*|}"
  out="$M_ROOT/$repo/UD-IQ4_XS/$file"
  total_all=$((total_all + expect))

  for attempt in 1 2 3 4 5; do
    sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
    if [ "$sz" -ge "$expect" ]; then
      log "SKIP $repo/$file 已完整 (size=$sz)"
      total_done=$((total_done + sz))
      break
    fi
    log "START[$attempt] $repo/$file  cur=${sz} 目标=${expect} ($(( (sz*100)/expect ))%)"
    # 进度: 独立 PROGRESS 文件实时覆盖
    (
      while kill -0 "$$" 2>/dev/null; do
        now=$(stat -c%s "$out" 2>/dev/null || echo 0)
        pct=0; [ "$expect" -gt 0 ] && pct=$(( (now*100)/expect ))
        mb=$(( now/1048576 ))
        echo "PROGRESS $file  now=${mb}MB  pct=${pct}%  目标=$((expect/1048576))MB" > ~/dl-ms-progress.txt
        sleep 15
      done
    ) &
    PROG_PID=$!

    wget -c -q --show-progress=off --timeout=180 --tries=20 \
      "$MS/$repo/resolve/master/UD-IQ4_XS/$file" -O "$out" 2>/dev/null
    rc=$?
    kill "$PROG_PID" 2>/dev/null

    sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
    if [ "$rc" -eq 0 ] && [ "$sz" -ge "$expect" ]; then
      log "DONE $repo/$file size=$sz (目标 $expect) ✓"
      total_done=$((total_done + sz))
      break
    else
      log "RETRY[$attempt] $repo/$file rc=$rc size=$sz (目标 $expect) — 续传"
      sleep 5
    fi
  done
done

grep -q "MAIN_DONE" "$STATUS" 2>/dev/null || \
  { echo "MAIN_DONE 全部完成 $(date '+%F %T')" >> "$STATUS"; }
rm -f ~/dl-ms-progress.txt
echo "=== DONE ==="
ls -la "$M_ROOT/Qwen3.8-Flash-Next-GGUF/UD-IQ4_XS/" "$M_ROOT/MiniMax-M2.7-GGUF/UD-IQ4_XS/"