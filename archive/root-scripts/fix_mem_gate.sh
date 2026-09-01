#!/bin/bash
# load-mem-gate v1.1 — 修显示单位 (MB→G); wait-gtt-release 同步修
set -u
exec 2>&1

sudo tee /usr/local/bin/load-mem-gate >/dev/null <<'EOF'
#!/bin/bash
# load-mem-gate <需要GB> — 加载模型前调用: MemAvailable 不足则等待/拒绝
# 返回 0=可加载, 1=超时拒绝; 单位: AVAIL 为 MB, 显示时 /1024 为 G
NEED_MB=$(( ${1:?用法: load-mem-gate <需要GB>} * 1024 ))
SAFETY_MB=$(( 12 * 1024 ))
WAITED=0
while true; do
  AVAIL=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ $((AVAIL - NEED_MB)) -ge $SAFETY_MB ]; then
    echo "[mem-gate] OK: MemAvailable $((AVAIL/1024))G >= ${1}G + 12G 垫"
    exit 0
  fi
  if [ $WAITED -ge 60 ]; then
    echo "[mem-gate] REJECT: 60s 后 MemAvailable 仍 $((AVAIL/1024))G < ${1}G+12G — 先 infer-unload 或 GTT 未回收" >&2
    exit 1
  fi
  echo "[mem-gate] WAIT: MemAvailable $((AVAIL/1024))G 不足 (${1}G+12G), 等 5s (${WAITED}s/60s)..."
  sleep 5; WAITED=$((WAITED+5))
done
EOF
sudo chmod 755 /usr/local/bin/load-mem-gate

sudo tee /usr/local/bin/wait-gtt-release >/dev/null <<'EOF'
#!/bin/bash
# wait-gtt-release — kill llama-server 后轮询等 GTT 回收 (替代 sleep 定值)
# 机理: GTT 释放是异步的, 实测 30-90s; sleep 8 曾致双模型叠加 OOM (2026-09-01)
for i in $(seq 1 36); do
  AVAIL=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ "$AVAIL" -ge 102400 ]; then
    echo "[gtt-wait] OK: MemAvailable $((AVAIL/1024))G (${i}x5s) — GTT 已回收"
    exit 0
  fi
  sleep 5
done
echo "[gtt-wait] TIMEOUT 180s: MemAvailable $((AVAIL/1024))G — 有进程残留, pgrep llama-server 检查" >&2
exit 1
EOF
sudo chmod 755 /usr/local/bin/wait-gtt-release

echo "=== 验证 ==="
load-mem-gate 70
load-mem-gate 200 && echo "!! 不应通过" || echo "(200G 正确拒绝)"
wait-gtt-release
echo DONE_V11
