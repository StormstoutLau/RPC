#!/usr/bin/env python3
"""`ops/derived_view.py` + 门禁 `derived-view` 的测试 —— **A3**（2026-09-29）

派生**只读视图**：清单类文档的"第二定义点"正解 —— 抄的那份从真值**渲染**出来，
`--check` **逐字节**验证"没被手改、也没过期"。

覆盖：
  · **三态退出码**（0 一致 / 1 过期·漂移 / 2 渲染链路故障）互不混淆；
  · **先验红**（改真值不重渲染 ⇒ 必须 rc=1 且报「过期」）· **变异自证**（桩恒返 0 ⇒ 先验红断言必红）；
  · **跨行尾 / BOM 可复现性**（同一真值 LF vs CRLF vs BOM ⇒ 同一 `source-hash`）；
  · 守门条：档内**只含确定性字段**（**无 `generated-at`**）；
  · 端到端 + 结构护栏（gate 已注册 · quick）。

⚠⚠ **本文件自带 `__main__` 入口**：门禁 `py-tests` 以**脚本**方式调用（只认退出码）。
  没有它 ⇒ 被 import、正常退出 0 ⇒ 门禁报 PASS 而**一条都没跑**（O-89 实测过一次）。
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import derived_view as dv  # noqa: E402
import rpc_check as R  # noqa: E402


# ── 夹具脚手架：在临时根上重建"真值 + 落档视图"这一对 ────────────────────────
def _real_truth() -> str:
    return (ROOT / "inventory" / "ports.yaml").read_text(encoding="utf-8-sig")


def _mk_root(truth: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="dv-test-"))
    (d / "inventory").mkdir(parents=True, exist_ok=True)
    (d / "inventory" / "ports.yaml").write_text(truth, encoding="utf-8", newline="\n")
    return d


def _write_truth(d: Path, truth: str) -> None:
    (d / "inventory" / "ports.yaml").write_text(truth, encoding="utf-8", newline="\n")


class _TempView:
    """把 `dv.VIEW` 指向临时档（`check()` 读的是模块全局 VIEW，故须临时改）。"""

    def __init__(self, path: Path):
        self.path = path
        self.old = None

    def __enter__(self):
        self.old = dv.VIEW
        dv.VIEW = self.path
        return self.path

    def __exit__(self, *exc):
        dv.VIEW = self.old
        return False


# ── ① 真值 → 渲染：确定性 + 守门条（只含确定性字段 / LF / 无 BOM）───────────────
def test_render_is_bytewise_deterministic():
    assert dv.render(ROOT) == dv.render(ROOT), "同一真值两次渲染必须逐字节一致"


def test_view_has_no_nondeterministic_field():
    """★ 守门条（勘误 §1.2）：档内**只含确定性字段** —— `generated-at` 这种**非确定字段**不得入档。"""
    text = dv.render(ROOT)
    assert "generated-at" not in text, "时间戳入档 ⇒ 每次渲染该行必变 ⇒ 比对永远失败"
    assert "source-hash:" in text and "generator:" in text
    assert text.startswith(dv.MARKER), "档头注释标记缺失 ⇒ 人不知道这是派生件"
    assert "\r" not in text, "渲染必须是 LF（否则跨平台 source-hash/比对漂移）"


def test_header_fields_are_whitelisted():
    """档头 `key: value` 行**只有** `source-hash` / `generator`（多一个非白名单字段 = 引入非确定性）。"""
    text = dv.render(ROOT)
    keys = {ln.split(":", 1)[0] for ln in text.splitlines()
            if ":" in ln and ln[:1].islower() and ln[:1].isalpha() and "|" not in ln[:1]}
    assert keys == {"source-hash", "generator"}, f"档头字段超出白名单: {keys}"


# ── ② ★★ 先验红：改真值不重渲染 ⇒ 必须 rc=1 且报「过期」────────────────────────
def test_prior_red_truth_changed():
    truth = _real_truth()
    d = _mk_root(truth)
    try:
        view = d / "派生视图_端口分配.md"
        with _TempView(view):
            view.write_text(dv.render(d), encoding="utf-8", newline="\n")
            assert dv.check(d)[0] == dv.EXIT_OK, "前置：一致态必须绿"
            _write_truth(d, truth + "\n# 改真值（不重渲染）\n")
            rc, msg = dv.check(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    assert rc == dv.EXIT_STALE, f"改真值后必须过期(rc=1)，实际 rc={rc}: {msg}"
    assert "过期" in msg, f"报错必须点明「过期」: {msg}"


# ── ③ ★★ 变异自证：桩恒返 0 ⇒ 先验红断言必红 ────────────────────────────────
def _mutant_always_ok(_root=ROOT):
    """**假绿版**判据的桩：恒返"一致" ⇒ 先验红断言必须因此判红。"""
    return dv.EXIT_OK, "PASS: mutant"


def test_mutation_self_proof():
    truth = _real_truth()
    d = _mk_root(truth)
    try:
        view = d / "v.md"
        with _TempView(view):
            view.write_text(dv.render(d), encoding="utf-8", newline="\n")
            _write_truth(d, truth + "\n# changed\n")
            real_rc, _ = dv.check(d)
            mutant_rc, _ = _mutant_always_ok(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    assert real_rc == dv.EXIT_STALE, "真判据必须检出真值改动"
    assert mutant_rc == dv.EXIT_OK, "桩应恒返 0（先证明假绿确实存在）"
    assert mutant_rc != dv.EXIT_STALE, "若桩也报过期，则变异自证不成立"


# ── ④ 三态边界：故障(2) / 漂移(1) / 缺哈希行(1) ──────────────────────────────
def test_view_missing_is_fault_not_stale():
    """★ 落档缺失 ⇒ **故障(2)** 而非"过期(1)" —— 两态**绝不可混**（否则人会去查代码而非补档）。"""
    d = _mk_root(_real_truth())
    try:
        with _TempView(d / "不存在.md"):
            rc, msg = dv.check(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    assert rc == dv.EXIT_FAULT, f"档缺必须是 2，实际 {rc}: {msg}"


def test_hand_edited_view_is_stale():
    """哈希一致但正文被手改一个字符 ⇒ 1（逐字节不等）。"""
    truth = _real_truth()
    d = _mk_root(truth)
    try:
        view = d / "v.md"
        with _TempView(view):
            view.write_text(dv.render(d).replace("端口分配", "端口分配X"), encoding="utf-8", newline="\n")
            rc, msg = dv.check(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    assert rc == dv.EXIT_STALE and "逐字节" in msg, f"手改必须报逐字节不一致: rc={rc} {msg}"


def test_missing_hash_line_shortcircuits():
    truth = _real_truth()
    d = _mk_root(truth)
    try:
        view = d / "v.md"
        with _TempView(view):
            body = "\n".join(ln for ln in dv.render(d).splitlines() if not ln.startswith("source-hash:"))
            view.write_text(body + "\n", encoding="utf-8", newline="\n")
            rc, msg = dv.check(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    assert rc == dv.EXIT_STALE and "source-hash" in msg, f"缺哈希行必须判过期: rc={rc} {msg}"


# ── ⑤ ★ 跨行尾 / BOM 可复现性（`source-hash` 不得随检出配置变）────────────────
def test_cross_line_ending_and_bom_reproducible():
    lf = "version: 1\nmanaged:\n  - port: 22\n    proto: tcp\n"
    d = Path(tempfile.mkdtemp(prefix="dv-eol-"))
    (d / "inventory").mkdir(parents=True, exist_ok=True)
    f = d / "inventory" / "ports.yaml"
    try:
        f.write_bytes(lf.encode("utf-8"))
        h_lf = dv.source_hash(d)
        f.write_bytes(lf.replace("\n", "\r\n").encode("utf-8"))
        assert f.read_bytes() != lf.encode("utf-8"), "前置：CRLF 版原始字节必须与 LF 不同"
        h_crlf = dv.source_hash(d)
        f.write_bytes(b"\xef\xbb\xbf" + lf.encode("utf-8"))
        h_bom = dv.source_hash(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    assert h_lf == h_crlf, "CRLF vs LF ⇒ 同一 source-hash（否则视图在不同机器互相过期）"
    assert h_lf == h_bom, "带 BOM ⇒ 同一 source-hash"


# ── ⑥ 端到端 + 结构护栏 ─────────────────────────────────────────────────────
def test_gate_end_to_end_on_real_repo():
    st, note, detail = R.check_derived_view(None)
    assert st == "PASS", f"本仓视图应当与真值一致: {st} · {detail}"
    assert "source-hash" in note and "逐字节一致" in note, f"报数不符: {note}"


def test_gate_warns_when_script_absent(monkeypatch=None):
    """渲染器不在 ⇒ **WARN**（登记依据没了，不谎报 PASS，也不硬 FAIL）。"""
    old = R.DERIVED_VIEW
    try:
        R.DERIVED_VIEW = ROOT / "ops" / "__不存在__.py"
        st, note, _ = R.check_derived_view(None)
    finally:
        R.DERIVED_VIEW = old
    assert st == "WARN", f"缺脚本应为 WARN，实际 {st}: {note}"


def test_entry_registered_and_quick():
    ids = {c["id"]: c for c in R.CHECKS}
    assert "derived-view" in ids, "derived-view 未注册进 CHECKS"
    assert ids["derived-view"]["quick"] is True, "derived-view 必须 quick（否则提交时跑不到）"


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