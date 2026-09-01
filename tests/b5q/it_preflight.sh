#!/bin/bash
# B5q 集成验收 Pre-flight (CHECKLIST §0)
echo '--- P1 两站可达 ---'
ssh -o ConnectTimeout=5 10.10.10.1 'hostname -s' 2>/dev/null || ssh -o ConnectTimeout=5 192.168.1.11 'hostname -s'
echo '--- P2 现役状态 ---'
echo "A rpc-server@m27-q4ks: $(ssh 10.10.10.1 'systemctl is-active rpc-server@m27-q4ks' 2>/dev/null)"
echo "B llama-server: $(systemctl list-units 'llama-server@*' --no-legend 2>/dev/null | head -3 | tr '\n' ' ')"
[ -z "$(systemctl list-units 'llama-server@*' --no-legend 2>/dev/null)" ] && echo '(B 无运行实例)'
echo '--- P3 conf 快照 ---'
TS=$(date +%Y%m%d-%H%M%S)
sudo cp -a /etc/llama-instances "/tmp/llama-instances.bak.${TS}" && echo "snapshot: /tmp/llama-instances.bak.${TS}"
echo '--- P4 GTT 余量 (B / A) ---'
grep -E 'GTT|MemAvailable' /proc/meminfo
ssh 10.10.10.1 'grep -E "GTT|MemAvailable" /proc/meminfo' 2>/dev/null
echo '--- A 站 rpccache 热缓存确认 ---'
ssh 10.10.10.1 'du -sh /data/rpccache/m27-q4ks 2>/dev/null; ls /data/rpccache/ 2>/dev/null | head -5'
