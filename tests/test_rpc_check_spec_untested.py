#!/usr/bin/env python3
"""`ops/rpc_check.py` 的 `check_spec_untested` 测试 —— **O-91**（2026-09-26）

判据 = **规范类文档**（`U[0-9]-*.md` / `D7-PROTOCOL-*.md`）必须带**非空**的 `## 未实测登记` 节。
形状与判据 `adr` 同源（锚精确节名 · 恰 1 个 · 节体 ≥1 列表项 或 ≥2 表格行 · 扫描只到下一个 H2）。

⚠⚠ **本判据的射程必须在这里被钉住**：它**只**保证「那一节在、且非空」，
  **不保证**「正文里没有无证据断言」—— 后者**不可机判**（见 `test_scope_is_only_the_section`）。

⚠ 本文件**自带 `__main__` 入口**：门禁 `py-tests` 以**脚本**方式调用（只认退出码）。
  没有它 ⇒ 被 import、定义一堆 `test_*`、正常退出 0 ⇒ 门禁报 PASS 而**一条都没跑**（O-89 实测过一次）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

DOC = "U4-INVALIDATION-RULES.md"   # 真实文件名的形状（用于构造正/反例，不读它）


def _doc(*, head="## 未实测登记", body="1. 只有文档，没有实现\n2. 无真实实例\n", extra=""):
    """构造一份最小规范：一个 H1 + 一个 `未实测登记` 节（body 可控）+ 可选附加。"""
    return f"# 示例规范\n\n引言。\n\n{head}\n\n{body}\n{extra}\n## 另一个节\n\nx\n"


# ── ① 正例 ───────────────────────────────────────────────────────────────
def test_positive_nonempty_list():
    bad, note = R.validate_spec_untested(_doc())
    assert bad == [], f"正例不该判红: {bad}"
    assert "列表项 2" in note


def test_positive_nonempty_table():
    bad, note = R.validate_spec_untested(_doc(body="| a | b |\n|---|---|\n| 1 | 2 |\n"))
    assert bad == [] and "表格行" in note


# ── ② 反例族 ─────────────────────────────────────────────────────────────
def test_missing_section_is_red():
    bad, _ = R.validate_spec_untested("# 示例规范\n\n只有正文，没有假设区。\n")
    assert bad and "缺" in bad[0]


def test_duplicate_section_is_red():
    bad, _ = R.validate_spec_untested(_doc() + "\n## 未实测登记\n\n1. 又写了一遍\n")
    assert any("只允许 1 个" in x for x in bad), f"重复节必须判红: {bad}"


def test_empty_section_is_red():
    """只写标题、后面直接是下一个 H2 ⇒ 空节。"""
    bad, _ = R.validate_spec_untested("# 示例规范\n\n## 未实测登记\n\n## 另一个节\n\nx\n")
    assert bad and "是空的" in bad[0]


def test_table_header_only_is_red():
    """★ 边界：**只有表头**（1 个表格行）⇒ 仍算空（ADR 同规则：≥2 行 = 表头+数据）。"""
    bad, _ = R.validate_spec_untested(_doc(body="| a | b |\n|---|---|\n"))
    assert bad and "是空的" in bad[0], f"只有表头必须判空: {bad}"


# ── ③ 边界：子节 **不截断**节体（与 ADR 同规则） ───────────────────────────
def test_subsection_does_not_truncate_body():
    """★ `### 子节` **属节体** —— 若按"任意标题"截断，会把这种（很常见的）写法判成空节。

    ⚠ 这条是"判据格式过窄 ⇒ 假红"的回归闸（ADR 判据的注释里记过同一个坑）。
    """
    text = "# 示例规范\n\n## 未实测登记\n\n### 1. 第一类\n\n1. 具体条目\n\n## 另一个节\n\nx\n"
    bad, note = R.validate_spec_untested(text)
    assert bad == [], f"子节里的列表项应算节体，不该判空: {bad}"
    assert "列表项 1" in note


# ── ④ ★★ 先验红：证明这条判据**不是恒真**，也**不是只看有没有那一行** ─────────
def _naive_has_head(text):
    """一个**只判"有没有那一行"**的桩（= 假绿版判据）。"""
    return None if "## 未实测登记" in text else "缺节"


def test_the_check_is_not_vacuous():
    """★★ 同一份**空节**文本：假绿桩放过它，真判据必须判红。

    没这条，"空节"这一类会**静默通过**（本仓头号形态：**判据什么都没判**）。
    """
    empty_section = "# 示例规范\n\n## 未实测登记\n\n## 另一个节\n\nx\n"
    assert _naive_has_head(empty_section) is None, "桩应当放过（证明假绿确实存在）"
    assert R.validate_spec_untested(empty_section)[0], "真判据必须判红"


# ── ⑤ ★★ 射程钉住：它**不判**正文里的无证据断言（别读过头） ─────────────────
def test_scope_is_only_the_section():
    """★★ 一份**满是凭印象断言**的正文，只要"那一节非空" ⇒ 本判据**会放行**。

    ⚠ 这不是缺陷，是**射程**：'无证据断言不得进正文'**不可机判**，**仍是纪律**。
      把它写成断言 ⇒ **假绿**（判据判了别的东西）。
    ⇒ 本测试的作用是**永久记录这条边界**：任何人想用本判据声称"断言已受控"，会先看到它。
    """
    text = ("# 示例规范\n\n"
            "据统计共 42 处站点（**没有任何取证**）。版本是 1.2.3（**凭印象**）。\n\n"
            "## 未实测登记\n\n1. 上述两个数都未实测\n")
    bad, _ = R.validate_spec_untested(text)
    assert bad == [], "本判据**只**看那一节；正文的无据断言**不**在射程内"


# ── ⑥ E 标报数：口径正确（`（E1）` 裸 vs `（E1，cmd）` 带取证） ───────────────
def test_emark_counting():
    text = "结论甲（E1）。结论乙（E1，`ps -o lstart`）。结论丙（E2，根因报告 §1）。结论丁（E4）。"
    hits = list(R.SPEC_EMARK_RE.finditer(text))
    assert len(hits) == 4, f"应命中 4 处，实际 {len(hits)}"
    bare = [m for m in hits if not m.group(2).strip(" ，,;；:：")]
    assert len(bare) == 2, f"裸标应 2 处，实际 {len(bare)}"


# ── ⑦ 端到端：真读本仓（含"命中集 ≥1"——防空判） ───────────────────────────
def test_repo_end_to_end():
    files = sorted({p for g in R.SPEC_UNTESTED_GLOBS for p in R.SPEC_DIR.glob(g)})
    assert files, "★ 命中集为空 ⇒ 判据**没有对象**（会退化成空判）"
    for p in files:
        bad, _ = R.validate_spec_untested(p.read_text(encoding="utf-8"))
        assert bad == [], f"{p.name} 应当合规: {bad}"


def test_entry_is_registered_and_quick():
    """结构护栏：本判据必须在 CHECKS 注册，且 **quick**（否则提交时跑不到）。"""
    ids = {c["id"]: c for c in R.CHECKS}
    assert "spec-untested" in ids, "spec-untested 未注册进 CHECKS"
    assert ids["spec-untested"]["quick"] is True, "spec-untested 必须 quick（否则提交时跑不到）"


# ── ⑧ ★★ O-123（2026-09-30）：把 `inventory/untested-index.yaml` 的分诊**接上消费者** ─────────
#   为什么加在这里而不是新开判据：**不新增 gate id**（本判据本来就管"未实测登记"这件事），
#     且不给手册/CHECKS 计数添负担 —— 索引的"叶子节点"缺口靠**既有**门禁补上。
#   ★ 口径（唯一判据）：`needs_decision: true` ⇒ **点名**（= 「**未裁项不许静默**」）。
#   ⚠ **不判**：分诊**写得对不对**（人工判断）；也**不重做**闭集校验（那是
#     `tests/test_untested_index_sync.py` 的职责 —— 判据只在一处）。
def _item(spec="U4-INVALIDATION-RULES", n=1, state="todo", blocker="implementation", nd=False):
    return {"spec": spec, "n": n, "state": state, "blocker": blocker, "needs_decision": nd}


def test_triage_counts_distribution():
    warn, st = R.summarize_untested_triage(
        [_item(), _item(state="boundary", blocker="none"), _item(state="retired", blocker="none")])
    assert st["n"] == 3, st
    assert st["state"]["todo"] == 1 and st["state"]["boundary"] == 1, st
    assert st["blocker"]["implementation"] == 1 and st["blocker"]["none"] == 2, st
    assert st["needs_decision"] == 0, st
    assert warn == [], "无未裁项 ⇒ 不该有告警"


def test_triage_needs_decision_warns():
    """★★ 本条唯一的**判据**：`needs_decision: true` ⇒ 点名（未裁项不许静默）。"""
    warn, st = R.summarize_untested_triage([_item(), _item(spec="U5-TRUST-BASIS", n=6, nd=True)])
    assert st["needs_decision"] == 1 and len(warn) == 1, (st, warn)
    assert "U5-TRUST-BASIS#6" in warn[0], warn


def test_triage_not_vacuous_and_empty_safe():
    """★ 边界/先验红：全 `needs_decision: false` 与**空输入**都不得告警、不得崩（防恒真）。"""
    assert R.summarize_untested_triage([])[0] == []
    assert R.summarize_untested_triage(None)[0] == []
    warn, st = R.summarize_untested_triage([_item(), _item(), _item()])
    assert warn == [] and st["needs_decision"] == 0, (warn, st)


def test_triage_repo_end_to_end():
    """端到端：真读本仓索引 ⇒ 条目 ≥1（防空判）且 `needs_decision` 当前应为 **0**。"""
    import yaml
    inv = yaml.safe_load(R.UNTESTED_INDEX.read_text(encoding="utf-8"))
    warn, st = R.summarize_untested_triage(inv.get("items"))
    assert st["n"] >= 1, "★ 条目为 0 ⇒ 消费没有对象（会退化成空判）"
    assert st["needs_decision"] == 0, f"仍有未裁项 ⇒ 必须被看见: {warn}"


def test_triage_wiring_is_visible_in_gate():
    """接线：门禁必须**报出**分诊分布（覆盖率），且用的是这个纯函数（不是另写一份判据）。"""
    src = (ROOT / "ops" / "rpc_check.py").read_text(encoding="utf-8")
    assert "summarize_untested_triage(" in src
    assert "索引分诊" in src, "门禁 note 里必须带上分诊分布（否则消费者=隐形）"


# ── 无 pytest 的自跑入口（本文件自己也要有！） ──────────────────────────────
def _run_all() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    fails = []
    for name, fn in tests:
        try:
            fn()
        except AssertionError as e:
            fails.append(name)
            print(f"  FAIL {name}: assert 失败 {e or ''}".rstrip())
        except Exception as e:
            fails.append(name)
            print(f"  FAIL {name}: {type(e).__name__}: {e}")
        else:
            print(f"  ok   {name}")
    print()
    if not tests:
        print("RESULT: FAIL 未发现任何 test_* 函数（入口本身坏了）")
        return 1
    print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
    print(f"  （{len(tests) - len(fails)}/{len(tests)} 通过）")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_run_all())
