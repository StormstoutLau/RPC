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

# ── O-99：**变异【本体】** 而非包装 ─────────────────────────────────────────────
# ★ 难点：本体的返回形状**各不相同**（`(bad, notes)` / `bool` / `str` / `dict`）⇒
#   手写"恒绿桩"必须知道类型，**自动构造不出来**。
# ★★ 解法 = **记忆化变异（memoization mutation）** —— **不依赖类型**：
#   把本体换成一个"**第一次真跑并记住结果，之后恒返回第一次的结果**"的桩。
#   ⇒ 含义 = "**该函数退化成了一个常量**"。若该测试**真的在断言它的行为**（正反例都喂），
#     第二个用例必然对不上 ⇒ **红**。若照样绿 ⇒ 这份测试**没在断言本体**。
#   ⚠ **已知的假阴性（如实写在 docstring 里）**：若测试**只调用一次**本体，记忆化桩与原函数
#     **完全等价** ⇒ 不会红 ⇒ 会被误判成 `DEFENSE_EMPTY`。⇒ 故本模式的结果**只作线索**，
#     并且**必须**与"该测试含正反例"的常识一起读（不单独当缺陷清单）。
DRIVER_UNITS = r'''
import sys, runpy
sys.path.insert(0, r"{ops}")
sys.path.insert(0, r"{root}")
import rpc_check as R
for _u in {units!r}:
    _orig = getattr(R, _u, None)
    if _orig is None:
        continue
    _cache = {{}}
    def _mk(o, c):
        def _memo(*a, **k):
            if "v" not in c:
                c["v"] = o(*a, **k)
            return c["v"]
        return _memo
    setattr(R, _u, _mk(_orig, _cache))
runpy.run_path(r"{test}", run_name="__main__")
'''


def judge_units(fn_name: str) -> list:
    """用 **AST** 找 `check_x` 函数体里**直接调用**的**同模块函数**（= 它的"本体"）。

    ★ 为什么需要它：本仓的测试纪律测的是**本体**（`validate_*`/`decide_*`/`parse_*`），
      而 `check_*` 只是把本体拼成 `(status, note, detail)` 的**薄包装** ⇒
      变异包装**测不出东西**（实测 `DEFENSE_EMPTY = 41/43`）。⇒ 变异对象必须换成**本体**。
    ⚠ 只取**直接调用**的一层（不做传递闭包）：传递闭包会把"整个模块"拉进来 ⇒ 变异面过大、
      红的原因不可归因（那正是"看起来更硬其实没读到"的反面：**看起来更硬其实读太多**）。
    """
    import ast
    src = (OPS / "rpc_check.py").read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == fn_name:
            called = []
            for sub in ast.walk(n):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                    nm = sub.func.id
                    if nm in defined and nm != fn_name and nm not in called:
                        called.append(nm)
            return called
    return []



def _called_names(path: Path) -> set:
    """AST 取测试文件里**真正被调用**的函数名集合（`Call(func=Name)`）。

    ★★ 为什么必须用 **AST** 而不是文本匹配（O-99 口径收紧的核心）：
      文本匹配会把**字符串/注释里的字面**也算成"调用" —— 本仓有一类**结构护栏**测试
      （`src.count("check_x(")` 那种对源码做文本扫描的断言）⇒ 于是那份测试被算作"测了 check_x"
      ⇒ 变异后当然照样绿 ⇒ **假 `DEFENSE_EMPTY`**。
      ★ 本会话已因"文本层当语义"吃过两次亏（O-87 · §64 的口径），**这次不用文本**。
    """
    import ast
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    return {n.func.id for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)} | \
           {n.func.attr for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}


def covering_tests(check_id: str, fn_name: str) -> list:
    """哪些测试文件**真的调用了**这条判据（= 其包装函数）。

    ★★ **口径两轮收紧（2026-09-26 实测教训，必须留档）**：
      第一版 = "文件里出现该 id 或函数名" ⇒ 抽样得 **12/12 全 `DEFENSE_EMPTY`** ——
      **不是"假防线"，而是候选集错**（测试**提到**某个词就被算作"测了那条判据"）。
      第二版（文本）仍有假阳性：**结构护栏**对源码做文本扫描，字面里含 `check_x(` ⇒ 又被算进来。
      第三版（**本版**）= **AST 调用集**，并**去掉**"按 `CHECKS` 表驱动"那条通道 ——
      那条通道命中的是 `test_rpc_check_three_classes.py` 这类**测调度器**的文件（注入假断言），
      **它们不跑真判据** ⇒ 变异后必然照样绿 ⇒ 是**交叉噪声**的来源。
    """
    return [p for p in sorted(TESTS.glob("test_*.py")) if fn_name in _called_names(p)]


def tests_calling_units(units: list) -> list:
    """哪些测试文件**真的调用了**这些"本体"函数（O-99：本体模式的候选集）。"""
    us = set(units)
    return [p for p in sorted(TESTS.glob("test_*.py")) if us & _called_names(p)]


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


def mutate_units(check: dict, test: Path, units: list) -> dict:
    """**变异本体**（O-99）：对照 + 记忆化变异 ⇒ 四态。"""
    rc0, _ = run_one(test)
    if rc0 != 0:
        return {"verdict": "BASELINE_RED", "rc_base": rc0, "rc_mut": None, "units": units}
    driver = DRIVER_UNITS.format(ops=str(OPS), root=str(ROOT), units=units, test=str(test))
    try:
        p = subprocess.run([sys.executable, "-c", driver], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300)
        rc1 = p.returncode
    except subprocess.TimeoutExpired:
        return {"verdict": "ERROR", "rc_base": rc0, "rc_mut": 124, "units": units}
    except Exception as e:                               # noqa: BLE001
        return {"verdict": "ERROR", "rc_base": rc0, "rc_mut": None, "units": units,
                "err": type(e).__name__}
    return {"verdict": "EFFECTIVE" if rc1 != 0 else "DEFENSE_EMPTY",
            "rc_base": rc0, "rc_mut": rc1, "units": units}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--id", action="append", default=[])
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--units", action="store_true",
                    help="O-99：变异【本体】（AST 提取同模块直接调用 + 记忆化桩）而非包装")
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
    elif a.units:
        # ★★ O-99（2026-09-26 实测）：**本体模式的候选必须是【全部判据】** ——
        #   因为实测 **"调用包装"的测试文件 = 0/35**（本仓测试全测本体）⇒
        #   若沿用"有测试引用包装"来选候选，本模式会**一条都不跑**（正是本批第一次实测踩到的）。
        target = rows if a.all else ([rows[0]] if a.sample else rows)
        if a.sample:
            step = max(1, len(rows) // a.sample)
            target = rows[::step][:a.sample]
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

    # ── O-99：**变异本体**（对比上面的"变异包装"）──
    # ★ 口径：候选 = **真的调用了该判据本体**的测试文件（AST）—— 不是"调用了包装"的文件。
    if a.units:
        print(f"[本体变异] 选中 {len(target)} 条（AST 提取同模块直接调用 + 记忆化桩）")
        tally, bad, nounit, notest = {}, [], [], []
        for r in target:
            us = judge_units(r["fn"])
            if not us:
                nounit.append(r["id"])
                tally["NO_UNIT"] = tally.get("NO_UNIT", 0) + 1
                continue
            utests = tests_calling_units(us)
            if not utests:
                notest.append(r["id"])
                tally["NO_TEST_UNIT"] = tally.get("NO_TEST_UNIT", 0) + 1
                continue
            for tp in utests:
                res = mutate_units(next(x for x in R.CHECKS if x["id"] == r["id"]), tp, us)
                v = res["verdict"]
                tally[v] = tally.get(v, 0) + 1
                mark = "  " if v == "EFFECTIVE" else "★ "
                print(f"  {mark}{r['id']:<18} × {tp.name:<40} {v}"
                      f"  (base={res['rc_base']} mut={res['rc_mut']}) units={','.join(us)[:60]}")
                if v != "EFFECTIVE":
                    bad.append({"id": r["id"], "test": tp.name, **res})
        print(f"[汇总·本体变异] " + " · ".join(f"{k}={v}" for k, v in sorted(tally.items())))
        if nounit:
            print("[NO_UNIT] AST 未找到同模块直接调用（待人工登记本体）: " + ", ".join(nounit))
        if notest:
            print("[NO_TEST_UNIT] 有本体但**无测试直接调用本体**（点名）: " + ", ".join(notest))
        if bad:
            print("[需处置]")
            for x in bad:
                print(f"  · {x['id']} × {x['test']} ⇒ {x['verdict']}")
        return 0

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
