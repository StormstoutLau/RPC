"""`D7-P3-2 标准复核目录` 的正反注入 + **先验红** —— 永久护栏（2026-09-26）

守的是 **D-43 的退出判据**「编排可判 + **免终裁类目有清单**」，以及它照抄的那条 ITIL 门槛：
**同一类复核被批准两次**，才该问「它能不能成为标准复核」。

★ 本文件最要紧的一条：**「只填数字拿不出锚点」必须红** ——
  否则 `approvals: 2` 就是一句自说自话，门槛等于没有。
⚠ 另一条要守住的是**不许读过头**：`entries` 当前**实测 0 条**，
  本判据**不判**「类目选得对不对」，也**不判**「该不该引入豁免」（D-48 要求先证与结构 contain 不冲突）。
"""
import copy
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _entry(**over):
    e = {
        "id": "doc-only-review",
        "scope": "只改文档、不碰代码与 inventory 真值表、不带附件",
        "exempt_from": "l2-semantic",
        "still_required": ["L1 机械门（金标 / accept / status）", "doclinks", "adr"],
        "risk_basis": "机械门能全覆盖；改动可逆且无外部副作用",
        "approvals": 2,
        "approval_anchors": ["run/20260910010101", "run/20260920020202"],
        "revoke_if": "出现一次漏过（豁免类里出了红）",
        "review_every": 90,
    }
    e.update(over)
    return e


def _doc(**over):
    base = {
        "admission": {
            "rule": "同一类复核被批准两次 ⇒ 才该问它能不能成为标准复核",
            "min_approvals": 2,
            "type_axis": "review-kind",
            "type_axis_note": "合成样例里假定有轴",
            "ratio_target": {"low": 40, "high": 60, "unit": "percent", "judged": False},
        },
        "entry_schema": {
            "exempt_stages": ["l2-semantic", "final-adjudication"],
            "required": ["id", "scope", "exempt_from", "still_required", "risk_basis",
                         "approvals", "approval_anchors", "revoke_if", "review_every"],
            "fields": [{"id": k, "type": "any", "note": "n"} for k in
                       ("id", "scope", "exempt_from", "still_required", "risk_basis",
                        "approvals", "approval_anchors", "revoke_if", "review_every")],
        },
        "entries": [],
        "empty_reason": "本仓没有类型轴 ⇒ 候选无法由数据浮出（实测）",
        "unverified": [{"item": "exempt_stages 第二级", "why": "本仓无对象"}],
    }
    base.update(over)
    return copy.deepcopy(base)


def _with_entries(entries, **over):
    """带类目的正例形状：有类目 ⇒ `type_axis` 必须非空（否则那是另一条反例）。"""
    return _doc(entries=entries, **over)


CASES = [
    # ── 正例 ──────────────────────────────────────────────────────────
    ("正例 空目录（0 条）+ `empty_reason`", _doc(), True, "免终裁类目 0 条"),
    ("正例 一条合规类目（approvals=2 且锚点 2 条）", _with_entries([_entry()]), True, "免终裁类目 1 条"),

    # ── 准入门槛（D-43 / ITIL）────────────────────────────────────────
    ("★反例 `min_approvals=1` ⇒ 每类都是标准复核 = 判据恒真",
     _doc(admission=dict(_doc()["admission"], min_approvals=1)), False, "必须 ≥ 2"),
    ("★反例 `min_approvals` 缺失",
     _doc(admission={k: v for k, v in _doc()["admission"].items() if k != "min_approvals"}),
     False, "必须 ≥ 2"),
    ("★★反例 **只填数字拿不出锚点**（approvals=2 但只有 1 条 anchor）",
     _with_entries([_entry(approval_anchors=["run/only-one"])]), False, "只填数字拿不出锚点"),
    ("★反例 `approvals` 未达门槛（1 < 2）",
     _with_entries([_entry(approvals=1, approval_anchors=["run/a"])]), False, "未达准入门槛"),
    ("★反例 `approval_anchors` 为空列表",
     _with_entries([_entry(approval_anchors=[])]), False, "`approval_anchors` 必须是非空字符串列表"),
    ("★反例 `approval_anchors` 里混了空串",
     _with_entries([_entry(approval_anchors=["run/a", "  "])]), False, "必须是非空字符串列表"),

    # ── 类型轴：★「有类目却无轴」= 类目没有浮出依据 ──────────────────────
    ("★★反例 **有类目但 `type_axis` 为空** ⇒ 类目凭什么浮出来的",
     _with_entries([_entry()], admission=dict(_doc()["admission"], type_axis="")),
     False, "类目没有浮出依据"),
    ("★反例 `type_axis` 键缺失（必须显式空串，不许省键）",
     _doc(admission={k: v for k, v in _doc()["admission"].items() if k != "type_axis"}),
     False, "必须是字符串"),
    ("★反例 `type_axis_note` 为空 ⇒ 现状没写下来",
     _doc(admission=dict(_doc()["admission"], type_axis_note="")), False, "没写下来"),

    # ── 比例目标（只报数，但必须登记且有 judged 标注）──────────────────
    ("★反例 `ratio_target.judged` 不是布尔",
     _doc(admission=dict(_doc()["admission"],
                         ratio_target={"low": 40, "high": 60, "unit": "percent", "judged": "no"})),
     False, "`ratio_target.judged` 必须是布尔"),
    ("★反例 `ratio_target` low ≥ high",
     _doc(admission=dict(_doc()["admission"],
                         ratio_target={"low": 60, "high": 40, "unit": "percent", "judged": False})),
     False, "low/high 非法"),
    ("★反例 缺 `ratio_target`",
     _doc(admission={k: v for k, v in _doc()["admission"].items() if k != "ratio_target"}),
     False, "缺 `admission.ratio_target`"),

    # ── schema ───────────────────────────────────────────────────────
    ("★反例 `exempt_stages` 为空 ⇒ 『免哪一层』没定义",
     _doc(entry_schema=dict(_doc()["entry_schema"], exempt_stages=[])), False, "`entry_schema.exempt_stages`"),
    ("★反例 `required` 为空 ⇒ 没有必填就没有门",
     _doc(entry_schema=dict(_doc()["entry_schema"], required=[])), False, "`entry_schema.required` 为空"),
    ("★反例 `required` 引用了不存在的字段",
     _doc(entry_schema=dict(_doc()["entry_schema"], required=_doc()["entry_schema"]["required"] + ["ghost"])),
     False, "引用了不存在的字段"),
    ("★反例 **孤儿字段**：`fields` 有但 `required` 没用它 ⇒ 装饰",
     _doc(entry_schema=dict(_doc()["entry_schema"],
                            fields=_doc()["entry_schema"]["fields"] + [{"id": "vibes", "type": "str", "note": "n"}])),
     False, "孤儿字段"),
    ("★反例 字段缺 `note` ⇒ 含义靠猜",
     _doc(entry_schema=dict(_doc()["entry_schema"],
                            fields=[{"id": "id", "type": "str"}] + _doc()["entry_schema"]["fields"][1:])),
     False, "缺 `note`"),
    ("★反例 缺 `admission` 段",
     _doc(admission={}), False, "缺 `admission` 段"),

    # ── 条目 ─────────────────────────────────────────────────────────
    ("★反例 类目缺必填字段（`scope`）",
     _with_entries([{k: v for k, v in _entry().items() if k != "scope"}]), False, "缺必填 `scope`"),
    ("★反例 `exempt_from` 不在封闭枚举里",
     _with_entries([_entry(exempt_from="whatever")]), False, "不在封闭枚举"),
    ("★反例 `still_required` 为空 ⇒ **免终裁 ≠ 免一切**没落实",
     _with_entries([_entry(still_required=[])]), False, "缺必填 `still_required`"),
    ("★反例 `review_every=0`（豁免无再评审周期）",
     _with_entries([_entry(review_every=0)]), False, "必须是正整数"),
    ("★反例 类目 `id` 重复",
     _with_entries([_entry(), _entry(approval_anchors=["run/x", "run/y"])]), False, "`id` 重复"),

    # ── 空 / 未定项 ──────────────────────────────────────────────────
    ("★反例 `entries` 为空却没有 `empty_reason`",
     _doc(empty_reason=""), False, "没有 `empty_reason`"),
    ("★反例 缺 `entries` 字段（『不存在』与『为空』必须可区分）",
     {k: v for k, v in _doc().items() if k != "entries"}, False, "缺 `entries` 字段"),
    ("★反例 `unverified` 为空 ⇒ 未实测部分没登记",
     _doc(unverified=[]), False, "`unverified` 为空"),
    ("★反例 顶层不是映射", ["nope"], False, "顶层不是映射"),
]


def main() -> int:
    fails = []

    for desc, doc, want_ok, kw in CASES:
        bad, notes = R.validate_review_catalog(doc)
        blob = " ".join(bad) + " " + " ".join(notes)
        ok = ((not bad) == want_ok) and (kw in blob)
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':{'在' if kw in blob else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} notes={notes}")

    # ── 端到端：真读 inventory/review-catalog.yaml ───────────────────────
    real = None
    try:
        import yaml
        real = yaml.safe_load(R.REVIEW_CATALOG_INV.read_text(encoding="utf-8"))
        bad, notes = R.validate_review_catalog(real)
        ok = not bad
        print(f"  {'ok  ' if ok else 'FAIL'} 端到端 真读 inventory/review-catalog.yaml\n        {notes} · bad={len(bad)}")
        if not ok:
            fails.append(f"真值文件自身不过: {bad}")
        n = len(real.get("entries") or [])
        print(f"  ok   实况报数：免终裁类目 **{n} 条**"
              f"（0 是实测结论，理由在 `empty_reason`）")
    except ImportError:
        print("  skip 端到端（缺 pyyaml）")

    # ── ★ 先验红自证（**在真文件上**）：塞一条 approvals=2 但只给 1 个锚点 ⇒ 必须红 ──
    if real is not None:
        mutated = copy.deepcopy(real)
        if not mutated.get("admission", {}).get("type_axis"):
            # 真文件当前 type_axis 为空 ⇒ 先补轴，**只让"锚点不足"这一条**成为唯一红因
            mutated["admission"]["type_axis"] = "review-kind"
        mutated["entries"] = [_entry(approval_anchors=["run/only-one"])]
        bad2, _ = R.validate_review_catalog(mutated)
        red = any("只填数字拿不出锚点" in b for b in bad2)
        print(f"  {'ok  ' if red else 'FAIL'} 先验红自证：在**真文件**上塞一条『approvals=2 但锚点只有 1』⇒ "
              f"必须红（{'是' if red else '否'}）")
        if not red:
            fails.append("先验红自证失败：真文件上锚点不足没被拦 ⇒ ITIL 门槛形同虚设")

    # ── ★ 先验红自证②：**真文件**的 `type_axis` 为空，此时若塞类目 ⇒ 必须报「没有浮出依据」──
    if real is not None:
        m2 = copy.deepcopy(real)
        if not m2.get("admission", {}).get("type_axis"):
            m2["entries"] = [_entry()]
            bad3, _ = R.validate_review_catalog(m2)
            red3 = any("类目没有浮出依据" in b for b in bad3)
            print(f"  {'ok  ' if red3 else 'FAIL'} 先验红自证②：真文件 `type_axis` 为空时塞类目 ⇒ 必须红")
            if not red3:
                fails.append("先验红自证②失败：无轴却有类目没被拦")
        else:
            print("  skip 先验红自证②（真文件已有 type_axis）")

    # ── 结构护栏 ────────────────────────────────────────────────────────
    ids = {c["id"] for c in R.CHECKS}
    if "review-catalog" not in ids:
        fails.append("CHECKS 里没有 id='review-catalog' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'review-catalog' 已在 CHECKS 注册")
    # ★ 判据不许"读过头"：fix 文本里必须写明它**不判**类目选得对不对
    fix = next((c.get("fix", "") for c in R.CHECKS if c["id"] == "review-catalog"), "")
    if "不判" in fix and "已有免终裁通道" in fix:
        print("  ok   结构护栏：fix 文本显式写了『不判什么』与『别读成已有免终裁通道』")
    else:
        fails.append("review-catalog 的 fix 文本没把『不判什么 / 别读过头』写清 ⇒ 读者会把它读成已达标")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
