#!/bin/bash
# A 站批量删除 (2026-09-01 用户裁决: MiniMax AWQ + m27 rpccache + qwen3.5-uncensored 缓存)
set -u
echo "=== 删除前 ==="
df -h /data | tail -1

echo "=== 0. 前置安全: 无 rpc-server 运行 ==="
pgrep -af "rpc-server" | grep -v grep || echo "(无进程, 安全)"

echo "=== 1. 删 MiniMax AWQ (A 站副本) ==="
sudo rm -rf /data/models/MiniMax-M2.7-AWQ-G32-STRIX-2H
echo "rc=$?"

echo "=== 2. 删 m27 rpccache (168.6G) + qwen3.5-uncensored 缓存 (23.9G) ==="
sudo rm -rf /data/rpccache/m27-q4ks
sudo rm -rf /data/rpccache/qwen3.5-122b-a10b-uncensored-hauhaucs-aggressive
echo "rc=$?"

echo "=== 3. rpccache 剩余 ==="
sudo du -sm /data/rpccache/* 2>/dev/null

echo "=== 4. GLM-5.3-Flash 定位 (分析用, 不删) ==="
sudo find /data /home/scott-lau -maxdepth 4 -iname "*GLM-5.3*" -type d 2>/dev/null | head -3
sudo du -smL /home/scott-lau/.lmstudio/models/unsloth/GLM-5.3-Flash-GGUF 2>/dev/null

echo "=== 5. 删除后 ==="
df -h /data | tail -1
echo DONE_A_DEL
