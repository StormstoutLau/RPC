#!/usr/bin/env python3
"""门禁 `executor-trace` 的测试 —— **A2**（2026-09-29）

执行侧**过程留痕**：治「判据只能看产物，看不到过程」。最小充分集**5 项**
（cmd / env / fs / tool / artifact），唯一不可核的**工具调用链**必须**如实标 `uncore`**。

覆盖：
  · **先验红**（删任一采集点标记 ⇒ 必须 FAIL 且报出该标记）· **变异自证**（桩恒返 PASS ⇒ 先验红断言必红）；
  · **负向自证**（出现 `chain=core`/`chain=verified` ⇒ 伪称可核 ⇒ FAIL）；
  · **覆盖两态**（runDir 有件且齐段 ⇒ PASS；有件缺段 ⇒ FAIL；**0 个 ⇒ PASS 且标"未验"**）；
  · **锚定段**（2026-09-30 补：执行体自报哈希 ⇒ FAIL · 留痕件 `ts` 与 runDir 不符 ⇒ FAIL ·
    主控侧无哈希记录 ⇒ **只报数**）；
  · 端到端 + 结构护栏（gate 已注册 · quick）。

⚠⚠ **本文件自带 `__main__` 入口**：门禁 `py-tests` 以**脚本**方式调用（只认退出码）。
  没有它 ⇒ 被 import、正常退出 0 ⇒ 门禁报 PASS 而**一条都没跑**（O-89 实测过一次）。
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


# ── 脚手架：把 `R.AGENT_CLI` 指向临时文件（判据读的是模块全局，故须临时改）────────
class _TempCli:
    def __init__(self, path: Path):
        self.path = path
        self.old = None

    def __enter__(self):
        self.old = R.AGENT_CLI
        R.AGENT_CLI = self.path
        return self.path

    def __exit__(self, *exc):
        R.AGENT_CLI = self.old
        return False


def _real_cli_text() -> str:
    return R.AGENT_CLI.read_text(encoding="utf-8-sig", errors="replace")


def _write_cli(text: str) -> Path:
    f = Path(tempfile.mkdtemp(prefix="et-test-")) / "agent-cli.ps1"
    f.write_text(text, encoding="utf-8", newline="\n")
    return f


# ── 覆盖夹具：伪造 runDir（把 cluster 的两个私有助手桩掉）──────────────────────
class _FakeRuns:
    """把 `cluster._agent_proj_roots` / `_chain_runs` 桩成"给定 runDir 列表"。"""

    def __init__(self, run_dirs):
        self.run_dirs = run_dirs
        self.old = None

    def __enter__(self):
        import cluster
        self._c = cluster
        self.old = (cluster._agent_proj_roots, cluster._chain_runs)
        cluster._agent_proj_roots = lambda: ({}, "")
        cluster._chain_runs = lambda roots: [("TS", "fake", d) for d in self.run_dirs]
        return self

    def __exit__(self, *exc):
        self._c._agent_proj_roots, self._c._chain_runs = self.old
        return False


def _trace_text(full=True) -> str:
    lines = ["# executor-trace v1 ts=TS"]
    for lit, _ in R.EXEC_TRACE_SECTIONS:
        if lit == "[artifact] hashes=":
            lines.append(lit + "main-side")          # 锚定段要求：哈希由主控侧算（不得自报）
        elif full or lit != "[tool] chain=uncore":
            lines.append(lit + "x")
    return "\n".join(lines) + "\n"


# ── ① ★★ 先验红：删任一采集点标记 ⇒ 必须 FAIL 且点名该标记 ────────────────────
def test_prior_red_each_section():
    real = _real_cli_text()
    for lit, _ in R.EXEC_TRACE_SECTIONS:
        assert lit in real, f"前置：真 agent-cli.ps1 应含 {lit!r}"
        f = _write_cli(real.replace(lit, lit.replace("[", "[X")))
        with _TempCli(f):
            st, note, detail = R.check_executor_trace(None)
        assert st == "FAIL", f"删掉采集点 {lit!r} 后必须红，实际 {st}: {note}"
        assert any(lit in d for d in detail), f"detail 必须点名 {lit!r}: {detail}"


# ── ② ★★ 变异自证：桩恒返 PASS ⇒ 先验红断言必红 ────────────────────────────────
def _mutant_always_pass(_ctx=None):
    return "PASS", "mechanism: mutant", []


def test_mutation_self_proof():
    real = _real_cli_text()
    lit = R.EXEC_TRACE_SECTIONS[0][0]
    f = _write_cli(real.replace(lit, lit.replace("[", "[X")))
    with _TempCli(f):
        real_st, _, _ = R.check_executor_trace(None)
    mutant_st, _, _ = _mutant_always_pass(None)
    assert real_st == "FAIL", "真判据必须检出被删的采集点"
    assert mutant_st == "PASS", "桩应恒返 PASS（先证明假绿确实存在）"
    assert mutant_st != real_st, "若桩也判红，则变异自证不成立"


# ── ③ 负向自证：伪称可核（chain=core / chain=verified）⇒ FAIL ──────────────────
def test_fake_core_claim_is_red():
    real = _real_cli_text()
    for fake in ("chain=core", "chain=verified"):
        f = _write_cli(real + f"\n# {fake}\n")
        with _TempCli(f):
            st, note, detail = R.check_executor_trace(None)
        assert st == "FAIL", f"出现 {fake!r} 必须红，实际 {st}: {note}"
        assert any(fake in d for d in detail), f"detail 必须点名 {fake!r}: {detail}"


# ── ④ 覆盖两态：有件齐段 ⇒ PASS；有件缺段 ⇒ FAIL；0 个 ⇒ PASS 且"未验"────────
def test_coverage_full_is_pass():
    d = Path(tempfile.mkdtemp(prefix="et-run-"))
    (d / "executor-trace.txt").write_text(_trace_text(full=True), encoding="utf-8", newline="\n")
    with _FakeRuns([d]):
        st, note, detail = R.check_executor_trace(None)
    assert st == "PASS", f"齐段应 PASS: {st} · {detail}"
    assert "含该件 1 个" in note and "齐段 1" in note, f"报数不符: {note}"


def test_coverage_missing_section_is_red():
    d = Path(tempfile.mkdtemp(prefix="et-run-"))
    (d / "executor-trace.txt").write_text(_trace_text(full=False), encoding="utf-8", newline="\n")
    with _FakeRuns([d]):
        st, note, detail = R.check_executor_trace(None)
    assert st == "FAIL", f"缺段必须红，实际 {st}: {note}"
    assert any("[tool] chain=uncore" in x for x in detail), f"detail 必须点出缺的段: {detail}"


def test_coverage_zero_is_pass_but_unverified():
    with _FakeRuns([]):
        st, note, detail = R.check_executor_trace(None)
    assert st == "PASS", f"0 个应为 PASS（报数不入分母）: {st} · {detail}"
    assert "未验" in note, f"必须显式标「未验」: {note}"


# ── ④b ★ 锚定段（2026-09-30）：留痕件与主控侧哈希记录须"同一对象、同一权威"──────
#   为什么单列这一段：A2 的 runtime 验收要求 = "留痕件齐 **+ 与产物哈希交叉锚定**"，
#   而上面两段只判"五段在不在"，**不判锚**。实测（2026-09-30 · 11 个含件 runDir）：
#   `ts` 与目录名 11/11 相符 · `content_digest` 11/11 规范 · `hashes` 11/11 = `main-side`
#   ⇒ **存量零违规**（先量后定档）⇒ 前两条可判 **FAIL**；"主控侧无记录"只**报数**
#   （"没验到 ≠ 验出问题"，故意不做 FAIL）。
def _run_dir_with_trace(trace_text, run_json=None):
    d = Path(tempfile.mkdtemp(prefix="et-anchor-"))
    (d / "executor-trace.txt").write_text(trace_text, encoding="utf-8", newline="\n")
    if run_json is not None:
        (d / ".agent-run.json").write_text(json.dumps(run_json), encoding="utf-8", newline="\n")
    return d


def test_anchor_selfreported_hash_is_red():
    t = _trace_text(full=True).replace("[artifact] hashes=main-side",
                                       "[artifact] hashes=sha256:" + "ab" * 32)
    d = _run_dir_with_trace(t, {"content_digest": "sha256:" + "cd" * 32})
    with _FakeRuns([d]):
        st, note, detail = R.check_executor_trace(None)
    assert st == "FAIL", f"执行体自报产物哈希必须红（伪称可核）: {st} · {note}"
    assert any("自报" in x for x in detail), f"detail 必须点名「自报」: {detail}"


def test_anchor_ts_mismatch_is_red():
    t = _trace_text(full=True).replace("ts=TS", "ts=别的run")
    d = _run_dir_with_trace(t, {"content_digest": "sha256:" + "cd" * 32})
    with _FakeRuns([d]):
        st, note, detail = R.check_executor_trace(None)
    assert st == "FAIL", f"留痕件 ts 与 runDir 不符（归属不符）必须红: {st} · {note}"
    assert any("归属" in x for x in detail), f"detail 必须点名「归属」: {detail}"


def test_anchor_missing_main_side_digest_is_gap_not_fail():
    d = _run_dir_with_trace(_trace_text(full=True), None)      # 无 .agent-run.json
    with _FakeRuns([d]):
        st, note, detail = R.check_executor_trace(None)
    assert st == "PASS", f"缺主控侧记录只报数（没验到 ≠ 验出问题）: {st} · {note}"
    assert "无锚记录 1" in note, f"note 必须报出无锚记录: {note}"


def test_anchor_all_green_on_fake_full_run():
    d = _run_dir_with_trace(_trace_text(full=True), {"content_digest": "sha256:" + "cd" * 32})
    with _FakeRuns([d]):
        st, note, detail = R.check_executor_trace(None)
    assert st == "PASS", f"齐段 + 锚在 应 PASS: {st} · {detail}"
    assert "ts 相符 1" in note and "自报 0" in note and "无锚记录 0" in note, f"报数不符: {note}"


# ── ⑤ 端到端 + 结构护栏 ─────────────────────────────────────────────────────
def test_gate_end_to_end_on_real_repo():
    st, note, detail = R.check_executor_trace(None)
    assert st == "PASS", f"本仓留痕机制应当齐备: {st} · {detail}"
    assert "采集点 5/5" in note, f"报数不符: {note}"
    assert "自报 0" in note and "无锚记录 0" in note, f"锚定读数应全绿（存量零违规）: {note}"


def test_missing_cli_is_red():
    old = R.AGENT_CLI
    try:
        R.AGENT_CLI = ROOT / "ops" / "__不存在__.ps1"
        st, note, _ = R.check_executor_trace(None)
    finally:
        R.AGENT_CLI = old
    assert st == "FAIL", f"缺 agent-cli.ps1 必须 FAIL（不可判 ≠ 通过），实际 {st}: {note}"


def test_entry_registered_and_quick():
    ids = {c["id"]: c for c in R.CHECKS}
    assert "executor-trace" in ids, "executor-trace 未注册进 CHECKS"
    assert ids["executor-trace"]["quick"] is True, "executor-trace 必须 quick（否则提交时跑不到）"


# ── 无 pytest 的自跑入口（本文件自己也要有！）───────────────────────────────
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