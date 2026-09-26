"""`D7-P4-1 多轮闭环 + 轮数上限` 的正反注入 + **先验红** —— 永久护栏（2026-09-26）

守的是 **D7-P4-1 的退出判据**：「多轮闭环可跑；**轮数上限有判据**」。

★★ 本批实测抓到的真缺陷（本文件就是防它再回来）：**注释里的上限落后于代码** ——
   `agent-cli.ps1` 里**两处**写 `retry <=2`，而代码分别是 `-lt 3` 与 `-le 3`
   （O-46 把 cap 从 2 改成 3 时，注释没跟）。⇒ 故有 `prose_caps` **封闭集**：
   散文里的每一处上限都必须登记，且必须与代码一致；**新冒出一处**也要红。

★ 另一条要守住的是「**上限**」与「**正向终止**」**两半都要在**：
   上限只管"最多几轮"，"什么时候**可以停**"（EASE 早停）是另一半。
"""
import copy
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

PROBE = "tmp/_mr_probe.ps1"          # 只为"多处上限不一致 / 散文完整性"两条先验红而临时造
PROBE_ABS = ROOT / PROBE


def _loop(lid, **over):
    lp = {
        "id": lid, "kind": "advance", "what": "w", "carrier": "c", "evidence": "e",
        "delta": "none", "delta_note": "dn",
        # ★ 这一段**故意**含「继续」二字：第一版判据是**文本禁令**（禁"继续"）⇒ 在这里**当场假红**。
        #   现改为 `on_exceed_kind` 封闭枚举 ⇒ 本正例同时是"文本口径假阳性"的**回归护栏**。
        "on_exceed": "超限 ⇒ 升级（不是继续）", "on_exceed_kind": "escalate",
        "round_counter": {"kind": "shell-var", "var": "N", "how": "计数"},
        "cap_state": "capped", "max_rounds": 3,
        "stop_on_agreement": "一致即停", "stop_on_agreement_machine_readable": True,
    }
    lp.update(over)
    return lp


def _doc(**over):
    base = {
        "loops": [_loop("a")],
        "prose_words": ["retry"],
        "prose_caps": [{"file": "ops/station-bin/agent-cli.ps1", "line_token": "tok",
                        "word": "retry", "expect": 3, "why": "w"}],
        "unverified": [{"item": "i", "why": "w"}],
    }
    base.update(over)
    return copy.deepcopy(base)


CASES = [
    # ── 正例 ──────────────────────────────────────────────────────────
    ("正例 最小合格", _doc(), True, "闭环 1 条"),
    ("正例 `kind: retry` 也合法（但必须**分开标**）",
     _doc(loops=[_loop("a", kind="retry")]), True, "kind ['retry']"),

    # ── 上限：**三者必居其一**（漏写是本项最要防的形态）──────────────────
    ("★★反例 **`cap_state` 缺失** ⇒ 漏写上限（不许靠「没写就是没有」）",
     _doc(loops=[{k: v for k, v in _loop("a").items() if k != "cap_state"}]),
     False, "不在封闭集"),
    ("★反例 `cap_state: capped` 但 `max_rounds` 非正整数",
     _doc(loops=[_loop("a", max_rounds=0)]), False, "不是正整数"),
    ("★反例 `cap_state: capped` 但 `max_rounds` 缺",
     _doc(loops=[{k: v for k, v in _loop("a").items() if k != "max_rounds"}]),
     False, "不是正整数"),
    ("★★反例 `unbounded-by-design` 但缺 `unbounded_reason` ⇒ 与「忘了写」无法区分",
     _doc(loops=[_loop("a", cap_state="unbounded-by-design")]), False, "必须给理由"),
    ("★★反例 `undecided` 但缺 `needs_decision_by` ⇒ 未定也要写清等谁裁",
     _doc(loops=[_loop("a", cap_state="undecided")]), False, "等谁裁"),

    # ── kind / 轮次可数 ───────────────────────────────────────────────
    ("★反例 `kind` 不在封闭集（状态推进型与重试型**必须分开标**）",
     _doc(loops=[_loop("a", kind="loop")]), False, "分开标"),
    ("★反例 缺 `round_counter` ⇒ 轮次从哪来没写",
     _doc(loops=[{k: v for k, v in _loop("a").items() if k != "round_counter"}]),
     False, "轮次从哪来"),
    ("★反例 `round_counter.kind` 不在封闭集",
     _doc(loops=[_loop("a", round_counter={"kind": "vibes", "how": "h"})]), False, "不在封闭集"),
    ("★反例 `file-glob` 型缺 `glob`",
     _doc(loops=[_loop("a", round_counter={"kind": "file-glob", "how": "h"})]), False, "没给 `glob`"),
    ("★反例 `shell-var` 型缺 `var`",
     _doc(loops=[_loop("a", round_counter={"kind": "shell-var", "how": "h"})]), False, "没给 `var`"),

    # ── EASE：正向终止是另一半 ────────────────────────────────────────
    ("★★反例 缺 `stop_on_agreement` ⇒ 只管上限、不管「什么时候可以停」",
     _doc(loops=[{k: v for k, v in _loop("a").items() if k != "stop_on_agreement"}]),
     False, "正向终止条件"),
    ("★反例 `stop_on_agreement_machine_readable` 非布尔",
     _doc(loops=[_loop("a", stop_on_agreement_machine_readable="yes")]), False, "必须是布尔"),

    # ── 超限处置（**结构性枚举**，不是文本禁令）────────────────────────
    ("★正例 `on_exceed` 散文里含「继续」**也应当过**（文本口径会假红，已改成枚举）",
     _doc(loops=[_loop("a", on_exceed="这一步不再继续旧方案 ⇒ 升级")]), True, "闭环 1 条"),
    ("★反例 `on_exceed_kind` 不在封闭集",
     _doc(loops=[_loop("a", on_exceed_kind="keep-going")]), False, "不在封闭集"),
    ("★★反例 已有上限却把 `on_exceed_kind` 留 `undecided` ⇒ 上限只有一半",
     _doc(loops=[_loop("a", on_exceed_kind="undecided")]), False, "上限只有一半"),
    ("★反例 `on_exceed` 为空",
     _doc(loops=[_loop("a", on_exceed="")]), False, "缺 `on_exceed`"),

    # ── 散文上限 / 口径 ───────────────────────────────────────────────
    ("★★反例 `prose_words` 为空 ⇒ 散文上限没有扫描口径",
     _doc(prose_words=[]), False, "`prose_words` 为空"),
    ("★★反例 `prose_caps` 为空 ⇒ 注释里的上限没人管",
     _doc(prose_caps=[]), False, "`prose_caps` 为空"),
    ("★反例 `prose_caps` 的 `expect` 非整数",
     _doc(prose_caps=[{"file": "f", "line_token": "t", "worth": 1, "why": "w", "expect": "3"}]),
     False, "必须是整数"),
    ("★反例 `prose_caps` 缺 `line_token`",
     _doc(prose_caps=[{"file": "f", "why": "w", "expect": 3}]), False, "缺 `line_token`"),

    # ── 其它 ──────────────────────────────────────────────────────────
    ("★★反例 `loops` 为空 ⇒ 多轮闭环没有对象（退化空判）",
     _doc(loops=[]), False, "没有对象"),
    ("★反例 缺 `unverified`", _doc(unverified=[]), False, "`unverified` 为空"),
    ("★反例 顶层不是映射", ["nope"], False, "顶层不是映射"),
]


def main() -> int:
    fails = []

    for desc, doc, want_ok, kw in CASES:
        bad, notes = R.validate_multi_round(doc)
        blob = " ".join(bad) + " " + " ".join(notes)
        ok = ((not bad) == want_ok) and (kw in blob)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':{'在' if kw in blob else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} notes={notes}")

    # 先跑一次真读（后面多处要用）—— 与 `check_multi_round` 同源
    real = None
    status = note = ""
    try:
        import yaml
        real = yaml.safe_load(R.MULTI_ROUND_INV.read_text(encoding="utf-8"))
        status, note, det = R.check_multi_round(None)
    except ImportError:
        print("  skip 端到端（缺 pyyaml）")

    # ── 端到端 ─────────────────────────────────────────────────────────
    if real is not None:
        ok = status != "FAIL" and "闭环 3 条" in note
        print(f"  {'ok  ' if ok else 'FAIL'} 端到端 check_multi_round ⇒ {status}\n        {note}")
        if not ok:
            fails.append(f"端到端不过: {status} {note} {det}")
        # ★「绝不静默」：未定上限的闭环必须**点名**
        if status == "WARN":
            named = any("plan-review-loop" in x for x in det)
            print(f"  {'ok  ' if named else 'FAIL'} ★ WARN 时**点名**了上限未定的闭环（不静默）")
            if not named:
                fails.append(f"WARN 但没点名 ⇒ 静默降级：{det}")

    # ── ★★ 先验红自证（**在真文件上** + 真 `agent-cli.ps1`）───────────────
    if real is not None:
        muts = [
            ("把 `agent-resume.max_rounds` 改成 4（与代码不符）",
             lambda m: [lp.update(max_rounds=4) for lp in m["loops"] if lp["id"] == "agent-resume"],
             "与代码**不符**"),
            ("把一条 `cap_sites` 的 marker 改坏（实测 0 处）",
             lambda m: [lp["cap_sites"][0].update(marker="NO_SUCH_VAR")
                        for lp in m["loops"] if lp.get("cap_sites")],
             "实测到"),
            ("把散文上限的 `expect` 改成 2",
             lambda m: m["prose_caps"][0].update(expect=2), "散文上限与登记**不符**"),
        ]
        for desc, mut, kw in muts:
            m = copy.deepcopy(real)
            mut(m)
            st2, _n2, d2 = R.check_multi_round(None, doc=m)
            red = st2 == "FAIL" and any(kw in x for x in d2)
            print(f"  {'ok  ' if red else 'FAIL'} 先验红自证：真文件上{desc} ⇒ 必须红（{'是' if red else '否'}）")
            if not red:
                fails.append(f"先验红自证失败：真文件上{desc} 没被拦（{st2} {d2}）")

    # ── ★★ 两条**只能用临时探针**验的（真文件里造不出干净的反例）──────────
    try:
        PROBE_ABS.write_text(
            "# 探针: 两处**同值不同实现**与两处散文上限\n"
            "A=0\n"
            "while [ $A -lt 2 ]; do A=$((A+1)); done\n"
            "B=0\n"
            "while [ $B -lt 3 ]; do B=$((B+1)); done\n"
            "# probe prose one: retry <=9\n"
            "# probe prose two: retry <=3\n", encoding="utf-8")
        base = {
            "loops": [_loop("probe", cap_sites=[
                {"file": PROBE, "marker": "A", "op": "-lt", "where": "impl-A"},
                {"file": PROBE, "marker": "B", "op": "-lt", "where": "impl-B"}])],
            "prose_words": ["retry"],
            "prose_caps": [{"file": PROBE, "line_token": "probe prose two",
                            "word": "retry", "expect": 3, "why": "w"}],
            "unverified": [{"item": "i", "why": "w"}],
        }
        st3, _n3, d3 = R.check_multi_round(None, doc=copy.deepcopy(base))
        inc = st3 == "FAIL" and any("多处实现的上限不一致" in x for x in d3)
        print(f"  {'ok  ' if inc else 'FAIL'} ★★先验红：**两份实现上限不同值**（2 vs 3）⇒ 必须红"
              f"（{'是' if inc else '否'}）")
        if not inc:
            fails.append(f"多处上限不一致没被拦（{st3} {d3}）")
        uncov = st3 == "FAIL" and any("未登记的散文上限" in x for x in d3)
        print(f"  {'ok  ' if uncov else 'FAIL'} ★★先验红：文件里有**未登记**的散文上限 ⇒ 必须红"
              f"（{'是' if uncov else '否'}）")
        if not uncov:
            fails.append(f"未登记的散文上限没被拦（{st3} {d3}）")
    finally:
        if PROBE_ABS.exists():
            PROBE_ABS.unlink()

    # ── 结构护栏 ────────────────────────────────────────────────────────
    ids = {c["id"] for c in R.CHECKS}
    if "multi-round" not in ids:
        fails.append("CHECKS 里没有 id='multi-round' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'multi-round' 已在 CHECKS 注册")
    if real is not None:
        # ★ 本项的两半都要在真值表里：**上限** 与 **正向终止** 与 **超限处置**
        miss = [lp.get("id") for lp in real.get("loops") or []
                if not lp.get("stop_on_agreement") or not lp.get("on_exceed")
                or not isinstance(lp.get("cap_state"), str)]
        print(f"  {'ok  ' if not miss else 'FAIL'} 结构护栏：每条闭环都写了 上限状态 + 正向终止 + 超限处置"
              f"（缺: {miss}）")
        if miss:
            fails.append(f"真值表里有闭环缺三件之一: {miss}")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
