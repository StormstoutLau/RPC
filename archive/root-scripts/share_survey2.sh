#!/bin/bash
# share_survey2.sh — 共享方案补充调研 (两站)
echo "=== [B1] B 站 /data 挂载与 / 的关系 ==="
df -h / /data /home 2>/dev/null | grep -v tmpfs
findmnt -n -o TARGET,SOURCE,FSTYPE /data 2>/dev/null || echo "( /data 非独立挂载 = 与 / 同盘 )"
echo
echo "=== [B2] B 站两库 repo 对照 (publisher/repo 名, 判断同构) ==="
echo "--- .lmstudio/models repos ---"
find ~/.lmstudio/models -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sed 's|.*/models/||' | sort
echo "--- /data/models/gguf repos ---"
find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sed 's|/data/models/gguf/||' | sort
echo
echo "=== [B3] LM Studio 版本 ==="
~/.lmstudio/.internal/app-install-location.json 2>/dev/null; cat ~/.lmstudio/.internal/app-install-location.json 2>/dev/null | head -3
echo
echo "=== [B4] B 站 .lmstudio/models 内已有软链? ==="
find ~/.lmstudio/models -maxdepth 2 -type l 2>/dev/null | head -10
echo
echo "=== [A侧] A 站 /data/models 结构 ==="
ssh -o ConnectTimeout=10 scott-lau@10.10.10.1 '
  findmnt -n -o TARGET,SOURCE,FSTYPE /data 2>/dev/null || echo "(A: /data 非独立挂载)"
  ls -la /data/models/ 2>/dev/null | head -10
  ls -la /data/models/gguf 2>/dev/null | head -5 || echo "(A: /data/models/gguf 不存在或空)"
  echo "--- A 站 .lmstudio repos ---"
  find ~/.lmstudio/models -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sed "s|.*/models/||" | sort
'