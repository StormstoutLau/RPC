"""D6-P0-1「**非执行三分**」的注入用例 —— 永久护栏（**三类各一**）

三分（唯一落点 = `rpc_check.run_checks`）：
  · **MODE_SKIP**   = 调用方**不给**它（`--quick`/`--only` 未选中）⇒ **不进 results ⇒ 不计失败**
  · **SKIP_FAILED** = `needs` 里有 FAIL/SKIP_FAILED ⇒ **算失败**（不许静默降级成 skip）
  · **WARN**        = **环境降级**（缺 paramiko/pyyaml 等）⇒ **不进 FAIL 集，但必须可见**

⚠ 本文件用**注入假断言**（不跑真 I/O）—— 这正是把执行循环抽成 `run_checks` 的目的。
⚠ 三类的**后果必须不同**，否则"三分"就退化成"一句话含糊"（本仓头号失败形态）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _fake(cid, status, needs=None):
    return {"id": cid, "title": cid, "quick": True, "needs": needs or [],
            "fn": (lambda s, c: (lambda ctx: (s, f"{c} {s}", [])))(status, cid)}


def main() -> int:
    fails = []
    # 假断言集：up=真 FAIL · dep=依赖 up ⇒ 级联 · env=环境降级(WARN) · ok=正常
    ALL = [_fake("up", "FAIL"), _fake("dep", "PASS", needs=["up"]),
           _fake("env", "WARN"), _fake("ok", "PASS")]

    res, nfail = R.run_checks(ALL)
    st = {r[0]: r[2] for r in res}

    # ② SKIP_FAILED：needs 未满足 ⇒ **算失败**（会阻断）
    ok2 = st.get("dep") == "SKIP_FAILED" and nfail == 2 and st.get("up") == "FAIL"
    print(f"  {'ok  ' if ok2 else 'FAIL'} [类② SKIP_FAILED] needs 未满足 ⇒ 算失败 "
          f"（{st} · failures={nfail}）")
    if not ok2:
        fails.append(f"类② 不对: {st} failures={nfail}")

    # ③ WARN：环境降级 ⇒ **不计失败**、但**在 results 里可见**
    ok3 = st.get("env") == "WARN" and nfail == 2 and any(r[0] == "env" for r in res)
    print(f"  {'ok  ' if ok3 else 'FAIL'} [类③ WARN] 环境降级 ⇒ 不计失败但仍可见 "
          f"（failures 仍 {nfail}）")
    if not ok3:
        fails.append(f"类③ 不对: {st} failures={nfail}")

    # ① MODE_SKIP：**不给它** ⇒ 不进 results ⇒ 不计失败（与类②严格不同）
    res1, nfail1 = R.run_checks([c for c in ALL if c["id"] in ("env", "ok")])
    ids1 = {r[0] for r in res1}
    ok1 = nfail1 == 0 and "up" not in ids1 and "dep" not in ids1
    print(f"  {'ok  ' if ok1 else 'FAIL'} [类① MODE_SKIP] 未选中 ⇒ 不进 results、不计失败 "
          f"（ids={sorted(ids1)} · failures={nfail1}）")
    if not ok1:
        fails.append(f"类① 不对: ids={ids1} failures={nfail1}")

    # ④ ★ 三者后果**互不相同**（"三分"的全部意义：机器可区分）
    ok4 = (st.get("dep") == "SKIP_FAILED" and st.get("env") == "WARN"
           and st.get("dep") != st.get("env") and nfail != nfail1)
    print(f"  {'ok  ' if ok4 else 'FAIL'} [互斥] 三类后果不同：SKIP_FAILED 计失败 · WARN 不计 · 未选中不计")
    if not ok4:
        fails.append("三类后果未区分")

    # ⑤ 结构护栏：三分所需符号都在（改坏任一 ⇒ 语义坍塌）
    if not (hasattr(R, "MODE_SKIP") and "SKIP_FAILED" in R.MARKS and "WARN" in R.MARKS):
        fails.append("缺 MODE_SKIP / SKIP_FAILED / WARN 之一 ⇒ 三分语义坍塌")
    else:
        print(f"  ok   结构护栏：MODE_SKIP={R.MODE_SKIP} · MARKS={R.MARKS}")

    # ⑥ 行为等价：`main()` 已改用 `run_checks`，对**真断言**仍要走通（缝没改行为）
    real, _rf = R.run_checks([c for c in R.CHECKS if c["id"] == "syntax"])
    ok6 = (len(real) == 1 and real[0][0] == "syntax"
           and real[0][2] in ("PASS", "WARN", "FAIL", "SKIP_FAILED"))
    print(f"  {'ok  ' if ok6 else 'FAIL'} [等价] 真断言走同一缝：syntax → "
          f"{real[0][2] if real else '?'}")
    if not ok6:
        fails.append(f"run_checks 对真 CHECKS 行为异常: {real}")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
