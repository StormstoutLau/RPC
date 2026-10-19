"""`edges` 断言（D7-P1-3）的正反注入 —— 永久护栏（2026-09-26）

D7-P1-3 的退出判据后半句 =「**`provenance` 缺 ⇒ 边无效**可机判」。本文件保护的就是它。

对象不是"某段代码写得对不对"，而是**那份清单自己**：`inventory/edges.yaml`。
它最容易被做成空头承诺的地方有两处，各有一组用例：
  · **无效边被"丢掉继续"**（把"判不了"悄悄变成"没有这条边"）⇒ 用例 5~13；
  · **空清单被读成"一切正常"** ⇒ 用例 2/3（空必须显式 + 必须给 `empty_reason`）。

⚠ 两处**刻意不做**的事：
  · 空清单**不 FAIL**（没有对象 ≠ 违规）—— 但**必须**有 `empty_reason`，且门禁**显式报"0 条"`；
  · 载荷**允许**含 `:`（只按**第一个** `:` 切分）—— 用例 17 钉住它，
    因为产物初稿的"载荷禁含 `:`"与它自己的示例自相矛盾。
"""
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

S_ID = "u1:sha256:32:0123456789abcdef0123456789abcdef"
D_ID = "u1:sha256:32:fedcba9876543210fedcba9876543210"

KINDS = ["document_level", "formal_handoff_package"]
PREFIXES = ["hash", "filetrack", "manual", "tool"]


def _doc(**over):
    base = {"version": 1, "kinds": list(KINDS), "provenance_prefixes": list(PREFIXES),
            "edges": [], "empty_reason": "前置缺失：U-1 身份未落地，造不出合规的 src/dst"}
    base.update(over)
    return base


def _edge(**over):
    e = {"src": S_ID, "dst": D_ID, "kind": "document_level", "provenance": "manual:operator-a:2026-09-26:reason=x"}
    e.update(over)
    return e


def _nonempty(edges=None, **over):
    return _doc(edges=[_edge()] if edges is None else edges, **over)


CASES = [
    # ── 正例 ────────────────────────────────────────────────────────────
    ("正例 空清单 + empty_reason（空本身不是违规，但必须显式）",
     _doc(), True, "边 0 条"),
    ("正例 一条合规边",
     _nonempty(), True, "边 1 条 · 无效 0 条"),
    ("正例 载荷含 `:`（只按第一个 `:` 切分 ⇒ filetrack 合法）",
     _nonempty(edges=[_edge(provenance="filetrack:v1.2.3:in=a,out=b")]), True, "无效 0 条"),

    # ── ★ 空清单：必须显式、必须有说法 ──────────────────────────────────
    ("★反例 空清单**没有** empty_reason ⇒ 空得没说法",
     _doc(empty_reason=""), False, "没有 `empty_reason`"),
    ("★反例 缺 `edges` 字段（分不清「空」与「忘了写」）",
     {"version": 1, "kinds": list(KINDS), "provenance_prefixes": list(PREFIXES)}, False, "缺 `edges` 字段"),

    # ── ★ provenance：七种「缺」 ────────────────────────────────────────
    ("★反例 缺 provenance 字段",
     _nonempty(edges=[{"src": S_ID, "dst": D_ID, "kind": "document_level"}]), False, "缺字段"),
    ("★反例 provenance = 空串",
     _nonempty(edges=[_edge(provenance="")]), False, "无效"),
    ("★反例 provenance = 仅空白",
     _nonempty(edges=[_edge(provenance="   ")]), False, "仅含空白"),
    ("★反例 provenance = unknown（禁用词，不区分大小写）",
     _nonempty(edges=[_edge(provenance="Unknown")]), False, "禁用词"),
    ("★反例 provenance = `manual:`（有前缀、载荷为空）—— 反向自查用例",
     _nonempty(edges=[_edge(provenance="manual:")]), False, "载荷为空"),
    ("★反例 provenance 前缀不在封闭集（猜的）",
     _nonempty(edges=[_edge(provenance="guessed:x")]), False, "不在封闭集"),
    ("★反例 provenance 无 `:`（不成形式）",
     _nonempty(edges=[_edge(provenance="manual")]), False, "缺 `<前缀>:<载荷>` 形式"),

    # ── ★ U3#3：`manual` 载荷必须是三段式 `<标识>:<日期>:reason=<理由>`（spec §3）──
    # 先验红：本组用例在**未实现**前必须失败（当前 `edge_provenance_invalid` 只判「前缀 ∈ 集 + 载荷非空」）。
    ("★反例 manual 载荷只有两段（缺 `reason=` 那一段）",
     _nonempty(edges=[_edge(provenance="manual:operator-a:2026-09-26")]), False, "三段式"),
    ("★反例 manual 日期段不成 `YYYY-MM-DD`",
     _nonempty(edges=[_edge(provenance="manual:operator-a:20260926:reason=x")]), False, "日期段"),
    ("★反例 manual 第三段不以 `reason=` 起",
     _nonempty(edges=[_edge(provenance="manual:operator-a:2026-09-26:why=x")]), False, "reason="),
    ("★反例 manual 作者标识是绝对路径（不得是用户名/主机名/IP/盘符）",
     _nonempty(edges=[_edge(provenance="manual:/home/admin:2026-09-26:reason=x")]), False, "作者标识"),
    ("正例 manual 三段式合规（角色标识 · 非用户名）",
     _nonempty(edges=[_edge(provenance="manual:operator-a:2026-09-26:reason=initial_sync")]), True, "无效 0 条"),

    # ── ★ src/dst 必须与 U-1 咬合 ───────────────────────────────────────
    ("★反例 src 不是 U-1 身份形态（随手写路径）",
     _nonempty(edges=[_edge(src="out/foo.md")]), False, "不是 U-1 产物身份形态"),
    ("★反例 dst 用大写 hex（形态不合）",
     _nonempty(edges=[_edge(dst="u1:sha256:32:ABCDEF0123456789ABCDEF0123456789")]), False, "不是 U-1 产物身份形态"),

    # ── ★ 枚举 / 重复 ──────────────────────────────────────────────────
    ("★反例 kind 不在 `kinds` 封闭枚举里",
     _nonempty(edges=[_edge(kind="depends_on")]), False, "不在 `kinds` 封闭枚举"),
    ("★反例 (src,dst,kind) 重复 ⇒ 同一事实两处定义",
     _nonempty(edges=[_edge(), _edge()]), False, "重复"),
    ("★反例 `kinds` 为空 ⇒ kind 没有枚举可判",
     _doc(kinds=[], edges=[_edge()]), False, "`kinds` 为空"),
    ("★反例 `provenance_prefixes` 为空",
     _doc(provenance_prefixes=[], edges=[_edge()]), False, "`provenance_prefixes` 为空"),
    ("★反例 `kinds` 有重复项",
     _doc(kinds=KINDS + ["document_level"], edges=[_edge()]), False, "有重复项"),
    ("★反例 顶层不是映射",
     ["not", "a", "dict"], False, "顶层不是映射"),
]


def main() -> int:
    fails = []
    for desc, doc, want_ok, kw in CASES:
        bad, notes = R.validate_edges(doc)
        blob = " ".join(bad) + " " + " ".join(notes)
        got_kw = kw in blob
        ok = ((not bad) == want_ok) and got_kw
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':"
              f"{'在' if got_kw else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} notes={notes}")

    # 端到端：**真读本仓的 inventory/edges.yaml**
    try:
        import yaml
        real = yaml.safe_load((ROOT / "inventory" / "edges.yaml").read_text(encoding="utf-8"))
        bad, notes = R.validate_edges(real)
        ok = not bad
        print(f"  {'ok  ' if ok else 'FAIL'} 端到端 真读 inventory/edges.yaml\n"
              f"        {notes} · bad={len(bad)}")
        if not ok:
            fails.append(f"真值文件自身不过: {bad}")
    except ImportError:
        print("  skip 端到端（缺 pyyaml）")

    # 结构护栏：函数存在**且已注册**（"写了函数忘了进 CHECKS" = 挂名假判）
    if "edges" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='edges' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'edges' 已在 CHECKS 注册")

    # 生成物登记护栏：edges.yaml 必须登记进 artifacts.yaml（否则它是"静默缺口"）
    try:
        import yaml
        art = yaml.safe_load((ROOT / "inventory" / "artifacts.yaml").read_text(encoding="utf-8"))
        hit = [i for i in (art.get("items") or []) if i.get("path") == "inventory/edges.yaml"]
        if not hit or hit[0].get("check") != "edges":
            fails.append("inventory/edges.yaml 未在 artifacts.yaml 登记为生成物（check: edges）")
        else:
            print("  ok   生成物护栏：edges.yaml 已登记 check: edges")
    except ImportError:
        pass

    # ── ★★ `U3#4`（2026-09-30 · 批 4）：**拦截率 / 误杀率**（实测读数，不是"只测过一条合成用例"）──
    # 口径：把上面的 `CASES` 按 `want_ok` 分成两族 ——
    #   `拦截率` = 反例里被判出问题的比例（判据"会咬"）；`误杀率` = 正例里被判出问题的比例（判据"不滥杀"）。
    # ⚠⚠ **如实标注射程**：样例是**构造的**（实测 n = **17 反例 / 3 正例**），**不代表脏数据分布**
    #   —— 规范 §未实测 4 的原话"脏数据分布未知"**仍然成立**，本条只把它从"**只测过 1 条**"推进到"**有 n 条**"。
    pos = [d for _desc, d, w, _kw in CASES if w]
    neg = [d for _desc, d, w, _kw in CASES if not w]
    killed = sum(1 for d in pos if R.validate_edges(d)[0])
    caught = sum(1 for d in neg if R.validate_edges(d)[0])

    def _naive(doc):
        """**先验红用的桩**：只判「有没有 `provenance` 字段」（= 最容易被写成的那版假绿判据）。"""
        if not isinstance(doc, dict):
            return []                                  # 顶层不是映射 —— 桩**看不见**（正是它的盲区）
        return [1 for e in (doc.get("edges") or [])
                if isinstance(e, dict) and "provenance" not in e]
    naive_caught = sum(1 for d in neg if _naive(d))

    ok = (caught == len(neg)) and (killed == 0)
    print(f"  {'ok  ' if ok else 'FAIL'} ★#4 拦截率 {caught}/{len(neg)} · 误杀率 {killed}/{len(pos)}"
          f"（口径 = 本文件 CASES；⚠ 样例**构造**，脏数据分布仍未知）")
    if not ok:
        fails.append(f"#4 拦截率/误杀率不达标: caught={caught}/{len(neg)} killed={killed}/{len(pos)}")
    # ★ 先验红自证：假绿桩**抓不全**反例 ⇒ 证明上面那个 `caught == len(neg)` 不是恒真
    red = naive_caught < len(neg)
    print(f"  {'ok  ' if red else 'FAIL'} 先验红自证（#4）：只判「有没有 provenance 字段」的桩 "
          f"只抓到 {naive_caught}/{len(neg)} ⇒ 真判据的拦截率不是恒真")
    if not red:
        fails.append("先验红自证（#4）失败：假绿桩与真判据拦截数相同 ⇒ 断言可能恒真")

    # ── ★★ `U3#9`（方向自洽性）：`filetrack` 的 `in=`/`out=` 必须与 src/dst **同向** ──
    # spec §1.1：`src`=依赖方/写方(下游) · `dst`=被依赖方/读方(上游) ⇒
    #   `out=`（被写文件）的身份 == src · `in=`（被读文件）的身份 == dst。
    # ⚠ `identity_of` 是**注入**的（纯函数才可夹测）；解析不到 ⇒ **报「未核」**，绝不静默判通过。
    # 先验红：本块在 `edge_direction_error` **未实现**前必然失败。
    idmap = {"inventory/edges.yaml": S_ID, "inventory/dialect.yaml": D_ID}
    d_cases = [
        ("正例 方向自洽", _edge(provenance="filetrack:v0.0.0:in=inventory/dialect.yaml,out=inventory/edges.yaml"), idmap, True, False),
        ("★反例 in/out 互换 ⇒ 依赖方向全反（静默错，故必抓）", _edge(provenance="filetrack:v0.0.0:in=inventory/edges.yaml,out=inventory/dialect.yaml"), idmap, True, True),
        ("★反例 filetrack 缺 `out=` ⇒ 形态不完备", _edge(provenance="filetrack:v0.0.0:in=inventory/dialect.yaml"), idmap, False, True),
        ("⚠ 解析不到身份 ⇒ 未核（不判同向，但必须可见）", _edge(provenance="filetrack:v0.0.0:in=missing.yaml,out=inventory/edges.yaml"), idmap, False, False),
        ("不适用（非 filetrack ⇒ 本检查不接）", _edge(provenance="manual:operator-a:2026-09-26:reason=x"), idmap, False, False),
    ]
    fn = getattr(R, "edge_direction_error", None)
    if fn is None:
        fails.append("`edge_direction_error` 不存在 ⇒ U3#9 方向自洽性判据缺失")
        print("  FAIL U3#9：`edge_direction_error` 不存在")
    else:
        for desc, e, im, want_checked, want_bad in d_cases:
            reason, checked = fn(e, im.get)
            ok = (checked == want_checked) and (bool(reason) == want_bad)
            print(f"  {'ok  ' if ok else 'FAIL'} U3#9 {desc}\n        reason={reason!r} checked={checked}")
            if not ok:
                fails.append(f"U3#9 {desc} ⇒ reason={reason!r} checked={checked}")
        import inspect
        src = inspect.getsource(R.check_edges)
        if "edge_direction_error(" not in src:
            fails.append("`check_edges` 未调用 `edge_direction_error` ⇒ 判据写了不接线（挂名假判）")
        else:
            print("  ok   U3#9 结构护栏：check_edges 已调用 edge_direction_error")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
