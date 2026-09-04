#!/bin/bash
# bs1-locktest.py — BS-1: opencode.db WAL 并发写锁串行化验证 (python sqlite3, 独立副本)
# 只读生产 db 特性 + 用副本测并发写时序
python3 - <<'PY'
import sqlite3, os, time, shutil, tempfile
src = os.path.expanduser("~/.local/share/opencode/opencode.db")
print("== 生产 db 只读特性 ==")
con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
print("journal_mode:", con.execute("PRAGMA journal_mode").fetchone())
try:
    print("busy_timeout(ms):", con.execute("PRAGMA busy_timeout").fetchone())
except Exception as e:
    print("busy_timeout err:", e)
print("wal_size:", os.path.getsize(src+'-wal') if os.path.exists(src+'-wal') else 0)
con.close()

print("== 用副本测并发写锁时序 (非生产) ==")
tmp = tempfile.mktemp(suffix='.db', prefix='bs1-', dir='/tmp')
shutil.copy(src, tmp)
c = sqlite3.connect(tmp)
c.execute("PRAGMA journal_mode=WAL")
c.execute("CREATE TABLE IF NOT EXISTS t_bs(x)")
c.execute("INSERT INTO t_bs SELECT 1 FROM (SELECT 1 UNION ALL SELECT 1 LIMIT 500)")
c.commit(); c.close()

def writer(n):
    cc = sqlite3.connect(tmp)
    t0 = time.time()
    cc.execute("INSERT INTO t_bs SELECT 1 FROM (SELECT 1 UNION ALL SELECT 1 LIMIT %d)" % n)
    cc.commit(); cc.close()
    return time.time()-t0

# 并发两写 (模拟两工作区同时 tool 写)
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(2) as ex:
    t0 = time.time()
    futs = [ex.submit(writer, 500), ex.submit(writer, 500)]
    [f.result() for f in futs]
    wall = time.time()-t0
print(f"并发2写同一db wall_ms={wall*1000:.1f}")

t0 = time.time(); writer(500); wall1 = time.time()-t0
t0 = time.time(); writer(500); wall2 = time.time()-t0
print(f"串行2写总_ms={(wall1+wall2)*1000:.1f} (各写 {wall1*1000:.1f}/{wall2*1000:.1f}ms)")
print("== 判定: 若并发wall≈串行total => 写锁串行化(BUSY/排队); 若near 1x => WAL可并行 ==")
os.remove(tmp)
PY
echo OK