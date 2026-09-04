#!/bin/bash
# bs1-locktest.sh — BS-1: opencode.db 锁/写入特性探测 (只读, 不写生产db)
# 不需写真实表: 用独立临时db副本模拟并发写, 验证 SQLite 锁串行化事实
set -u
SRC="$HOME/.local/share/opencode/opencode.db"
TMPDB="/tmp/bs1-copy-$$.db"
echo "== 源 db (只读属性) =="; ls -l "$SRC"
echo "== journal_mode / busy_timeout (只读 PRAGMA) =="
sqlite3 "$SRC" "PRAGMA journal_mode;" 2>&1
sqlite3 "$SRC" "PRAGMA busy_timeout;" 2>&1
echo "== WAL + shared-memory 存在 =="
ls -l "$SRC-wal" "$SRC-shm" 2>&1
echo "== 并发写锁串行化事实验证 (用独立副本, 非生产) =="
if command -v sqlite3 >/dev/null 2>&1; then
  cp "$SRC" "$TMPDB" 2>/dev/null && echo "副本 $TMPDB"
  echo "--- 两并发写同一副本表 (autocommit) ---"
  T0=$(date +%s%N)
  sqlite3 "$TMPDB" "CREATE TABLE IF NOT EXISTS t_bs1(x); INSERT INTO t_bs1 SELECT 1 FROM (SELECT 1 UNION ALL SELECT 1 LIMIT 500);" &
  P1=$!
  sqlite3 "$TMPDB" "CREATE TABLE IF NOT EXISTS t_bs2(x); INSERT INTO t_bs2 SELECT 1 FROM (SELECT 1 UNION ALL SELECT 1 LIMIT 500);" &
  P2=$!
  wait $P1 $P2
  E0=$(date +%s%N); echo "并发写2进程_ms=$(( (E0-T0)/1000000 ))"
  T1=$(date +%s%N)
  sqlite3 "$TMPDB" "INSERT INTO t_bs1 SELECT 1 FROM (SELECT 1 UNION ALL SELECT 1 LIMIT 1000);"
  E1=$(date +%s%N); echo "单写同量_ms=$(( (E1-T1)/1000000 ))"
  echo "--- 若并发约=单写(无slowdown)=排它锁已关/可并行; 若并发>单写2x=写锁串行 ---"
else
  echo "本机无 sqlite3 CLI"
fi
rm -f "$TMPDB"
echo OK