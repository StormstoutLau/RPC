#!/bin/bash
# A 站: 盘点 AWQ + rpccache
set -u
echo "=== 1. MiniMax AWQ (A 站副本) ==="
ls -d /data/models/MiniMax* 2>/dev/null
sudo du -smL /data/models/MiniMax-AWQ 2>/dev/null
echo "=== 2. rpccache 清单 ==="
sudo du -sm /data/rpccache/* 2>/dev/null
echo "=== 3. A 站 /data 大项总览 ==="
sudo du -sm /data/* 2>/dev/null | sort -rn | head -8
echo DONE_A
