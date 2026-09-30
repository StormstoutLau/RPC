"""`U-5 信任基座四问 + 晋升门 schema` 的正反注入 + **先验红** —— 永久护栏（2026-09-26）

两半，刻意不同：
  · **四问判据**（`v1_*`/`v2_*`/`v3_*`/`v4_*`）—— 判据库，**不是** `CHECKS` 项
    （本仓没有形式化信任基座的对象：**V-2 真空** · V-1/V-4 各仅 1 项目 · V-3 仅关键词级）；
  · **晋升门 schema**（`inventory/promotion.yaml`）—— **是** `CHECKS` 项（`promotion`），
    因为被判的对象**真实存在**（schema 自身 + 三处实现的映射）。

★ 本文件守的核心是 **D-38**：三处独立发明的晋升门**统一为一个 schema，不许发明第四种**。
  它最容易被绕开的方式是"**悄悄加一个没人用的字段**"（= 变相发明第四种）⇒
  ⇒ 故有 **孤儿字段 / 孤儿判据** 两条反例，且**在真文件上**做**先验红自证**（不是只拿合成样例测）。
"""
import copy
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _doc(**over):
    base = {
        "fields": [{"id": "anchor", "type": "str"}, {"id": "entries", "type": "int"},
                   {"id": "success_count", "type": "int"},
                   {"id": "min_success_for_inject", "type": "int"},
                   {"id": "recurrence", "type": "int"}, {"id": "min_recurrence", "type": "int"},
                   {"id": "verified", "type": "bool"}],
        "gate": {
            "required": ["anchor"],
            "capacity": {"field": "entries", "max": 50, "policy": "lru"},
            "criteria": [
                {"id": "success_rate", "field": "success_count", "op": ">=", "ref": "$min_success_for_inject"},
                {"id": "recurrence", "field": "recurrence", "op": ">=", "ref": "$min_recurrence"},
                {"id": "verified", "field": "verified", "op": "==", "ref": True},
            ],
            "structure": [{"id": "asymmetric_config"}, {"id": "double_blind"}],
        },
        "mapping_closure": [
            {"id": "textbook", "uses": ["anchor", "entries", "success_count", "min_success_for_inject"],
             "criteria_used": ["success_rate"]},
            {"id": "spec_workflow", "uses": ["anchor", "recurrence", "min_recurrence"],
             "criteria_used": ["recurrence"]},
            {"id": "fin_agent", "uses": ["verified"], "criteria_used": ["verified"]},
        ],
        "entries": [], "empty_reason": "本仓没有共享记忆层",
        "unverified": [{"item": "min_recurrence 阈值", "why": "原文未给次数"}],
    }
    base.update(over)
    return copy.deepcopy(base)


def _crit(**over):
    c = {"id": "success_rate", "field": "success_count", "op": ">=", "ref": "$min_success_for_inject"}
    c.update(over)
    return c


CASES = [
    ("正例 最小合格 schema", _doc(), True, "字段 7"),
    ("★反例 缺 `fields`", _doc(fields=[]), False, "`fields` 为空"),
    ("★反例 缺 `gate.required`", _doc(gate={"capacity": {"field": "entries", "max": 50, "policy": "lru"},
                                            "criteria": _doc()["gate"]["criteria"],
                                            "structure": [{"id": "x"}]}), False, "`gate.required` 为空"),
    ("★反例 `gate.structure` 为空（§11.7 没落地）",
     _doc(gate=dict(_doc()["gate"], structure=[])), False, "`gate.structure` 为空"),
    ("★反例 capacity.max 非正整数",
     _doc(gate=dict(_doc()["gate"], capacity={"field": "entries", "max": 0, "policy": "lru"})),
     False, "必须是正整数"),
    ("★反例 capacity.policy 不在封闭集",
     _doc(gate=dict(_doc()["gate"], capacity={"field": "entries", "max": 50, "policy": "random"})),
     False, "不在封闭集"),
    ("★反例 capacity.field 引用了不存在的字段",
     _doc(gate=dict(_doc()["gate"], capacity={"field": "ghost", "max": 50, "policy": "lru"})),
     False, "不在 `fields` 里"),
    ("★反例 **D-38 三种判据并存被破坏**（删掉 verified）",
     _doc(gate=dict(_doc()["gate"], criteria=[_crit(), _crit(id="recurrence", field="recurrence",
                                                             ref="$min_recurrence")])),
     False, "三种判据并存"),
    ("★反例 criteria 的 op 不在封闭集",
     _doc(gate=dict(_doc()["gate"], criteria=[_crit(op="=~"), *_doc()["gate"]["criteria"][1:]])),
     False, "不在封闭集"),
    ("★反例 `$ref` 引用不存在的字段",
     _doc(gate=dict(_doc()["gate"], criteria=[_crit(ref="$ghost"), *_doc()["gate"]["criteria"][1:]])),
     False, "引用了不存在的字段"),
    ("★反例 `$ref` 类型与 field 不匹配（int vs str）",
     _doc(gate=dict(_doc()["gate"], criteria=[_crit(ref="$anchor"), *_doc()["gate"]["criteria"][1:]])),
     False, "类型不匹配"),

    # ── ★★ 映射闭包：D-38 的核心（"悄悄加一个没人用的字段" = 变相发明第四种）──
    ("★★反例 **孤儿字段**：fields 里加一个没有任何实现用到的字段",
     _doc(fields=_doc()["fields"] + [{"id": "fourth_thing", "type": "int"}]),
     False, "孤儿字段"),
    ("★★反例 **孤儿判据**：criteria 里加一条没有实现使用的判据",
     _doc(gate=dict(_doc()["gate"], criteria=_doc()["gate"]["criteria"]
                    + [{"id": "vibes", "field": "entries", "op": ">=", "ref": 1}])),
     False, "孤儿判据"),
    ("★反例 `mapping_closure` 为空 ⇒ D-38『须能被三处各自映射』没被判",
     _doc(mapping_closure=[]), False, "`mapping_closure` 为空"),
    ("★反例 mapping 的 `uses` 含不存在的字段",
     _doc(mapping_closure=[{"id": "a", "uses": ["ghost"], "criteria_used": ["verified"]},
                           {"id": "b", "uses": ["recurrence", "min_recurrence"], "criteria_used": ["recurrence"]},
                           {"id": "c", "uses": ["anchor", "entries", "success_count",
                                                "min_success_for_inject", "verified"],
                            "criteria_used": ["success_rate"]}]),
     False, "不存在的字段"),
    ("★反例 mapping 没声明 `criteria_used`",
     _doc(mapping_closure=[{"id": "a", "uses": ["anchor", "entries", "success_count",
                                               "min_success_for_inject", "recurrence",
                                               "min_recurrence", "verified"], "criteria_used": []}]),
     False, "没声明 `criteria_used`"),

    # ── 条目 / 新设项 ───────────────────────────────────────────────────
    ("★反例 缺 `entries` 字段", {k: v for k, v in _doc().items() if k != "entries"},
     False, "缺 `entries` 字段"),
    ("★反例 entries 为空且 no `empty_reason`", _doc(empty_reason=""), False, "没有 `empty_reason`"),
    ("★反例 `unverified` 为空（新设项没登记）", _doc(unverified=[]), False, "`unverified` 为空"),
    ("★反例 顶层不是映射", ["nope"], False, "顶层不是映射"),
]

V_CASES = [
    # ── V-3 ★★ `U5#4`（2026-09-30 裁 / `O-123`）：**裁掉"默认名单"形态** ⇒ 白名单**必须显式声明** ──
    # ⚠ 下面几条的**期望值改动过**（旧版：缺省回落默认名单 ⇒ `True`；`whitelist=[]` ⇒ `False`）。
    #   ⇒ **方向 = 改写断言**（照裁），**不是回退代码**。
    ("V-3 正例 公理 ⊆ **显式声明**的白名单",
     lambda: R.v3_axiom_whitelist(["propext", "Quot.sound"], whitelist=["propext", "Quot.sound"]), True, ""),
    ("★V-3 反例 白名单外公理",
     lambda: R.v3_axiom_whitelist(["propext", "MyCheat"], whitelist=["propext", "Quot.sound"]),
     False, "白名单外公理"),
    ("★V-3 反例 **未声明白名单**（None）⇒ 判不通过（裁掉默认名单：取自原文举例 ≠ 裁定）",
     lambda: R.v3_axiom_whitelist(["propext"]), False, "未声明公理白名单"),
    ("★V-3 正例 **显式空声明** `whitelist=[]` ⇒ 合法（语义 = 「确实不需要额外公理」）",
     lambda: R.v3_axiom_whitelist([], whitelist=[]), True, ""),
    ("★V-3 反例 显式空声明 + 却用了公理 ⇒ 仍红（空声明**不是**判据恒真）",
     lambda: R.v3_axiom_whitelist(["propext"], whitelist=[]), False, "白名单外公理"),
    # V-4
    ("V-4 正例 依赖全钉 rev + ledger 齐",
     lambda: R.v4_build_reproducible([{"name": "mathlib", "rev": "abc123"}],
                                     {"tool_versions": {"lean": "4.9.0"}, "input_hash": "deadbeef"}),
     True, ""),
    ("★V-4 反例 依赖**未钉 rev**",
     lambda: R.v4_build_reproducible([{"name": "mathlib"}],
                                     {"tool_versions": {"lean": "4.9.0"}, "input_hash": "x"}),
     False, "未钉 rev"),
    ("★V-4 反例 ledger 缺 `input_hash`",
     lambda: R.v4_build_reproducible([{"name": "mathlib", "rev": "abc"}], {"tool_versions": {"lean": "4.9.0"}}),
     False, "input_hash"),
    # V-1
    ("V-1 正例 逐条对应且带锚点",
     lambda: R.v1_definition_correspondence([{"claim": "官方陈述 1", "formal": "T1", "anchor": "L120"}]),
     True, ""),
    ("★V-1 反例 某条缺 anchor ⇒ 不可追溯",
     lambda: R.v1_definition_correspondence([{"claim": "c", "formal": "T1"}]),
     False, "不可追溯"),
    ("★V-1 反例 对应表为空",
     lambda: R.v1_definition_correspondence([]), False, "对应表为空"),
    # V-2
    ("V-2 正例 跳链连续",
     lambda: R.v2_bridge_completeness([{"from": "正文 §3", "to": "定义 D1", "evidence": "map.md:12"},
                                       {"from": "定义 D1", "to": "定理 T1", "evidence": "map.md:20"}]),
     True, ""),
    ("★V-2 反例 **断链**（a.to ≠ b.from）",
     lambda: R.v2_bridge_completeness([{"from": "正文 §3", "to": "定义 D1", "evidence": "x"},
                                       {"from": "定义 D2", "to": "定理 T1", "evidence": "y"}]),
     False, "断链"),
    ("★V-2 反例 跳表为空（V-2 实测是真空）",
     lambda: R.v2_bridge_completeness([]), False, "跳表为空"),
]


def main() -> int:
    fails = []

    for desc, doc, want_ok, kw in CASES:
        bad, notes = R.validate_promotion(doc)
        blob = " ".join(bad) + " " + " ".join(notes)
        ok = ((not bad) == want_ok) and (kw in blob)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':{'在' if kw in blob else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} notes={notes}")

    for desc, fn, want_ok, kw in V_CASES:
        got_ok, bad = fn()
        blob = " ".join(bad)
        ok = (got_ok == want_ok) and (kw in blob)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        ok={got_ok} · '{kw}':{'在' if kw in blob else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ ok={got_ok} bad={bad}")

    # ── 端到端：真读 inventory/promotion.yaml ────────────────────────────
    real = None
    try:
        import yaml
        real = yaml.safe_load((ROOT / "inventory" / "promotion.yaml").read_text(encoding="utf-8"))
        bad, notes = R.validate_promotion(real)
        ok = not bad
        print(f"  {'ok  ' if ok else 'FAIL'} 端到端 真读 inventory/promotion.yaml\n        {notes} · bad={len(bad)}")
        if not ok:
            fails.append(f"真值文件自身不过: {bad}")
    except ImportError:
        print("  skip 端到端（缺 pyyaml）")

    # ── ★ 先验红自证（**在真文件上**）：加一个孤儿字段 ⇒ 必须红 ─────────────
    if real is not None:
        mutated = copy.deepcopy(real)
        mutated["fields"].append({"id": "fourth_thing", "type": "int"})
        bad2, _ = R.validate_promotion(mutated)
        red = any("孤儿字段" in b for b in bad2)
        print(f"  {'ok  ' if red else 'FAIL'} 先验红自证：在**真文件**上加入一个没人用的字段 ⇒ "
              f"被识别为孤儿字段（{'是' if red else '否'}）")
        if not red:
            fails.append("先验红自证失败：真文件上加孤儿字段没被识别 ⇒ 映射闭包规则形同虚设")

    # ── ★★ `U5#5`（2026-09-30 · 批 4）：**把 gate 变"可走"** + 第一条真实条目 ──────────
    # 缺口（本批实测发现）：此前 `validate_promotion` 只判 schema **自身** ⇒ **即便加一条也没有任何东西检查它**。
    E = R.promotion_entry_verdict
    _gate = _doc()["gate"]
    _good = {"id": "X", "anchor": "a", "verified": True, "recurrence": 0, "success_count": 0}
    ok_e, why, sat = E(_good, _gate)
    print(f"  {'ok  ' if (ok_e and sat == ['verified']) else 'FAIL'} "
          f"★5-1 条目 `verified:true` ⇒ 可晋升（三种判据**任一**满足）· satisfied={sat}")
    if not (ok_e and sat == ["verified"]):
        fails.append(f"entry walker 正例不过: ok={ok_e} why={why} sat={sat}")
    ok_e, why, _ = E({k: v for k, v in _good.items() if k != "anchor"}, _gate)
    print(f"  {'ok  ' if (not ok_e and any('缺必填字段' in w for w in why)) else 'FAIL'} "
          f"★5-2 先验红：**缺 anchor** ⇒ 拦（Spec_Workflow『缺锚点不得登记』）")
    if ok_e:
        fails.append("缺 anchor 的条目被放行 ⇒ required 形同虚设")
    ok_e, why, _ = E({"id": "X", "anchor": "a", "recurrence": 0, "success_count": 0}, _gate)
    print(f"  {'ok  ' if (not ok_e and any('没有任何判据满足' in w for w in why)) else 'FAIL'} "
          f"★5-3 先验红：**一个判据都不满足** ⇒ 拦（且点名「阈值未定不许假定」）")
    if ok_e:
        fails.append("无判据满足的条目被放行 ⇒ criteria 形同虚设")
    # ★ 门槛未给 ⇒ 该判据**不满足**，但**不编数**（`O-126`）
    ok_e2, _why2, sat2 = E({"id": "X", "anchor": "a", "success_count": 5}, _gate)
    print(f"  {'ok  ' if ((not ok_e2) and sat2 == []) else 'FAIL'} "
          f"★5-4 只给 `success_count` 但**门槛未给** ⇒ 该判据不满足（**不许替它假定阈值**）")
    if ok_e2:
        fails.append("门槛未给却被判满足 ⇒ 假精确（O-126 同族）")
    # 容量件套：条数超 max ⇒ 拦
    _over = _doc(entries=[dict(_good, id=f"e{i}") for i in range(51)])
    bad_c, _n = R.validate_promotion(_over)
    print(f"  {'ok  ' if any('capacity.max' in b for b in bad_c) else 'FAIL'} "
          f"★5-5 容量件套：51 条 > max=50 ⇒ 拦")
    if not any("capacity.max" in b for b in bad_c):
        fails.append("容量件套被绕过（条数超上限没人管）")

    # ── 结构护栏 ────────────────────────────────────────────────────────
    ids = {c["id"] for c in R.CHECKS}
    if "promotion" not in ids:
        fails.append("CHECKS 里没有 id='promotion' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'promotion' 已在 CHECKS 注册")
    if any(i in ids for i in ("v1", "v2", "v3", "v4", "trust")):
        fails.append("四问判据不该是 CHECKS 项（本仓没有形式化信任基座的对象）")
    else:
        print("  ok   结构护栏：四问判据是判据库、**不是** CHECKS 项（本仓无对象，已如实登记）")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
