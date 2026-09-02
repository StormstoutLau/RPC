#!/usr/bin/env bash
# ============================================================================
# backup-memories.sh — D5 L9: codex-memory 记忆数据手动备份 (B 站)
# 动作: memory.db 在线快照 (python sqlite backup API, 避免 WAL 捕获不一致)
#       + memories/ 目录 → ~/backups/memories-YYYYMMDD-HHMM.tar.gz
#       轮换: 保留最近 7 份
# 用法: bash backup-memories.sh   (建议纳入手动纪律: 每周或大变更前)
# ============================================================================
set -u
TS=$(date +%Y%m%d-%H%M)
DIR=~/backups
TMP=/tmp/mem-backup-$TS
mkdir -p "$DIR" "$TMP"

echo '=== 1. memory.db 在线快照:'
python3 - <<PYEOF
import sqlite3, os
src = os.path.expanduser('~/.local/share/opencode/memory.db')
dst = '$TMP/memory.db'
s = sqlite3.connect(src)
d = sqlite3.connect(dst)
s.backup(d)
d.close(); s.close()
print('快照:', dst, f'({os.path.getsize(dst)} bytes)')
PYEOF

echo '=== 2. memories/ 目录复制:'
cp -r ~/.local/share/opencode/memories "$TMP/memories"
find "$TMP/memories" -type f | wc -l | sed 's/^/  文件数: /'

echo '=== 3. 打包:'
tar -czf "$DIR/memories-$TS.tar.gz" -C "$TMP" .
ls -lh "$DIR/memories-$TS.tar.gz" | awk '{print "  " $5, $9}'

echo '=== 4. 轮换 (保留最近 7 份):'
ls -t "$DIR"/memories-*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm -v | sed 's/^/  删除: /'
echo '  现存备份:'
ls -t "$DIR"/memories-*.tar.gz 2>/dev/null | head -7 | sed 's/^/    /'

rm -rf "$TMP"
echo '=== 完成'
