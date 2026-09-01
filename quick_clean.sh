#!/bin/bash
# quick_clean.sh — B 站快清理: journal 收缩 + apt 缓存 + 旧内核 (不动任何模型)
echo "=== 清理前 ==="
df -h / | tail -1

echo "--- [1] journal 收缩到 200M ---"
sudo journalctl --vacuum-size=200M 2>&1 | tail -2

echo "--- [2] apt 缓存 ---"
sudo apt-get clean 2>&1 | head -1
sudo du -sh /var/cache/apt 2>/dev/null

echo "--- [3] crash 转储残留 (前 5.8G 已删, 查剩余 135M) ---"
ls -lh /var/crash/ | head -4
sudo rm -f /var/crash/*.crash /var/crash/*.upload /var/crash/*.uploaded 2>/dev/null
echo "已清"

echo "--- [4] 旧内核清理 (保留 6.17.0-40 + 运行中; 7.0 系与 6.17.0-22/23/29/35 是候选) ---"
dpkg -l | grep -E "^ii.*linux-(image|modules|headers)-[0-9]" | awk "{print \$2}" | sort

echo "=== 清理后 ==="
df -h / | tail -1