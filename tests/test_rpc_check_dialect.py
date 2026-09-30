"""`dialect` 断言（D7-P1-1）的正反注入 —— 永久护栏（2026-09-26）

D7-P1-1 的退出判据是「单一轴字典 + 映射表落盘；**映射表本身可被门禁校验（源词表变了下游红）**」。
本文件保护的就是那后半句 —— 它最容易被做成**空头承诺**（"我们会盯着源"）。

本断言的两种对象病**都有真实来源**，不是假想：
  · **漏项**：`b1b` 的对照表实测漏了摘要族 2 的第三行（`Cpp_Hub` 平台支持档位）⇒ `coverage` 双向点行数；
  · **静默漂移**：源词表改了、映射表还是旧的 ⇒ 源切片指纹比对。

⚠ 两处**刻意不做**的事（否则就是本仓头号形态）：
  · 读不到源**不**当作通过 —— 读失败 ⇒ 显式报"不可判"（`test 16`）；
  · 指纹口径（CRLF / 尾空白）必须与写指纹时**逐字一致**，否则每次都假红 ⇒ `test 15b` 钉住它。
"""
import hashlib
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

SRC = "L1 官方\nL2 社区\n"
# 与 SRc 同内容、但 CRLF + 行尾空白的变体 ⇒ **必须**算出同一个哈希（口径钉死）
SRC_CRLF = "L1 官方\r\nL2 社区  \r\n"
SRC_SHA = "af488798235febd98c392c3929fcac1660e573d61118fc74fba95ec8a256c98d"

FILES = {"docs/src.md": SRC}
EXISTS = {"docs/src.md": True}

# ★★ `U1#5`（2026-10-01）：命名空间白名单**不再来自 dialect.yaml**，改从**注册表**读
#   ⇒ 夹具必须显式喂一个注册表（这也顺带证明"白名单真的换了来源"：本夹具的 `_inv()` 里**没有** `namespaces` 键）。
REG = {"namespaces": [
    {"id": "open_data", "label": "Open_Data", "status": "active", "since": "2026-09-26", "aliases": ["Open_Data"]},
    {"id": "retired_one", "label": "旧项目", "status": "retired", "since": "2026-09-26", "aliases": []},
]}


def _inv(**over):
    base = {
        "axis": {"id": "evidence-strength", "label": "证据强度",
                 "values": [{"id": "official", "label": "官方来源"},
                            {"id": "community", "label": "社区来源"}]},
        # ⚠ 这里**故意没有** `namespaces` 键：取值域的真值已剥到 `inventory/namespaces.yaml`（`REG`）
        "sources": [{"id": "s1", "path": "docs/src.md", "whole_file": True, "sha256": SRC_SHA}],
        "coverage": [{"family": "L", "expected_rows": 1}],
        "mapping": [{"family": "L", "namespace": "open_data", "symbol": "L1", "source": "Open_Data",
                     "raw_meaning": "官方来源级", "relation": "冲突",
                     "axis": "evidence-strength", "axis_value": "official"}],
        "conflicts": [{"symbol": "L", "sides": "A vs B", "why": "不同轴"}],
        "undecidable": [{"item": "X 的含义", "missing": "定义原文"}],
    }
    base.update(over)
    return base


def _row(**over):
    r = {"family": "L", "namespace": "open_data", "symbol": "L1", "source": "Open_Data",
         "raw_meaning": "官方来源级", "relation": "冲突",
         "axis": "evidence-strength", "axis_value": "official"}
    r.update(over)
    return r


CASES = [
    # ── 正例 ────────────────────────────────────────────────────────────
    ("正例 最小合格",
     _inv(), True, "映射 1 行"),
    ("正例 not-assigned + axis_note（未定轴允许，但必须说明属于什么轴）",
     _inv(mapping=[_row(axis="not-assigned", axis_value=None, axis_note="属阶段序轴")]),
     True, "映射 1 行"),
    ("正例 axis_value=undefined + 理由（属此轴但逐级对应不可判）",
     _inv(mapping=[_row(axis_value="undefined", axis_note="摘要未给逐级对应")]),
     True, "映射 1 行"),

    # ── ★ 前缀必填（§11.4 教训①）──────────────────────────────────────
    ("★反例 缺 namespace（前缀是**必填字段**，不靠人自觉）",
     _inv(mapping=[_row(namespace=None)]), False, "缺 `namespace`"),
    ("★反例 namespace 不在**注册表**白名单里（`U1#5`：白名单来源已换）",
     _inv(mapping=[_row(namespace="ghost_proj")]), False, "不在命名空间注册表"),
    ("★反例 namespace 是 `retired`（注册表里在、但**不许新用**）",
     _inv(mapping=[_row(namespace="retired_one")]), False, "不在命名空间注册表"),
    ("★反例 缺 symbol",
     _inv(mapping=[_row(symbol=None)]), False, "缺 `symbol`"),

    # ── ★ 不许硬塞 / 不许猜 ─────────────────────────────────────────────
    ("★反例 not-assigned 却没写 axis_note（硬塞的入口）",
     _inv(mapping=[_row(axis="not-assigned", axis_value=None)]), False, "必须**写 `axis_note`"),
    ("★反例 not-assigned 又给了 axis_value（自相矛盾）",
     _inv(mapping=[_row(axis="not-assigned", axis_note="属阶段序轴")]), False, "自相矛盾"),
    ("★反例 axis_value=undefined 却没写理由（“看着像就填”的入口）",
     _inv(mapping=[_row(axis_value="undefined")]), False, "说明为何不可判"),
    ("★反例 axis_value 不在轴的 values 里",
     _inv(mapping=[_row(axis_value="guessed")]), False, "不在 `axis.values`"),
    ("★反例 axis 取值不在封闭枚举",
     _inv(mapping=[_row(axis="evidence-strength-2")]), False, "不在封闭枚举"),
    ("★反例 relation 不在封闭枚举",
     _inv(mapping=[_row(relation="有点冲突")]), False, "不在封闭枚举"),
    ("★反例 缺 axis_value（属证据强度轴却不给取值）",
     _inv(mapping=[_row(axis_value=None)]), False, "缺 `axis_value`"),

    # ── ★ 同一事实两处定义 ─────────────────────────────────────────────
    ("★反例 (namespace, symbol) 重复",
     _inv(mapping=[_row(), _row()], coverage=[{"family": "L", "expected_rows": 2}]),
     False, "两处定义"),

    # ── ★ 漏项（b1b 实犯）──────────────────────────────────────────────
    ("★反例 coverage 期望 2 行、实际 1 行 ⇒ 漏项",
     _inv(coverage=[{"family": "L", "expected_rows": 2}]), False, "漏项"),
    ("★反例 coverage 期望 1 行、实际 2 行 ⇒ 多行也红（双向）",
     _inv(mapping=[_row(), _row(symbol="L2")], coverage=[{"family": "L", "expected_rows": 1}]),
     False, "漏项"),
    ("★反例 mapping 出现未登记的 family",
     _inv(mapping=[_row(family="NEW")], coverage=[{"family": "L", "expected_rows": 1}]),
     False, "未在 `coverage` 登记"),
    ("反例 coverage 整段缺失（没有防漏项的判据）",
     _inv(coverage=[]), False, "`coverage` 缺失"),

    # ── ★ 源词表指纹（退出判据原文）─────────────────────────────────────
    ("★反例 源内容变了 ⇒ 指纹不符 ⇒ 下游红",
     _inv(sources=[{"id": "s1", "path": "docs/src.md", "whole_file": True, "sha256": "0" * 64}]),
     False, "指纹不符"),
    ("★反例 源的 path 不存在（登记指向空物）",
     _inv(sources=[{"id": "s1", "path": "docs/ghost.md", "whole_file": True, "sha256": SRC_SHA}]),
     False, "path 不存在"),
    ("★反例 读不到源 ⇒ 显式“不可判”，不当作通过",
     _inv(), False, "不可判"),
    ("★反例 切片起点找不到 ⇒ 前提失效",
     _inv(sources=[{"id": "s1", "path": "docs/src.md", "slice_start": "### 11.1 ",
                    "slice_next_prefix": "### ", "sha256": SRC_SHA}]),
     False, "找不到"),

    # ── ★ 两节的"非空"义务 ─────────────────────────────────────────────
    ("★反例 conflicts 为空（该记的冲突没记）",
     _inv(conflicts=[]), False, "`conflicts` 为空"),
    ("★反例 undecidable 为空",
     _inv(undecidable=[]), False, "`undecidable` 为空"),
    ("★反例 undecidable 条目缺 missing",
     _inv(undecidable=[{"item": "X"}]), False, "缺字段"),

    # ── 轴自身 ──────────────────────────────────────────────────────────
    ("★反例 axis.values 为空（“单一轴字典”名不副实）",
     _inv(axis={"id": "evidence-strength", "values": []}), False, "没有轴"),
    ("★反例 axis.values 的 id 重复",
     _inv(axis={"id": "evidence-strength",
                "values": [{"id": "official", "label": "A"}, {"id": "official", "label": "B"}]}),
     False, "有重复"),
]

# 需要外部注入"读失败"的用例（单独跑，不进 CASES 的通用夹具）
READ_FAIL_CASE = "★反例 读不到源 ⇒ 显式“不可判”，不当作通过"


def main() -> int:
    fails = []

    for desc, inv, want_ok, kw in CASES:
        reader = (lambda p: FILES[p]) if desc != READ_FAIL_CASE else (
            lambda p: (_ for _ in ()).throw(UnicodeDecodeError("utf-8", b"", 0, 1, "boom")))
        bad, notes = R.validate_dialect(inv, reader, lambda p: EXISTS.get(p, False), REG)
        blob = " ".join(bad) + " " + " ".join(notes)
        got_kw = kw in blob
        ok = ((not bad) == want_ok) and got_kw
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':"
              f"{'在' if got_kw else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} notes={notes}")

    # 口径钉死：CRLF + 行尾空白必须与 LF 同哈希（否则每次都假红 ⇒ 判据会被关掉）
    if R._dialect_norm(SRC_CRLF) != R._dialect_norm(SRC):
        fails.append("指纹口径不一致：CRLF/行尾空白变体算出了不同文本 ⇒ 会假红")
    elif hashlib.sha256(R._dialect_norm(SRC).encode("utf-8")).hexdigest() != SRC_SHA:
        fails.append("指纹口径变了（哈希与登记的 64 位常量不符）⇒ 真值表里的 sha256 全部作废")
    else:
        print("  ok   口径钉死：CRLF/尾空白 ⇒ 同一哈希")

    # 端到端：**真读本仓的 inventory/dialect.yaml** —— 抓我自己写 yaml/口径的自伤
    try:
        import yaml
        real = yaml.safe_load((ROOT / "inventory" / "dialect.yaml").read_text(encoding="utf-8"))
        reg_real = yaml.safe_load((ROOT / "inventory" / "namespaces.yaml").read_text(encoding="utf-8"))
        bad, notes = R.validate_dialect(
            real, lambda p: (ROOT / p).read_text(encoding="utf-8", errors="replace"),
            lambda p: (ROOT / p).exists(), reg_real)
        nb, nn = R.validate_namespaces(reg_real)
        if nb:
            fails.append(f"真注册表自身不自洽: {nb}")
        else:
            print(f"  ok   端到端 真读 inventory/namespaces.yaml\n        {' · '.join(nn)} · bad=0")
        ok = not bad
        print(f"  {'ok  ' if ok else 'FAIL'} 端到端 真读 inventory/dialect.yaml\n"
              f"        {notes} · bad={len(bad)}")
        if not ok:
            fails.append(f"真值文件自身不过: {bad}")
    except ImportError:
        print("  skip 端到端（缺 pyyaml）")

    # 结构护栏：函数存在**且已注册**（"写了函数忘了进 CHECKS" = 挂名假判）
    if "dialect" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='dialect' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'dialect' 已在 CHECKS 注册")

    # 生成物登记护栏：dialect.yaml 必须登记进 artifacts.yaml（否则它是"静默缺口"）
    try:
        import yaml
        art = yaml.safe_load((ROOT / "inventory" / "artifacts.yaml").read_text(encoding="utf-8"))
        hit = [i for i in (art.get("items") or []) if i.get("path") == "inventory/dialect.yaml"]
        if not hit or hit[0].get("check") != "dialect":
            fails.append("inventory/dialect.yaml 未在 artifacts.yaml 登记为生成物（check: dialect）")
        else:
            print("  ok   生成物护栏：dialect.yaml 已登记 check: dialect")
    except ImportError:
        pass

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
