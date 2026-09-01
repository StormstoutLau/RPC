#!/bin/bash
# a4_dist.sh — B站: 接收 part01+02, 校验, USB4 转发 A站
# 用法: bash a4_dist.sh  (在 B 站运行; tar 包已 scp 到 ~/vllm-dist/)
set -euo pipefail
DIST=/home/scott-lau/vllm-dist
MD5_P1_EXPECT=4905106ECDB0D12A33834CEEDFA3C887

echo "=== 1. verify part01 ==="
MD5P1=$(md5sum "$DIST/vllm-rocm-gfx1151.part01.tar.gz" | awk '{print toupper($1)}')
if [ "$MD5P1" != "$MD5_P1_EXPECT" ]; then
  echo "PART01 MD5 MISMATCH: got=$MD5P1"; exit 1
fi
echo "part01 MD5 OK"

echo "=== 2. forward to A via USB4 (10.10.10.1) ==="
ssh -o BatchMode=yes -o ConnectTimeout=10 scott-lau@10.10.10.1 "mkdir -p /home/scott-lau/vllm-dist"
rsync -a --info=progress2 "$DIST/vllm-rocm-gfx1151.part01.tar.gz" scott-lau@10.10.10.1:/home/scott-lau/vllm-dist/
rsync -a --info=progress2 "$DIST/vllm-rocm-gfx1151.part02.tar.gz" scott-lau@10.10.10.1:/home/scott-lau/vllm-dist/
echo "forward done"

echo "=== 3. verify A-side md5 ==="
MD5A=$(ssh -o BatchMode=yes scott-lau@10.10.10.1 "md5sum /home/scott-lau/vllm-dist/vllm-rocm-gfx1151.part01.tar.gz" | awk '{print toupper($1)}')
if [ "$MD5A" != "$MD5_P1_EXPECT" ]; then
  echo "A-SIDE PART01 MD5 MISMATCH: got=$MD5A"; exit 1
fi
echo "A-side part01 MD5 OK"
echo "A_DIST_DONE"
