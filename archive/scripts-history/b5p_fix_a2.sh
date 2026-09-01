#!/bin/bash
# B5p 修复 v2: A 站 agent HUB_URL → USB4 稳定地址 (Go 纯 resolver 解不了 mDNS .local)
set -e
sudo sed -i 's|HUB_URL=http://scott-lau-GTR-Pro.local:8090|HUB_URL=http://10.10.10.2:8090|' /etc/systemd/system/beszel-agent.service
sudo systemctl daemon-reload
sudo systemctl restart beszel-agent
sleep 8
systemctl is-active beszel-agent
journalctl -u beszel-agent -n 5 --no-pager | tail -3
