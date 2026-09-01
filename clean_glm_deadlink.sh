#!/bin/bash
# 清理 GLM 冷移残留死链 (B 站)
set -u
echo "=== 死链确认 ==="
ls -la /data/models/gguf/unsloth/ | head -5
sudo rm /data/models/gguf/unsloth/GLM-5.3-Flash-GGUF
LEFT=$(ls -A /data/models/gguf/unsloth/ 2>/dev/null | wc -l)
echo "unsloth 剩余条目: $LEFT"
if [ "$LEFT" -eq 0 ]; then
  sudo rmdir /data/models/gguf/unsloth/ && echo "(空目录已删)"
fi
echo "=== 全库死链复查 ==="
find /data/models/gguf -xtype l 2>/dev/null | wc -l
df -h /data | tail -1
echo DONE
