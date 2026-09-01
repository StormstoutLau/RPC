#!/bin/bash
# B5q 集成验收 §1: 真实 bench 全流程 + 时长回填 (CHECKLIST §1)
set -uo pipefail
echo '--- 停 B 站生产实例 (bench 需独占 GTT; 验收后恢复) ---'
sudo systemctl stop llama-server@m27-q4ks
sleep 2
systemctl is-active llama-server@m27-q4ks || true

echo '--- B5q-2 真实 bench (热缓存, 计时) ---'
START=$(date +%s)
/usr/local/bin/b5_bench_cluster.sh --alias m27-q4ks
RC=$?
END=$(date +%s)
ELAPSED=$((END - START))
echo "=== bench rc=${RC} elapsed=${ELAPSED}s ($((ELAPSED/60))min$((ELAPSED%60))s) ==="

echo '--- 收尾验证 ---'
echo "A rpc-server@m27-q4ks: $(ssh 10.10.10.1 'systemctl is-active rpc-server@m27-q4ks')"
echo "--- bench 日志 ---"
ls -t /tmp/bench_cluster_m27-q4ks_*.log | head -1
tail -8 "$(ls -t /tmp/bench_cluster_m27-q4ks_*.log | head -1)"
