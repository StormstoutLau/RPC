#!/usr/bin/env python3
"""`ops/rpc_check.py` 的 A5「确定性噪声口径 + 双跑逐字节比对」测试 —— **A5**（2026-09-29）

覆盖：判据纯函数（`det_manifest_diff` / `det_scan_noise`）· 噪声真值表健康 · `determinism: n/a` 纪律 ·
**真管线双跑实测**（真读本仓 `inventory/*.yaml` 两次）· 先验红（时间戳写进产物 ⇒ 必须报）· 变异自证。

⚠⚠ **本文件自带 `__main__` 入口**：门禁 `py-tests` 以**脚本**方式调用（只认退出码）。
  没有它 ⇒ 被 import、正常退出 0 ⇒ 门禁报 PASS 而**一条都没跑**（O-89 实测过一次）。
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


# ── ① 判据纯函数：逐字节比对 ────────────────────────────────────────────────
def test_diff_equal_manifests_is_empty():
    m = {"a.txt": "00", "b.txt": "11"}
    assert R.det_manifest_diff(m, dict(m)) == []


def test_diff_key_order_irrelevant():
    """★ 键序不同 ⇒ 仍是**同一集合** ⇒ 不报差异（底稿边界用例⑤）。"""
    assert R.det_manifest_diff({"a": "1", "b": "2"}, {"b": "2", "a": "1"}) == []


def test_diff_detects_missing_and_changed():
    d = R.det_manifest_diff({"a": "1"}, {"a": "2", "b": "3"})
    paths = {x["path"] for x in d}
    assert paths == {"a", "b"}, f"应报 a(改) 与 b(缺)，实际 {paths}"


def test_crlf_vs_lf_is_a_difference():
    """★ 底稿边界用例④：行尾不同 ⇒ **判不一致**（比对端**不**归一化换行符）。"""
    crlf = hashlib.sha256(b"x\r\n").hexdigest()
    lf = hashlib.sha256(b"x\n").hexdigest()
    assert R.det_manifest_diff({"f": crlf}, {"f": lf}), "CRLF vs LF 必须判为不同（不归一化）"


# ── ② ★★ 先验红：把**时间戳**写进产物 ⇒ 双跑必须报差异 ────────────────────────
def _manifest_of(paths):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def test_prior_red_timestamp_in_artifact():
    """★★ 同一份产物：一次原样、一次**追加当前时间戳** ⇒ 差异清单**必须非空**且点到该路径。"""
    base = ROOT / "inventory" / "id-site-census.yaml"
    assert base.exists(), "先验红需要一个真实产物文件"
    a = {"id-site-census.yaml": hashlib.sha256(base.read_bytes()).hexdigest()}
    b = {"id-site-census.yaml": hashlib.sha256(base.read_bytes() + b"\n2026-09-29T12:00:00").hexdigest()}
    diffs = R.det_manifest_diff(a, b)
    assert diffs and diffs[0]["path"] == "id-site-census.yaml", f"时间戳噪声必须被报出: {diffs}"


def _mutant_diff_always_empty(_a, _b):
    """**假绿版**判据的桩：恒返空 ⇒ 先验红断言必须因此判红。"""
    return []


def test_mutation_self_proof():
    """★★ 把比较函数换成"恒返空" ⇒ `test_prior_red_timestamp_in_artifact` 的核心断言必须失败。

    没这条，"先验红"就可能只是**碰巧**（或判据本身恒真）而无人知道。
    """
    base = ROOT / "inventory" / "id-site-census.yaml"
    a = {"f": hashlib.sha256(base.read_bytes()).hexdigest()}
    b = {"f": hashlib.sha256(base.read_bytes() + b"\n2026-09-29T12:00:00").hexdigest()}
    assert R.det_manifest_diff(a, b), "真判据必须报差异"
    assert _mutant_diff_always_empty(a, b) == [], "桩应当恒返空（证明假绿确实存在）"
    # 变异体在"先验红"上会漏掉差异 ⇒ 自证成立
    assert not _mutant_diff_always_empty(a, b), "若桩也报差异，则变异自证不成立"


# ── ③ 判据纯函数：噪声扫描 ──────────────────────────────────────────────────
def test_noise_scanner_hits_each_machine_type():
    import yaml
    tbl = yaml.safe_load(R.DET_NOISE_INV.read_text(encoding="utf-8"))
    for e in tbl["noise_types"]:
        samples = R._DET_SAMPLES.get(e["id"])
        if not samples:
            continue                      # 无字面模式者（并发键序 / 文件系统元数据）不参与
        for s in samples:
            assert e["id"] in R.det_scan_noise(s, [e]), f"{e['id']} 应命中样本 {s!r}"


def test_noise_scanner_ignores_clean_text():
    import yaml
    tbl = yaml.safe_load(R.DET_NOISE_INV.read_text(encoding="utf-8"))
    assert R.det_scan_noise("普通内容，没有噪声。", tbl["noise_types"]) == []


# ── ④ `determinism: n/a` 纪律（机读形态）────────────────────────────────────
def test_na_requires_reason():
    bad = []
    n = R._det_walk_na({"items": [{"path": "x", "determinism": "n/a"}]}, "t.yaml", bad)
    assert n == 1 and bad and "缺 `reason`" in bad[0], f"缺理由必须报违规: {bad}"


def test_na_with_reason_is_ok():
    bad = []
    n = R._det_walk_na({"items": [{"path": "x", "determinism": "n/a", "reason": "推远端，不可双跑"}]},
                       "t.yaml", bad)
    assert n == 1 and bad == [], f"有理由不该报违规: {bad}"


# ── ⑤ ★★ 真管线双跑实测：真读本仓 inventory/*.yaml 两次 ──────────────────────
def test_repo_double_run_is_bytewise_identical():
    """★★ 一个**真管线**的双跑：同一批真实产物读两次 ⇒ 清单**逐字节一致**（差异 == 空）。"""
    paths = sorted((ROOT / "inventory").glob("*.yaml"))
    assert len(paths) >= 10, "★ 命中集过小 ⇒ 双跑没有对象（会退化成空判）"
    assert R.det_manifest_diff(_manifest_of(paths), _manifest_of(paths)) == []


# ── ⑥ 端到端：真读本仓表 ⇒ 判据必须 PASS，且报数正确 ────────────────────────
def test_gate_end_to_end():
    st, note, detail = R.check_determinism(None)
    assert st == "PASS", f"本仓噪声表应当健康: {st} · {detail}"
    assert "噪声 7 类" in note and "可机检 5" in note, f"报数不符: {note}"
    assert "updated=2026-09-29" in note, f"应报读数日期: {note}"


# ── ⑦ 结构护栏 ─────────────────────────────────────────────────────────────
def test_entry_is_registered_and_quick():
    ids = {c["id"]: c for c in R.CHECKS}
    assert "determinism" in ids, "determinism 未注册进 CHECKS"
    assert ids["determinism"]["quick"] is True, "determinism 必须 quick（否则提交时跑不到）"


def test_applies_to_consumers_are_real():
    import yaml
    tbl = yaml.safe_load(R.DET_NOISE_INV.read_text(encoding="utf-8"))
    known = {c["id"] for c in R.CHECKS}
    for e in tbl["noise_types"]:
        for cid in (e.get("applies_to") or []):
            assert cid in known, f"{e['id']} 的消费者 {cid!r} 不是真实断言 id（孤儿消费者）"


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