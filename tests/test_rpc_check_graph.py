"""D6-P0-1 断言依赖图的**正反注入**（永久护栏，2026-09-23）

为什么可以不改文件就做注入：判据被抽成**纯函数** `_validate_graph(checks)`。
护栏的意义：`needs` 一旦被引入（后续给断言加依赖），**未知 id / 成环必须当场红** ——
否则"级联"会变成静默漏跑（本仓"假绿"的头号形态）。

真值语义（`ops/rpc_check.py` main 的"非执行三分"）：
  · **MODE_SKIP**   = `--quick`/`--only` 未选中 ⇒ 合法，不计失败
  · **SKIP_FAILED** = `needs` 里有 FAIL/SKIP_FAILED ⇒ **算失败**（不许静默降级）
  · **WARN**        = 环境降级（如缺 paramiko）⇒ 不进 FAIL 集，但必须可见
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

CASES = [
    ("正例 真实 CHECKS（当前全靠空 needs）", R.CHECKS, True),
    ("正例 合法依赖链 a<-b", [{"id": "a"}, {"id": "b", "needs": ["a"]}], True),
    ("正例 空 needs（向后兼容）", [{"id": "a"}, {"id": "b"}], True),
    ("★反例 未知 id", [{"id": "a", "needs": ["nope"]}], False),
    ("★反例 成环 a->b->a", [{"id": "a", "needs": ["b"]}, {"id": "b", "needs": ["a"]}], False),
    ("★反例 自环 a->a", [{"id": "a", "needs": ["a"]}], False),
]


def main() -> int:
    fails = []
    for desc, checks, expect_ok in CASES:
        errs = R._validate_graph(checks)
        ok = not errs
        mark = "ok  " if ok == expect_ok else "FAIL"
        if ok != expect_ok:
            fails.append(f"{desc}: 期望 ok={expect_ok} 实得 ok={ok} errs={errs}")
        print(f"  {mark} {desc}  errs={errs}")

    # 结构性护栏：三分语义的标记必须齐（少一个就会有人在结论里把它算错桶）
    for key in ("PASS", "WARN", "FAIL", "SKIP_FAILED"):
        if key not in R.MARKS:
            fails.append(f"MARKS 缺 {key} ⇒ 结论区会把该类算错桶")
    if not hasattr(R, "MODE_SKIP"):
        fails.append("缺 MODE_SKIP ⇒ '模式性省略'与'级联失败'无法区分（三分语义失效）")
    print(f"\n  MARKS = {R.MARKS} · MODE_SKIP = {getattr(R, 'MODE_SKIP', None)}")
    print(f"  CHECKS 里已声明 needs 的条数 = {sum(1 for c in R.CHECKS if c.get('needs'))}")

    print(f"\n正反注入 {len(CASES)} 条 + 结构护栏 5 项")
    if fails:
        print("FAIL:")
        for x in fails:
            print("  ✗ " + x)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
