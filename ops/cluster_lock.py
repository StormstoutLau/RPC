"""O-178：`cluster.py load` / `unload` 的**跨进程互斥**。

为什么需要
----------
2026-10-28 实测：两个 `load` 在同一秒停掉 A/B —— A 站 worker 刚停，B 站 head 就去取它的
显存（`ggml_backend_rpc_get_device_memory`）⇒ `ggml-rpc` 判致命 ⇒ `GGML_ABORT`，core-dump。
当时的修法是「head 先停、worker 后停」+「unload 不再三站齐发」，**但那两刀只保证单进程内
的顺序**，两个进程并发时仍可复现（台账 `O-178` 的剩余项）。

判据设计
--------
- **原子创建**：`os.open(..., O_CREAT|O_EXCL)` —— 创建成功即持锁，失败即有人在持；
- **不猜死活**：锁文件写 `pid / ts / cmd`；未超 `STALE_SEC` 一律当 **live** 拒绝；
- **崩溃可恢复**：超过 `STALE_SEC`（默认 1800s = 30 分钟，远大于一次加载的 10-15 分钟）
  才允许覆盖 —— 宁可多等，不可在别人加载中途抢锁；
- **只删自己的**：释放时校验 pid，避免 stale 覆盖后误删新持有者的锁；
- **逃生口**：`RPC_NO_LOCK=1`（测试/紧急）；`--force` **不复用**（它的语义是「明知会打断
 别人的 head 也继续」，与并发互斥是两件事）。
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCK = ROOT / "tmp" / ".cluster.lock"
# 一次真实加载 10-15 分钟（deepseek 145G）；取 30 分钟留足余量。
STALE_SEC = float(os.environ.get("RPC_LOCK_STALE_SEC", "1800"))


class ClusterLocked(RuntimeError):
    """另一个 cluster 进程正持锁。调用方应拒绝并**不做任何卸载动作**。"""


def cluster_lock_path() -> str:
    return str(DEFAULT_LOCK)


def read_lock(path=None) -> tuple[int, float, str] | None:
    """读锁文件；不存在/为空/读不了 ⇒ None。"""
    p = Path(path or DEFAULT_LOCK)
    try:
        txt = p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not txt:
        return None
    parts = txt.splitlines()
    try:
        pid = int(parts[0].strip())
    except (ValueError, IndexError):
        pid = 0
    try:
        ts = float(parts[1].strip())
    except (ValueError, IndexError):
        ts = 0.0
    cmd = " ".join(parts[2:]).strip()
    return pid, ts, cmd


def lock_state(path=None, now: float | None = None) -> tuple[str, int, float, str]:
    """`free` / `live` / `stale`。

    `stale` = 内容损坏（pid/ts 读不出）或已超过 `STALE_SEC` —— 两者都**可覆盖**。
    """
    info = read_lock(path)
    if info is None:
        return "free", 0, 0.0, ""
    pid, ts, cmd = info
    now = time.time() if now is None else now
    if pid <= 0 or ts <= 0:
        return "stale", pid, ts, cmd
    if now - ts > STALE_SEC:
        return "stale", pid, ts, cmd
    return "live", pid, ts, cmd


@contextmanager
def cluster_lock(purpose: str = "", path=None):
    """持锁执行；`ClusterLocked` 由调用方转成 exit 6（**不在这里静默跳过**）。"""
    if os.environ.get("RPC_NO_LOCK") == "1":
        yield
        return
    p = Path(path or DEFAULT_LOCK)
    p.parent.mkdir(parents=True, exist_ok=True)
    state, pid, ts, cmd = lock_state(p)
    if state == "live":
        age = int(time.time() - ts) if ts else 0
        raise ClusterLocked(
            f"另一个 cluster 进程正在运行 (pid={pid}, 已 {age}s, cmd={cmd or '?'})；"
            "等它结束，或确认无进程后删除锁文件"
        )
    if state == "stale":
        try:
            p.unlink()
        except OSError:
            pass
    try:
        fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        # stale 清理与另一进程抢跑：保守拒绝，不重试
        raise ClusterLocked(f"锁文件刚被另一进程创建：{p}") from exc
    try:
        cmdline = purpose or " ".join(sys.argv[1:])
        os.write(fd, f"{os.getpid()}\n{time.time():.0f}\n{cmdline}\n".encode("utf-8", "replace"))
    finally:
        os.close(fd)
    try:
        yield
    finally:
        info = read_lock(p)
        if info is not None and info[0] == os.getpid():
            try:
                p.unlink()
            except OSError:
                pass
