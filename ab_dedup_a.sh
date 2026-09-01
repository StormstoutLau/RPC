#!/bin/bash
# ab_dedup_a.sh — A 站站间去重执行 (删与 B 重复的 16 repo, 保留 unsloth/GLM)
# 前提: 用户裁定全删 + B 为唯一下载点; 22 文件已逐一对上 B 同名同大小
set -e
echo "=== 删前状态 ==="
df -h / | tail -1
echo
echo "=== 待删 repo (保留 unsloth) ==="
ls ~/.lmstudio/models/ | grep -vx unsloth
echo
TOTAL_BEFORE=$(df --output=avail -B1G / | tail -1)
# 逐 repo 删除 (显式列名, 不用通配, 防误删)
for pub in autotrust HauhauCS Jackrong mradermacher second-state TeichAI; do
  rm -rf ~/.lmstudio/models/$pub/
  echo "removed: $pub/"
done
rm -rf ~/.lmstudio/models/lmstudio-community/
echo "removed: lmstudio-community/"
echo
echo "=== 保留确认 ==="
ls ~/.lmstudio/models/
du -sh ~/.lmstudio/models/* 2>/dev/null
echo
echo "=== 清理 /data/models/gguf 死软链 (目标已不存在) ==="
CLEANED=0
for link in /data/models/gguf/*/*; do
  if [ -L "$link" ] && [ ! -e "$link" ]; then
    rm "$link"
    CLEANED=$((CLEANED+1))
    echo "dead-link removed: $link"
  fi
done
# 清空 publisher 目录 (只剩空壳的)
for pubdir in /data/models/gguf/*/; do
  if [ -z "$(ls -A "$pubdir" 2>/dev/null)" ]; then
    rmdir "$pubdir"
    echo "empty publisher dir removed: $pubdir"
  fi
done
echo "dead links cleaned: $CLEANED"
echo
echo "=== 删后状态 ==="
df -h / | tail -1
TOTAL_AFTER=$(df --output=avail -B1G / | tail -1)
echo "释放: $((TOTAL_AFTER - TOTAL_BEFORE))G"
echo
echo "=== infer-list 视角验证 (A 站残留可见 repo) ==="
find -L /data/models/gguf -mindepth 2 -maxdepth 2 -type d 2>/dev/null | sed 's|/data/models/gguf/||' | sort
