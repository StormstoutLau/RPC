#!/bin/bash
echo "== llama-server@* 单元 ==="
systemctl list-units "llama-server@*" --all --no-legend 2>/dev/null | head -20
echo "== enabled 的 llama-server 单元 ==="
systemctl list-unit-files "llama-server@*" --no-legend 2>/dev/null | head
echo "== 当前 active 模型单元 → 停掉卸载 =="
A=$(systemctl list-units "llama-server@*" --state=active --no-legend 2>/dev/null | awk '{print $1}')
echo "active_units: $A"
for u in $A; do echo "stopping $u"; systemctl stop "$u" 2>&1 | head -2; done
sleep 2
echo "== 停后状态 =="
systemctl list-units "llama-server@*" --state=active --no-legend 2>/dev/null | head || echo "(all stopped)"
echo "== mem after unload =="
free -g | head -2