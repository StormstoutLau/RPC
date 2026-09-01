#!/bin/bash
# diag_tb_mgmt.sh — 谁在管 B 站 thunderbolt0 的 IP (服务 vs NM)
echo "=== NM 对 thunderbolt0 的管理 ==="
nmcli -f DEVICE,TYPE,STATE,CONNECTION device show thunderbolt0 2>/dev/null
nmcli -f NAME,DEVICE,TYPE connection show 2>/dev/null | grep -i thunderbolt
echo
echo "=== TB 接口地址 (确认 10.10.10.2 在) ==="
ip -br addr show thunderbolt0
echo
echo "=== 现行 10.10.10.2 归属 (NM connection?) ==="
nmcli -f GENERAL.DEVICE,IP4.ADDRESS connection show --active 2>/dev/null | head -10