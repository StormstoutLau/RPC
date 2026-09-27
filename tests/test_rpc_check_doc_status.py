"""`O-108`：`doc-status` 判据（同一文档**两处状态声明** = 真值 + 派生）正反用例（2026-09-27）。

为什么要有：该判据管的是"**同一事实两处表达**"这个面 —— 实测 **34 份实例两处都有、
其中 12 处两处不等**（含 `draft` ↔ `verified` 这类**互斥**）。
★ 它必须**真的会红**，且必须**只红真的不等**（写法差异要宽容，否则红一片假阳性）。

★ **先验红**（本仓通用纪律）：对**真表副本 / 真扫描结果的副本**做一次变异 ⇒ 断言判据
**红且点名**（★ 只断言"红"不够：`bad[0]` 会掩盖后面所有问题）。
⚠ 本文件**不改真文件**（对 `copy.deepcopy` 出的 dict / list 变异）⇒ 零写入风险；
末尾仍**自证真文件字节未变** + **真扫描未受影响**。

用法（退出码 0 = 全过）：
    py tests\\test_rpc_check_doc_status.py
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import rpc_check as R                                    # noqa: E402

INV = ROOT / "inventory" / "doc-status.yaml"
ORIG_BYTES = INV.read_bytes()                            # ★ 字节级原件（自证未变）

import yaml                                              # noqa: E402
REAL = yaml.safe_load(ORIG_BYTES.decode("utf-8")) or {}
REAL_PAIRS, REAL_TPL = R.scan_doc_status()

fails = []
total = 0


def chk(name, cond, extra=""):
    global total
    total += 1
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


def red(mutate, label, expect):
    """先验红：对**真表 / 真扫描的副本**做一次变异 ⇒ 断言 **红 且 点名**。"""
    d, p = copy.deepcopy(REAL), copy.deepcopy(REAL_PAIRS)
    tpl = REAL_TPL
    mutate(d, p)
    bad, _ = R.validate_doc_status(p, d, n_template=tpl)
    blob = " ".join(bad)
    ok = bool(bad) and (expect in blob)
    detail = "" if ok else ("**没红**" if not bad else f"红了但**没点名** {expect!r}: {blob[:110]}")
    chk("先验红 · " + label, ok, (" <- " + detail) if detail else "")


# ── ① 正例：真表 + 真扫描必须过 ────────────────────────────────────────────
bad, notes = R.validate_doc_status(copy.deepcopy(REAL_PAIRS), copy.deepcopy(REAL), n_template=REAL_TPL)
chk("正例 · 真表 + 真扫描通过", not bad, (" <- " + bad[0][:100]) if bad else "")
print("      note =", (notes[0] if notes else "(无)"))

# ── ② 规模护栏 + 事实核对（免得判据对着一个空集宣 PASS）────────────────────
chk("真扫描：两处都有 >= 20（否则判据没对象）", len(REAL_PAIRS) >= 20, f" <- {len(REAL_PAIRS)}")
chk("真扫描：模板被排除且计入报数", REAL_TPL >= 3, f" <- {REAL_TPL} 个模板")
eq = sum(1 for x in REAL_PAIRS if R._doc_token(x["fm"]) == R._doc_token(x["body"]))
chk("真扫描：不等数 == 0（清账后）", len(REAL_PAIRS) - eq == 0,
    f" <- 不等 {len(REAL_PAIRS) - eq}")
chk("真扫描：冻结数 == 不等数（清账后 freeze 为空，一致性仍成立）",
    len(REAL.get("freeze") or []) == len(REAL_PAIRS) - eq,
    f" <- 冻结 {len(REAL.get('freeze') or [])} / 不等 {len(REAL_PAIRS) - eq}")


# ★ 清账（2026-09-27）后真表**再无不等项 / freeze 为空** ⇒ 夹具由「找」改为「造」：
def _unequal_pair(p):
    """取任意一个『两处都有』的对 ⇒ 把它改成**不等**（并返回它，供后续变异）。"""
    if not p:
        raise AssertionError("真扫描里没有任何『两处都有』的对（夹具前提不成立）")
    x = p[0]
    x["fm"], x["body"] = "verified", "draft"
    return x


def _frozen_pair(d, p):
    """夹具：造一个**在 freeze 里**的不等项（真表 freeze 已清空 ⇒ 需注入一条）。"""
    x = _unequal_pair(p)
    d["freeze"] = [e for e in (d.get("freeze") or []) if e["file"] != x["file"]]
    d["freeze"].append({"file": x["file"], "fm": x["fm"], "body": x["body"],
                        "why": "夹具注入（真表 freeze 已清空）"})
    return x


# ── ③ ★★ 先验红：核心 —— 非冻结的"两处不等"必须红且点名 ───────────────────
def m_new_unequal(d, p):
    x = _unequal_pair(p)                            # 造一个新的"不等"
    d["freeze"] = [e for e in (d.get("freeze") or []) if e["file"] != x["file"]]   # 且**不在**冻结里


red(m_new_unequal, "非冻结的两处不等（判派生过期）", "派生过期")
red(m_new_unequal, "同上 —— 必须**点名文件**", "两处状态声明")

# ── ④ 先验红：冻结清单的三种腐化（防腐化）────────────────────────────────
def m_healed(d, p):
    """冻结项**已自愈**（真文件被修好、但忘删冻结项）⇒ 必须报「删掉它」。"""
    x = _frozen_pair(d, p)
    x["body"] = x["fm"]                              # 两处一致 ⇒ 自愈


red(m_healed, "冻结项已自愈（须从 freeze 删掉）", "已自愈")


def m_gone(d, p):
    """冻结项**不再是两处都有**（少了一处）⇒ 该面已只剩一个位点 ⇒ 须报「删掉它」。"""
    x = _frozen_pair(d, p)
    p.remove(x)                                       # 少了一处 ⇒ 不再是"两处都有"


red(m_gone, "冻结项已不再是两处都有（须删掉）", "已不再是")


def m_bad_file(d, p):
    _frozen_pair(d, p)                                # 清账后 freeze 为空 ⇒ 先注入一条再腐化
    d["freeze"][0]["file"] = "spec/__no_such_doc__.md"


red(m_bad_file, "冻结项文件不在仓里（登记腐化）", "不在仓里")


def m_no_why(d, p):
    _frozen_pair(d, p)                                # 清账后 freeze 为空 ⇒ 先注入一条再腐化
    d["freeze"][0].pop("why", None)


red(m_no_why, "冻结项缺 why（豁免没写理由）", "why")

# ── ⑤ 先验红：表级声明（缺了就会退化成"豁免清单"）────────────────────────
red(lambda d, p: d.pop("semantics", None), "缺 semantics（退化成豁免清单）", "single_write")
red(lambda d, p: d["semantics"].pop("derived", None), "缺 semantics.derived", "derived")
red(lambda d, p: d.pop("updated", None), "缺 updated（没有读数日期）", "updated")
red(lambda d, p: d.pop("unverified", None), "缺 unverified（自陈未定项没登记）", "unverified")
red(lambda d, p: (d.pop("freeze", None), d.__setitem__("freeze", "not-a-list")),
    "freeze 不是列表", "不是列表")


bad_nm, _ = R.validate_doc_status([], ["not a mapping"])
chk("顶层不是映射 ⇒ 红", bool(bad_nm) and "不是映射" in " ".join(bad_nm),
    " <- " + (bad_nm[0][:60] if bad_nm else "没红"))

# ── ⑥ 归一表单测（★ 写法差异必须宽容，否则红一片假阳性）──────────────────
cases = [("draft", "draft"), ("草稿", "draft"), ("**draft**", "draft"),
         ("draft（草稿）", "draft"), ("Review 中", "in-review"), ("in-review", "in-review"),
         ("待验收", "pending"), ("已验收通过", "accepted"), ("验收通过", "accepted"),
         ("已作废（superseded）", "superseded"), ("approved（签字 2026-09-03）", "approved")]
badc = [(v, R._doc_token(v), w) for v, w in cases if R._doc_token(v) != w]
chk(f"归一表 {len(cases)} 例全中", not badc, (" <- " + str(badc[:3])) if badc else "")

# ── ⑦ ★ 射程写死（`DOC_STATUS_HEAD`）：换 head 必须换结果，证明它不是装饰 ──
p_small, _ = R.scan_doc_status(head=5)
chk("head=5 ⇒ 收不到「两处都有」（正文行在文档头之后）", len(p_small) == 0,
    f" <- {len(p_small)}")
chk("head=20（真值）⇒ 34 对", len(REAL_PAIRS) == 34, f" <- {len(REAL_PAIRS)}")

# ── ⑧ 门禁函数本身（走真表 + 真扫描，不注入）──────────────────────────────
lvl, note, bad = R.check_doc_status(None)
chk("check_doc_status(真表) == PASS", lvl == "PASS" and not bad,
    f" <- {lvl}: {(bad[0][:90] if bad else note[:80])}")
chk("门禁的 note 含两处/一致/不等三项计数",
    ("两处都有" in note and "一致" in note and "不等" in note), " <- " + note[:110])

# ── ⑨ ★ 自证：真文件**字节未变** + 真扫描未被本文件污染 ────────────────────
chk("真文件字节未变（本文件不写仓）", INV.read_bytes() == ORIG_BYTES)
p2, t2 = R.scan_doc_status()
chk("真扫描复跑一致（未受副本变异影响）", p2 == REAL_PAIRS and t2 == REAL_TPL)

# ★ O-89 纪律：门禁只认退出码 ⇒ 必须有 `RESULT:` 汇总行
print(f"\n共 {total} 条")
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
