#!/bin/bash
# b5e_deploy.sh — B5e: Cockpit 部署 (SOP v2, 7.13 审计修正后) + lm-download@.service 交付
# 两站通用; 前置审计关键项: A 站 9090 被 mihomo 占 → 统一 9095; 不装 cockpit-pcp (pmlogger 43xx 端口群);
#   A 站 noble-backports 源缺失 → 脚本内自动启用, 不可用则 fallback universe
# 安全边界: 全程不动 llama-server / rpc-server (推理零影响)
set -uo pipefail
log() { echo "[b5e $(hostname -s) $(date '+%H:%M:%S')] $*"; }

PORT=9095

log "=== A. cockpit 安装 (优先 backports, 不带 cockpit-pcp) ==="
if dpkg -l cockpit 2>/dev/null | grep -q '^ii'; then
  log "cockpit 已装, 跳过"
else
  TARGET=""
  if apt-cache policy cockpit 2>/dev/null | grep -q bpo; then
    TARGET="-t noble-backports"; log "backports 源已有"
  else
    echo "deb http://cn.archive.ubuntu.com/ubuntu noble-backports universe main" \
      | sudo tee /etc/apt/sources.list.d/99-noble-backports.list >/dev/null
    sudo apt-get update -o Dir::Etc::sourcelist="sources.list.d/99-noble-backports.list" \
      -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0" >/dev/null 2>&1
    if apt-cache policy cockpit 2>/dev/null | grep -q bpo; then
      TARGET="-t noble-backports"; log "backports 源启用 OK"
    else
      sudo rm -f /etc/apt/sources.list.d/99-noble-backports.list
      log "WARN: backports 不可用, fallback universe"
    fi
  fi
  sudo apt-get install -y ${TARGET} cockpit 2>&1 | tail -4
  if dpkg -l cockpit 2>/dev/null | grep -q '^ii'; then
    log "cockpit 安装 OK (版本 $(dpkg-query -W -f='${Version}' cockpit))"
  else
    log "ERROR: cockpit 安装失败"; exit 1
  fi
fi

log "=== B. 端口 ${PORT} (cockpit.socket drop-in; cockpit.conf 不能改端口) ==="
sudo mkdir -p /etc/systemd/system/cockpit.socket.d
printf '[Socket]\n# 清空默认 9090 (B5e 审计: A 站被 mihomo 占)\nListenStream=\nListenStream=%s\n' "$PORT" \
  | sudo tee /etc/systemd/system/cockpit.socket.d/10-port.conf >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now cockpit.socket >/dev/null 2>&1 || true

log "=== C. cockpit 验证 ==="
for i in 1 2 3; do
  ss -tln | grep -q ":${PORT} " && break
  sleep 2
done
if ss -tln | grep ":${PORT} "; then
  log "LISTEN ${PORT} OK"
else
  log "ERROR: ${PORT} 未监听"; exit 1
fi
CODE=$(curl -sk --max-time 15 -o /dev/null -w '%{http_code}' https://127.0.0.1:${PORT}/ 2>/dev/null || echo fail)
log "https 自检: HTTP ${CODE} (200/401 均正常 — socket 激活首次连接略慢)"

log "=== D. lm-download@.service 交付 (6.6 缺口①) ==="
command -v aria2c >/dev/null 2>&1 || sudo apt-get install -y aria2 >/dev/null 2>&1
sudo mkdir -p /etc/lm-download/tasks
sudo tee /etc/systemd/system/lm-download@.service >/dev/null <<'EOF'
[Unit]
Description=LM model download task %i (aria2 x16 + hf-mirror)
After=network-online.target
Wants=network-online.target
ConditionPathExists=/etc/lm-download/tasks/%i.env

[Service]
Type=oneshot
EnvironmentFile=/etc/lm-download/tasks/%i.env
ExecStart=/usr/bin/aria2c --max-connection-per-server=16 --split=16 --min-split-size=64M --continue=true --summary-interval=30 --console-log-level=warn --dir=${DL_DIR} --out=${DL_OUT} ${DL_URL}
RemainAfterExit=yes
Nice=10
EOF
# 冒烟任务模板 (小文件, 验证 unit 链路; 留作示例)
sudo tee /etc/lm-download/tasks/smoke-test.env >/dev/null <<'EOF'
# 任务定义示例: 三变量; 下载 = systemctl start lm-download@<name>.service
# 进度 = Cockpit journal 页 或 journalctl -u lm-download@<name> -f
DL_URL=https://hf-mirror.com/Qwen/Qwen2.5-0.5B-Instruct/raw/main/config.json
DL_DIR=/tmp/lm-dl-test
DL_OUT=config.json
EOF
sudo systemctl daemon-reload
sudo systemctl start lm-download@smoke-test.service
sleep 8
if [ -f /tmp/lm-dl-test/config.json ]; then
  log "lm-download 冒烟 OK ($(stat -c %s /tmp/lm-dl-test/config.json) bytes)"
else
  log "WARN: lm-download 冒烟文件未出现 — journalctl -u lm-download@smoke-test 排查"
fi

log "=== E. pm-qos-usb4 启停冒烟 (模拟 Cockpit UI 管理动作) ==="
sudo systemctl stop pm-qos-usb4
S1=$(systemctl is-active pm-qos-usb4)
sudo systemctl start pm-qos-usb4
S2=$(systemctl is-active pm-qos-usb4)
log "pm-qos-usb4: stop→${S1} / start→${S2} (期望 inactive→active)"

log "=== F. 推理服务零影响确认 ==="
systemctl list-unit-files llama-server.service --no-legend 2>/dev/null | grep -q llama-server \
  && log "llama-server: $(systemctl is-active llama-server)"
systemctl list-unit-files rpc-server.service --no-legend 2>/dev/null | grep -q rpc-server \
  && log "rpc-server: $(systemctl is-active rpc-server)"
log "=== B5E_DEPLOY_DONE ==="
