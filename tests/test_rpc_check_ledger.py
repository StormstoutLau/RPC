#!/usr/bin/env python3
"""`ops/rpc_check.py` 的 `check_ledger_status` 测试 —— **O-93**（2026-09-26）

判据 = 台账（`OPEN-ISSUES.md`）**每行的状态格必须可机读**：格首标记自证
（`✅`/`◐`/`⏳`/`🔵`，**允许加粗包裹**），且状态格子**不在固定第几格**（本表列数不齐）。

⚠⚠ **本判据的射程必须在这里钉住**：它**只保证"读得到"**，**不判**"应该闭环多少"，
  也**不判**状态写得对不对（见 `test_scope_is_only_readability`）。

⚠ 本文件**自带 `__main__` 入口**：门禁 `py-tests` 以**脚本**方式调用（只认退出码）。
  没有它 ⇒ 被 import、定义一堆 `test_*`、正常退出 0 ⇒ 门禁报 PASS 而**一条都没跑**（O-89 实测过一次）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _row(oid, status_cell, extra=""):
    """按**老行形状**（8 格）造一行：ID|类别|严重度|简述|状态|归属|<br />|<br />"""
    return f"| {oid} | 功能缺口 | P3 | 简述 | {status_cell} | 归属 | <br /> | <br /> |"


# ── ① 正例：老行形状（8 格） ─────────────────────────────────────────────
def test_positive_legacy_shape():
    rows = R.parse_ledger_rows(_row("O-01", "✅ closed"))
    assert len(rows) == 1 and rows[0]["status"].startswith("✅"), rows


# ── ② ★★ 边界：标记被**加粗包裹**（这是"假开"的直接根因） ─────────────────
def test_bold_wrapped_marker_is_readable():
    """实测 22 行写成 `**✅ …**`；直接用 `^✅` 会判"无状态" ⇒ **假开**（我的第一版探针就是这么错的）。"""
    rows = R.parse_ledger_rows(_row("O-30", "**✅ 纪律已入册（2026-09-24）**"))
    assert rows[0]["status"].startswith("✅"), rows[0]["status"]


def test_bold_wrapped_marker_counts_as_closed():
    """★★ **可读 ≠ 分类正确** —— 加粗包裹的行必须被算作**闭环**，而不只是"读得到"。

    ⚠⚠ 这条是本批实测补的：第一版实现只对**匹配**归一、**比较**时仍拿裸文本
      ⇒ `**✅ …**` 不 `startswith('✅')` ⇒ **15 行被算成「仍开着」**（又一次**假开**）。
      抓出来的方式 = **判据报数与独立探针报数不一致**（判据 57/35 vs 探针 72/20）。
    ⚠ 而当时的测试②写的是 `startswith("**✅")` —— **把 bug 写成了期望**（断言太弱 ⇒ 它替 bug 背书）。
      ⇒ 本条的教训：**报数型判据必须与独立实现对数**，否则"数对了没有"没人知道。
    """
    rows = R.parse_ledger_rows(_row("O-30", "**✅ 纪律已入册（2026-09-24）**"))
    closed = [r for r in rows if r["status"].startswith(R.LEDGER_CLOSED_MARK)]
    assert len(closed) == 1, f"加粗包裹的 ✅ 必须算闭环，实际 status={rows[0]['status']!r}"


# ── ③ ★ 边界：**位置不固定**（老行状态在第 5 格、新行在第 6 格） ────────────
def test_position_independent():
    legacy = _row("O-01", "✅ closed")
    modern = "| O-93 | 台账 | P2 | 简述 | 证据文本 | ◐ 已登记 · 未处置 |"
    a = R.parse_ledger_rows(legacy)[0]["status"]
    b = R.parse_ledger_rows(modern)[0]["status"]
    assert a.startswith("✅") and b.startswith("◐"), (a, b)


# ── ④ ★ 边界：后面的格**复述** ✅（老行「归属批次」列）⇒ 取**第一个**命中 ────
def test_first_hit_wins_over_echo():
    """状态格是 `◐ …`（未闭环）、归属格复述 `✅ 已修` ⇒ 状态必须取**第一个** ⇒ **未闭环**。"""
    line = "| O-99 | 并发 | P1 | 简述 | ◐ 已登记未处置 | ✅ 已修 |"
    rows = R.parse_ledger_rows(line)
    assert rows[0]["status"].startswith("◐"), rows[0]["status"]
    closed = [r for r in rows if r["status"].startswith(R.LEDGER_CLOSED_MARK)]
    assert closed == [], "复述的 ✅ 不得把该行算成闭环"


# ── ⑤ 反例：格首无标记 ⇒ 读不出来 ────────────────────────────────────────
def test_no_marker_is_unreadable():
    for cell in ("已定性（2026-09-25）", "⚠ 实测复现", ""):
        rows = R.parse_ledger_rows(_row("O-99", cell))
        assert rows[0]["status"] == "", f"`{cell}` 不该被当成状态"


# ── ⑥ ★★ 先验红：证明这条判据不是「按整行找 ✅」那种口径 ────────────────────
def _naive_row_has_check(line):
    """桩：整行出现 ✅ 就算闭环（= 我最初那版口径）。"""
    return "✅" in line


def test_the_check_is_not_vacuous():
    """★★ 同一行：**桩会把「开着」判成闭环**（因为引文里出现了 ✅），真判据必须读出「未闭环」。

    没这条，判据就只是"整行找 ✅"的同义词 —— 而那正是实测里**假关**（"看起来都没事了"）的来源。
    """
    line = "| O-99 | 安全 | P1 | 简述 | ◐ 已登记 · 未闭环；引文里引用过 ✅ 已修的旧行 | 归属 |"
    assert _naive_row_has_check(line) is True, "桩应当判成闭环（证明该口径确实会错）"
    assert R.parse_ledger_rows(line)[0]["status"].startswith("◐"), "真判据必须读出「未闭环」"


# ── ⑦ ★★ 射程钉住：它**不判**状态写得对不对（别读过头） ────────────────────
def test_scope_is_only_readability():
    """★★ 一行 `✅ 已闭环` 但内容其实没闭环 ⇒ 本判据**会放行**。

    ⚠ 这不是缺陷，是**射程**：本判据只保证**读得到**；「状态写得对不对」**不可机判**，仍要人读。
    ⇒ 本测试**永久记录**这条边界：谁想用它声称"台账已被审计"，会先看到它。
    """
    lying = _row("O-99", "✅ 已闭环（其实什么都没做）")
    rows = R.parse_ledger_rows(lying)
    assert rows[0]["status"].startswith("✅"), "判据**只**看标记，不看内容真伪"


# ── ⑧ 端到端：真读本仓台账（含"防空判"） ─────────────────────────────────
def test_repo_end_to_end():
    assert R.LEDGER.is_file(), "台账文件必须存在（判据的登记依据）"
    rows = R.parse_ledger_rows(R._read_text(R.LEDGER))
    assert len(rows) >= 80, f"★ 数据行过少（{len(rows)}）⇒ 可能格式被改动，判据近乎空判"
    bad = [r["id"] for r in rows if not r["status"]]
    assert bad == [], f"这些行的状态不可机读: {bad}"
    opened = [r for r in rows if not r["status"].startswith(R.LEDGER_CLOSED_MARK)]
    assert opened, "★ 一条都不开着 ⇒ 可疑（本仓不会没有 open issue）"


def test_entry_is_registered_and_quick():
    ids = {c["id"]: c for c in R.CHECKS}
    assert "ledger-status" in ids, "ledger-status 未注册进 CHECKS"
    assert ids["ledger-status"]["quick"] is True, "ledger-status 必须 quick（否则提交时跑不到）"


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
