#!/bin/bash
# B5q §4 (重): USB4 路径全量同步+双端校验 (管理网假阳性佐证 + A-only ~42G)
set -uo pipefail
echo '--- 佐证: 管理网 (192.168.1.11) ssh 状态 ---'
ssh -o ConnectTimeout=5 192.168.1.11 'hostname -s' 2>&1 | head -2 || true
echo '--- USB4 全量同步+双端校验 ---'
START=$(date +%s)
bash ~/scripts/b5k_sync.sh --go --usb4 --verify 2>&1 | tail -35
RC=$?
echo "=== b5k rc=${RC} elapsed=$(( $(date +%s) - START ))s ==="
