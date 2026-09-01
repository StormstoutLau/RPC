#!/bin/bash
# dbg_find.sh — 定位 dedup 脚本零输出原因
echo "=== [1] find /data/models (无 -type) ==="
sudo find /data/models -name "*.gguf" 2>&1 | head -5
echo "=== [2] find -type f ==="
sudo find /data/models -name "*.gguf" -type f 2>&1 | head -5
echo "=== [3] /data/models/gguf 是不是软链? ==="
ls -la /data/models/
file /data/models/gguf
echo "=== [4] process substitution 测试 ==="
count=$(while IFS=$'\t' read -r s p; do echo "$p"; done < <(sudo find /data/models -name "*.gguf" -type f -printf "%s\t%p\n" 2>/dev/null | head -3) | wc -l)
echo "proc-sub 循环读出行数: $count"
echo "=== [5] 直接 sudo -n 测试 (无 tty) ==="
sudo -n true 2>&1 && echo "sudo -n OK"