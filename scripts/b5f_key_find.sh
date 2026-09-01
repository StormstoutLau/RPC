#!/bin/bash
# b5f_key_find.sh — B5f 在 hub 数据目录找密钥文件 (B 站)
echo "===== $(hostname -s) hub data dir @ $(date '+%F %T') ====="
sudo ls -la /var/lib/beszel/
echo ""
echo "--- data 子目录 ---"
sudo ls -la /var/lib/beszel/beszel_data/ 2>/dev/null || sudo find /var/lib/beszel -maxdepth 2 -ls
echo ""
echo "--- 找 key 文件 ---"
sudo find /var/lib/beszel -name "*key*" -o -name "*.pem" 2>/dev/null | head -10
echo ""
echo "--- 搜 PocketBase DB 里的密钥 (若 db 是 sqlite) ---"
DB=$(sudo find /var/lib/beszel -name "*.db" 2>/dev/null | head -1)
echo "DB=${DB}"
if [ -n "$DB" ]; then
  sudo sqlite3 "$DB" ".tables" 2>/dev/null || echo "sqlite3 不可用"
fi
