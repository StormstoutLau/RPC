"""O-95 / O-96 护栏：**同机并发写 ⇒ 丢更新**的两处生产者（2026-09-26）。

为什么要有这条测试：两处的症状都是"**两个进程各自成功、但先写的那些 key/run 没了**" ——
盘上**没有任何报错**，锚也只在你**事后**去比时才发现不符。⇒ 只有构造**确定性交错**才能守。

被守的两条（都属"读 → 改 → 写"整文件）：
  · O-95 `inventory/audit-baseline/{host}.json` —— 同机两个 `--accept`
  · O-96 `archive/evidence-chain/agent-chain.json`（+ cold 镜像 + 锚）—— 两个 `cluster.py agent chain`

守的方式（**不用真并发碰运气**）：把"另一个进程"的写**注入到确定的位置**（第 2 次 `load` 时覆盖），
再断言 ① 本次的 key/run **最终都在盘上**（自愈）② `attempts > 1`（确实走了重试）
③ 幂等（重试**不重复入链**）④ 不收敛时**如实报 `race`**（不假装成功）。

用法（退出码 0 = 全过）：
    py tests\\test_station_write_races.py
"""
import json
import sys
import hashlib
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import cluster as C                                    # noqa: E402

fails = []
total = 0


def chk(name, cond, extra=""):
    global total
    total += 1
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


# ── 0. 结构护栏：重试与"如实报 race"必须真的在（防"写了但没跑"）──
src = (ROOT / "ops" / "cluster.py").read_text(encoding="utf-8")
chk("0a O-95 生产者含写后校验（verify 读回 + wanted 判定）",
    "on_disk = set(agent_audit_baseline_load()" in src and "if wanted <= on_disk:" in src)
chk("0b O-96 生产者含写后校验（on_disk 判定 + want）",
    "want = set(prepared)" in src and "if want <= on_disk:" in src)
chk("0c 两处都**如实报 race**（不假装成功）",
    src.count('"race": True') >= 2, f"count={src.count(chr(34) + 'race' + chr(34) + ': True')}")


def _tmp_baseline():
    """把 O-95 的基线目录指到临时目录（**必须**在模块常量上打补丁：函数读的就是它）。"""
    d = Path(tempfile.mkdtemp(prefix="o95-"))
    C.AGENT_AUDIT_BASELINE_DIR = d
    C.AGENT_AUDIT_BASELINE = d / "audit-baseline.json"
    return d


# ── A. O-95：注入"同机另一进程后写覆盖" ⇒ 必须自愈（且 attempts > 1）──
d = _tmp_baseline()
real_load = C.agent_audit_baseline_load
calls = {"n": 0}
FOREIGN = ["gap/foreign-process/wrote-later"]


def load_with_injection():
    """第 1 次真读；第 2 次（= 本次的**校验读**）注入"另一进程刚覆盖了本机分片"。"""
    calls["n"] += 1
    if calls["n"] == 2:
        tgt = d / f"{C._audit_host()}.json"
        tgt.write_text(json.dumps({"version": 1, "host": C._audit_host(),
                                   "keys": FOREIGN, "created": "", "updated": ""}),
                       encoding="utf-8")
        return {"version": 1, "keys": list(FOREIGN), "created": "", "updated": "", "sources": []}
    return real_load()


C.agent_audit_baseline_load = load_with_injection
res = C.agent_audit_baseline_accept(["gap/ours/a", "gap/ours/b"])
C.agent_audit_baseline_load = real_load
disk = set(real_load().get("keys") or [])
chk("A1 被覆盖后仍走重试（attempts > 1）", res.get("attempts", 0) > 1, f"attempts={res.get('attempts')}")
chk("A2 本次的 key **没丢**（自愈）", {"gap/ours/a", "gap/ours/b"} <= disk)
chk("A3 对方的 key **也在**（重试带上了刚读到的新并集）", set(FOREIGN) <= disk)
chk("A4 收敛 ⇒ 不报 race", not res.get("race"))

# ── B. O-95：永远不收敛 ⇒ **如实报 race**（宁可显式失败也不静默丢）──
d = _tmp_baseline()
real_load = C.agent_audit_baseline_load
C.agent_audit_baseline_load = lambda: {"version": 1, "keys": ["gap/someone-else"],
                                       "created": "", "updated": "", "sources": []}
res = C.agent_audit_baseline_accept(["gap/never"])
C.agent_audit_baseline_load = real_load
chk("B1 不收敛 ⇒ race=True（不假装成功）", res.get("race") is True, f"res={res}")
chk("B2 且试满 10 次（有界重试，不死循环）", res.get("attempts") == 10)

# ── C. O-95：重复 accept 幂等（added 空、键不重复）──
d = _tmp_baseline()
C.agent_audit_baseline_accept(["k1", "k2"])
again = C.agent_audit_baseline_accept(["k1", "k2"])
chk("C1 重复 accept ⇒ added 空（单调并集）", again.get("added") == [], f"added={again.get('added')}")
chk("C2 键不重复（无重复写入膨胀）",
    sorted(real_load().get("keys") or []) == ["k1", "k2"])

# ── D. O-96：注入"另一并发的 chain 后写覆盖" ⇒ 必须自愈且**外来 run 保留**──
d = Path(tempfile.mkdtemp(prefix="o96-"))
C.AGENT_CHAIN = d / "agent-chain.json"
C.AGENT_CHAIN_COLD = d / "cold" / "agent-chain.json"
C.AGENT_CHAIN_ANCHOR = d / "ANCHOR.txt"
FAKE_RUNS = [("20260101000000000001", "projA", d / "runs" / "r1"),
             ("20260101000000000002", "projA", d / "runs" / "r2")]
C._agent_proj_roots = lambda: ({"projA": d}, "")
C._chain_runs = lambda roots: list(FAKE_RUNS)
C._run_digest = lambda run_dir, recipe="v1": {"digest": "d" * 64, "files": []}
real_chain_load = C._chain_load
cl = {"n": 0}
FOREIGN_ENTRY = {"proj": "projB", "run_id": "20260101000000000099",
                 "digest": "e" * 64, "prev": "-", "files": [], "recipe": "v1"}


def chain_load_with_injection(p):
    """第 2 次（= 校验读）注入"另一进程刚写出一条自己的链"（不含我们的 run）。"""
    cl["n"] += 1
    if cl["n"] == 2:
        p.write_text(json.dumps({"version": 1, "entries": [FOREIGN_ENTRY]}, ensure_ascii=False),
                     encoding="utf-8")
    return real_chain_load(p)


C._chain_load = chain_load_with_injection
res = C.agent_chain_append()
C._chain_load = real_chain_load
disk_chain = json.loads(C.AGENT_CHAIN.read_text(encoding="utf-8"))
ids = {(e["proj"], e["run_id"]) for e in disk_chain["entries"]}
chk("D1 被覆盖后仍走重试（attempts > 1）", res.get("attempts", 0) > 1, f"attempts={res.get('attempts')}")
chk("D2 本次两个 run **都入链**（链丢 run 已治）",
    {("projA", FAKE_RUNS[0][0]), ("projA", FAKE_RUNS[1][0])} <= ids, f"ids={sorted(ids)}")
chk("D3 并发对方的条目**保留**（重试不抹掉别人）", ("projB", FOREIGN_ENTRY["run_id"]) in ids)
chk("D4 prev 仍串成序（首条指向外来条目的 digest）",
    disk_chain["entries"][1].get("prev") == FOREIGN_ENTRY["digest"],
    f"prev={disk_chain['entries'][1].get('prev', '')[:8]}")
chk("D5 收敛 ⇒ 不报 race", not res.get("race"))
chk("D6 锚与链成对写（锚文件已生成）", C.AGENT_CHAIN_ANCHOR.is_file())

# ── E. O-96：幂等 —— 再跑一次**不重复入链**（重试不产生重复条目是"自愈"的前提）──
res2 = C.agent_chain_append()
disk2 = json.loads(C.AGENT_CHAIN.read_text(encoding="utf-8"))
chk("E1 重复跑 ⇒ added 空", res2.get("added") == [], f"added={res2.get('added')}")
chk("E2 条目数不变（无重复膨胀）",
    len(disk2["entries"]) == len(disk_chain["entries"]),
    f"{len(disk2['entries'])} vs {len(disk_chain['entries'])}")

# ── F. 真并发冒烟：8 线程 × 各写不相交 key ⇒ 最终并集必须完整 ──
d = _tmp_baseline()
N_THREADS, PER = 8, 20
errs = []


def worker(i):
    try:
        C.agent_audit_baseline_accept([f"gap/t{i}/k{j}" for j in range(PER)])
    except Exception as e:                                   # noqa: BLE001
        errs.append(f"t{i}: {e.__class__.__name__}: {e}")


ts = [threading.Thread(target=worker, args=(i,)) for i in range(N_THREADS)]
[t.start() for t in ts]
[t.join() for t in ts]
union = set(real_load().get("keys") or [])
want_all = {f"gap/t{i}/k{j}" for i in range(N_THREADS) for j in range(PER)}
chk("F1 真并发无异常", not errs, str(errs[:2]))
chk("F2 真并发后并集完整（%d 个 key 一个不丢）" % len(want_all), want_all <= union,
    f"缺 {len(want_all - union)} 个")
chk("F3 无多余 key（并集语义，不做快照覆盖）", union == want_all, f"多 {len(union - want_all)} 个")

# ── G. O-96 真并发：8 线程各带自己的 run 集 ⇒ 链必须**一条不丢**（这是"锁 vs 重试"的分界）──
#   为什么必须有这条：D 段只模拟"2 方" ⇒ **重试**也能过。而 8 方时重试会**耗尽**（O-95 的 F 段实测
#   160 个 key 丢 80 个）⇒ 本条是"**必须用锁**"这一结论的守门测试。
d = Path(tempfile.mkdtemp(prefix="o96c-"))
C.AGENT_CHAIN = d / "agent-chain.json"
C.AGENT_CHAIN_COLD = d / "cold" / "agent-chain.json"
C.AGENT_CHAIN_ANCHOR = d / "ANCHOR.txt"
C._agent_proj_roots = lambda: ({"projA": d}, "")
tl = threading.local()


def runs_per_thread(roots):
    return [(f"20260301{i:014d}", "projA", d / "runs" / f"r{i}")
            for i in getattr(tl, "ids", [])]


C._chain_runs = runs_per_thread
C._run_digest = lambda run_dir, recipe="v1": {
    "digest": hashlib.sha256(str(run_dir).encode("utf-8")).hexdigest(), "files": []}

N_TH, PER_TH = 8, 3
t_errs, races = [], []


def chain_worker(i):
    tl.ids = [i * PER_TH + j for j in range(PER_TH)]
    try:
        r = C.agent_chain_append()
        if r.get("race"):
            races.append(f"t{i}")
    except Exception as e:                                   # noqa: BLE001
        t_errs.append(f"t{i}: {e.__class__.__name__}: {e}")


ts = [threading.Thread(target=chain_worker, args=(i,)) for i in range(N_TH)]
[t.start() for t in ts]
[t.join() for t in ts]
final_ids = {(e["proj"], e["run_id"])
             for e in json.loads(C.AGENT_CHAIN.read_text(encoding="utf-8"))["entries"]}
want_ids = {("projA", f"20260301{i:014d}") for i in range(N_TH * PER_TH)}
chk("G1 真并发无异常", not t_errs, str(t_errs[:2]))
chk("G2 真并发后**链一条不丢**（%d 条）" % len(want_ids), want_ids <= final_ids,
    f"缺 {len(want_ids - final_ids)} 条")
chk("G3 无重复条目（幂等 ∧ prev 串成序）",
    len(final_ids) == len(json.loads(C.AGENT_CHAIN.read_text(encoding='utf-8'))["entries"]))
chk("G4 无一方报 race（锁把冲突消掉了）", not races, str(races))

print("--------------------------------")
print(f"STATION_WRITE_RACES pass={total - len(fails)}/{total} fail={len(fails)}")
if fails:
    print("FAILED: " + ", ".join(fails))
# ★ O-89 纪律：门禁 `py-tests` 只认退出码 ⇒ 必须有 `RESULT:` 汇总行。
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
