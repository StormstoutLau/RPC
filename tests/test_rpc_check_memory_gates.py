"""`D7-P3-3 记忆四道门 + 授权边界` 的正反注入 + **先验红** —— 永久护栏（2026-09-26）

守的是 **D-47**（共享记忆做，但必须带四道门 write/retrieval/promotion/reuse）与
**D-48**（**不要指望"审得更准"，要靠"结构 contain"**），前提是 **D-40**（单人开发者是常态假设）。

★ 本文件最要紧的四条：
  1. **「缺一道门」必须红** —— 否则"四门各一条判据"只是句承诺；
  2. **「挂名假判」必须红** —— 门的 `judgment.ref` 指向不存在的判据 = 本仓最典型的假绿；
  3. **「既说是结构、又声明不是结构」必须红** —— 两段混用就是「把两件事说成一件」；
  4. **`touchpoint_hits=None` 必须与 `[]` 可区分** —— 「没判」与「判了且通过」不许长得一样。

⚠ 本文件里**不得出现记忆路径的字面量**（否则 `tests/` 自己会变成"未登记的记忆面接触点"）——
   全部从真值表取。这不是洁癖：它同时是"记忆路径唯一字面定义点在 yaml"的**行为级自证**。
"""
import copy
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

KNOWN = {"memory-gates", "promotion", "input-provenance"}
TOK_DB = "FAKE_DB_TOKEN"      # 合成样例里用**假**路径（真路径只在真值表里）
TOK_DIR = "FAKE_DIR_TOKEN/"


def _gate(gid, ref="memory-gates", kind="check", **over):
    g = {"id": gid, "what": "w", "object": "o", "not_covers": "n", "evidence": "e",
         "judgment": {"kind": kind, "ref": ref}}
    g.update(over)
    return g


def _bridge(bid, gate="cwd-keyed", controllable=False, **over):
    b = {"id": bid, "channel": "c", "isolated": True, "key": "cwd", "gate": gate,
         "controllable_by_us": controllable, "why": "w", "evidence": "e"}
    b.update(over)
    return b


def _sc(sid, **over):
    s = {"id": sid, "rule": "r", "judged_by": "memory-gates", "why_structural": "ws"}
    s.update(over)
    return s


def _doc(**over):
    base = {
        "gates": [_gate("write"), _gate("retrieval", ref="input-provenance"),
                  _gate("promotion", ref="promotion"), _gate("reuse")],
        "bridges": [_bridge("b-cwd", gate="cwd-keyed"),
                    _bridge("b-shared", gate="by-design-shared", controllable=True)],
        "structural_constraints": [_sc("s1")],
        "known_non_structural": [{"id": "k1", "rule": "r", "today": "t",
                                  "why_not_structural": "wn", "object_absent_why": "o"}],
        "touchpoints": [{"file": "ops/station-bin/agent-cli.ps1", "why": "w", "egress": False}],
        "egress": {"path_tokens": {"db": TOK_DB, "dir": TOK_DIR}, "carrier_tokens": ["scp"]},
        "text_prefix": {"marker": "FAKE_MARKER", "forbidden_in": ["tests"]},
        "unverified": [{"item": "i", "why": "w"}],
    }
    base.update(over)
    return copy.deepcopy(base)


HITS_OK = ["ops/station-bin/agent-cli.ps1"]

CASES = [
    # ── 正例 ──────────────────────────────────────────────────────────
    ("正例 最小合格（`touchpoint_hits=None` ⇒ 不判扫描）", _doc(), None, True, "未接扫描输入"),
    ("正例 接了扫描且命中已登记", _doc(), HITS_OK, True, "接触点扫描命中 1 个文件"),

    # ── ① 四道门 ──────────────────────────────────────────────────────
    ("★★反例 **缺一道门**（删掉 reuse）",
     _doc(gates=[_gate("write"), _gate("retrieval"), _gate("promotion")]), None, False, "缺一道门"),
    ("★反例 **多出一道门**（四门是封闭集）",
     _doc(gates=_doc()["gates"] + [_gate("extra")]), None, False, "多出一道门"),
    ("★反例 `gates` 为空 ⇒ 四门没有对象（退化空判）",
     _doc(gates=[]), None, False, "四道门没有对象"),
    ("★反例 一道门缺 `not_covers` ⇒ 部分覆盖会被读成全覆盖",
     _doc(gates=[_gate("write", not_covers="")] + _doc()["gates"][1:]), None, False, "不覆盖什么"),
    ("★反例 一道门缺 `what`",
     _doc(gates=[_gate("write", what="")] + _doc()["gates"][1:]), None, False, "缺 `what`"),
    ("★反例 一道门缺 `judgment` 段 ⇒ 这道门没有判据",
     _doc(gates=[{k: v for k, v in _gate("write").items() if k != "judgment"}] + _doc()["gates"][1:]),
     None, False, "这道门没有判据"),
    ("★★反例 **挂名假判**（`judgment.ref` 指向不存在的 CHECKS id）",
     _doc(gates=[_gate("write", ref="no-such-check")] + _doc()["gates"][1:]), None, False, "挂名假判"),
    ("★反例 `kind: na` 但缺 `object_absent_why`",
     _doc(gates=[_gate("write", kind="na", ref="")] + _doc()["gates"][1:]),
     None, False, "也要写下来"),
    ("★反例 `judgment.kind` 不在封闭集",
     _doc(gates=[_gate("write", kind="maybe")] + _doc()["gates"][1:]), None, False, "不在封闭集"),

    # ── ② 私有 → 共享的通道 ────────────────────────────────────────────
    ("★★反例 `bridges` 为空 ⇒ **关键一跳没有对象**",
     _doc(bridges=[]), None, False, "关键一跳"),
    ("★★反例 **`gate: none` 且本仓可控 ⇒ 红**（本仓能关却不关）",
     _doc(bridges=[_bridge("b-open", gate="none", controllable=True)]), None, False, "本仓能关却不关"),
    ("★正例 `gate: none` 但**本仓不可控** ⇒ 不红（引擎侧；只点名，见 `check_` 的 WARN）",
     _doc(bridges=[_bridge("b-engine", gate="none", controllable=False)]), None, True, "引擎侧 1 条"),
    ("★反例 `by-design-shared` 但 `why` 为空 ⇒ 与 `none` 无法区分",
     _doc(bridges=[_bridge("b1", gate="by-design-shared", why="")]), None, False, "无法区分"),
    ("★反例 `cwd-keyed` 但缺 `key`（没键就不叫键控）",
     _doc(bridges=[_bridge("b1", gate="cwd-keyed", key="")]), None, False, "没写 `key`"),
    ("★反例 `gate` 不在封闭集",
     _doc(bridges=[_bridge("b1", gate="maybe")]), None, False, "不在封闭集"),
    ("★反例 `isolated` 不是布尔（是形容词就不是实测口径）",
     _doc(bridges=[_bridge("b1", isolated="yes")]), None, False, "必须是布尔"),
    ("★反例 `controllable_by_us` 不是布尔",
     _doc(bridges=[_bridge("b1", controllable_by_us="yes")]), None, False, "必须是布尔"),

    # ── ③ 结构性约束 ──────────────────────────────────────────────────
    ("★★反例 `structural_constraints` 为空 ⇒ 授权边界没写成结构性约束",
     _doc(structural_constraints=[]), None, False, "没有写成结构性约束"),
    ("★★反例 `judged_by: NA_UNIT` ⇒ **它就不是结构性约束**（该移到另一段）",
     _doc(structural_constraints=[_sc("s1", judged_by="NA_UNIT")]), None, False, "它就不是结构性约束"),
    ("★反例 `judged_by` 指向不存在的 CHECKS id ⇒ 没判据的还只是纪律",
     _doc(structural_constraints=[_sc("s1", judged_by="ghost")]), None, False, "仍只是纪律"),
    ("★反例 缺 `why_structural`",
     _doc(structural_constraints=[_sc("s1", why_structural="")]), None, False, "为什么它是结构"),
    ("★反例 缺 `rule`",
     _doc(structural_constraints=[_sc("s1", rule="")]), None, False, "缺 `rule`"),

    # ── ③b 今天还不是结构性约束的（如实登记）────────────────────────────
    ("★★反例 `known_non_structural` 为空 ⇒ 「不是结构」这件事没写下来",
     _doc(known_non_structural=[]), None, False, "不是结构"),
    ("★★反例 **两边同一个 id**（既说是结构、又声明不是结构）",
     _doc(known_non_structural=[{"id": "s1", "rule": "r", "today": "t",
                                 "why_not_structural": "w", "object_absent_why": "o"}]),
     None, False, "同时说成"),
    ("★反例 `known_non_structural` 缺 `today`（今天靠什么）",
     _doc(known_non_structural=[{"id": "k1", "rule": "r", "why_not_structural": "w",
                                 "object_absent_why": "o"}]), None, False, "缺 `today`"),

    # ── ④ 接触点封闭集 ────────────────────────────────────────────────
    ("★★反例 **未登记的记忆面接触点**（形状外文件）",
     _doc(), HITS_OK + ["ops/handmade-mem.py"], False, "未登记的记忆面接触点"),
    ("★反例 接触点缺 `why`",
     _doc(touchpoints=[{"file": "ops/station-bin/agent-cli.ps1", "egress": False}]), None, False, "缺 `why`"),
    ("★反例 `touchpoints` 为空 ⇒ 新开一条通道不会被发现",
     _doc(touchpoints=[]), None, False, "封闭集"),
    ("★反例 接触点缺 `egress` 布尔",
     _doc(touchpoints=[{"file": "ops/station-bin/agent-cli.ps1", "why": "w"}]), None, False, "`egress` 必须是布尔"),

    # ── ⑤ 口径段 ──────────────────────────────────────────────────────
    ("★反例 `egress.path_tokens` 不是映射（顺序口径本仓吃过亏）",
     _doc(egress={"path_tokens": [TOK_DB], "carrier_tokens": ["scp"]}), None, False, "必须是非空映射"),
    ("★反例 `egress.carrier_tokens` 为空 ⇒ 不知道什么算跨机搬运",
     _doc(egress={"path_tokens": {"db": TOK_DB}, "carrier_tokens": []}), None, False, "跨机搬运"),
    ("★反例 `text_prefix` 缺 `marker`",
     _doc(text_prefix={"marker": "", "forbidden_in": ["tests"]}), None, False, "`text_prefix` 段缺"),
    ("★反例 `unverified` 为空 ⇒ 未实测部分没登记",
     _doc(unverified=[]), None, False, "`unverified` 为空"),
    ("★反例 顶层不是映射", ["nope"], None, False, "顶层不是映射"),
]


def main() -> int:
    fails = []

    for desc, doc, hits, want_ok, kw in CASES:
        bad, notes = R.validate_memory_gates(doc, known_checks=KNOWN, touchpoint_hits=hits)
        blob = " ".join(bad) + " " + " ".join(notes)
        ok = ((not bad) == want_ok) and (kw in blob)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':{'在' if kw in blob else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} notes={notes}")

    # ── ★ 「没判」与「判了且通过」必须可区分 ─────────────────────────────
    d = _doc()
    b1, n1 = R.validate_memory_gates(d, known_checks=KNOWN, touchpoint_hits=None)
    b2, n2 = R.validate_memory_gates(d, known_checks=KNOWN, touchpoint_hits=[])
    sep = (not b1) and (not b2) and any("未接扫描输入" in x for x in n1) and not any("未接扫描输入" in x for x in n2)
    print(f"  {'ok  ' if sep else 'FAIL'} ★ `touchpoint_hits=None`（不判）与 `[]`（判过）的**结论可区分**")
    if not sep:
        fails.append(f"None 与 [] 不可区分 ⇒ 该判据在没接扫描输入时是恒真的（n1={n1} n2={n2}）")

    # ── 端到端：真读 yaml + 真扫盘 + 真提取（走 check_memory_gates 本体）──────
    real = None
    try:
        import yaml
        real = yaml.safe_load(R.MEMORY_GATES_INV.read_text(encoding="utf-8"))
        status, note, det = R.check_memory_gates(None)
        ok = status != "FAIL" and "四门齐（4/4" in note
        print(f"  {'ok  ' if ok else 'FAIL'} 端到端 check_memory_gates ⇒ {status}\n        {note}")
        if not ok:
            fails.append(f"端到端不过: {status} {note} {det}")
        # ★「绝不静默」：若有引擎侧无门通道 ⇒ 状态必须是 WARN **且**明细点名
        if status == "WARN":
            named = any("adhoc-notes-flat" in x for x in det)
            print(f"  {'ok  ' if named else 'FAIL'} ★ WARN 时**点名**了引擎侧无门通道（不静默）")
            if not named:
                fails.append(f"WARN 但没点名无门通道 ⇒ 静默降级：{det}")
        # ★ 记忆路径字面量**只在 yaml**：判据源码里不得出现
        toks = list((real.get("egress") or {}).get("path_tokens", {}).values())
        src = (ROOT / "ops" / "rpc_check.py").read_text(encoding="utf-8")
        leaked = [t for t in toks if t in src]
        print(f"  {'ok  ' if not leaked else 'FAIL'} ★ 记忆路径字面量**只在 yaml**"
              f"（判据源码里泄漏 {leaked}）")
        if leaked:
            fails.append(f"记忆路径在 rpc_check.py 里被硬编码: {leaked} ⇒ 第二份定义点")
    except ImportError:
        print("  skip 端到端（缺 pyyaml）")

    # ── SC-1 正向自证：真文件里**恰好一条** symlink，且源在站级 $HOME 下 ────────
    if real is not None:
        db_tok = (real.get("egress") or {}).get("path_tokens", {}).get("db", "")
        syms = R.extract_memory_symlinks(R.AGENT_CLI.read_text(encoding="utf-8", errors="replace"), db_tok)
        guard = real.get("plane_guard") or {}
        if len(syms) != 1:
            fails.append(f"真文件里 symlink 实测 {len(syms)} 处（要求恰 1）")
            print(f"  FAIL SC-1 正向自证：实测 {len(syms)} 处 symlink（要求恰 1）")
        else:
            src_p, tgt_p = R.parse_symlink_paths(syms[0][1])
            okp = any(src_p and src_p.startswith(p) for p in (guard.get("allowed_source_prefixes") or []))
            oks = bool(tgt_p) and tgt_p.endswith(str(guard.get("allowed_target_suffix") or "\0"))
            print(f"  {'ok  ' if (okp and oks) else 'FAIL'} SC-1 正向自证：恰 1 处 symlink，源在站级前缀"
                  f"（{'是' if okp else '否'}），目标后缀对得上（{'是' if oks else '否'}）")
            if not (okp and oks):
                fails.append(f"SC-1 正向自证失败: src={src_p!r} tgt={tgt_p!r}")

    # ── ★ 先验红自证（**在真文件上**，四处各自必须红）─────────────────────
    if real is not None:
        muts = [
            ("清空 `structural_constraints`", lambda m: m.update(structural_constraints=[]), "没有写成结构性约束"),
            ("把一条通道改成 `gate: none` + 本仓可控",
             lambda m: m["bridges"][0].update(gate="none", controllable_by_us=True), "本仓能关却不关"),
            ("清空 `touchpoints`", lambda m: m.update(touchpoints=[]), "封闭集"),
        ]
        for desc, mut, kw in muts:
            m = copy.deepcopy(real)
            mut(m)
            bad2, _ = R.validate_memory_gates(m, known_checks=KNOWN, touchpoint_hits=HITS_OK)
            red = any(kw in b for b in bad2)
            print(f"  {'ok  ' if red else 'FAIL'} 先验红自证：真文件上{desc} ⇒ 必须红（{'是' if red else '否'}）")
            if not red:
                fails.append(f"先验红自证失败：真文件上{desc} 没被拦（期望含 {kw!r}）")

        # ★ **登记腐化**：这条要碰盘 ⇒ 走 `check_memory_gates` 的注入缝（纯函数判不了）
        m = copy.deepcopy(real)
        m["touchpoints"] = list(m["touchpoints"]) + [
            {"file": "ops/ghost-mem.py", "why": "w", "egress": False}]
        st, _note, det = R.check_memory_gates(None, doc=m)
        red = st == "FAIL" and any("登记腐化" in x for x in det)
        print(f"  {'ok  ' if red else 'FAIL'} 先验红自证：真文件上登记一个**不存在**的接触点 ⇒ "
              f"必须红（{'是' if red else '否'}）· 状态 {st}")
        if not red:
            fails.append(f"先验红自证失败：登记腐化没被拦（{st} {det}）")

    # ── 结构护栏 ────────────────────────────────────────────────────────
    ids = {c["id"] for c in R.CHECKS}
    if "memory-gates" not in ids:
        fails.append("CHECKS 里没有 id='memory-gates' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'memory-gates' 已在 CHECKS 注册")
    # ★ 四门里有两门**复用已有判据**（不重复定义）—— 这是 D-38/D-47 的"建映射、不迁移"
    if real is not None:
        refs = {g["id"]: (g.get("judgment") or {}).get("ref") for g in real.get("gates") or []}
        reuse = [k for k, v in refs.items() if v in ("promotion", "input-provenance")]
        print(f"  ok   结构护栏：复用既有判据的门 = {reuse}（新判据只补没有对象的门）")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
