#!/bin/bash
# 删除 qwen3.5-122b-a10b-claude-distill-v2-i1 (B 站, 用户裁决 2026-09-01)
set -u
REPO=/data/models/gguf/mradermacher/Qwen3.5-122B-A10B-Claude-Distill-v2-i1-GGUF
CONF=/etc/llama-instances/qwen3.5-122b-a10b-claude-distill-v2-i1.env

echo "=== 0. 删除前状态 ==="
df -h /data | tail -1
echo "--- 确认无服务运行此模型 ---"
pgrep -af "qwen3.5-122b-a10b-claude" | grep -v grep || echo "(无进程, 安全)"

echo "=== 1. 删物理库 (66.4G) ==="
sudo rm -rf $REPO
echo "rc=$?"

echo "=== 2. mradermacher/ 目录处置 ==="
LEFT=$(ls -A /data/models/gguf/mradermacher/ 2>/dev/null | wc -l)
echo "剩余条目: $LEFT"
if [ "$LEFT" -eq 0 ]; then
  sudo rmdir /data/models/gguf/mradermacher/ && echo "(空目录已删)"
else
  echo "(非空保留: $(ls /data/models/gguf/mradermacher/ | head -3))"
fi

echo "=== 3. 删 conf ==="
sudo rm -f $CONF && echo "conf 已删"

echo "=== 4. 死链检查 ==="
find /data/models/gguf -xtype l 2>/dev/null | head -5 || true

echo "=== 5. 删除后状态 ==="
df -h /data | tail -1
infer-list 2>/dev/null | grep -i "122b" || echo "(infer-list 已无 122b-claude 条目)"
echo DONE
