"""`D7-P3-2 结论收束记账` 的正反注入 + **先验红** —— 永久护栏（2026-09-26）

守的是合并稿 §13.3 那句话：「D7 的结论留痕应**复用 `inbox` 的 `40_state/LOG.md`
追加式纪律**，**不新造账本**。」

★ 本文件最要紧的两条不是"字段齐不齐"，而是：
  · **「未登记的账本」必须红** —— 否则"不新造账本"只是句承诺；
  · **`scan_hits=None` 必须与 `scan_hits=[]` 可区分** ——
    「**没判**」与「**判了且通过**」不许长得一样（合并稿 §8.2 原话）。
    若把 `None` 当成"空命中 ⇒ 过"，那这条判据在**没接扫描输入**时就是**恒真**的。
"""
import copy
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _doc(**over):
    base = {
        "disciplines": ["append-only"],
        "ledgers": [{
            "id": "inbox-state-log",
            "what": "受理区状态变更记录",
            "globs": ["inbox/*/40_state/LOG.md"],
            "writer": "管理员（人）",
            "discipline": "append-only",
            "truth_doc": "inbox/README.md §3",
            "verify": "门禁 `inbox`",
        }],
        "not_a_ledger": [{"glob": "**/review.json", "why": "一次派发一份的产物，不追加"}],
        "scan": {"globs": ["inbox/*/40_state/LOG.md"], "exclude_dirs": [".git", "tmp"]},
        "unverified": [{"item": "扫描口径只覆盖 inbox", "why": "别名账本看不到"}],
    }
    base.update(over)
    return copy.deepcopy(base)


def _led(**over):
    lg = _doc()["ledgers"][0]
    lg.update(over)
    return lg


# scan_hits 与样例 doc 的 globs 一致 ⇒ 正例在"接了扫描"时也应过
HITS_OK = ["inbox/paper-2026-08-23/40_state/LOG.md", "inbox/_template/40_state/LOG.md"]

CASES = [
    # ── 正例（两种：不接扫描 / 接了扫描且全已登记）──────────────────────
    ("正例 最小合格（`scan_hits=None` ⇒ 不判扫描）", _doc(), None, True, "未接扫描输入"),
    ("正例 接了扫描且命中全部已登记", _doc(), HITS_OK, True, "扫描命中 2 处"),

    # ── 结构 ──────────────────────────────────────────────────────────
    ("★反例 顶层不是映射", ["nope"], None, False, "顶层不是映射"),
    ("★反例 `disciplines` 为空", _doc(disciplines=[]), None, False, "`disciplines` 为空"),
    ("★反例 `ledgers` 为空 ⇒ 本表没有对象（退化空判）", _doc(ledgers=[]), None, False, "没有对象"),
    ("★反例 账本缺 `id`", _doc(ledgers=[_led(id="")]), None, False, "缺 `id`"),
    ("★反例 账本 `id` 重复", _doc(ledgers=[_led(), _led(globs=["x/LOG.md"])]), None, False, "重复"),
    ("★反例 账本缺 `writer`（唯一写入者没写）",
     _doc(ledgers=[_led(writer="")]), None, False, "`writer`"),
    ("★反例 账本缺 `verify`（没有独立校验）",
     _doc(ledgers=[_led(verify="")]), None, False, "`verify`"),
    ("★反例 账本缺 `truth_doc`（纪律没出处）",
     _doc(ledgers=[_led(truth_doc="")]), None, False, "`truth_doc`"),
    ("★反例 `discipline` 不在声明集里",
     _doc(ledgers=[_led(discipline="semi-append")]), None, False, "不在声明集"),
    ("★反例 账本既无 `globs` 也无 `paths`",
     _doc(ledgers=[_led(globs=[])]), None, False, "既无 `globs` 也无 `paths`"),
    ("★反例 **孤儿纪律**：声明了却没有账本用它",
     _doc(disciplines=["append-only", "watch-only"]), None, False, "孤儿纪律"),

    # ── ★★ "不新造账本"的正面表述 ───────────────────────────────────────
    ("★★反例 `not_a_ledger` 为空 ⇒ 没写下『什么不算账本』",
     _doc(not_a_ledger=[]), None, False, "什么不算账本"),
    ("★反例 `not_a_ledger` 缺 `why`",
     _doc(not_a_ledger=[{"glob": "**/review.json", "why": ""}]), None, False, "缺 `glob` 或 `why`"),
    ("★★反例 **相撞**：同一形态既登记为账本、又声明不是账本",
     _doc(not_a_ledger=[{"glob": "inbox/*/40_state/LOG.md", "why": "我偏说它不是"}]),
     None, False, "相撞"),

    # ── 扫描口径 ──────────────────────────────────────────────────────
    ("★反例 `scan.globs` 为空 ⇒ 没有扫描口径",
     _doc(scan={"globs": [], "exclude_dirs": [".git"]}), None, False, "`scan.globs` 为空"),
    ("★反例 `scan.exclude_dirs` 为空 ⇒ 口径不完整",
     _doc(scan={"globs": ["inbox/*/40_state/LOG.md"], "exclude_dirs": []}), None, False, "`scan.exclude_dirs` 为空"),

    # ── ★★ 扫描侧：这两条才是本判据的存在理由 ────────────────────────────
    #   ⚠ 用例形状很要紧：`inbox/<任意项目>/40_state/LOG.md` **本就命中**登记的 glob 形状
    #     （那是"形状覆盖"，不是"只认某一个项目"）⇒ 要构造**形状外**的路径才算"未登记"。
    #     本文件第一版就写错在这里：拿 `inbox/other-2026-01-01/40_state/LOG.md` 当"未登记"，
    #     实测 bad=[] ⇒ **是我不敢信的那条反例先被测试拦下了**。
    ("★★反例 **未登记的账本**（扫描命中了一个**形状外**的路径）",
     _doc(), HITS_OK + ["ops/handmade-log/LOG.md"], False, "未登记的账本"),
    ("★正例 同形状的另一项目**不算**未登记（形状覆盖，不是只认一个项目）",
     _doc(), ["inbox/other-project-2026-01-01/40_state/LOG.md"], True, "扫描命中 1 处"),
    ("★★反例 **登记腐化**（登记了 globs 却一条也没命中）",
     _doc(), [], False, "一条也没命中"),
    ("★正例 反向对照：`scan_hits=[]` 在**没有**声明 globs 的账本上不构成腐化",
     _doc(ledgers=[_led(globs=[], paths=["ops/station-bin/agent-chain.json"])]),
     [], True, "扫描命中 0 处"),

    # ── 未定项 ────────────────────────────────────────────────────────
    ("★反例 `unverified` 为空 ⇒ 未实测部分没登记",
     _doc(unverified=[]), None, False, "`unverified` 为空"),
]


def main() -> int:
    fails = []

    for desc, doc, hits, want_ok, kw in CASES:
        bad, notes = R.validate_conclusion_ledgers(doc, scan_hits=hits)
        blob = " ".join(bad) + " " + " ".join(notes)
        ok = ((not bad) == want_ok) and (kw in blob)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':{'在' if kw in blob else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} notes={notes}")

    # ── ★ 「没判」与「判了且通过」必须可区分 ─────────────────────────────
    b1, n1 = R.validate_conclusion_ledgers(_doc(ledgers=[_led(globs=[], paths=["x.json"])]), scan_hits=None)
    b2, n2 = R.validate_conclusion_ledgers(_doc(ledgers=[_led(globs=[], paths=["x.json"])]), scan_hits=[])
    sep = (not b1) and (not b2) and any("未接扫描输入" in x for x in n1) and not any("未接扫描输入" in x for x in n2)
    print(f"  {'ok  ' if sep else 'FAIL'} ★ `scan_hits=None`（不判）与 `[]`（判过）的**结论可区分**")
    if not sep:
        fails.append(f"None 与 [] 不可区分 ⇒ 该判据在没接扫描输入时是恒真的（n1={n1} n2={n2}）")

    # ── 端到端：真读 inventory/conclusion-ledgers.yaml + **真扫盘** ─────────
    real = None
    hits = None
    try:
        import yaml
        real = yaml.safe_load(R.LEDGERS_INV.read_text(encoding="utf-8"))
        hits = R._scan_ledger_hits()
        bad, notes = R.validate_conclusion_ledgers(real, scan_hits=hits)
        ok = not bad
        print(f"  {'ok  ' if ok else 'FAIL'} 端到端 真读 + 真扫盘\n        {notes} · bad={len(bad)}")
        if not ok:
            fails.append(f"真值文件自身不过: {bad}")
        # 盘上存在性（check_ 里那一半）也走一遍
        miss = [p for lg in (real.get("ledgers") or []) for p in (lg.get("paths") or [])
                if not (ROOT / p).exists()]
        print(f"  {'ok  ' if not miss else 'FAIL'} 端到端 登记的 `paths` 全部在盘上（缺 {len(miss)}）")
        if miss:
            fails.append(f"登记路径不存在: {miss}")
    except ImportError:
        print("  skip 端到端（缺 pyyaml）")

    # ── ★ 先验红自证（**在真文件上**）：把登记 globs 改坏 ⇒ 必须报「未登记的账本」
    if real is not None:
        mutated = copy.deepcopy(real)
        for lg in mutated["ledgers"]:
            if lg.get("globs"):
                lg["globs"] = ["inbox/*/40_state/LOGX.md"]      # 真盘上不存在这个名字
        bad2, _ = R.validate_conclusion_ledgers(mutated, scan_hits=hits)
        red = any("未登记的账本" in b for b in bad2)
        print(f"  {'ok  ' if red else 'FAIL'} 先验红自证：在**真文件**上把账本 globs 改坏 ⇒ "
              f"扫到的 LOG.md 变成『未登记』（{'是' if red else '否'}）")
        if not red:
            fails.append("先验红自证失败：真文件上把 globs 改坏却没报未登记账本 ⇒ 判据形同虚设")

    # ── ★ 先验红自证②：`not_a_ledger` 清空 ⇒ 必须红 ─────────────────────
    if real is not None:
        m2 = copy.deepcopy(real)
        m2["not_a_ledger"] = []
        bad3, _ = R.validate_conclusion_ledgers(m2, scan_hits=hits)
        red3 = any("什么不算账本" in b for b in bad3)
        print(f"  {'ok  ' if red3 else 'FAIL'} 先验红自证②：清空 `not_a_ledger` ⇒ 必须红")
        if not red3:
            fails.append("先验红自证②失败：清空 not_a_ledger 没被拦")

    # ── 结构护栏：口径必须**只在 yaml**（代码里不许再定一份）──────────────
    #   ★ 用**行为**证明，不用文本扫描：把 `LEDGERS_INV` 指向一份临时 yaml（换了 scan.globs），
    #     若扫描结果随之改变 ⇒ 口径**确实来自 yaml**；若不变 ⇒ 代码里另有一份写死的口径。
    ids = {c["id"] for c in R.CHECKS}
    if "conclusion-ledger" not in ids:
        fails.append("CHECKS 里没有 id='conclusion-ledger' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'conclusion-ledger' 已在 CHECKS 注册")

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        alt = Path(td) / "alt-ledgers.yaml"
        alt.write_text(
            "disciplines: [append-only]\n"
            "ledgers:\n"
            "  - {id: alt, globs: ['docs/*.md'], what: x, writer: y, discipline: append-only,"
            "     truth_doc: z, verify: v}\n"
            "not_a_ledger: [{glob: '**/review.json', why: because}]\n"
            "scan: {globs: ['docs/*.md'], exclude_dirs: ['.git']}\n"
            "unverified: [{item: a, why: b}]\n", encoding="utf-8")
        saved = R.LEDGERS_INV
        try:
            R.LEDGERS_INV = alt
            alt_hits = R._scan_ledger_hits()
        finally:
            R.LEDGERS_INV = saved
        moved = bool(alt_hits) and all(h.startswith("docs/") and h.endswith(".md") for h in alt_hits) \
            and alt_hits != hits
        print(f"  ok   结构护栏：换掉 yaml 的 `scan.globs` ⇒ 扫描结果随之改变"
              f"（docs 侧 {len(alt_hits)} 处 vs 原 {len(hits)} 处）· 口径确实来自 yaml"
              if moved else
              f"  FAIL 结构护栏：换掉 yaml 的 `scan.globs` 后扫描结果**没变** ⇒ 代码里另有一份口径")
        if not moved:
            fails.append("口径不在 yaml（换 yaml 不影响扫描结果）⇒ 第二份口径")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
