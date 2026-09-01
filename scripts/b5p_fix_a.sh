#!/bin/bash
# B5p: IP 漂移修复 — A 站 (agent HUB_URL → B 站 mDNS)
set -e
TS=$(date +%Y%m%d-%H%M%S)

sudo cp /etc/systemd/system/beszel-agent.service "/etc/systemd/system/beszel-agent.service.bak-$TS"
sudo sed -i 's|HUB_URL=http://192.168.1.15:8090|HUB_URL=http://scott-lau-GTR-Pro.local:8090|' /etc/systemd/system/beszel-agent.service

sudo systemctl daemon-reload
sudo systemctl restart beszel-agent
sleep 4
echo "A agent: $(systemctl is-active beszel-agent)"
echo "=== 残留旧 IP 检查 (应为空) ==="
grep -rF 192.168.1.15 /etc/systemd/system/beszel-agent.service 2>/dev/null || echo "NO_OLD_IP_LEFT ✓"
