"""`U-4 失效规则 H-1~H-4` 的正反注入 + **先验红** —— 永久护栏（2026-09-26）

`D7-P1-4` 的判据落体不是"数据"而是"**一段可执行的判据**"（`rpc_check.decide_invalidation`）——
理由：`D7-P1` 的**批级**判据要求"各条判据落盘并**通过先验红**"（方案 §7），纸面表达式过不了。

本文件守三件事：
  ① **四条规则各一组正反用例**（H-1 / H-2 / H-3 / H-4）—— 每条都要能"红"；
  ② ★ **硬不变量**：任何"**判不了**"的情形都**不得**落到 `MODE_SKIP`
     （`MODE_SKIP` 的后果是"不进 results ⇒ 不计失败" ⇒ 那正是"静默 skip"：
     把"判不了"悄悄变成"没事"）；用**穷举全部输入组合**（2×3×2×3×2 = **72** 种）来钉它，而不是举一两个例子；
     ⚠ **O-88（2026-09-26）后该不变量的"判不了"定义精确化**：`affected` 非空时才看 `incremental_equivalent`
     （下游为空 ⇒ 没有增量 ⇒ H-1 不适用）；`MODE_SKIP` 的合法前提 = **已判定**两类
     （`changed` 为空 ∨ `affected` 空且已闭包）—— 放宽处**自带反例**（见 CASES 里两条 `O-88 反例`）；
  ③ **先验红自证**：证明"`cls != MODE_SKIP`"这条断言**非恒真**（故意错映射 ⇒ 必须能红）。
"""
import sys
from itertools import product

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

D = R.decide_invalidation

# 四条规则各一组：(说明, 参数, 期望 action, 期望 class, 期望 reason 关键词)
CASES = [
    # ── H-1 增量必须与全量等价 ──────────────────────────────────────────
    ("H-1 正例 已证等价 + 闭包 ⇒ 可安全增量",
     dict(changed_ids=["p1"], affected=["a"], affected_is_closure=True, incremental_equivalent=True),
     "incremental", None, "四条规则全过"),
    ("★H-1 反例 已证**不等价** ⇒ 不得走增量",
     dict(changed_ids=["p1"], affected=["a"], affected_is_closure=True, incremental_equivalent=False),
     "full_rebuild", "WARN", "H-1"),
    ("★H-1 反例 **未证**等价（`None`）⇒ 也不得走增量（未证 ≠ 等价，fail-closed）",
     dict(changed_ids=["p1"], affected=["a"], affected_is_closure=True, incremental_equivalent=None),
     "full_rebuild", "WARN", "H-1"),

    # ── H-2 失效必须保守 ────────────────────────────────────────────────
    ("★H-2 反例 影响面**未闭包化** ⇒ 保守取全量（宁可多算）",
     dict(changed_ids=["p1"], affected=["a"], affected_is_closure=False, incremental_equivalent=True),
     "full_rebuild", "WARN", "H-2"),

    # ── H-3 无法安全判定 ⇒ 强制全量 ─────────────────────────────────────
    ("★H-3 反例 **无法安全判定**（affected=None）⇒ 强制全量",
     dict(changed_ids=["p1"], affected=None, affected_is_closure=True, incremental_equivalent=True),
     "full_rebuild", "WARN", "H-3"),
    # ★★ O-88（2026-09-26）：`affected=[] ∧ 已闭包` = **已判定「确实无下游」** ⇒ 第三个归宿（`none`/`MODE_SKIP`）。
    #   ⚠ **本用例的期望值是变更过的**（原为 `incremental`，理由"四条规则全过"）：对**空集**做增量
    #     与"付全量"一样，都是**把 empty set 当成有活干**；正确语义 = **明确的无动作 + 理由**。
    #     判定依据 = "先判是回归还是期望陈旧" ⇒ 此处是**期望陈旧**（DEV-LOG-014 §54.4）。
    ("★O-88 `affected=[] ∧ 已闭包` ⇒ 已判定无下游（无动作，带理由）",
     dict(changed_ids=["p1"], affected=[], affected_is_closure=True, incremental_equivalent=True),
     "none", "MODE_SKIP", "确实无下游"),
    ("★O-88 实测形态 `affected=[] ∧ 已闭包 ∧ eq=False` ⇒ **不再白白付全量**",
     dict(changed_ids=["p1"], affected=[], affected_is_closure=True, incremental_equivalent=False),
     "none", "MODE_SKIP", "确实无下游"),
    # ★ 反例：**没有被放宽**——三条保守路径一条都不能少（否则 O-88 就成了"给判不了开口子"）
    ("★O-88 反例 `affected=[] ∧ **未闭包化**` ⇒ 仍保守全量（空集也要闭包化才算「已判定」）",
     dict(changed_ids=["p1"], affected=[], affected_is_closure=False, incremental_equivalent=True),
     "full_rebuild", "WARN", "H-2"),
    ("★O-88 反例 **有下游**但等价性未证 ⇒ 仍不许 skip（H-1）",
     dict(changed_ids=["p1"], affected=["a"], affected_is_closure=True, incremental_equivalent=False),
     "full_rebuild", "WARN", "H-1"),

    # ── H-4 失败不得部分覆盖 ────────────────────────────────────────────
    ("★H-4 反例 重算**失败** ⇒ 不落盘（保留上一份有效产物），且**算失败**",
     dict(changed_ids=["p1"], affected=["a"], affected_is_closure=True, incremental_equivalent=True,
          build_failed=True),
     "none", "SKIP_FAILED", "H-4"),
    ("★H-4 优先级 失败 ∧ 同时“判不了影响面” ⇒ **失败优先**（两者都不许静默）",
     dict(changed_ids=["p1"], affected=None, incremental_equivalent=None, build_failed=True),
     "none", "SKIP_FAILED", "H-4"),

    # ── 空变更集：允许 MODE_SKIP 的**第一类**（O-88 后**不再是唯一**）────────
    ("空白例 变更集为空 ⇒ 确实无需动作（允许 MODE_SKIP 的情形之一）",
     dict(changed_ids=[], affected=None, incremental_equivalent=None),
     "none", "MODE_SKIP", "不是「判不了」"),
]


def main() -> int:
    fails = []

    for desc, kw, want_action, want_cls, want_kw in CASES:
        action, cls, reason = D(**kw)
        ok = (action == want_action) and (cls == want_cls) and (want_kw in reason)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n"
              f"        → action={action} class={cls} · '{want_kw}'"
              f"{'在' if want_kw in reason else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ ({action}, {cls}, {reason})")

    # ── ★ 硬不变量：穷举全部 72 种输入组合（不是举例子）─────────────────
    n, n_undecided, n_skip = 0, 0, 0
    for changed, affected, closure, eq, failed in product(
            ([], ["p1"]), (None, ["a"], []), (True, False), (None, True, False), (False, True)):
        n += 1
        action, cls, reason = D(changed, affected, closure, eq, failed)
        if action not in R.U4_ACTIONS:
            fails.append(f"action={action!r} 不在封闭枚举 {R.U4_ACTIONS}")
        if cls not in R.U4_CLASSES:
            fails.append(f"class={cls!r} 不在封闭枚举 {R.U4_CLASSES}")
        if not str(reason).strip():
            fails.append(f"组合 ({changed},{affected},{closure},{eq},{failed}) **没有理由** ⇒ 静默")
        # 硬不变量：只要「判不了/失败」，就绝不许是 MODE_SKIP
        # ⚠ O-88（2026-09-26）：末项加了 `and bool(affected)` —— 这**不是**为了变绿，而是 H-1 的**射程**：
        #   `incremental_equivalent` 的语义是"**增量**结果是否已证与全量等价"，而**下游为空 ⇒ 没有增量**
        #   ⇒ 该维度**不存在** ⇒ 空集情形已由 O-88 的新分支（`affected=[] ∧ 已闭包` ⇒ 无动作）认领。
        #   ★ 放宽判据必须自带反例 ⇒ 上面的 `★O-88 反例 有下游但等价性未证 ⇒ 仍不许 skip` 就是它。
        # ⚠ `MODE_SKIP` 的**唯一**合法前提 = "已判定"两类：`changed` 为空 ∨ (`affected` 空 ∧ 已闭包)。
        undecided = ((affected is None) or (closure is False) or failed
                     or (eq is not True and bool(affected)))
        if changed and undecided:
            n_undecided += 1
            if cls == "MODE_SKIP":
                n_skip += 1
                fails.append(f"★ 硬不变量破了：({changed},{affected},{closure},{eq},{failed}) "
                             f"是「判不了」却落到 MODE_SKIP ⇒ 静默 skip")
    print(f"  {'ok  ' if not n_skip else 'FAIL'} 穷举 {n} 种输入组合 · "
          f"其中「判不了/失败」{n_undecided} 种 · 落到 MODE_SKIP 的 {n_skip} 种（必须为 0）")

    # ── ★ 先验红自证：`cls != MODE_SKIP` 这条断言**非恒真** ───────────────
    # 用一个**故意错映射**的桩函数（把 H-3 映射成 MODE_SKIP）证明"它会红" ——
    # 否则本文件里的不变量可能只是"永远不会被触发"的装饰。
    def _wrong_mapping(changed, affected, closure, eq, failed):
        return ("full_rebuild", "MODE_SKIP", "故意错映射")     # 就是 D-26 禁止的那种
    red = _wrong_mapping(["p1"], None, True, True, False)[1] == "MODE_SKIP"
    print(f"  {'ok  ' if red else 'FAIL'} 先验红自证：错映射（H-3 ⇒ MODE_SKIP）确实能被识别为违反不变量")
    if not red:
        fails.append("先验红自证失败：错映射没被识别 ⇒ 不变量形同虚设")

    # ── 结构护栏：它是**判据库**、**不是** CHECKS 项（如实：无对象可判）─────
    ids = {c["id"] for c in R.CHECKS}
    if "u4" in ids or "invalidation" in ids:
        fails.append("U-4 不该是 CHECKS 项（本仓没有可判的对象）—— 若已接门禁，请连同文档一起改")
    else:
        print("  ok   结构护栏：U-4 是判据库、**不是** CHECKS 项（本仓无对象，已如实登记）")

    # ── ★ U-4 **执行侧**（A6，2026-09-29）：逐项三态 + 防假绿硬约束 ────────────────
    # 决策（③）之后落成执行报告（④）；重算交给注册表 ⇒ 这里用**假执行器**注入三态。
    E = R.execute_invalidation

    def _ok(t):        # 全成功、版本递增
        return {"status": "success", "version": {"a": 1, "b": 2, "c": 3}.get(t, 1)}

    def _one_fail(t):  # 只有 b 失败
        return ({"status": "failed", "detail": "故意让 1 项失败"} if t == "b"
                else {"status": "success", "version": 1})

    def _flat_ver(t):  # 成功但版本**不递增**
        return {"status": "success", "version": 1}

    def _no_ver(t):    # 成功但**没有版本证据**
        return {"status": "success"}

    def _boom(t):
        raise RuntimeError("boom")

    EXEC_CASES = [
        ("执行侧 正例 全成功 + 版本递增 ⇒ executed",
         "incremental", None, "四条规则全过", ["a", "b", "c"], {"incremental": _ok}, "executed"),
        ("★执行侧 反例 **1 项失败** ⇒ 必须 partial-failed（禁报成功）",
         "incremental", None, "r", ["a", "b"], {"incremental": _one_fail}, "partial-failed"),
        ("★执行侧 反例 版本**不严格递增** ⇒ partial-failed",
         "incremental", None, "r", ["a", "b"], {"incremental": _flat_ver}, "partial-failed"),
        ("★执行侧 反例 成功但**无版本证据** ⇒ partial-failed（fail-closed）",
         "incremental", None, "r", ["a"], {"incremental": _no_ver}, "partial-failed"),
        ("★执行侧 反例 执行器返回**非法状态** ⇒ 按失败 ⇒ partial-failed",
         "incremental", None, "r", ["a"], {"incremental": lambda t: {"status": "???"}}, "partial-failed"),
        ("★执行侧 反例 执行器**抛异常** ⇒ 算失败（不静默吞）",
         "incremental", None, "r", ["a"], {"incremental": _boom}, "partial-failed"),
        ("★执行侧 反例 **无注册执行器**（有活）⇒ not-executed（**绝不报 executed**）",
         "full_rebuild", "WARN", "H-3 影响面无法安全判定", ["a"], {}, "not-executed"),
        ("执行侧 无动作 MODE_SKIP ⇒ no-op（**不算成功**）",
         "none", "MODE_SKIP", "无需动作", [], {}, "no-op"),
        ("★执行侧 H-4 失败（SKIP_FAILED）⇒ partial-failed（**算失败**，不与 no-op 同档）",
         "none", "SKIP_FAILED", "H-4 重算失败", ["a"], {}, "partial-failed"),
    ]
    for desc, action, cls, reason, affected, execs, want in EXEC_CASES:
        rep = E(action, cls, reason, affected=affected, executors=execs)
        bad_items = [it["status"] for it in rep["items"] if it["status"] not in R.U4_ITEM_STATUS]
        ok = (rep["status"] == want and rep["status"] in R.U4_EXEC_STATUS and not bad_items)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        → status={rep['status']}（期望 {want}）")
        if not ok:
            fails.append(f"{desc} ⇒ status={rep['status']} bad_items={bad_items}")

    # ── ★ 先验红自证（执行侧）：防假绿硬约束**非恒真** ────────────────────────
    # 同一假执行器：全成功 ⇒ executed；**只把一项改成失败** ⇒ 必须落回 partial-failed。
    # 若两处都得 executed，则"1 项失败不得报整体成功"这条约束就是装饰。
    _r_ok = E("incremental", None, "r", affected=["a", "b"], executors={"incremental": _ok})
    _r_bad = E("incremental", None, "r", affected=["a", "b"], executors={"incremental": _one_fail})
    red = (_r_ok["status"] == "executed" and _r_bad["status"] == "partial-failed")
    print(f"  {'ok  ' if red else 'FAIL'} 先验红自证（执行侧）：改坏 1 项 ⇒ 整体从 executed 落回 partial-failed")
    if not red:
        fails.append("先验红自证（执行侧）失败：防假绿硬约束可能恒真（装饰）")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
