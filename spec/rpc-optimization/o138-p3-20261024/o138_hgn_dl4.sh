#!/bin/bash
# O-138 v2 .hgn 下载器 v4
# 三次迭代的教训：
#   v1（16 段 ×4GiB，>> 追加 + --retry-all-errors）⇒ part 超长（重试/302 时整段重复追加）
#   v2（16 段，tmp+校验）⇒ 安全但块太大，单块失败代价高
#   v3（256MiB 块 × 16 并发 ×2 文件）⇒ 32+ 连接被镜像限流到每连 30KiB/s，且僵死连接堆积成 63 个
#   v4 = 64MiB 块 · **每文件 6 并发** · `--speed-time 25 --speed-limit 300000` 杀僵死 · 每块 tmp 校验 · sha256 终验
# 用法: bash o138_hgn_dl4.sh <file> <total> <sha256> [conc]
set -u
REPO="peonist-ai/halogen-qwen3.8-flash-next"
DEST="/data/models/hgn/peonist-ai/halogen-qwen3.8-flash-next"
F="$1"; TOTAL="$2"; SHA="$3"; CONC="${4:-6}"
CHUNK=67108864
URL="https://hf-mirror.com/$REPO/resolve/main/$F"
mkdir -p "$DEST"
NP=$(( (TOTAL + CHUNK - 1) / CHUNK ))
echo "[$(date +%H:%M:%S)] START $F chunks=$NP chunk=64MiB conc=$CONC"

fetch_one() {
  i="$1"; a=$((i*CHUNK)); b=$((a+CHUNK-1)); [ "$b" -ge "$TOTAL" ] && b=$((TOTAL-1))
  want=$((b-a+1)); part="$DEST/$F.part$(printf %03d $i)"; tmp="$part.tmp"
  [ "$(stat -c %s "$part" 2>/dev/null || echo 0)" -eq "$want" ] && return 0
  t=0
  while [ "$t" -lt 25 ]; do
    rm -f "$tmp"
    curl -sL --fail --max-time 600 --speed-time 25 --speed-limit 300000 -r "$a-$b" "$URL" -o "$tmp"
    [ "$(stat -c %s "$tmp" 2>/dev/null || echo 0)" -eq "$want" ] && { mv -f "$tmp" "$part"; return 0; }
    rm -f "$tmp"; t=$((t+1)); sleep 3
  done
  echo "GIVEUP chunk$i"; return 1
}

i=0
while [ "$i" -lt "$NP" ]; do
  fetch_one "$i" &
  i=$((i+1))
  while [ "$(jobs -rp | wc -l)" -ge "$CONC" ]; do sleep 1; done
done
wait
echo "[$(date +%H:%M:%S)] chunks done: $(ls "$DEST"/$F.part* 2>/dev/null | wc -l)/$NP"
BAD=0
for i in $(seq 0 $((NP-1))); do
  a=$((i*CHUNK)); b=$((a+CHUNK-1)); [ "$b" -ge "$TOTAL" ] && b=$((TOTAL-1))
  want=$((b-a+1)); part="$DEST/$F.part$(printf %03d $i)"
  [ "$(stat -c %s "$part" 2>/dev/null || echo 0)" -ne "$want" ] && BAD=1
done
if [ "$BAD" -eq 0 ]; then
  cat $(for i in $(seq 0 $((NP-1))); do printf '%s ' "$DEST/$F.part$(printf %03d $i)"; done) > "$DEST/$F.merging"
  echo "[$(date +%H:%M:%S)] merged; sha256 verifying"
  ACT=$(sha256sum "$DEST/$F.merging" | cut -d' ' -f1)
  if [ "$ACT" = "$SHA" ]; then
    mv "$DEST/$F.merging" "$DEST/$F"; rm -f "$DEST/$F".part*
    echo "OK $F"
  else
    echo "SHA_MISMATCH act=$ACT"; rm -f "$DEST/$F.merging"
  fi
else
  echo "FAIL incomplete; rerun to resume"
fi
