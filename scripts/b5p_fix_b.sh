#!/bin/bash
# B5p: IP 漂移修复 — B 站 (mDNS/localhost 化, 备份先行)
set -e
TS=$(date +%Y%m%d-%H%M%S)

# 1. beszel-agent (B): hub 在本机 → 127.0.0.1 (永久免疫 IP 漂移)
sudo cp /etc/systemd/system/beszel-agent.service "/etc/systemd/system/beszel-agent.service.bak-$TS"
sudo sed -i 's|HUB_URL=http://192.168.1.15:8090|HUB_URL=http://127.0.0.1:8090|' /etc/systemd/system/beszel-agent.service

# 2. beszel-hub APP_URL → mDNS (通知邮件里的链接)
sudo cp /etc/systemd/system/beszel-hub.service "/etc/systemd/system/beszel-hub.service.bak-$TS"
sudo sed -i 's|APP_URL=http://192.168.1.15:8090|APP_URL=http://scott-lau-GTR-Pro.local:8090|' /etc/systemd/system/beszel-hub.service

sudo systemctl daemon-reload
sudo systemctl restart beszel-hub
sleep 4
sudo systemctl restart beszel-agent
sleep 3
echo "B agent: $(systemctl is-active beszel-agent), hub: $(systemctl is-active beszel-hub)"

# 3. b5k_sync.sh: A 站管理网 IP → mDNS
cp ~/scripts/b5k_sync.sh ~/scripts/b5k_sync.sh.bak-$TS
sed -i 's|A_MGMT="192.168.1.11"|A_MGMT="scott-lau-NEX.local"|' ~/scripts/b5k_sync.sh
sed -i 's|默认走管理网 192.168.1.11|默认走管理网 mDNS|' ~/scripts/b5k_sync.sh

# 4. cockpit machines.d: A 站 → mDNS
sudo cp /etc/cockpit/machines.d/99-webui.json "/etc/cockpit/machines.d/99-webui.json.bak-$TS"
sudo sed -i 's|"192.168.1.11"|"scott-lau-NEX.local"|g' /etc/cockpit/machines.d/99-webui.json

echo "=== 残留旧 IP 检查 (应为空) ==="
grep -rF -e 192.168.1.15 -e 192.168.1.11 /etc/systemd/system/beszel-agent.service /etc/systemd/system/beszel-hub.service ~/scripts/b5k_sync.sh /etc/cockpit/machines.d/99-webui.json 2>/dev/null || echo "NO_OLD_IP_LEFT ✓"
