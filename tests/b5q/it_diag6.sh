#!/bin/bash
# 诊断: rpc-nodes 探测失败 vs A 端口 LISTEN 矛盾 (backlog Recv-Q=2)
echo '--- B 探测 50052 ---'
timeout 3 bash -c 'exec 3<>/dev/tcp/10.10.10.1/50052' && echo 'probe OK' || echo "probe FAIL rc=$?"
echo '--- A: 50052 连接状态 ---'
ssh -o BatchMode=yes 10.10.10.1 'ss -tn state established "( sport = :50052 )"; echo ---listen:; ss -tlnp "( sport = :50052 )"; echo ---proc:; pgrep -af "rpc.server|llama-rpc" | head -5; echo ---srv-uptime:; systemctl show rpc-server@m27-q4ks -p ActiveEnterTimestamp'
