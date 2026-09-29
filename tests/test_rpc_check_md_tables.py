#!/usr/bin/env python3
"""`ops/rpc_check.py` 的 `check_md_tables` 测试 —— **A4**（2026-09-29）

判据 = 同一张 markdown 表里 **分隔行 / 数据行** 的**格数**必须 == **表头**格数。
事故形态（真实、已抽象）：某字段文本里出现**一个未转义的竖线** ⇒ 该行被拆成比表头更多的格，
  字段错位、**长期无人发现**（此前**没有任何检查器读"列数"**）。

口径（**唯一实现** = `md_table_scan`，照 `dogfood-cards/land-a4-cell-safety.md` 的**已勘误**底稿）：
  ① **空单元格计入**格数；② 分隔行必须**紧邻**表头；③ 代码围栏 / GFM 缩进码块**跳过**；
  ④ 单元格里的转义竖线**不算分隔**。

⚠ 本文件**自带 `__main__` 入口**：门禁 `py-tests` 以**脚本**方式调用（只认退出码）。
  没有它 ⇒ 被 import、定义一堆 `test_*`、正常退出 0 ⇒ 门禁报 PASS 而**一条都没跑**（O-89 实测过一次）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _tbl(*rows, head="| a | b | c |", sep="|---|---|---|"):
    return "\n".join([head, sep, *rows]) + "\n"


# ── ① 正例 ───────────────────────────────────────────────────────────────
def test_positive_wellformed():
    v, n = R.md_table_scan(_tbl("| 1 | 2 | 3 |", "| x | y | z |"))
    assert v == [], f"合规表不该判红: {v}"
    assert n == 1, f"应识别 1 张表，实际 {n}"


def test_empty_cell_counts_as_column():
    """★ 口径①：`| a |  | c |` 是 **3 格**（空单元格计入）—— 若按"非空才计数"会得 2 ⇒ 假红。"""
    v, n = R.md_table_scan(_tbl("| 1 |  | 3 |"))
    assert v == [], f"空单元格应计入列数（3 格）：{v}"
    assert n == 1


def test_escaped_pipe_is_content_not_separator():
    """★ 口径④：单元格里的**转义竖线** `\\|` 是内容，**不拆格** ⇒ 该行仍是 3 格。"""
    v, n = R.md_table_scan(_tbl(r"| a\|b | 2 | 3 |"))
    assert v == [], f"转义竖线不该被当分隔符：{v}"
    assert n == 1


# ── ② ★★ 先验红：未转义竖线 ⇒ 该行**必须**被报出 ────────────────────────────
def test_prior_red_unescaped_pipe_splits_cell():
    """★★ A4 的**先验红点**：往数据行塞一个**未转义**竖线 ⇒ 该行格数变多 ⇒ **必须**报出。"""
    v, n = R.md_table_scan(_tbl("| x | y | z | extra |"))
    assert v, "未转义竖线导致拆成 4 格 ⇒ 必须判红"
    ln, kind, dc, hc = v[0]
    assert (kind, dc, hc) == ("row", 4, 3), f"应报 row 4≠3，实际 {v[0]}"
    assert ln == 3, f"应指向第 3 行（第 1 个数据行），实际 {ln}"


def test_prior_red_missing_cell():
    """数据行**少一格**（2≠3）⇒ 必须报出。"""
    v, _ = R.md_table_scan(_tbl("| x | y |"))
    assert v and v[0][1] == "row" and v[0][2] == 2 and v[0][3] == 3, f"实际 {v}"


def test_prior_red_separator_mismatch():
    """分隔行与表头**不等**（4≠3）⇒ 报 sep 类违规。"""
    v, n = R.md_table_scan(_tbl("| 1 | 2 | 3 |", sep="|---|---|---|---|"))
    assert n == 1 and v and v[0][1] == "sep" and v[0][2] == 4 and v[0][3] == 3, f"实际 {v}"


# ── ③ 边界：围栏 / 缩进码块 / 分隔行必须紧邻 ────────────────────────────────
def test_code_fence_pseudo_table_is_skipped():
    """```围栏内的伪表格**不参与判定**（GFM 里它就不是表）⇒ 不报违规，且**表数为 0**。"""
    md = "```\n| a | b |\n|---|---|\n| x | y | z |\n```\n"
    v, n = R.md_table_scan(md)
    assert v == [] and n == 0, f"围栏内不该判：v={v} n={n}"


def test_tilde_fence_pseudo_table_is_skipped():
    """`~~~` 围栏（勘误①补入的形态）内的伪表格同样跳过。"""
    md = "~~~\n| a | b |\n|---|---|\n| x | y | z |\n~~~\n"
    v, n = R.md_table_scan(md)
    assert v == [] and n == 0, f"~~~ 围栏内不该判：v={v} n={n}"


def test_indented_code_block_is_skipped():
    """GFM 缩进码块（≥4 空格）里的"表"**不是表** ⇒ 跳过（底稿 §假绿 第 2 条）。"""
    md = "    | a | b |\n    |---|---|\n    | x | y | z |\n"
    v, n = R.md_table_scan(md)
    assert v == [] and n == 0, f"缩进码块不该判：v={v} n={n}"


def test_separator_must_be_adjacent_to_header():
    """★ 口径②：表头 → **空行/散文** → `|---|` **不是**一张表（GFM 要求紧邻）⇒ 不判。"""
    md = "| a | b |\n\n散文一行\n|---|---|\n| x | y | z |\n"
    v, n = R.md_table_scan(md)
    assert n == 0 and v == [], f"分隔行不紧邻表头 ⇒ 不该当成表：v={v} n={n}"


# ── ④ ★★ 变异自证：把判据改成**恒返空**⇒ 先验红那几条**必然失守** ──────────────
def _mutant_always_empty(_text):
    """变异体：恒返"没有违规"（= 一台**假绿机**）。"""
    return [], 0


def test_mutation_self_proof():
    """★★ 变异自证：把判据换成恒返空 ⇒ 先验红用例必须**抓不到**（证明那几条断言不是恒真装饰）。"""
    bad_md = _tbl("| x | y | z | extra |")
    assert R.md_table_scan(bad_md)[0], "真判据必须报出未转义竖线"
    assert _mutant_always_empty(bad_md)[0] == [], "变异体恒返空 ⇒ 恰好漏掉 ⇒ 自证成立"


# ── ⑤ 端到端：真读本仓 ─────────────────────────────────────────────────────
def test_repo_end_to_end():
    """真跑本仓：应为 **PASS**（存量 28 处已逐条冻结在 `inventory/md-tables.yaml`）。"""
    status, note, detail = R.check_md_tables(None)
    assert status == "PASS", f"本仓应 PASS，实际 {status}；明细：{detail[:6]}"
    assert "表 " in note and "新增 0" in note, f"note 应报表数与『新增 0』：{note}"


def test_frozen_entries_all_exist():
    """冻结清单**逐条**的 `file` 必须在仓里（否则就是登记腐化 —— 门禁也会报）。"""
    import yaml
    inv = yaml.safe_load((ROOT / "inventory" / "md-tables.yaml").read_text(encoding="utf-8"))
    fr = inv.get("frozen") or []
    assert fr, "冻结清单为空 ⇒ 本测试失去对象（或本表被误清空）"
    missing = [e.get("file") for e in fr if not (ROOT / str(e.get("file") or "")).exists()]
    assert not missing, f"冻结条目指向不存在的文件：{missing}"


# ── ⑥ 结构护栏：注册 + quick ───────────────────────────────────────────────
def test_entry_is_registered_and_quick():
    ids = {c["id"]: c for c in R.CHECKS}
    assert "md-tables" in ids, "md-tables 未注册进 CHECKS"
    assert ids["md-tables"]["quick"] is True, "md-tables 必须 quick（否则提交时跑不到）"


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