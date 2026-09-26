"""`D7-P4-3 rubric + 自环盲区` 的正反注入 + **先验红** —— 永久护栏（2026-09-26）

守的是 **Ds 简报 15 / 12 / 21**：
  · 15（§4.10④）rubric **只报本次引入的问题**（防意见被历史债务淹没）；
  · 12（§4.7）**自环盲区显式登记**（三站自环 ≠ 异构第三方）；
  · 21（§4.13）派生边表 ⇒ 路线总表 §4.5 已列**非范围** ⇒ 只登记**触发条件**。

★ 本文件最要紧的两条：
  1. ★★ **必含句要"真找到"** —— rubric 是纯文本资源，删掉一句没人会知道；
  2. ★★ **`impl-same-source` 盲区必须在案** —— 三站互审走**同一份实现**，
     同源代码的缺陷**互审在结构上发现不了**（与"跨站≠跨族"正交）。
"""
import copy
import inspect
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

KNOWN = {"ps1-golden", "model-families", "secrets"}


def _bs(bid, kind="implementation", guard=None, **over):
    b = {"id": bid, "what": "w", "kind": kind, "why_blind": "互审看不见的理由", "evidence": "e",
         "other_guard": guard if guard is not None else {"kind": "check", "ref": "ps1-golden", "why": "w"}}
    b.update(over)
    return b


def _doc(**over):
    base = {
        "rubric": {
            "file": "ops/station-bin/review/rubric-4level.txt",
            "reader": {"file": "ops/station-bin/agent-cli.ps1",
                       "marker": "[System.IO.File]::ReadAllText", "why": "显式 UTF-8"},
            "must_contain": [{"id": "only-new-issues", "marker": "只报本次新引入的问题",
                              "why": "第 15 条"}],
        },
        "blindspots": [_bs("impl-same-source")],
        "derived_edges": {"status": "deferred", "condition": "九项目中任一提需求时", "why": "w"},
        "unverified": [{"item": "i", "why": "w"}],
    }
    base.update(over)
    return copy.deepcopy(base)


CASES = [
    # ── 正例 ──────────────────────────────────────────────────────────
    ("正例 最小合格", _doc(), True, "rubric 必含 1 条"),

    # ── rubric：必含句 ────────────────────────────────────────────────
    ("★反例 缺 `rubric.file` ⇒ rubric 落点没写",
     _doc(rubric={k: v for k, v in _doc()["rubric"].items() if k != "file"}),
     False, "rubric 落点没写"),
    ("★★反例 `must_contain` 为空 ⇒ 关键纪律被删掉也没人知道",
     _doc(rubric=dict(_doc()["rubric"], must_contain=[])), False, "关键纪律被删掉"),
    ("★反例 必含条缺 `why`",
     _doc(rubric=dict(_doc()["rubric"], must_contain=[{"id": "x", "marker": "m"}])),
     False, "缺 `why`"),
    ("★反例 必含条 `id` 重复",
     _doc(rubric=dict(_doc()["rubric"], must_contain=[
         {"id": "x", "marker": "m", "why": "w"}, {"id": "x", "marker": "m2", "why": "w"}])),
     False, "重复"),
    ("★反例 `rubric.reader` 缺 `marker`",
     _doc(rubric=dict(_doc()["rubric"], reader={"file": "ops/x", "why": "w"})),
     False, "缺 `file` / `marker`"),
    ("★反例 `rubric.reader` 缺 `why` ⇒ 没说清为什么显式编码",
     _doc(rubric=dict(_doc()["rubric"],
                      reader={"file": "ops/x", "marker": "m"})), False, "为什么要显式编码"),

    # ── 自环盲区 ──────────────────────────────────────────────────────
    ("★★反例 缺 `impl-same-source` ⇒ **本仓最实质的盲区没登记**",
     _doc(blindspots=[_bs("other-blindspot", kind="dispatch")]), False, "impl-same-source"),
    ("★反例 `blindspots` 为空 ⇒ 自环盲区没登记",
     _doc(blindspots=[]), False, "没有登记"),
    ("★★反例 缺 `why_blind` ⇒ 没说清为什么互审看不见",
     _doc(blindspots=[{k: v for k, v in _bs("impl-same-source").items() if k != "why_blind"}]),
     False, "为什么互审看不见"),
    ("★反例 `kind` 不在封闭集",
     _doc(blindspots=[_bs("impl-same-source", kind="vibes")]), False, "不在封闭集"),
    ("★反例 缺 `other_guard` ⇒ 没写别的机制覆盖它",
     _doc(blindspots=[{k: v for k, v in _bs("impl-same-source").items() if k != "other_guard"}]),
     False, "别的机制"),
    ("★★反例 `other_guard.kind=check` 但 ref **不是已注册的 CHECKS id**（挂名）",
     _doc(blindspots=[_bs("impl-same-source", guard={"kind": "check", "ref": "ghost-check"})]),
     False, "不是已注册的 CHECKS id"),
    ("★反例 `other_guard.kind=test` 但测试文件不存在",
     _doc(blindspots=[_bs("impl-same-source", guard={"kind": "test", "ref": "test_nope.py"})]),
     False, "不存在"),
    ("★★反例 `other_guard` 是 `na` 但缺 `why` ⇒「没有替代机制」也要给理由",
     _doc(blindspots=[_bs("impl-same-source", guard={"kind": "na"})]), False, "也要给理由"),
    ("★正例 `other_guard` 是 `na` 且给了理由 ⇒ 不红（点名在案）",
     _doc(blindspots=[_bs("impl-same-source", guard={"kind": "na", "why": "本仓不在该范围"})]),
     True, "无替代机制的 1"),

    # ── 派生边表 ──────────────────────────────────────────────────────
    ("★★反例 `derived_edges` 是 `deferred` 但缺 `condition` ⇒ 触发条件没写死",
     _doc(derived_edges={"status": "deferred", "why": "w"}), False, "触发条件没写死"),
    ("★反例 `derived_edges.status` 不在封闭集",
     _doc(derived_edges={"status": "maybe", "why": "w"}), False, "不在封闭集"),
    ("★反例 缺 `derived_edges` 段 ⇒ 第 21 条连登记都没有",
     _doc(derived_edges=None), False, "连登记都没有"),

    # ── 其它 ──────────────────────────────────────────────────────────
    ("★反例 缺 `unverified`", _doc(unverified=[]), False, "`unverified` 为空"),
    ("★反例 顶层不是映射", ["nope"], False, "顶层不是映射"),
]


def main() -> int:
    fails = []

    for desc, doc, want_ok, kw in CASES:
        bad, notes = R.validate_rubric_blindspot(doc, known_checks=KNOWN)
        blob = " ".join(bad) + " " + " ".join(notes)
        ok = ((not bad) == want_ok) and (kw in blob)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':{'在' if kw in blob else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} notes={notes}")

    # ── 端到端 ─────────────────────────────────────────────────────────
    real = None
    try:
        import yaml
        real = yaml.safe_load(R.RUBRIC_INV.read_text(encoding="utf-8"))
        status, note, det = R.check_rubric_blindspot(None)
        ok = status != "FAIL" and "rubric 必含 5 条" in note
        print(f"  {'ok  ' if ok else 'FAIL'} 端到端 check_rubric_blindspot ⇒ {status}\n        {note}")
        if not ok:
            fails.append(f"端到端不过: {status} {note} {det}")
        # ★★ rubric 里那 5 句**真在**（不是自报）
        rb = real.get("rubric") or {}
        txt = (ROOT / str(rb.get("file"))).read_text(encoding="utf-8", errors="replace")
        missing = [m.get("id") for m in rb.get("must_contain") or [] if m.get("marker") not in txt]
        print(f"  {'ok  ' if not missing else 'FAIL'} ★ rubric 必含句**逐个真找到**（缺: {missing}）")
        if missing:
            fails.append(f"rubric 缺必含句: {missing}")
    except ImportError:
        print("  skip 端到端（缺 pyyaml）")

    # ── ★★ 先验红自证（**在真文件上**）──────────────────────────────────
    if real is not None:
        muts = [
            ("把某条必含句的 marker 改成文件里没有的词",
             lambda m: m["rubric"]["must_contain"][0].update(marker="NO_SUCH_CLAUSE"), "找不到"),
            ("把 `impl-same-source` 盲区删掉",
             lambda m: m.__setitem__("blindspots",
                                     [b for b in m["blindspots"] if b["id"] != "impl-same-source"]),
             "impl-same-source"),
            ("把 `reader.marker` 改成 agent-cli.ps1 里没有的串",
             lambda m: m["rubric"]["reader"].update(marker="NO_SUCH_READER"), "找不到"),
            ("清空 `derived_edges.condition`",
             lambda m: m["derived_edges"].update(condition=""), "触发条件没写死"),
            ("把某条盲区的 `other_guard.kind` 改成 `na` 且不给理由",
             lambda m: m["blindspots"][0].update(other_guard={"kind": "na"}), "也要给理由"),
        ]
        for desc, mut, kw in muts:
            m = copy.deepcopy(real)
            mut(m)
            st2, _n2, d2 = R.check_rubric_blindspot(None, doc=m)
            red = st2 == "FAIL" and any(kw in x for x in d2)
            print(f"  {'ok  ' if red else 'FAIL'} 先验红自证：真文件上{desc} ⇒ 必须红（{'是' if red else '否'}）")
            if not red:
                fails.append(f"先验红自证失败：真文件上{desc} 没被拦（{st2} {d2}）")

    # ── 结构护栏 ────────────────────────────────────────────────────────
    ids = {c["id"] for c in R.CHECKS}
    if "rubric-blindspot" not in ids:
        fails.append("CHECKS 里没有 id='rubric-blindspot' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'rubric-blindspot' 已在 CHECKS 注册")
    ps = list(inspect.signature(R.check_rubric_blindspot).parameters)
    print(f"  {'ok  ' if ps[0] == 'ctx' else 'FAIL'} ★ 结构护栏：`check_rubric_blindspot` 首参是 `ctx`（{ps}）")
    if ps[0] != "ctx":
        fails.append(f"check_rubric_blindspot 首参不是 ctx（{ps}）⇒ harness 会把它当 doc")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
