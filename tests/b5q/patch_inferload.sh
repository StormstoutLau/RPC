#!/bin/bash
# B5q-1: infer-load 哨兵化补丁 (L50: 硬编码 IP → auto, 仅影响新生成 conf)
sudo cp /usr/local/bin/infer-load /usr/local/bin/infer-load.bak-b5q 2>/dev/null
sudo sed -i 's/RPCV="10.10.10.1:50052"/RPCV="auto"/' /usr/local/bin/infer-load
echo "--- patch 后 ---"
grep -n 'RPCV=' /usr/local/bin/infer-load
