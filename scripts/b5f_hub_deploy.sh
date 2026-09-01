#!/bin/bash
# b5f_hub_deploy.sh — B5f Beszel hub 部署 (B 站 :8090, 幂等)
# 官方依据: beszel.dev/guide/agent-installation (KEY/TOKEN/HUB_URL/LISTEN)
# 版本锁: v0.18.8 (侦察 2026-08-30 latest)
set -uo pipefail

VER="0.18.8"
HUB_BIN=/opt/beszel/beszel
DATA_DIR=/var/lib/beszel
UNIT=/etc/systemd/system/beszel-hub.service
PORT=8090
ADMIN_EMAIL="peng.liu.john@gmail.com"
ADMIN_PASS="Beszel-$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' \n')"

echo "===== $(hostname -s) B5f hub deploy @ $(date '+%F %T') ====="
fail() { echo "FATAL: $*"; exit 1; }

# ---------- [0] preflight ----------
ss -tln | grep -q ":${PORT} " && systemctl is-active --quiet beszel-hub.service && echo "hub 已在跑 (幂等重入)" || echo "端口 ${PORT} 空闲 ✓"

# ---------- [1] 下载 hub 二进制 (锁 v0.18.8) ----------
if [ ! -x "$HUB_BIN" ] || ! "$HUB_BIN" --version 2>/dev/null | grep -q "0.18.8"; then
  echo "--- [1] 下载 beszel ${VER} hub ---"
  sudo mkdir -p /opt/beszel
  for i in 1 2 3; do
    curl -sL --max-time 180 --retry 2 \
      "https://github.com/henrygd/beszel/releases/download/v${VER}/beszel_linux_amd64.tar.gz" \
      | tar -xz -C /tmp beszel && break
    echo "重试 $i ..."
  done
  [ -f /tmp/beszel ] || fail "hub 二进制下载失败"
  sudo install -m 755 /tmp/beszel "$HUB_BIN"
  rm -f /tmp/beszel
fi
"$HUB_BIN" --version 2>/dev/null || echo "(二进制 --version 不支持, 跳过版本打印)"

# ---------- [2] 运行用户 + 数据目录 ----------
if ! id beszel >/dev/null 2>&1; then
  sudo useradd -r -s /usr/sbin/nologin -d "$DATA_DIR" -m beszel || fail "useradd beszel 失败"
fi
sudo mkdir -p "$DATA_DIR" && sudo chown beszel:beszel "$DATA_DIR"

# ---------- [3] systemd ----------
echo "--- [3] 安装 beszel-hub.service ---"
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Beszel monitoring hub (B5f) :${PORT}
After=network-online.target
Wants=network-online.target

[Service]
User=beszel
WorkingDirectory=${DATA_DIR}
ExecStart=${HUB_BIN} serve --http 0.0.0.0:${PORT}
Environment=APP_URL=http://192.168.1.15:${PORT}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now beszel-hub.service

# ---------- [4] 等就绪 ----------
OK=""
for i in $(seq 1 20); do
  curl -s --max-time 3 "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1 && { OK=1; break; }
  sleep 2
done
[ -n "$OK" ] || { echo "FATAL: hub 未就绪"; journalctl -u beszel-hub -n 30 --no-pager; exit 1; }
echo "hub :${PORT} 就绪 ✓"

# ---------- [5] superuser 创建 (PocketBase CLI 透传) ----------
echo "--- [5] superuser upsert ---"
if sudo -u beszel "$HUB_BIN" superuser upsert "$ADMIN_EMAIL" "$ADMIN_PASS" 2>&1 | tail -2; then
  echo "superuser ✓"
else
  echo "upsert 不支持, 试 create ..."
  sudo -u beszel "$HUB_BIN" superuser create "$ADMIN_EMAIL" "$ADMIN_PASS" 2>&1 | tail -2 || echo "CLI 建号失败 — 需走 Web UI 首次注册"
fi
echo "ADMIN_EMAIL=$ADMIN_EMAIL"
echo "ADMIN_PASS=$ADMIN_PASS"

# ---------- [6] systems 集合 schema 探测 (为 agent 全自动部署探路) ----------
echo "--- [6] API 探测: systems schema ---"
AUTH=$(curl -s -X POST "http://127.0.0.1:${PORT}/api/collections/_superusers/auth-with-password" \
  -H 'Content-Type: application/json' \
  -d "{\"identity\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASS}\"}")
TOKEN=$(echo "$AUTH" | jq -r .token // empty 2>/dev/null)
if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
  echo "superuser token 获取 ✓"
  curl -s "http://127.0.0.1:${PORT}/api/collections/systems/records" \
    -H "Authorization: ${TOKEN}" | head -c 600; echo
  echo "--- 现有 users 集合 (admin 关联用) ---"
  curl -s "http://127.0.0.1:${PORT}/api/collections/users/records" \
    -H "Authorization: ${TOKEN}" | jq -r '.items[]? | "\(.id) \(.email)"' 2>/dev/null || echo "(空/失败)"
else
  echo "superuser auth 失败: $(echo "$AUTH" | head -c 200)"
fi

# ---------- [7] 推理服务零影响 ----------
echo "--- [7] llama-server ---"
systemctl is-active llama-server.service
echo "===== hub 部署完成 ====="
