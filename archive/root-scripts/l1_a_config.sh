#!/bin/bash
# L1 观测增强 — A 站 (2026-09-01, 按 A站挂死根因分析_20260901.md 执行)
set -u
exec 2>&1

echo "########## L1a: GRUB 无效参数清理 (amdgpu.wq_unbound=1 不存在) ##########"
echo "--- 当前 cmdline ---"
cat /proc/cmdline
echo "--- 参数所在源文件 ---"
SRCFILES=$(grep -rl "amdgpu.wq_unbound" /etc/default/grub /etc/default/grub.d/ /etc/kernel/cmdline 2>/dev/null)
echo "${SRCFILES:-<grub 配置中未找到 — 可能残留于已生成的 grub.cfg>}"

for f in $SRCFILES; do
  sudo cp -a "$f" "$f.bak.20260901"
  sudo sed -i 's/amdgpu.wq_unbound=1 \?//g; s/ \?amdgpu.wq_unbound=1//g' "$f"
  sudo sed -i 's/  \+/ /g' "$f"
  echo "已清理: $f (备份: $f.bak.20260901)"
  grep -n "CMDLINE" "$f" 2>/dev/null | head -5
done

if grep -rqs "amdgpu.wq_unbound" /etc/default/grub /etc/default/grub.d/ /etc/kernel/cmdline 2>/dev/null; then
  echo "!! 参数仍残留, 跳过 update-grub, 需人工检查"
else
  echo "--- update-grub ---"
  sudo update-grub 2>&1 | tail -8
fi
echo "--- GRUB 默认项钉扎检查 ---"
sudo grub-editenv list 2>/dev/null || true
grep -E "^GRUB_DEFAULT|^GRUB_SAVEDEFAULT" /etc/default/grub 2>/dev/null || echo "(无显式 GRUB_DEFAULT)"
sudo grep -m1 -A3 "menuentry 'Ubuntu" /boot/grub/grub.cfg 2>/dev/null | head -4

echo ""
echo "########## L1b: softlockup 全核栈打印 (先只开 backtrace 不开 panic) ##########"
CONF=/etc/sysctl.d/99-softlockup-forensics.conf
sudo tee $CONF >/dev/null <<'EOF'
# A 站挂死取证 (2026-09-01): softlockup 时打印全核 backtrace, 经 console/netconsole 可捕获
kernel.watchdog=1
kernel.softlockup_all_cpu_backtrace=1
EOF
sudo sysctl -p $CONF
echo "--- 生效值确认 ---"
sysctl kernel.watchdog kernel.softlockup_all_cpu_backtrace

echo ""
echo "########## L1c 前置: USB4 接口名 + B 站 MAC ##########"
ip -br a | grep -v "^lo"
IFACE=$(ip -br a | awk '$1!="lo" && /10\.10\.10\.1\// {print $1}')
echo "A 站 USB4 接口: ${IFACE:-<未找到>}"
if [ -n "$IFACE" ]; then
  ping -c1 -W2 10.10.10.2 >/dev/null 2>&1
  MAC=$(ip neigh show 10.10.10.2 dev "$IFACE" 2>/dev/null | awk '{print $5}' | head -1)
  echo "B 站 10.10.10.2 MAC: ${MAC:-<未解析>}"
fi
echo "DONE_L1A_L1B"
