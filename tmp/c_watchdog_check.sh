#!/bin/bash
# 1. 查看服务 enable/active 状态 + 模板现状
set +e
echo "=== 服务 enable 状态 ==="
systemctl is-enabled llama-server@qwen3.8-27b-mtp.service 2>/dev/null
systemctl is-active llama-server@qwen3.8-27b-mtp.service 2>/dev/null
echo "=== 模板 Restart 现状 ==="
grep -nE 'Restart|RestartSec' /etc/systemd/system/llama-server@.service
echo "=== 是否有 drop-in 覆盖 ==="
ls -la /etc/systemd/system/llama-server@qwen3.8-27b-mtp.service.d/ 2>/dev/null || echo '(无 drop-in)'
echo "=== 服务当前 pid ==="
systemctl show llama-server@qwen3.8-27b-mtp.service -p MainPID -p SubState 2>/dev/null