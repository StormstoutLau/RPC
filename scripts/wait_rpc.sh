#!/bin/bash
# wait_rpc.sh — 等待 A 站 rpc-server (10.10.10.1:50052) 可达, 最长 5 分钟
# 被 B 站 llama-server.service 的 ExecStartPre 调用; A 站起不来时避免白加载
for i in $(seq 60); do
    if timeout 1 bash -c 'echo > /dev/tcp/10.10.10.1/50052' 2>/dev/null; then
        exit 0
    fi
    sleep 5
done
echo "ERROR: A 站 rpc-server 300 秒内不可达, 放弃本次启动" >&2
exit 1
