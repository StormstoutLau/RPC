"""`O-105`：`capabilities` 判据（能力 → 载体 → 判定）的正反用例 + **先验红**（2026-09-27）。

为什么要有：该判据管的是"**能力的存在性有没有可核载体**"—— 它**天然容易腐化**
（载体文件改名 / 判据被删后没人管登记）⇒ 必须证明它**真的会红**（否则就是"通过是因为什么都没判"）。

★ **先验红**（本仓通用纪律）：把**真产物**的内容改成"坏"的形态，断言判据
**红且点名**（★ 只断言"红"不够 —— 第一条 bad 会掩盖后面所有问题，
本文件首版就踩过：4 条用例的明细全是同一条『缺 updated』）。
⚠ 但本文件**不改真文件** —— 判据的纯函数接受 `doc`，故只对**真表解析出的 dict** 做变异
（`copy.deepcopy`）⇒ **证明"判据读的是真产物"，且零写入风险**（比改文件再恢复更安全，
证据力相同）。末尾仍**自证真文件字节未变**。

用法（退出码 0 = 全过）：
    py tests\\test_rpc_check_capability_inventory.py
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import rpc_check as R                                    # noqa: E402

INV = ROOT / "inventory" / "capability-inventory.yaml"
ORIG_BYTES = INV.read_bytes()                            # ★ 字节级原件（自证未变）

import yaml                                              # noqa: E402
REAL = yaml.safe_load(ORIG_BYTES.decode("utf-8")) or {}
KNOWN = {c["id"] for c in R.CHECKS}
EXISTS = lambda rel: (ROOT / rel).exists()               # noqa: E731

fails = []
total = 0


def chk(name, cond, extra=""):
    global total
    total += 1
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


def _first(doc, pred):
    for it in doc.get("items") or []:
        if pred(it):
            return it
    return None


def red(mutate, label, expect):
    """先验红：对**真表副本**做一次变异 ⇒ 断言 **红 且 点名**（`expect` 必须出现）。"""
    d = copy.deepcopy(REAL)
    mutate(d)
    bad, _ = R.validate_capability_inventory(d, KNOWN, EXISTS)
    blob = " ".join(bad)
    ok = bool(bad) and (expect in blob)
    detail = "" if ok else ("**没红**" if not bad else f"红了但**没点名** {expect!r}: {blob[:110]}")
    chk("先验红 · " + label, ok, (" <- " + detail) if detail else "")


# ── ① 正例：真表原样必须过 ────────────────────────────────────────────────
bad, notes = R.validate_capability_inventory(copy.deepcopy(REAL), KNOWN, EXISTS)
chk("正例 · 真表原样通过", not bad, (" <- " + bad[0][:100]) if bad else "")
print("      note =", (notes[0] if notes else "(无)"))

# ── ② 规模护栏：表被掏空就不该还绿 ────────────────────────────────────────
vset = {i.get("verdict") for i in REAL.get("items", []) if isinstance(i, dict)}
chk("真表三种判定都在（否则刻度没被行使）",
    vset >= {"present", "partial", "absent"}, " <- " + str(sorted(vset)))
chk("真表项数 >= 20（防被掏空）", len(REAL.get("items") or []) >= 20,
    f" <- {len(REAL.get('items') or [])} 项")

# ── ③ ★★ 先验红：**载体可达性**是核心（三类载体各一条）────────────────────


def m_file_missing(d):
    it = _first(d, lambda x: any(c.get("kind") == "file" for c in (x.get("carriers") or [])))
    for c in it["carriers"]:
        if c.get("kind") == "file":
            c["ref"] = "ops/__does_not_exist__.py"
            return


red(m_file_missing, "载体文件不存在", "__does_not_exist__.py")


def m_gate_fake(d):
    it = _first(d, lambda x: any(c.get("kind") == "gate" for c in (x.get("carriers") or [])))
    for c in it["carriers"]:
        if c.get("kind") == "gate":
            c["ref"] = "no-such-gate"
            return


red(m_gate_fake, "载体判据不是已注册 CHECKS id（挂名）", "不是已注册的 CHECKS id")


def m_table_missing(d):
    it = _first(d, lambda x: any(c.get("kind") == "table" for c in (x.get("carriers") or [])))
    for c in it["carriers"]:
        if c.get("kind") == "table":
            c["ref"] = "no-such-table.yaml"
            return


red(m_table_missing, "载体真值表不存在", "no-such-table.yaml")


def m_no_carriers(d):
    _first(d, lambda x: x.get("verdict") == "present").pop("carriers", None)


red(m_no_carriers, "present 却不给载体（自报）", "必须给载体")


# ── ④ 先验红：表级口径 / 读数日期 ─────────────────────────────────────────
red(lambda d: d.pop("metric", None), "缺 metric（增长型计数没有口径）", "metric")
red(lambda d: d.pop("updated", None), "缺 updated（没有读数日期）", "updated")
red(lambda d: d.__setitem__("verdicts", ["present", "partial", "absent", "unknown"]),
    "声明的封闭集与判据实现不一致", "应为封闭集")

# ★ 反例：裸日期（yaml 会解析成 date）**必须收** —— 见 `_ds()` 的单测
d = copy.deepcopy(REAL)
d["updated"] = yaml.safe_load("updated: 2026-09-27")["updated"]
bad, _ = R.validate_capability_inventory(d, KNOWN, EXISTS)
chk("裸日期（date 对象）**不算缺**（_ds 口径）", not bad, (" <- " + bad[0][:90]) if bad else "")
chk("_ds 对 str/date/None 的行为", R._ds(" x ") == "x" and R._ds(None) == ""
    and len(R._ds(d["updated"])) == 10, f" <- {R._ds(d['updated'])!r}")

# ── ⑤ 先验红：理由 / 自指 / 结构 ─────────────────────────────────────────
def m_partial_no_gap(d):
    _first(d, lambda x: x.get("verdict") == "partial").pop("gap", None)


red(m_partial_no_gap, "partial 缺 gap（托词）", "gap")


def m_absent_no_why(d):
    _first(d, lambda x: x.get("verdict") == "absent").pop("why", None)


red(m_absent_no_why, "absent 缺 why（「不做」也要写下来）", "但缺 `why`")


def m_absent_bad_kind(d):
    _first(d, lambda x: x.get("verdict") == "absent")["why_kind"] = "whatever"


red(m_absent_bad_kind, "absent 的 why_kind 不在封闭集", "why_kind")

red(lambda d: d.__setitem__("self_id", "not-a-real-item"),
    "self_id 不在 items（自指缺口）", "自指缺口")
red(lambda d: d["items"][1].__setitem__("id", d["items"][0]["id"]), "id 重复", "重复")
red(lambda d: d.__setitem__("items", []), "items 为空（退化空判）", "退化空判")
red(lambda d: d.pop("unverified", None), "缺 unverified", "unverified")
red(lambda d: d["items"][0].__setitem__("verdict", "maybe"), "verdict 不在封闭集", "verdict")
red(lambda d: d["items"][0].__setitem__("domain", "misc"), "domain 不在封闭集", "domain")
red(lambda d: d["items"][0].__setitem__("basis", "E9"), "basis 不在封闭集", "basis")
red(lambda d: d["items"][0].pop("evidence", None), "缺 evidence（present 项）", "evidence")
# ★ 真表首版正是在这里红的：8 条 absent 全都没写 `evidence` —— 而「本仓没有这个机制」
#   本身就是一条**断言**（要么给读数，要么就是自报）⇒ absent **不豁免** evidence
red(lambda d: _first(d, lambda x: x.get("verdict") == "absent").pop("evidence", None),
    "缺 evidence（**absent 项不豁免**）", "evidence")
red(lambda d: _first(d, lambda x: x.get("verdict") == "absent").pop("basis", None),
    "缺 basis（**absent 项不豁免** —— 取证方式要写明）", "basis")

# ── ⑥ 门禁函数本身（走真表，不注入）──────────────────────────────────────
lvl, note, bad = R.check_capability_inventory(None)
chk("check_capability_inventory(真表) == PASS", lvl == "PASS" and not bad,
    f" <- {lvl}: {(bad[0][:90] if bad else note[:80])}")
chk("门禁的 note 含三项计数", ("present" in note and "partial" in note and "absent" in note),
    " <- " + note[:110])

# ── ⑦ ★ 自证：真文件**字节未变**（本文件全程只读真表）────────────────────
chk("真文件字节未变（本文件不写仓）", INV.read_bytes() == ORIG_BYTES)

# ★ O-89 纪律：门禁只认退出码 ⇒ 必须有 `RESULT:` 汇总行
print(f"\n共 {total} 条")
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
