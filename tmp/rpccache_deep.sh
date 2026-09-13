#!/bin/bash
# 深入: rpccache 机制 + 为何走 WiFi
set +e
echo "======== 1. rpc-server --cache 帮助 ========"
/opt/llama.cpp/ggml-rpc-server -h 2>&1 | grep -iA2 -E "cache|device|host|port"

echo "======== 2. 9859 rpc-server 是否也有 --cache ========"
/opt/llama.cpp-9859/ggml-rpc-server -h 2>&1 | grep -iA1 "cache" || echo "9859 无 cache 选项"

echo "======== 3. A/C 当前 rpc-server 是否带 -c 启动 ========"
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no scott-lau@192.168.1.33 "ps aux | grep -E 'ggml-rpc|rpc-server' | grep -v grep" 2>/dev/null
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no scott-lau@192.168.1.37 "ps aux | grep -E 'ggml-rpc|rpc-server' | grep -v grep" 2>/dev/null

echo "======== 4. 文档记载 9/1 时 worker 是否带 cache ========"
grep -riE "rpc-server|ggml-rpc|cache" /tmp/rpccache_analysis.sh 2>/dev/null

echo "======== 5. 环网线缆配对判断 ========"
echo "B ARP 表(全接口):"
ip neigh show | grep 10.10
echo "-> 若 10.10.10.1(A) 出现在 thunderbolt1(应连C), 10.10.11.3(C) 出现在 thunderbolt0(应连A) => 物理线缆交叉"