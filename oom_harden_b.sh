#!/bin/bash
# OOM 加固 (2026-09-01 B 站 litellm 被 OOM 杀教训): 关键服务保护 + 标准内存门
set -u
exec 2>&1

echo "=== 1. litellm OOM 保护 (OOMScoreAdjust=-500, 优先杀别人) ==="
sudo mkdir -p /etc/systemd/system/litellm.service.d
sudo tee /etc/systemd/system/litellm.service.d/oom-protect.conf >/dev/null <<'EOF'
# 2026-09-01 OOM 事故加固: litellm 只占 337M 却被 global OOM 选中 (试验脚本双模型叠加峰值)
# -500 = 显著降低被 OOM killer 选中概率; 同时限制自身内存防失控
[Service]
OOMScoreAdjust=-500
MemoryHigh=2G
MemoryMax=4G
EOF
sudo systemctl daemon-reload
sudo systemctl restart litellm
sleep 3
systemctl is-active litellm && echo "litellm 重启 OK, OOM 保护就位"

echo ""
echo "=== 2. netconsole-listen 同样保护 (挂死取证通道不能先死) ==="
sudo mkdir -p /etc/systemd/system/netconsole-listen.service.d
sudo tee /etc/systemd/system/netconsole-listen.service.d/oom-protect.conf >/dev/null <<'EOF'
[Service]
OOMScoreAdjust=-800
EOF
sudo systemctl daemon-reload
sudo systemctl restart netconsole-listen
systemctl is-active netconsole-listen && echo "netconsole-listen OOM 保护就位"

echo ""
echo "=== 3. 标准加载内存门脚本 (load-mem-gate) ==="
sudo tee /usr/local/bin/load-mem-gate >/dev/null <<'EOF'
#!/bin/bash
# load-mem-gate <需要GB> — 加载模型前调用: MemAvailable 不足则等待/拒绝
# 用法: load-mem-gate 70  (要加载 70G 模型)
# 返回 0=可加载, 1=超时拒绝
NEED_MB=$(( ${1:?用法: load-mem-gate <需要GB>} * 1024 ))
SAFETY_MB=$(( 12 * 1024 ))   # 系统安全垫 12G (litellm/监控/bash + KV/buffer 余量)
WAITED=0
while true; do
  AVAIL=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  if [ $((AVAIL - NEED_MB)) -ge $SAFETY_MB ]; then
    echo "[mem-gate] OK: MemAvailable ${AVAIL}G >= ${1}G + 12G 垫"
    exit 0
  fi
  if [ $WAITED -ge 60 ]; then
    echo "[mem-gate] REJECT: 等待 60s 后 MemAvailable 仍 ${AVAIL}G < ${1}G+12G — 先 infer-unload 或 GTT 未回收" >&2
    exit 1
  fi
  echo "[mem-gate] WAIT: MemAvailable ${AVAIL}G 不足 (${1}G+12G), 等 5s (${WAITED}s/60s)..."
  sleep 5; WAITED=$((WAITED+5))
done
EOF
sudo chmod 755 /usr/local/bin/load-mem-gate
echo "测试: load-mem-gate 70 (当前空载应 OK)"
load-mem-gate 70
echo "测试: load-mem-gate 200 (应拒绝)"
load-mem-gate 200 || echo "(拒绝符合预期)"

echo ""
echo "=== 4. GTT 释放验证脚本 (wait-gtt-release, kill 实例后用) ==="
sudo tee /usr/local/bin/wait-gtt-release >/dev/null <<'EOF'
#!/bin/bash
# wait-gtt-release — kill llama-server 后轮询等 GTT 回收 (替代 sleep 定值)
# 机理: GTT 释放是异步的, 实测 30-90s; sleep 8 曾致双模型叠加 OOM (2026-09-01)
BASE=$(awk '/MemAvailable/ {print int($2/1024/1024)}' /proc/meminfo)
echo "[gtt-wait] 基线 MemAvailable ~${BASE}G, 轮询至 >=100G 或 180s 超时"
for i in $(seq 1 36); do
  AVAIL=$(awk '/MemAvailable/ {print int($2/1024/1024)}' /proc/meminfo)
  if [ "$AVAIL" -ge 100 ]; then
    echo "[gtt-wait] OK: ${AVAIL}G (${i}x5s) — GTT 已回收"
    exit 0
  fi
  sleep 5
done
echo "[gtt-wait] TIMEOUT 180s: MemAvailable ${AVAIL}G — 有进程残留, pgrep llama-server 检查" >&2
exit 1
EOF
sudo chmod 755 /usr/local/bin/wait-gtt-release
echo DONE_HARDEN
