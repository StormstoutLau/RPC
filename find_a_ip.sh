#!/bin/bash
# find_a_ip.sh — B 站侧扫 192.168.1.0/24 找 A 站新 IP (arp 签名比对)
echo "=== B 站 arp 表 (已知邻居) ==="
ip neigh | grep -v FAILED | head -10
echo
echo "=== 并行 ping 扫描 (1-60, 0.3s 超时) ==="
for i in $(seq 1 60); do
  (ping -c 1 -W 1 192.168.1.$i >/dev/null 2>&1 && echo "alive 192.168.1.$i") &
done | sort
wait
echo
echo "=== 扫后 arp (新 MAC 出现即 A 站) ==="
ip neigh | grep -v FAILED | head -12