#!/bin/bash
# b5i_deploy_a.sh — B5i A 站: rpc-server@.service 模板 + 缓存目录改名 + disable 旧自启
# 幂等: 重复执行无副作用
set -uo pipefail
echo "===== $(hostname -s) B5i deploy @ $(date '+%F %T') ====="

# ---------- [1] 模板 unit (LLAMA_CACHE 用 %i 直接展开, 无需 conf) ----------
sudo tee /etc/systemd/system/rpc-server@.service >/dev/null <<'EOF'
[Unit]
Description=llama.cpp RPC worker %i (cache /data/rpccache/%i)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=scott-lau
Group=scott-lau
SupplementaryGroups=render video
Environment=LLAMA_CACHE=/data/rpccache/%i
ExecStart=/opt/llama.cpp/ggml-rpc-server -H 10.10.10.1 -p 50052 -c
Restart=always
RestartSec=5
StartLimitIntervalSec=0

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
echo "模板 unit ✓ rpc-server@.service (cache 路径 = /data/rpccache/<alias>)"

# ---------- [2] 现役缓存目录改名 (MiniMax-M2.7-Q4KS → m27-q4ks, 同盘 mv 零拷贝) ----------
if [ -d /data/rpccache/MiniMax-M2.7-Q4KS ] && [ ! -d /data/rpccache/m27-q4ks ]; then
  echo "改缓存目录名 (同盘零拷贝)..."
  sudo mv /data/rpccache/MiniMax-M2.7-Q4KS /data/rpccache/m27-q4ks
  echo "mv ✓ /data/rpccache/m27-q4ks"
else
  echo "缓存目录已就位 (m27-q4ks) 或旧目录不存在"
fi
ls -la /data/rpccache/ 2>/dev/null

# ---------- [3] disable 旧自启 (不停当前进程) ----------
sudo systemctl disable rpc-server 2>/dev/null && echo "旧 rpc-server 自启已 disable" || echo "旧 unit 已 disable/不存在"

echo ""
echo "=== A 站部署完成 ==="
