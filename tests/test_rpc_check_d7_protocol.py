"""D7 协议契约（A 段）· 三信封 + 六相状态机 + 8 条拦截 —— 正反注入 + **先验红**（2026-10-01）

`D7-PROTOCOL-CONTRACT.md` §未实测 7 / 8 / 9 三条（三红线 / 三不变量 / 角色禁项）此前**全是文档约束**
（"代码层无拦截/校验实现"）⇒ A 段把它们落成 `ops/rpc_check.py` 里的**纯函数判据库**，
本文件是它的**永久护栏**（同 `test_rpc_check_u4.py` 的定位：判据落体不是"数据"，是"**一段可执行的判据**"）。

守三件事：
  ① **三信封字段级**：缺字段即拒 · `RunReport` 含 `verdict` 即拒（红线「产出方不得自评」变机判）·
     ★ **词义冲突的机械切分**：`Verdict.verdict` 是 exit code（整数），判官四值属 `review.json`；
  ② **六相状态机**：单链 + P4b 可选分叉 + **不得跳过 L1** + **驱动角色固定**（角色不对即拒）；
  ③ **8 条拦截**（三红线 + 三不变量 + 两角色禁项）：逐条一组正反用例 + 注册表自洽。

★ **先验红自证**：本文件每条断言都配一个"**恒真桩**"反证（见 `main()` 末段）——
  一个"永远 ok / 永远放行"的实现必须能**当场红**，否则"全绿"没有信息量（本仓 O-89 同族教训）。

⚠ 本文件自带 `__main__` 入口：门禁 `py-tests` 以**脚本**方式调用（只认退出码 + `RESULT:` 行）。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

# ── 三个"全字段齐"的正样本（字段名照 §1.1；`# 八字段` 那项内部**不展开** —— §2 已登记"依据不足"）──
TC = {
    "task_id": "t-1",
    "task_desc": "生成 out/x.md",
    "accept": [{"criteria": "out/x.md 存在且非空", "criteria_hash": "ab12"}],
    "golden": {"ref": "golden/x.md", "checksum": "cd34"},
    "inputs": {"ref": "in/y.yaml", "digest": "ef56"},
    "evidence_budget": {"anchors": 3, "tool_calls": 20},
    "constraints": ["readonly"],          # 禁止项清单**不枚举**（§2 依据不足）
    "timeout_s": 900,
    "sensitivity": "local-only",          # 取值域**不判**（§2 依据不足）
    "readonly": True,
}
RR = {
    "run_id": "r-1",
    "attempt": 1,
    "artifact": {"digest": "aa11", "size": 1234},
    "inputs_digest": "ef56",
    "exit_code": 0,
    "decisions": [{"what": "占位：八字段内部结构**不判**"}],
    "evidence": ["L1:accept"],
    "usage": {"tool_calls": 7},
}
VD = {
    "verdict": 0,                          # ★ exit code（整数）—— 不是判官四值
    "phase": "P5",
    "l1_results": [{"gate": "accept", "ok": True}],
    "recorded_at": "2026-10-01T00:00:00Z",
    "seq": 1,                              # `recorded_at + seq` 是**两个键**
}

# (说明, kind, env, 期望 verdict)
ENV_CASES = [
    ("正例 TaskContract 全字段齐", "TaskContract", TC, "ok"),
    ("★反例 TaskContract 缺 task_id（缺字段即拒）",
     "TaskContract", {k: v for k, v in TC.items() if k != "task_id"}, "reject"),
    ("★反例 TaskContract 缺 golden.checksum（摘要逐字给出的子键）",
     "TaskContract", {**TC, "golden": {"ref": "golden/x.md"}}, "reject"),
    ("★反例 TaskContract.inputs 不是对象",
     "TaskContract", {**TC, "inputs": "in/y.yaml"}, "reject"),
    ("★反例 accept 为空列表 ⇒ 无判据 = 无从裁决",
     "TaskContract", {**TC, "accept": []}, "reject"),
    ("★★反例 accept 项缺 criteria_hash ⇒ 红线 3 的机判入口",
     "TaskContract", {**TC, "accept": [{"criteria": "out/x.md 存在"}]}, "reject"),
    ("★反例 未知信封 kind ⇒ fail-closed 拒（不是跳过）", "Other", TC, "reject"),
    ("★反例 信封不是对象 ⇒ 拒", "TaskContract", ["t-1"], "reject"),

    ("正例 RunReport 全字段齐（无 verdict）", "RunReport", RR, "ok"),
    ("★★反例 RunReport 含 verdict ⇒ 产出方不得自评（红线变机判）",
     "RunReport", {**RR, "verdict": 0}, "reject"),
    ("★反例 RunReport.artifact 缺 digest（子键逐字列出）",
     "RunReport", {**RR, "artifact": {"size": 1234}}, "reject"),
    ("★反例 RunReport.decisions 不是列表",
     "RunReport", {**RR, "decisions": "八字段"}, "reject"),

    ("正例 Verdict（verdict = exit code 整数）", "Verdict", VD, "ok"),
    ("★★反例 Verdict.verdict 写判官四值 'accept' ⇒ 词义冲突的机械切分",
     "Verdict", {**VD, "verdict": "accept"}, "reject"),
    ("★反例 Verdict 缺 seq（`recorded_at + seq` 是两个键）",
     "Verdict", {k: v for k, v in VD.items() if k != "seq"}, "reject"),
    ("★反例 Verdict.verdict 是 bool ⇒ 拒（bool 不是 exit code）",
     "Verdict", {**VD, "verdict": True}, "reject"),
]

# (说明, (state, to_state, actor), 期望 ok)
TRANS_CASES = [
    ("正例 P0→P1→P2→P3→P4a（单链）",
     [("drafted", "dispatched", R.D7_MASTER), ("dispatched", "claimed", R.D7_WORKER),
      ("claimed", "executing", R.D7_WORKER), ("executing", "collected", R.D7_WORKER),
      ("collected", "mech_verified", R.D7_MASTER)], True),
    ("正例 走 P4b：mech_verified → sem_verified → accepted（均由主控站）",
     [("mech_verified", "sem_verified", R.D7_MASTER), ("sem_verified", "accepted", R.D7_MASTER)], True),
    ("正例 P4b **可选**：mech_verified 直接 → rejected（跳过语义复核）",
     [("mech_verified", "rejected", R.D7_MASTER)], True),
    ("★反例 collected → accepted（**跳过 L1 机械门**，红线 2）",
     [("collected", "accepted", R.D7_MASTER)], False),
    ("★反例 drafted → claimed（**跨相跳步**：合法出边只有 dispatched）",
     [("drafted", "claimed", R.D7_MASTER)], False),
    ("★反例 dispatched → claimed 由**主控站**驱动（P1 属工作站）",
     [("dispatched", "claimed", R.D7_MASTER)], False),
    ("★反例 mech_verified → accepted 由**工作站**驱动（P5 属主控站）",
     [("mech_verified", "accepted", R.D7_WORKER)], False),
    ("★反例 终态 accepted **无出边**",
     [("accepted", "rejected", R.D7_MASTER)], False),
    ("★反例 未知当前态（fail-closed）",
     [("flying", "dispatched", R.D7_MASTER)], False),
    ("★反例 未知目标态（fail-closed）",
     [("drafted", "done", R.D7_MASTER)], False),
    ("★反例 未知角色（fail-closed）",
     [("drafted", "dispatched", "robot")], False),
]

# (rule, ctx, 期望 ok) —— §1.2 / §1.3 / §1.4 逐条
BLOCK_CASES = [
    ("RL1", {"actor": R.D7_MASTER}, True),
    ("RL1", {"actor": R.D7_WORKER}, False),          # ★ 工作站不得发完成信号
    ("I3",  {"actor": R.D7_WORKER}, False),          # ★ 与 RL1 同内容（同一实现）
    ("RL2", {"l1_results": [{"ok": True}], "l2_marks": []}, True),
    ("RL2", {"l1_results": [], "l2_marks": [{"hit": True}]}, False),   # ★ L2 先于 L1
    ("RL2", {"l1_results": [{"ok": True}], "l2_rewrites_l1": True}, False),  # ★ L2 改写 L1
    ("RL3", {"hash_p0": "ab12", "hash_now": "ab12"}, True),
    ("RL3", {"hash_p0": "ab12", "hash_now": "cd34"}, False),           # ★ 事后改判据
    ("RL3", {"hash_p0": None, "hash_now": "cd34"}, False),             # ★ 取不到固值 ⇒ 判不了 ⇒ 拒
    ("I1",  {"actor": R.D7_MASTER, "target": "events"}, True),
    ("I1",  {"actor": R.D7_WORKER, "target": "events"}, False),        # ★ 工作站写事件流
    ("I1",  {"actor": R.D7_WORKER, "target": "artifact"}, True),       # 射程外（只覆盖 events）
    ("I6",  {"decision": "pass"}, True),
    ("I6",  {"decision": None}, False),                                # ★ 判不了不得静默通过
    ("I6",  {"decision": "maybe"}, False),                             # ★ 未知值 ⇒ 拒
    ("PRM", {"actor": R.D7_MASTER, "action": "execute_task"}, False),  # ★ 主控站不执行任务本体
    ("PRM", {"actor": R.D7_MASTER, "action": "verify"}, True),
    ("PRW", {"actor": R.D7_WORKER, "action": "write_verdict"}, False), # ★ 工作站不写 verdict
    ("PRW", {"actor": R.D7_WORKER, "action": "self_accept"}, False),
    ("PRW", {"actor": R.D7_WORKER, "action": "redispatch"}, False),
    ("PRW", {"actor": R.D7_WORKER, "action": "merge"}, False),
    ("PRW", {"actor": R.D7_WORKER, "action": "execute_task"}, True),   # 执行是工作站的**本职**
]


def main() -> int:
    fails = []
    print("── ① 三信封校验器 ──")
    for desc, kind, env, want in ENV_CASES:
        v, why = R.validate_envelope(kind, env)
        ok = (v == want) and (v in R.D7_ENV_VERDICTS)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        → {v}（期望 {want}）· {why}")
        if not ok:
            fails.append(f"[信封] {desc} ⇒ {v}")

    print("── ② 六相状态机 ──")
    for desc, steps, want in TRANS_CASES:
        got, why = True, ""
        for st, to, ac in steps:
            o, nxt, why = R.d7_transition(st, to, ac)
            if not o:
                got = False
                break
            if nxt != to:
                got, why = False, f"返回的下游态 {nxt!r} ≠ 目标 {to!r}"
                break
        ok = (got == want)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        → ok={got}（期望 {want}）· {why}")
        if not ok:
            fails.append(f"[状态机] {desc} ⇒ ok={got}")

    print("── ③ 8 条拦截（三红线 + 三不变量 + 两角色禁项）──")
    for rule, ctx, want in BLOCK_CASES:
        got, why = R.d7_block(rule, **ctx)
        ok = (got == want)
        print(f"  {'ok  ' if ok else 'FAIL'} [{rule}] {ctx}\n        → ok={got}（期望 {want}）· {why}")
        if not ok:
            fails.append(f"[拦截 {rule}] {ctx} ⇒ ok={got}")

    # 注册表自洽：8 条规则、每条都有实现、RL1 与 I3 **共用**一份实现（不造第二份真值）
    ids = [r for r, _ in R.D7_BLOCK_RULES]
    print(f"── ④ 注册表自洽 ──（规则 {len(ids)} 条：{ids}）")
    checks = [
        ("规则恰 8 条", len(R.D7_BLOCK_RULES) == 8),
        ("每条规则都有实现", all(i in R.D7_BLOCK_FNS for i in ids)),
        ("实现表无孤儿", set(R.D7_BLOCK_FNS) == set(ids)),
        ("★ RL1 与 I3 共用同一实现（不造第二份）",
         R.D7_BLOCK_FNS["RL1"] is R.D7_BLOCK_FNS["I3"]),
        ("★ 未知规则 id ⇒ 拒（fail-closed）", R.d7_block("NOPE")[0] is False),
    ]
    for desc, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
        if not ok:
            fails.append(f"[注册表] {desc}")

    # ── ★ 先验红自证：把判据换成"恒真/恒假桩"，上面这些断言**必须**能红 ────────────
    print("── ⑤ 先验红自证（判据非恒真）──")
    reds = [
        ("信封：恒 ok 桩应至少红一条（含 RunReport 带 verdict 那条）",
         sum(1 for _, k, e, w in ENV_CASES if "ok" != w) > 0),
        ("状态机：恒 reject 桩应至少红一条正例",
         sum(1 for _, _, w in TRANS_CASES if w) > 0),
        ("拦截：恒放行桩应至少红一条反例",
         sum(1 for _, _, w in BLOCK_CASES if not w) > 0),
        ("★ 同一条信封：**去掉** verdict 绿 / **加上** verdict 红（判据真的在看这个字段）",
         R.validate_envelope("RunReport", RR)[0] == "ok"
         and R.validate_envelope("RunReport", {**RR, "verdict": 0})[0] == "reject"),
        ("★ 同一状态对：角色对则绿 / 角色错则红（判据真的在看角色）",
         R.d7_transition("dispatched", "claimed", R.D7_WORKER)[0] is True
         and R.d7_transition("dispatched", "claimed", R.D7_MASTER)[0] is False),
    ]
    for desc, ok in reds:
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
        if not ok:
            fails.append(f"[先验红] {desc}")

    # ── ⑥ 消费面（B 段新增的 CLI）—— **外壳的唯一调用点** ─────────────────────────
    # 为什么要测它：判据本体在 Python、调用方在外壳（PS）⇒ 没有可用的 CLI，外壳只能**重写一份**
    #   （= 同一事实两处表达）。故 CLI 是"接线"的前提，必须自己先站得住。
    # ⚠ 用 `sys.executable`（= 门禁同一个解释器），**不用** PATH 上的 `py`/`python`（O-36 的教训）。
    print("── ⑥ 消费面 CLI（外壳调用点）──")
    cli = str(ROOT / "ops" / "rpc_check.py")

    def _cli(args, stdin=None):
        p = subprocess.run([sys.executable, cli] + args, input=stdin, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return p.returncode, ((p.stdout or "") + (p.stderr or ""))

    with tempfile.TemporaryDirectory() as d:
        okf = Path(d) / "rr.json"
        okf.write_text(json.dumps(RR, ensure_ascii=False), encoding="utf-8")
        badf = Path(d) / "rr_verdict.json"
        badf.write_text(json.dumps({**RR, "verdict": 0}, ensure_ascii=False), encoding="utf-8")
        ctxf = Path(d) / "ctx_worker.json"
        ctxf.write_text(json.dumps({"actor": R.D7_WORKER}), encoding="utf-8")
        # ★ B2：红线 2 的**真实形态**（L1 事实 + L2 结论分开），三种组合各一
        rl2ok = Path(d) / "rl2_ok.json"
        rl2ok.write_text(json.dumps({"l1_results": [{"verdict": "green"}],
                                     "l2_marks": [{"hit": True}], "l2_rewrites_l1": False}),
                         encoding="utf-8")
        rl2nol1 = Path(d) / "rl2_nol1.json"
        rl2nol1.write_text(json.dumps({"l1_results": [], "l2_marks": [{"hit": True}]}), encoding="utf-8")
        rl2rw = Path(d) / "rl2_rewrite.json"
        rl2rw.write_text(json.dumps({"l1_results": [{"verdict": "green"}],
                                     "l2_rewrites_l1": True}), encoding="utf-8")
        cli_cases = [
            (["--d7-envelope", "RunReport", str(okf)], None, 0, "D7_ENVELOPE ok"),
            (["--d7-envelope", "RunReport", str(badf)], None, 1, "D7_ENVELOPE reject"),
            (["--d7-envelope", "RunReport", "-"],
             json.dumps(RR, ensure_ascii=False), 0, "D7_ENVELOPE ok"),      # stdin 通道
            (["--d7-envelope", "RunReport", str(Path(d) / "nope.json")], None,
             2, "D7_ENVELOPE undecidable"),                                 # ★ 判不了 ≠ 通过
            (["--d7-block", "RL1", "--d7-ctx", str(ctxf)], None, 1, "D7_BLOCK reject"),
            (["--d7-block", "NOPE"], None, 1, "D7_BLOCK reject"),           # 未知规则 ⇒ 拒
            (["--d7-transition", "drafted", "dispatched", "master"], None, 0, "D7_TRANSITION ok"),
            (["--d7-transition", "collected", "accepted", "master"], None, 1, "D7_TRANSITION reject"),
            # ★ B2：红线 2 的消费面（P4a/P4b 接线调的就是它）
            (["--d7-block", "RL2", "--d7-ctx", str(rl2ok)], None, 0, "D7_BLOCK ok"),
            (["--d7-block", "RL2", "--d7-ctx", str(rl2nol1)], None, 1, "D7_BLOCK reject"),
            (["--d7-block", "RL2", "--d7-ctx", str(rl2rw)], None, 1, "D7_BLOCK reject"),
            # ★★ B2 实测抓到的真缺陷：`ctx` 与判据**输入契约不符**（多传/拼错键）⇒ 归
            #   **undecidable（2）** —— 旧实现里 `**ctx` 抛 TypeError 会让进程退 **1**，
            #   与 `reject` **不可区分**（崩溃被冒充成"判据拒绝了" ⇒ 三态不可混被破坏）。
            (["--d7-block", "I6", "--d7-ctx", str(okf)], None, 2, "D7_BLOCK undecidable"),
        ]
        for args, stdin, want_rc, want_mark in cli_cases:
            rc, out = _cli(args, stdin)
            hit = want_mark in out
            ok = (rc == want_rc) and hit
            print(f"  {'ok  ' if ok else 'FAIL'} {' '.join(args)}\n        → exit={rc}（期望 {want_rc}）· "
                  f"标记 {'在' if hit else '**缺**'}「{want_mark}」")
            if not ok:
                fails.append(f"[CLI] {' '.join(args)} ⇒ exit={rc} mark={hit}")
        # ★ 同源对照（先验红）：**同一个**信封文件，仅多一个 `verdict` 键 ⇒ 0 → 1
        rc_ok, _ = _cli(["--d7-envelope", "RunReport", str(okf)])
        rc_bad, _ = _cli(["--d7-envelope", "RunReport", str(badf)])
        print(f"  {'ok  ' if (rc_ok, rc_bad) == (0, 1) else 'FAIL'} "
              f"★ 同源对照：去掉 verdict ⇒ {rc_ok} / 加上 verdict ⇒ {rc_bad}")
        if (rc_ok, rc_bad) != (0, 1):
            fails.append("[CLI] 同源对照失败")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())