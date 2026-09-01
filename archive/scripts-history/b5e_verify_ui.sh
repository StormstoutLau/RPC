#!/bin/bash
# b5e_verify_ui.sh — B5e 用户浏览器操作确认 (只读): 服务/端口/登录痕迹/主机切换器/推理服务
set -u
echo "===== $(hostname -s) @ $(date '+%F %T') ====="

echo "--- [1] cockpit socket/service 状态 ---"
systemctl is-active cockpit.socket cockpit.service 2>&1
systemctl status cockpit.socket --no-pager -n 0 2>/dev/null | head -4

echo "--- [2] 9095 监听 ---"
ss -tlnp 2>/dev/null | grep 9095 || echo "NOT LISTENING"

echo "--- [3] 最近登录/会话痕迹 (journal 最近 10 条 cockpit) ---"
journalctl -u cockpit.service --no-pager -n 10 -o short 2>/dev/null | grep -iE "login|session|auth|5549|9095" || journalctl -u cockpit.service --no-pager -n 5 -o short 2>/dev/null

echo "--- [4] 授权痕迹 (/etc/cockpit/) + 机器码 ---"
ls -la /etc/cockpit/ 2>/dev/null | grep -vE "^total|^d" || true
cat /etc/cockpit/machine-id 2>/dev/null || true

echo "--- [5] host switcher 机器清单 (B 站添加 A 站的落盘证据) ---"
for f in ~/.config/cockpit/machines.json /var/lib/cockpit/machines.json ~/.local/share/cockpit/machines.json; do
  if [ -f "$f" ]; then echo "FILE: $f"; cat "$f"; echo; fi
done

echo "--- [6] 推理服务不受影响 ---"
systemctl is-active llama-server.service rpc-server.service 2>&1 | paste -sd' ' -

echo "--- [7] 最近 cockpit WS 连接 ( Established 9095 ) ---"
ss -tnp 2>/dev/null | grep 9095 | grep -v LISTEN || echo "当前无活动 WS 连接 (正常, 浏览器页可已关闭)"
