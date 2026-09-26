"""`D7-P4-2 中断态两岸口径 + 不可信证据` 的正反注入 + **先验红** —— 永久护栏（2026-09-26）

守的是 **Ds 简报 11 / 18**：
  · 11（§4.5）**双向对称性检验（防死锁）** —— 两端都不把 `input-required` 当可完成态
    ⇒ 「D7 必须对同类中断态**双方同时声明**口径，否则**一端等待、一端失败的死锁**」；
  · 18（§4.11⑥）**把对方的文本当不可信证据**，其内部提及**不触发指令解析**。

★ 本文件最要紧的两条：
  1. ★★ **用真事故校准规则** —— `history` 里那条已修死锁，必须能被 `deadlock_risk()` **算出来**；
     算不出来就说明**判据是空转的**（而不是"没事故"）；
  2. ★★ **自报不算声明** —— 声称"已在某文件里声明不可信"的，必须去**那个文件里真找到**。

⚠ 另外守一条设计：`deadlock_risk` **不由真值表填**（自报 = 同一事实两个定义点）。
"""
import copy
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _ip(iid, **over):
    it = {"id": iid, "what": "w", "main_side": "m", "station_side": "s", "evidence": "e",
          "main_action": "self-contained", "station_action": "self-contained", "combined": "retry"}
    it.update(over)
    return it


def _doc(**over):
    base = {
        "interruptions": [_ip("i1")],
        "history": [{"id": "h1", "symptom": "s", "root_cause": "r", "fix": "f", "evidence": "e",
                     "as_pair": {"main_action": "self-contained", "station_action": "awaiting-peer"},
                     "expected_risk": "silent",
                     "regression_guard": {"kind": "fixture", "id": "o79①"}}],
        "untrusted_inputs": [{"id": "u1", "what": "w", "carrier": "c", "declared": False,
                              "why_not": "n/a"}],
        "trusted_inputs": [{"what": "x", "why": "y"}],
        "unverified": [{"item": "i", "why": "w"}],
    }
    base.update(over)
    return copy.deepcopy(base)


RISK_CASES = [
    ("risk 两侧都在等 ⇒ mutual", "awaiting-peer", "awaiting-peer", "mutual"),
    ("risk 主控等在等对方、站上自顾 ⇒ silent", "awaiting-peer", "self-contained", "silent"),
    ("risk 站上在等、主控自顾 ⇒ silent", "self-contained", "awaiting-peer", "silent"),
    ("★risk 一端等在等、另一端**主动解除** ⇒ none（方向反转对称）",
     "awaiting-peer", "unblocking-peer", "none"),
    ("★risk 一端在等、另一端**失败退出** ⇒ none（让对方等到一个结果，而不是空等）",
     "failing", "awaiting-peer", "none"),
    ("risk 两侧都不等 ⇒ none", "self-contained", "failing", "none"),
]

CASES = [
    # ── 正例 ──────────────────────────────────────────────────────────
    ("正例 最小合格", _doc(), True, "中断态 1 条"),
    ("★正例 一端等在等 + 另一端 failing ⇒ 不红（方向反转对称）",
     _doc(interruptions=[_ip("i1", main_action="failing", station_action="awaiting-peer")]),
     True, "有死锁风险的 0"),

    # ── 中止态：**两侧都要**（Ds 的死锁就出在"一端没写"）──────────────────
    ("★★反例 缺 `station_side` ⇒ **只有一端声明了口径**",
     _doc(interruptions=[{k: v for k, v in _ip("i1").items() if k != "station_side"}]),
     False, "只有一端声明了口径"),
    ("★反例 缺 `main_side`",
     _doc(interruptions=[{k: v for k, v in _ip("i1").items() if k != "main_side"}]),
     False, "只有一端声明了口径"),
    ("★反例 缺 `evidence`", _doc(interruptions=[_ip("i1", evidence="")]), False, "缺 `evidence`"),
    ("★★反例 `interruptions` 为空 ⇒ 中断态没有对象",
     _doc(interruptions=[]), False, "没有对象"),
    ("★反例 `main_action` 不在封闭集 ⇒ 谁在等谁判不了",
     _doc(interruptions=[_ip("i1", main_action="idle")]), False, "不在封闭集"),
    ("★反例 `combined` 不在封闭集",
     _doc(interruptions=[_ip("i1", combined="whatever")]), False, "不在封闭集"),

    # ── ★ 死锁风险：**由判据算** ────────────────────────────────────────
    ("★★反例 判出 silent 风险却**没有 `mitigation`**",
     _doc(interruptions=[_ip("i1", main_action="awaiting-peer",
                             station_action="self-contained")]),
     False, "没有 `mitigation`"),
    ("★正例 判出 silent 风险但**写了 mitigation** ⇒ 不红（点名在案）",
     _doc(interruptions=[_ip("i1", main_action="awaiting-peer", station_action="self-contained",
                             mitigation="30s 后取消")]),
     True, "有死锁风险的 1（i1:silent）"),

    # ── ★★ 用真事故校准规则 ─────────────────────────────────────────────
    ("★★反例 `history` 为空 ⇒ 修掉的静默死锁没登记",
     _doc(history=[]), False, "静默死锁没登记"),
    ("★★★反例 **规则算不出这条真事故**（把 as_pair 改成两侧都不等）",
     _doc(history=[dict(_doc()["history"][0],
                        as_pair={"main_action": "self-contained",
                                 "station_action": "self-contained"})]),
     False, "规则算不出这条真事故"),
    ("★★反例 `expected_risk` 填 none（历史死锁若算成 none 就不是死锁）",
     _doc(history=[dict(_doc()["history"][0], expected_risk="none")]), False, "expected_risk"),
    ("★反例 历史条目缺 `regression_guard`",
     _doc(history=[{k: v for k, v in _doc()["history"][0].items() if k != "regression_guard"}]),
     False, "没有护栏"),
    ("★反例 `regression_guard.kind` 不在封闭集",
     _doc(history=[dict(_doc()["history"][0], regression_guard={"kind": "manual", "id": "x"})]),
     False, "不在封闭集"),
    ("★反例 历史条目缺 `root_cause`",
     _doc(history=[{k: v for k, v in _doc()["history"][0].items() if k != "root_cause"}]),
     False, "缺 `root_cause`"),

    # ── 不可信输入（第 18 条）────────────────────────────────────────────
    ("★★反例 `untrusted_inputs` 为空 ⇒ 不可信证据没有对象",
     _doc(untrusted_inputs=[]), False, "没有对象"),
    ("★反例 `declared` 不是布尔",
     _doc(untrusted_inputs=[{"id": "u1", "what": "w", "carrier": "c", "declared": "yes"}]),
     False, "必须可判"),
    ("★反例 `declared: true` 却缺 `marker`（无法去文件里真找）",
     _doc(untrusted_inputs=[{"id": "u1", "what": "w", "carrier": "c", "declared": True,
                             "declared_in": "ops/x"}]),
     False, "自报不算"),
    ("★★反例 `declared: false` 却缺 `why_not` ⇒「没声明」也要给理由",
     _doc(untrusted_inputs=[{"id": "u1", "what": "w", "carrier": "c", "declared": False}]),
     False, "也要给理由"),
    ("★反例 `trusted_inputs` 为空 ⇒ 什么不算不可信没写",
     _doc(trusted_inputs=[]), False, "边界靠猜"),

    # ── 其它 ──────────────────────────────────────────────────────────
    ("★反例 缺 `unverified`", _doc(unverified=[]), False, "`unverified` 为空"),
    ("★反例 顶层不是映射", ["nope"], False, "顶层不是映射"),
]


def main() -> int:
    fails = []

    # ── `deadlock_risk()` 的四象限 ─────────────────────────────────────
    for desc, m, s, want in RISK_CASES:
        got, _why = R.deadlock_risk(m, s)
        ok = got == want
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        {m} × {s} ⇒ {got}（期望 {want}）")
        if not ok:
            fails.append(f"{desc} ⇒ 实测 {got}")

    # ── 结构自洽 ────────────────────────────────────────────────────────
    for desc, doc, want_ok, kw in CASES:
        bad, notes = R.validate_interruption(doc)
        blob = " ".join(bad) + " " + " ".join(notes)
        ok = ((not bad) == want_ok) and (kw in blob)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':{'在' if kw in blob else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} notes={notes}")

    # ── 端到端 ─────────────────────────────────────────────────────────
    real = None
    try:
        import yaml
        real = yaml.safe_load(R.INTERRUPT_INV.read_text(encoding="utf-8"))
        status, note, det = R.check_interruption(None)
        ok = status != "FAIL" and "中断态 3 条" in note
        print(f"  {'ok  ' if ok else 'FAIL'} 端到端 check_interruption ⇒ {status}\n        {note}")
        if not ok:
            fails.append(f"端到端不过: {status} {note} {det}")
    except ImportError:
        print("  skip 端到端（缺 pyyaml）")

    # ── ★★ 先验红自证（**在真文件上**）──────────────────────────────────
    if real is not None:
        muts = [
            ("把一条中断态改成**两侧都在等**却仍无 mitigation",
             lambda m: m["interruptions"][0].update(main_action="awaiting-peer",
                                                    station_action="awaiting-peer"),
             "没有 `mitigation`"),
            ("★把 `history.as_pair` 改成**两侧都不等**（真事故就「算不出来」了）",
             lambda m: m["history"][0].update(as_pair={"main_action": "self-contained",
                                                       "station_action": "self-contained"}),
             "规则算不出这条真事故"),
            ("把 `declared_in` 的 marker 改成一个文件里没有的词",
             lambda m: [u.update(marker="NO_SUCH_CLAUSE") for u in m["untrusted_inputs"]
                        if u.get("declared") is True],
             "自报不算声明"),
            ("把 `regression_guard.id` 改成一个不存在的夹具",
             lambda m: m["history"][0]["regression_guard"].update(id="o79-NOPE"),
             "护栏是空头的"),
        ]
        for desc, mut, kw in muts:
            m = copy.deepcopy(real)
            mut(m)
            st2, _n2, d2 = R.check_interruption(None, doc=m)
            red = st2 == "FAIL" and any(kw in x for x in d2)
            print(f"  {'ok  ' if red else 'FAIL'} 先验红自证：真文件上{desc} ⇒ 必须红（{'是' if red else '否'}）")
            if not red:
                fails.append(f"先验红自证失败：真文件上{desc} 没被拦（{st2} {d2}）")

    # ── 结构护栏 ────────────────────────────────────────────────────────
    ids = {c["id"] for c in R.CHECKS}
    if "interruption-untrusted" not in ids:
        fails.append("CHECKS 里没有 id='interruption-untrusted' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'interruption-untrusted' 已在 CHECKS 注册")
    # ★★ 设计护栏：`deadlock_risk` **不由真值表填**（自报 = 同一事实两个定义点）
    if real is not None:
        selfdecl = [it.get("id") for it in real.get("interruptions") or [] if "deadlock_risk" in it]
        print(f"  {'ok  ' if not selfdecl else 'FAIL'} ★ 结构护栏：真值表里**没有**自报的 "
              f"`deadlock_risk`（风险由判据算）{selfdecl}")
        if selfdecl:
            fails.append(f"真值表自报了 deadlock_risk: {selfdecl} ⇒ 应删除该字段（由判据算）")
    # ★ 签名护栏：第一参数必须是 ctx（否则 harness 传 {} 会被当成 doc）
    import inspect
    ps = list(inspect.signature(R.check_interruption).parameters)
    print(f"  {'ok  ' if ps[0] == 'ctx' else 'FAIL'} ★ 结构护栏：`check_interruption` 首参是 `ctx`（{ps}）")
    if ps[0] != "ctx":
        fails.append(f"check_interruption 首参不是 ctx（{ps}）⇒ harness 的 c['fn']({{}}) 会把它当 doc")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
