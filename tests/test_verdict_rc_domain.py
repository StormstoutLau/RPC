"""O-27 注入用例：`TASK_RC` 域判据 `_verdict_allowed`（裁定 b，2026-09-23）

为什么有这个测试
----------------
`evidence` 断言把 `.meta` 的 `TASK_RC` 与 `run.json` 的 `exit_code` 对账。旧实现里
`.meta` 记的是 **agent 码**，而 `run.json` 记的是 **整体码**（accept/golden 失败时脚本
`exit 9`，控制台再映射成 1）⇒ **两域不一致** ⇒ **每个"验收失败"的 run（agent 成功、
验收不过）都被判 FAIL 并阻断提交**（O-27，实测 `dogfood/202609232240596105`）。

修法 = **治同源**（裁定 b，**不是放宽判据**）：`.meta` 改为写**整体码**并加 `RC_DOMAIN=v2`；
断言**按域选集** —— v2 用原映射表（不放宽），无标记的历史 run 只做**有界宽容**（`0` → `{0,1}`）。

本文件是**正反注入**：既要证明新形态被接受，**更要证明"不一致仍会被拒"** ——
否则改法就只是把门拆掉了（本仓最忌的"假绿"）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import cluster  # noqa: E402

# (说明, TASK_RC, RC_DOMAIN, run.json exit_code, 期望该组合是否被允许)
CASES = [
    # ── v2：`.meta` 写整体码，与 run.json 同域 ──
    ("正例 v2 验收成功 (0⇄0)",              0, "v2",   0,  True),
    ("★反例 v2 两域不一致必须仍被拒",        0, "v2",   1,  False),
    ("正例 v2 验收失败的新正确形态 (9⇄1)",   9, "v2",   1,  True),
    ("正例 v2 兼容 claude 路未做映射 (9⇄9)", 9, "v2",   9,  True),
    ("正例 v2 超时 (6⇄6)",                  6, "v2",   6,  True),
    ("正例 v2 未知码自洽 (42⇄42)",          42, "v2",  42,  True),
    ("★反例 v2 未知码不一致 (42⇄43)",       42, "v2",  43,  False),
    # ── v1：无域标记的历史 run，只有界宽容 ──
    ("正例 v1 历史歧义被宽容 (0⇄1)",         0, None,   1,  True),
    ("★反例 v1 宽容是【有界】的 (0⇄9)",       0, None,   9,  False),
    ("正例 v1 既有超时条目 (124⇄6)",       124, None,   6,  True),
    ("正例 v1 验收失败既有条目 (9⇄1)",       9, None,   1,  True),
    # ── 域标记的健壮性 ──
    ("正例 域标记大小写/空白容错 (\" V2 \")", 0, " V2 ", 0, True),
]


def main() -> int:
    f = cluster._verdict_allowed
    fails = []
    for desc, rc, dom, ec, expect in CASES:
        allowed = f(rc, dom)
        got = ec in allowed
        mark = "ok " if got == expect else "FAIL"
        if got != expect:
            fails.append(f"{desc}: rc={rc} domain={dom!r} ec={ec} "
                         f"allowed={sorted(allowed)} 期望允许={expect} 实得={got}")
        print(f"  {mark} {desc}  (allowed={sorted(allowed)})")

    # 结构性护栏：v2 分支**不得**比 v1 更宽 —— 防"改法变成放宽"
    for rc in (0, 6, 9, 14, 24, 124):
        v2, v1 = f(rc, "v2"), f(rc, None)
        if not v2.issubset(v1):
            fails.append(f"v2 的允许集不是 v1 的子集 (rc={rc}: v2={sorted(v2)} v1={sorted(v1)})")

    print(f"\n正反注入用例 {len(CASES)} 条 · 护栏 6 条")
    if fails:
        print("FAIL:")
        for x in fails:
            print("  ✗ " + x)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
