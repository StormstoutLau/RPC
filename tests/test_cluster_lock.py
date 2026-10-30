"""O-178：`cluster_lock` 的契约与行为（跨进程互斥的唯一定义点）。

判据
----
- 四态：`free` / `live` / `stale`（超时）/ `stale`（内容损坏）；
- 持锁期间锁文件存在且写的是**本进程 pid**；退出即删除；
- **live 一律拒绝**（抛 `ClusterLocked`），stale 可覆盖；
- 释放只删**自己**的锁（不误删别人的）；
- `RPC_NO_LOCK=1` 完全旁路（测试/紧急）；
- CLI 契约：`cluster.py` 的 load 与 unload 分支都被锁包住，拒绝路径 `return 6`。

用法: py tests\\test_cluster_lock.py
"""
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import cluster_lock as cl  # noqa: E402

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def main() -> int:
    old_stale = cl.STALE_SEC
    old_no = os.environ.get("RPC_NO_LOCK")
    p = Path(ROOT / "tmp" / f".lock-test-{uuid.uuid4().hex[:8]}")

    try:
        cl.STALE_SEC = 60.0
        now = time.time()

        st = cl.lock_state(p, now=now)
        chk("无锁文件 ⇒ free", st[0] == "free", st)

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{os.getpid()}\n{int(now)}\nprobe\n", encoding="utf-8")
        st = cl.lock_state(p, now=now)
        chk("刚写的锁 ⇒ live", st[0] == "live" and st[1] == os.getpid(), st)

        st = cl.lock_state(p, now=now + 120)
        chk("超过 STALE_SEC ⇒ stale", st[0] == "stale", st)

        p.write_text("garbage\n", encoding="utf-8")
        st = cl.lock_state(p, now=now)
        chk("内容损坏 ⇒ stale（可覆盖，不永久锁死）", st[0] == "stale", st)

        p.unlink()
        with cl.cluster_lock(path=p, purpose="selftest"):
            info = cl.read_lock(p)
            chk("持锁时文件存在且写本进程 pid", info is not None and info[0] == os.getpid(), info)
        chk("退出 with 后锁文件已删除", not p.exists())

        p.write_text("999999\n" + str(int(now)) + "\nother\n", encoding="utf-8")
        blocked = False
        try:
            with cl.cluster_lock(path=p):
                pass
        except cl.ClusterLocked:
            blocked = True
        chk("他人持 live 锁 ⇒ 抛 ClusterLocked（不静默跳过）", blocked)
        p.unlink()

        p.write_text("999999\n" + str(int(now - 3600)) + "\nstale\n", encoding="utf-8")
        ok = False
        with cl.cluster_lock(path=p):
            ok = cl.read_lock(p)[0] == os.getpid()
        chk("stale 锁 ⇒ 可覆盖，且覆盖后写的是本进程 pid", ok)

        os.environ["RPC_NO_LOCK"] = "1"
        with cl.cluster_lock(path=p):
            pass
        chk("RPC_NO_LOCK=1 ⇒ 不创建/不校验锁文件", not p.exists())
    finally:
        cl.STALE_SEC = old_stale
        if old_no is None:
            os.environ.pop("RPC_NO_LOCK", None)
        else:
            os.environ["RPC_NO_LOCK"] = old_no
        try:
            p.unlink()
        except OSError:
            pass

    src = (ROOT / "ops" / "cluster.py").read_text(encoding="utf-8", errors="replace")
    chk("cluster.py: load 与 unload 都被 cluster_lock 包住", src.count("with cluster_lock(") >= 2,
        src.count("with cluster_lock("))
    chk("cluster.py: 拒绝路径 exit 6", src.count("return 6") >= 2, src.count("return 6"))
    chk("cluster.py: 复用 --force 之外提供逃生口提示", "RPC_NO_LOCK=1" in src)

    print("\nRESULT: " + ("ALL PASS" if not fails else f"FAIL ({len(fails)} 项) · " + ", ".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
