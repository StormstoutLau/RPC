#!/bin/bash
# b5e_audit.sh — B5e 前置审计: 两站本地事实核查 (只读, 不安装任何包)
echo "=== HOST ==="; hostname

echo "=== 1. OS 版本 ==="
lsb_release -ds 2>/dev/null || head -2 /etc/os-release

echo "=== 2. cockpit 包可用性 (apt 仓库版本 = 实际会装的版本) ==="
apt-cache policy cockpit cockpit-pcp 2>/dev/null
echo "--- 相关包 ---"
apt-cache policy packagekit pcp 2>/dev/null | grep -E '^[a-z]|Installed|Candidate' | head -12

echo "=== 3. cockpit 是否已装 ==="
dpkg -l 2>/dev/null | grep -i cockpit || echo "NOT_INSTALLED"

echo "=== 4. 端口占用 (9090 cockpit / 8090 beszel-hub / 45876 beszel-agent / 4000 litellm) ==="
ss -tln 2>/dev/null | grep -E ':(9090|8090|45876|4000)\b' || echo "ALL_FREE"

echo "=== 5. 防火墙状态 ==="
sudo ufw status 2>&1 | head -3

echo "=== 6. 本集群 systemd 服务存在性 (Cockpit 将管理的对象) ==="
for s in rpc-server llama-server pm-qos-usb4 usb4net-lowlatency; do
  printf '%-22s: ' "$s"
  systemctl list-unit-files "$s.service" --no-legend 2>/dev/null || echo "NOT_FOUND"
done

echo "=== 7. 用户/权限模型 (Cockpit 登录将用的账号) ==="
id scott-lau | head -1
sudo -n true 2>/dev/null && echo "SUDO=nopasswd" || echo "SUDO=needs_password"

echo "=== 8. 两站间 SSH 互信 (Cockpit 多机切换依赖) ==="
ssh -o BatchMode=yes -o ConnectTimeout=8 10.10.10.1 "echo A_REACHABLE_FROM_$(hostname -s)" 2>/dev/null || ssh -o BatchMode=yes -o ConnectTimeout=8 10.10.10.2 "echo B_REACHABLE_FROM_$(hostname -s)" 2>/dev/null || echo "PEER_SSH_FAIL"

echo "=== 9. universe 仓库启用 (cockpit 在 Ubuntu 的来源) ==="
grep -rhE '^deb ' /etc/apt/sources.list /etc/apt/sources.list.d/*.sources 2>/dev/null | head -6 || true

echo "=== B5E_AUDIT_DONE ==="
