#!/bin/bash
# a4_diag_rpc.sh — 检查 A 站 rpc-server 状态与日志
set -uo pipefail
echo "=== active state ==="
systemctl is-active rpc-server
echo "=== unit status (tail) ==="
systemctl status rpc-server --no-pager 2>&1 | tail -15
echo "=== recent journal ==="
journalctl -u rpc-server --no-pager -n 15 2>&1 | tail -15
echo "DIAG_RPC_DONE"
