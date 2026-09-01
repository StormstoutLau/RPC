#!/bin/bash
# b5f_agent_deploy.sh — B5f 部署 beszel-agent 到本站 (A/B 两站通用, 各自执行)
set -uo pipefail
VER="0.18.8"
TOKEN_VAL="1981a8c2688098e86317ad55e53be914"
HUB_URL_VAL="http://192.168.1.15:8090"
KEY_VAL="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAID898HJ5VlJ1Pryf99TXCy9Uxp4ot05HOevL7jhehY1+"
BIN=/usr/local/bin/beszel-agent
echo "===== $(hostname -s) beszel-agent deploy @ $(date '+%F %T') ====="

echo "--- [1] 下载 beszel-agent ${VER} ---"
if [ -x "$BIN" ] && "$BIN" --version 2>/dev/null | grep -q "$VER"; then
  echo "已有 binary ${VER}, 跳过下载"
else
  echo "下载 beszel-agent ${VER} ..."
  URL="https://github.com/henrygd/beszel/releases/download/v${VER}/beszel-agent_linux_amd64.tar.gz"
  curl -sL --retry 3 --connect-timeout 20 -o /tmp/beszel-agent.tar.gz "$URL" || { echo "下载失败"; exit 1; }
  SIZE=$(stat -c%s /tmp/beszel-agent.tar.gz)
  [ "$SIZE" -gt 1000000 ] || { echo "下载异常 (size=${SIZE}), URL 可能 404"; exit 1; }
  tar -xzf /tmp/beszel-agent.tar.gz -C /tmp beszel-agent
  sudo mv /tmp/beszel-agent "$BIN"
fi
ls -la "$BIN"

echo "--- [2] systemd unit ---"
sudo tee /etc/systemd/system/beszel-agent.service >/dev/null <<EOF
[Unit]
Description=Beszel Agent
After=network-online.target
Wants=network-online.target

[Service]
Environment=TOKEN=${TOKEN_VAL}
Environment=HUB_URL=${HUB_URL_VAL}
Environment=KEY="${KEY_VAL}"
ExecStart=${BIN}
Restart=always
RestartSec=5
StateDirectory=beszel-agent
WorkingDirectory=/var/lib/beszel-agent

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now beszel-agent.service
sleep 3
systemctl is-active beszel-agent.service

echo "--- [3] 端口 45876 监听 ---"
ss -tln | grep ':45876 ' || echo "45876 未监听!"

echo "--- [4] 最近日志 ---"
journalctl -u beszel-agent -n 15 --no-pager 2>/dev/null | tail -15
