#!/bin/bash
# B5q 集成验收 §3: GGML_VK_PREFER_HOST_MEMORY drop-in 对照 (CHECKLIST §3)
set -uo pipefail
A="10.10.10.1"

echo '--- 1. drop-in 就位 (A 站, b5i 模板 unit 本体不改) ---'
ssh "$A" 'sudo mkdir -p /etc/systemd/system/rpc-server@.service.d && printf "%s\n" "[Service]" "Environment=GGML_VK_PREFER_HOST_MEMORY=1" | sudo tee /etc/systemd/system/rpc-server@.service.d/hostmem.conf'
ssh "$A" 'sudo systemctl daemon-reload'
echo '--- 2. drop-in 内容 + env 生效验证 ---'
ssh "$A" 'cat /etc/systemd/system/rpc-server@.service.d/hostmem.conf'
echo '--- 3. 停 rpc-server → 重跑 bench (restart 使 env 生效; rpc-nodes --start 自动拉起) ---'
/usr/local/bin/rpc-nodes --stop m27-q4ks
sleep 2
START=$(date +%s)
/usr/local/bin/b5_bench_cluster.sh --alias m27-q4ks
RC=$?
ELAPSED=$(( $(date +%s) - START ))
echo "=== +env bench rc=${RC} elapsed=${ELAPSED}s ==="
echo '--- 4. env 实际注入验证 (服务已在收尾时停; 从 unit 层验证) ---'
ssh "$A" 'sudo systemctl show rpc-server@m27-q4ks -p Environment | head -2'
