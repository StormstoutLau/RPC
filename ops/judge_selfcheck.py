"""D7-P2-3：**审判据自身** —— 恒真检测（变异法）+ 覆盖率对账（2026-09-26）。

**为什么要有**：合并稿 §8.2（CORAL 专设 `Evaluator Corrections`：`PRISM` 的
"failed placements silently skipped" ⇒ 计分虚高）与本机群 ADR-0007 的教训**同源**：
**「判据通过了，是因为它什么都没判」**。对策原话：
**「判据的『通过』与『没判』必须可区分，覆盖率是唯一手段」**（合并稿 §8.2）。

**恒真检测 = 变异法**：把某条判据的 `fn` 换成**恒绿桩**（`("PASS","STUB",[])`）再跑它的测试
⇒ **测试必须变红**。若**仍然全绿** ⇒ 那份测试**没有在测该判据**（= **假防线**）。
★ 为什么这条是"硬"的：它**不读文本、不猜语义**，只比较**行为差异** —— 与 O-87
（"文本层判不出'是不是历史记档'"）划清界限。

★★ **四态判定（禁止"基本通过"**，合并稿 §8.4 可迁移做法第一条）：
    · `EFFECTIVE`     = 对照绿 **且** 变异红 ⇒ 这份测试**真的在测**该判据
    · `DEFENSE_EMPTY` = 对照绿 **且** 变异绿 ⇒ **假防线**（点名）
    · `BASELINE_RED`  = 对照组本身就红 ⇒ **不能用它判变异**（点名；先修测试）
    · `ERROR`         = 子进程异常/超时 ⇒ 不假装

⚠⚠ **一个必须防的假绿**：桩的形状若写错（不是 `(status, note, detail)`），判据会**抛异常** ⇒
   `run_checks` 把它当 FAIL ⇒ 测试**也会红** ⇒ 于是"桩坏了"被读成"测试有效"。
   ⇒ 本脚本**自己断言桩形状**（`STUB_OK` 常量），并在产出里**显式写明**。

用法：
    py ops/judge_selfcheck.py --list            # 只做覆盖率对账（不跑变异，秒出）
    py ops/judge_selfcheck.py --sample 4        # 抽样跑 4 条（门禁 quick 用）
    py ops/judge_selfcheck.py --all             # 全部"有测试"的判据
    py ops/judge_selfcheck.py --id ledger-status  # 指定一条
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPS = ROOT / "ops"
TESTS = ROOT / "tests"
sys.path.insert(0, str(OPS))

import rpc_check as R                                    # noqa: E402

# 恒绿桩：形状**必须**与 `run_checks` 的契约一致（`(status, note, detail)`）。
STUB_OK = ('PASS', 'SELFCHECK_STUB', [])

DRIVER = r'''
import sys, runpy
sys.path.insert(0, r"{ops}")
sys.path.insert(0, r"{root}")
import rpc_check as R
def _stub(ctx):
    return {stub!r}
setattr(R, {fn!r}, _stub)
for _c in R.CHECKS:
    if _c.get("id") == {cid!r}:
        _c["fn"] = _stub
runpy.run_path(r"{test}", run_name="__main__")
'''


def covering_tests(check_id: str, fn_name: str) -> list:
    """哪些测试文件**真的测了**这条判据。

    ★★ **口径两轮收紧（2026-09-26 实测教训，必须留档）**：
      第一版口径 = "文件里出现该 id 或函数名" ⇒ 抽样 4 条判据得到 **12/12 全 `DEFENSE_EMPTY`**。
      ★ 但**那不是"假防线"的证据**，而是**候选集选错**：一个测试文件**提到** `evidence` 这个词
      （注释/别的用途）就被当成"测了 evidence 判据" ⇒ 把判据换成恒绿桩，它当然照样绿。
      ⇒ **口径错会让判据"看起来在报警"，而报的是它自己选错了对象**（本会话第三次踩同族）。
      收紧后只认两条通道（都要能"打到判据本体"）：
        ① **直接调用判据函数**：`check_<fn>(` —— 这才叫"测了这条判据"；
        ② **按 `CHECKS` 表驱动**：文件里同时出现 `CHECKS` 与该 id（`test_rpc_check_three_classes.py`
           那类注入用例走的就是这条）。
    """
    import re
    call_re = re.compile(r"\b" + re.escape(fn_name) + r"\s*\(")
    out = []
    for p in sorted(TESTS.glob("test_*.py")):
        t = p.read_text(encoding="utf-8", errors="replace")
        if call_re.search(t):
            out.append(p)
        elif "CHECKS" in t and check_id in t:
            out.append(p)
    return out


def run_one(path: Path) -> tuple:
    """跑一个测试文件 ⇒ `(rc, tail)`。"""
    try:
        p = subprocess.run([sys.executable, str(path)], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300)
        tail = (p.stdout or "")[-300:] + (p.stderr or "")[-200:]
        return p.returncode, tail
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:                               # noqa: BLE001
        return 125, f"{type(e).__name__}: {e}"


def mutate_one(check: dict, test: Path) -> dict:
    """对照组 + 变异组 ⇒ 四态。"""
    fn = check["fn"].__name__
    rc0, _ = run_one(test)                                # 对照：不替换
    if rc0 != 0:
        return {"verdict": "BASELINE_RED", "rc_base": rc0, "rc_mut": None}
    driver = DRIVER.format(ops=str(OPS), root=str(ROOT), stub=STUB_OK,
                           fn=fn, cid=check["id"], test=str(test))
    try:
        p = subprocess.run([sys.executable, "-c", driver], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300)
        rc1 = p.returncode
    except subprocess.TimeoutExpired:
        return {"verdict": "ERROR", "rc_base": rc0, "rc_mut": 124}
    except Exception as e:                               # noqa: BLE001
        return {"verdict": "ERROR", "rc_base": rc0, "rc_mut": None, "err": f"{type(e).__name__}"}
    return {"verdict": "EFFECTIVE" if rc1 != 0 else "DEFENSE_EMPTY",
            "rc_base": rc0, "rc_mut": rc1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--id", action="append", default=[])
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    # 自证桩形状（防"桩坏了"被读成"测试有效"）
    assert isinstance(STUB_OK, tuple) and len(STUB_OK) == 3 and STUB_OK[0] == "PASS", "STUB 形状错"

    rows, covered, untested = [], [], []
    for c in R.CHECKS:
        ts = covering_tests(c["id"], c["fn"].__name__)
        rows.append({"id": c["id"], "fn": c["fn"].__name__, "tests": [t.name for t in ts]})
        (covered if ts else untested).append(c["id"])

    if a.id:
        target = [r for r in rows if r["id"] in a.id]
    elif a.all:
        target = [r for r in rows if r["tests"]]
    elif a.sample:
        # 抽样口径：**固定**（不随机）—— 取前 N 条"有测试"的 + 若列表里有未覆盖的则**必含一条**，
        #   否则"未覆盖"这类永远进不了抽样视野。★ 固定而非随机 ⇒ 结果可复现、可对账。
        avail = [r for r in rows if r["tests"]]
        step = max(1, len(avail) // a.sample)
        target = avail[::step][:a.sample]
    else:
        target = []

    if a.list or not target:
        print(f"[覆盖率] 判据 {len(rows)} 条 · **有测试引用 {len(covered)}** · "
              f"**无测试引用 {len(untested)}**")
        if untested:
            print("  无测试引用（点名，不静默跳过）: " + ", ".join(untested))
        if a.json:
            print(json.dumps({"covered": covered, "untested": untested, "rows": rows},
                             ensure_ascii=False))
        return 0

    print(f"[覆盖率] 判据 {len(rows)} 条 · 有测试引用 {len(covered)} · 无测试引用 {len(untested)}")
    if untested:
        print("  无测试引用: " + ", ".join(untested))
    print(f"[变异] 选中 {len(target)} 条（每条 = 对照 + 变异，各一次子进程）")
    tally = {}
    bad = []
    for r in target:
        c = next(x for x in R.CHECKS if x["id"] == r["id"])
        for tname in r["tests"]:
            res = mutate_one(c, TESTS / tname)
            v = res["verdict"]
            tally[v] = tally.get(v, 0) + 1
            flag = "  " if v == "EFFECTIVE" else "★ "
            print(f"  {flag}{r['id']:<18} × {tname:<44} {v}"
                  f"  (base rc={res['rc_base']} mut rc={res['rc_mut']})")
            if v != "EFFECTIVE":
                bad.append({"id": r["id"], "test": tname, **res})
    print(f"[汇总] " + " · ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    if bad:
        print("[需处置]")
        for b in bad:
            print(f"  · {b['id']} × {b['test']} ⇒ {b['verdict']}")
    if a.json:
        print(json.dumps({"tally": tally, "bad": bad}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
