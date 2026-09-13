#!/bin/bash
# 分析: 为何无 rpccache 且走 WiFi
set +e
echo "======== 1. 环网物理拓扑 (各站 thunderbolt 接口配对) ========"
echo "--- B ---"
ip -4 addr show 2>/dev/null | grep -w inet | grep -v 127.0.0.1
echo "--- B ARP (全) ---"
ip neigh show 2>/dev/null | grep -E "10\.10" 

echo "======== 2. 对话:RPC权重缓存机制 ========"
echo "--- master llama-server RPC flags ---"
/opt/llama.cpp/llama-server -h 2>&1 | grep -i -- "--rpc"
echo "--- 9859 llama-server RPC flags ---"
/opt/llama.cpp-9859/llama-server -h 2>&1 | grep -i -- "--rpc"

echo "======== 3. rpccache 文件/目录是否存在 ========"
ls -la ~/.cache/llama.cpp/rpc/ 2>/dev/null || echo "no ~/.cache/llama.cpp/rpc"
find ~ -maxdepth 3 -iname "*rpccache*" 2>/dev/null | head -5
ls -la ~/llama-distributed/ 2>/dev/null

echo "======== 4. 环网连通实测 (当前) ========"
ping -c 1 -W 2 10.10.10.1 2>&1 | tail -2
ping -c 1 -W 2 10.10.11.3 2>&1 | tail -2

echo "======== 5. B 站历史 inference.conf 的 RPC 地址 ========"
for f in ~/llama-distributed/inference.conf ~/llama-distributed/run_inference.sh /tmp/*.conf; do
  [ -f "$f" ] && echo "--- $f ---" && grep -iE "rpc|RPC_ADDR|10\.10" "$f" | head -8
done 2>/dev/null