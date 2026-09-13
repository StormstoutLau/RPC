#!/usr/bin/env python3
# _bs1_iso.py — O-09 L1 判据探针: 隔离后并发写不再串行化 (共享db vs 独立db)
# 判据: 并发两写独立db墙钟 < 共享db基线(串行化); 独立db busy 命中 = 0。
# 复刻 _bs1.py "副本测时序非生产"范式; 两场景同用 busy_timeout=5000 (对齐站上), 测整批墙钟。
import sqlite3, os, time, tempfile, shutil
from concurrent.futures import ThreadPoolExecutor

def makedb(path, rows=500):
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    c.execute("CREATE TABLE IF NOT EXISTS t_bs(x)")
    c.execute("INSERT INTO t_bs SELECT 1 FROM (SELECT 1 UNION ALL SELECT 1 LIMIT %d)" % rows)
    c.commit(); c.close()

def onewrite(path, n=200000):
    t0 = time.time()
    c = sqlite3.connect(path, timeout=5)
    c.execute("BEGIN IMMEDIATE")
    # 递归 CTE 真实物化 n 行 (inner UNION 常量集只有2行, 必须显式生成才能放大工作量)
    c.execute("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x<%d) INSERT INTO t_bs(x) SELECT 1 FROM c" % n)
    c.commit(); c.close()
    return (time.time()-t0)*1000

def batch(paths, n=200000):
    """整批并发写, 返回批墙钟 + busy命中。"""
    busy = 0
    def w(p):
        nonlocal busy
        try:
            return onewrite(p, n)
        except sqlite3.OperationalError as e:
            if 'busy' in str(e).lower() or 'locked' in str(e).lower():
                busy += 1
            return 0
    t0 = time.time()
    with ThreadPoolExecutor(len(paths)) as ex:
        ws = list(ex.map(w, paths))
    return (time.time()-t0)*1000, busy, ws

def main():
    base = tempfile.mkdtemp(prefix='bs1-iso-')
    single = os.path.join(base, 'single.db'); makedb(single)
    wm = onewrite(single)
    # 场景A 现状基线: 两并发写同一个 db (busy_timeout=5000 -> 第二写等待锁, 串行化)
    shared = os.path.join(base, 'shared.db'); makedb(shared)
    wallA, busyA, _ = batch([shared, shared])
    # 场景B 隔离后: 两并发写各自 db (无锁竞争, 并行)
    iso1 = os.path.join(base, 'iso1.db'); makedb(iso1)
    iso2 = os.path.join(base, 'iso2.db'); makedb(iso2)
    wallB, busyB, _ = batch([iso1, iso2])

    print("== O-09 L1 判据 ==")
    print(f"单写基准 single_ms={wm:.1f}")
    print(f"A 共享db基线  : 并发2写同db   batch_wall_ms={wallA:.1f} (≈2x单写=串行化)  busy_hits={busyA}")
    print(f"B 独立db隔离  : 并发2写异db   batch_wall_ms={wallB:.1f} (≈1x单写=并行)   busy_hits={busyB}")
    ratio = wallB/wallA if wallA else 0
    print(f"墙钟比 B/A = {ratio:.2f}  (<1.0 => 不再串行化)")
    ok = (ratio < 0.9) and (busyB == 0)
    print("L1=" + ("PASS" if ok else "FAIL"))
    shutil.rmtree(base, ignore_errors=True)

main()