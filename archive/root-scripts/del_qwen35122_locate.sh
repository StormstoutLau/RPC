#!/bin/bash
# 定位 qwen3.5-122b-a10b-claude-distill-v2-i1 物理库 + 软链 (B 站)
set -u
echo "=== 1. infer-list 条目 ==="
grep -i "qwen3.5-122b" /etc/llama-instances/*.env 2>/dev/null | head -5
echo "=== 2. 物理库定位 (.lmstudio) ==="
find /home/scott-lau/.lmstudio/models -maxdepth 3 -iname "*122b*" -o -maxdepth 3 -iname "*claude-distill*" 2>/dev/null | head -10
echo "=== 3. 软链视图 (/data/models/gguf) ==="
find /data/models/gguf -maxdepth 2 -iname "*122b*" 2>/dev/null | head -10
echo "=== 4. conf 文件 ==="
ls -la /etc/llama-instances/ | grep -i "122b\|claude" | head -5
echo "=== 5. rpccache ==="
ls /data/rpccache/ 2>/dev/null | grep -i "122b\|claude" | head -3
echo DONE
