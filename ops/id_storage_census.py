#!/usr/bin/env python3
"""ID **存储面**普查 —— 把"开库手工数 affected"变成可复算的机制（2026-09-26 · U-4）

## 为什么有这个文件

U-4 判据 `decide_invalidation()` 的一个入参是 `affected`（"哪些下游产物受影响"）。
2026-09-26 第一次把它数出来时，过程是**手工**的：打开 duckdb → 找 ID 列 → 数行数。
⇒ 结论**可复现**（人照做能得到同一个数），但**不可自动**（下次还得再手工一遍）。

本文件把那一步变成机制：**声明目标列 → 实测 → 对账**，输出 `affected` 集合。

## 三条设计决定（都为了"不变成一张自说自话的表"）

1. **声明 ≠ 事实**：脚本**声明**"哪列是主键"，但**必须回到库里核**
   （duckdb 查 `duckdb_constraints()` · sqlite 查 `PRAGMA table_info`）
   ⇒ 声明的 `role` 与实测不一致 ⇒ **判红**（"看起来更硬的判据其实没读到"是本仓头号形态）。
2. **共用 U-1 的判据**：一个值是不是 U-1 身份，**调 `rpc_check.u1_parse`**（不另写正则）
   ⇒ 与本仓唯一的 U-1 实现**同源**，避免"同一事实两个定义点"。
3. **只读**：`mode=ro` / `read_only=True` —— 它普查的是**别的项目**的生产库，**绝不写入**。

## 边界（别读成"它算出了影响面"）

- 它回答"**这些列里有多少行、形态是什么**"，**不回答**"改这些 ID 会不会出错" —— 后者是 H-1/H-3 的事。
- `affected` 的**完整性**取决于 `STORES` 清单是否齐全；⚠ 清单是**线索不是事实**（已吃过两次亏）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402  ★ 共用 U-1 判据（不另写正则）

CENSUS = ROOT / "inventory" / "id-storage-census.yaml"

# ── 口径（唯一实现；改这里 ⇒ 必须 --emit 重出真值）─────────────────────────────
SHAPE_SHA256_32 = "sha256[:32] 无前缀"
SHAPE_OTHER_HEX = "其它长度 hex"
SHAPE_PREFIXED = "带前缀"
SHAPE_U1 = "U-1 合规"
SHAPE_EMPTY = "空值"

PREFIXED_RE = re.compile(r"^([A-Za-z]+_+)([0-9a-f]+)$")
MAX_SHAPE_SAMPLE = 100000  # 形态取样的上限（防大表拖慢；命中上限会显式报出）

# ── 被普查的存储（**声明**；每条都要被实测核过） ────────────────────────────────
# role 的取值域固定：primary_key / record_key
STORES = (
    {"project": "Open_Data", "kind": "duckdb",
     "path": r"F:\Open_Data\alternative_data.duckdb",
     "table": "alt_events", "column": "event_id", "role": "primary_key"},
    {"project": "Open_Data", "kind": "duckdb",
     "path": r"F:\Open_Data\alternative_data.duckdb",
     "table": "raster_index", "column": "raster_id", "role": "primary_key"},
    {"project": "Open_Data", "kind": "duckdb",
     "path": r"F:\Open_Data\alternative_data.duckdb",
     "table": "spatial_entities", "column": "entity_id", "role": "primary_key"},
    # ⚠ 这条的 role 声明**改过一次**（2026-09-26）：原写 `record_key`（**真但不够具体**），
    #   实测它在 sqlite 里 `PRAGMA table_info` 的 pk 位 > 0 ⇒ 是**主键** ⇒ 改成 `primary_key`
    #   （声明要**尽量具体**，否则"最坏情况"永远测不出来 —— 与 `factor_pipeline` 那次的教训同族）。
    {"project": "Auto_Prover", "kind": "sqlite",
     "path": r"F:\Auto_Prover\.artifacts\m1\verdicts.db",
     "table": "verdicts", "column": "verdict_id", "role": "primary_key"},
    # ⚠ JSONL **无主键概念** ⇒ 只能声明 `record_key`；探测返回 `is_primary_key: None`（**显式未知**）。
    #   若有人把它声明成 `primary_key`，门禁 `id-storage` 会判红（`None is not True`）——这条**已被先验红验证过**。
    {"project": "Auto_Prover", "kind": "jsonl",
     "path": r"F:\Auto_Prover\.artifacts\m1\unified_cases.jsonl",
     "table": None, "column": "case_id", "role": "record_key"},
)

EXIT_OK, EXIT_MISMATCH, EXIT_DEGRADED = 0, 1, 2

# ── U-4 **执行侧**注册表（A6，2026-09-29）────────────────────────────────────
# ⚠ **故意为空**：本仓与九项目**都没有**失效传播实现（实测 **0/9**）⇒ 没有执行器可注册。
#   有活（`incremental` / `full_rebuild`）时会落到 `not-executed`（**不适用，带理由**），
#   **绝不**在无执行器时报成功 ⇒ 这张空表本身就是"执行侧未落地"的**机读证据**，不是遗漏。
#   注册形态：{action: callable(target) -> {"status": "success"|"failed"|"n/a", "version": int|None}}
EXECUTORS = {}


def classify(value):
    """一个 ID 值的**形态**（★ U-1 那一档调 `u1_parse`，与实现同源）。"""
    if value is None or value == "":
        return SHAPE_EMPTY
    s = str(value)
    if R.u1_parse(s) is not None:
        return SHAPE_U1
    if re.fullmatch(r"[0-9a-f]{64}", s):
        return SHAPE_OTHER_HEX
    if re.fullmatch(r"[0-9a-f]{32}", s):
        return SHAPE_SHA256_32
    if PREFIXED_RE.fullmatch(s):
        return SHAPE_PREFIXED
    return SHAPE_OTHER_HEX if re.fullmatch(r"[0-9a-f]+", s) else "非 hex"


def _shape_hist(values):
    hist = {}
    for v in values:
        k = classify(v)
        hist[k] = hist.get(k, 0) + 1
    return hist


def probe_duckdb(st):
    import duckdb
    con = duckdb.connect(st["path"], read_only=True)
    try:
        cols = [r[1] for r in con.execute('PRAGMA table_info("%s")' % st["table"]).fetchall()]
        if st["column"] not in cols:
            return {"error": f"列不存在: {st['table']}.{st['column']}"}
        pkcols = []
        for tn, ctype, ccols in con.execute(
                "SELECT table_name, constraint_type, constraint_column_names FROM duckdb_constraints() "
                "WHERE table_name = ?", [st["table"]]).fetchall():
            if ctype == "PRIMARY KEY":
                pkcols.extend(ccols)
        rows = con.execute('SELECT count(*) FROM "%s"' % st["table"]).fetchone()[0]
        distinct = con.execute('SELECT count(DISTINCT "%s") FROM "%s"' % (st["column"], st["table"])).fetchone()[0]
        vals = [r[0] for r in con.execute(
            'SELECT "%s" FROM "%s" LIMIT %d' % (st["column"], st["table"], MAX_SHAPE_SAMPLE)).fetchall()]
        return {"ok": True, "rows": rows, "distinct": distinct,
                "is_primary_key": st["column"] in pkcols,
                "shape": _shape_hist(vals), "shape_sampled": len(vals) < rows}
    finally:
        con.close()


def probe_sqlite(st):
    con = sqlite3.connect("file:" + st["path"].replace("\\", "/") + "?mode=ro", uri=True)
    try:
        info = con.execute('PRAGMA table_info("%s")' % st["table"]).fetchall()
        cols = [r[1] for r in info]
        if st["column"] not in cols:
            return {"error": f"列不存在: {st['table']}.{st['column']}"}
        pkcols = [r[1] for r in info if r[5]]          # r[5] = pk 序号（>0 即主键的一部分）
        rows = con.execute('SELECT count(*) FROM "%s"' % st["table"]).fetchone()[0]
        distinct = con.execute('SELECT count(DISTINCT "%s") FROM "%s"' % (st["column"], st["table"])).fetchone()[0]
        vals = [r[0] for r in con.execute(
            'SELECT "%s" FROM "%s" LIMIT %d' % (st["column"], st["table"], MAX_SHAPE_SAMPLE)).fetchall()]
        return {"ok": True, "rows": rows, "distinct": distinct,
                "is_primary_key": st["column"] in pkcols,
                "shape": _shape_hist(vals), "shape_sampled": len(vals) < rows}
    finally:
        con.close()


def probe_jsonl(st):
    vals, n = [], 0
    with open(st["path"], encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            n += 1
            if n <= MAX_SHAPE_SAMPLE:
                try:
                    vals.append(json.loads(line).get(st["column"]))
                except Exception:
                    vals.append("<解析失败>")
    return {"ok": True, "rows": n, "distinct": len({str(v) for v in vals}),
            "is_primary_key": None,                        # JSONL 无主键概念 ⇒ 显式未知，不假装
            "shape": _shape_hist(vals), "shape_sampled": n > MAX_SHAPE_SAMPLE}


PROBES = {"duckdb": probe_duckdb, "sqlite": probe_sqlite, "jsonl": probe_jsonl}


def census(verbose=False):
    """逐条实测（**不可达照实记**，不静默丢）。"""
    out = []
    for st in STORES:
        rec = {"project": st["project"], "kind": st["kind"], "path": st["path"],
               "table": st["table"], "column": st["column"], "declared_role": st["role"]}
        if not Path(st["path"]).is_file():
            rec["reachable"] = False
            out.append(rec)
            if verbose:
                print(f"  [--]  {st['project']:<12} {st['path']} 不可达")
            continue
        rec["reachable"] = True
        try:
            rec.update(PROBES[st["kind"]](st))
        except Exception as e:                             # 探测失败也要**可见**
            rec["probe_error"] = f"{type(e).__name__}: {e}"
        out.append(rec)
        if verbose:
            if rec.get("probe_error"):
                print(f"  [!!]  {st['project']:<12} {st['column']}: {rec['probe_error']}")
            else:
                print(f"  [ok] {st['project']:<12} {st['column']:<12} rows={rec.get('rows')} shape={rec.get('shape')}")
    return out


def _header():
    return (
        "# ID **存储面**普查真值（可复算）—— affected 的**生产者**\n"
        "#\n"
        "# 生成：`py ops/id_storage_census.py --emit`   ·   复算比对（门禁）：`id-storage`\n"
        "# 口径的**唯一实现**在 `ops/id_storage_census.py`；本文件只是它的一次输出快照。\n"
        "# ⚠ `shape` = ID 值的形态分布（取样 ≤ 10 万；`shape_sampled: true` 表示未全量）。\n"
        "# ⚠ `is_primary_key` 是**回库里核的**，不是照抄声明 —— 声明与实测不一致时门禁判红。\n"
        "# ⚠ JSONL 无主键概念 ⇒ `is_primary_key: null`（**显式未知**，不假装是 false）。\n"
    )


def emit():
    import yaml
    data = {"metric": {"shape_classes": [SHAPE_U1, SHAPE_SHA256_32, SHAPE_OTHER_HEX, SHAPE_PREFIXED, SHAPE_EMPTY],
                       "shape_sample_limit": MAX_SHAPE_SAMPLE,
                       "u1_judge": "rpc_check.u1_parse（与 U-1 实现同源）",
                       "role_domain": ["primary_key", "record_key"]},
            "stores": census(verbose=True)}
    CENSUS.write_text(_header() + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200),
                      encoding="utf-8")
    print(f"[emit] 写入 {CENSUS.relative_to(ROOT)} · 存储 {len(data['stores'])} 处")
    return EXIT_OK


def check():
    import yaml
    if not CENSUS.is_file():
        print(f"[FAIL] 真值缺失: {CENSUS.relative_to(ROOT)} ⇒ 先跑 --emit")
        return EXIT_MISMATCH
    doc = yaml.safe_load(CENSUS.read_text(encoding="utf-8")) or {}
    m = doc.get("metric") or {}
    drift = [k for k, v in (("shape_sample_limit", MAX_SHAPE_SAMPLE),
                            ("role_domain", ["primary_key", "record_key"])) if m.get(k) != v]
    print(f"[口径] 形态档={m.get('shape_classes')} · 取样上限={m.get('shape_sample_limit')} · "
          f"U-1 判据={m.get('u1_judge')}")
    if drift:
        print(f"[FAIL] **口径已漂移**: {drift} ⇒ 重跑 --emit 并复核下游结论")

    now = {(s["project"], s["path"], s["table"], s["column"]): s for s in census()}
    mism, unreach, badrole = [], [], []
    for s in doc.get("stores") or []:
        key = (s["project"], s["path"], s["table"], s["column"])
        cur = now.get(key)
        if cur is None:
            continue
        if not cur.get("reachable"):
            unreach.append(f"{s['project']}.{s['column']}")
            print(f"  [--]  {s['project']}.{s['column']} 不可达 ⇒ **本次无法复算**（降级，不当作通过）")
            continue
        # ★ 声明的 role 必须与库里的实测一致（"声明 ≠ 事实"）
        if s.get("declared_role") == "primary_key" and cur.get("is_primary_key") is not True:
            badrole.append(f"{s['project']}.{s['column']}: 声明 primary_key，但库里**不是**（实测 is_primary_key="
                           f"{cur.get('is_primary_key')}）")
        if s.get("rows") != cur.get("rows") or s.get("distinct") != cur.get("distinct"):
            mism.append(f"{s['project']}.{s['column']}: 真值 {s.get('rows')}行/{s.get('distinct')}distinct "
                        f"≠ 实测 {cur.get('rows')}行/{cur.get('distinct')}distinct")
        else:
            print(f"  [ok] {s['project']}.{s['column']:<12} {cur.get('rows')} 行 · "
                  f"shape={cur.get('shape')} · pk={cur.get('is_primary_key')}")

    if drift or mism or badrole:
        for x in drift + badrole + mism:
            print(f"[FAIL] {x}")
        return EXIT_MISMATCH
    if unreach:
        print(f"[WARN] 不可达 {len(unreach)}/{len(doc.get('stores') or [])} ⇒ 本次**affected 不完整**（可见，不静默）")
        return EXIT_DEGRADED
    print(f"[PASS] {len(now)} 处存储均可复算，且与真值一致")
    return EXIT_OK


def invalidate(changed_paths):
    """★ **消费者**：把 changed（本仓**已登记 U-1 的文件**）接到 `decide_invalidation()`。

    链条（五段各自有产出者，不再是手工）：
      ① **changed_ids**：由 `--changed <path>` 给出的文件 → 取其 `u1:` **声明**里的身份
         （⚠ 身份**由声明给出**，不靠反推 —— U-1 是哈希，反推不出 namespace）
      ② **affected**：`id_storage_census` 实测的存储面，按 **namespace** 归集
      ③a ★ **闭包核验**（`U4#3`，2026-09-30）：判定方**独立重算**（`verify_affected_closure`）
         —— **取代**旧的**自报位** `affected_is_closure=True`；本域无图查询面 ⇒ `boundary`
         （照裁反转为「登记为边界 + 事后抽检」）⇒ **不声称已闭包**（fail-closed）
      ③ **判据 + 呈现位**：`rpc_check.decide_invalidation()` → `action / class / reason`，逐行打印
      ④ **执行侧**：`rpc_check.execute_invalidation()` → 执行报告（`status` 四档 + 逐项三态）
         ⚠ 重算交给注册表 `EXECUTORS`；本仓注册表**故意为空**（九项目 0/9）⇒ 有活时报 `not-executed`，
         **不假装已执行**（`A6`，2026-09-29）
    """
    import yaml
    changed = []
    for p in changed_paths:
        f = Path(p) if Path(p).is_absolute() else (ROOT / p)
        if not f.is_file():
            print(f"[WARN] --changed 给的路径不存在，跳过: {p}")
            continue
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        decl = doc.get("u1") if isinstance(doc, dict) else None
        if not decl:
            print(f"[WARN] {f.relative_to(ROOT)} 没有 `u1:` 声明 ⇒ **无法把它算作 changed_id**（不猜）")
            continue
        err = R.u1_verify_declaration(decl)
        if err:
            print(f"[FAIL] {f.relative_to(ROOT)} 的 u1 声明不可复算: {err}")
            return EXIT_MISMATCH
        changed.append(decl)

    ns = sorted({d["namespace"] for d in changed})
    print(f"[① changed_ids] {len(changed)} 个 · namespace = {ns or '（无）'}")

    if not changed:
        print("[② affected] 无 changed_ids ⇒ 不枚举（**不是「没事」，是「没有输入」**）")
        return EXIT_MISMATCH

    stores = yaml.safe_load(CENSUS.read_text(encoding="utf-8")).get("stores") if CENSUS.is_file() else []
    aff = [s for s in (stores or []) if s.get("reachable") and _ns_of_project(s["project"]) in ns]
    rows = sum(s.get("rows") or 0 for s in aff)
    print(f"[② affected] `id_storage_census` 实测：{len(aff)} 列 / **{rows} 行**")
    for s in aff:
        print(f"      {s['project']}.{s.get('table')}.{s['column']}  ({s.get('rows')} 行 · shape={s.get('shape')})")

    # ③ 判据：**入参如实** —— 增量等价性"未证"就写 False（不替它乐观）
    # ⚠ `affected` 传**空列表也不要传 None**：二者语义不同 ——
    #   空列表 = "**已判定**为空"（`affected_is_closure=True` 时 = 真的没有下游）
    #   None   = "**判不了**"（H-3 的触发条件）
    #   写成 `affected or None` 会把"已知为空"错误升格成"判不了"，从而**白白付一次全量**。
    affected_labels = [f"{s['project']}.{s.get('table')}.{s['column']}" for s in aff]
    changed_ids = [d["identity"] for d in changed]

    # ★③a 闭包**独立重算**（`U4#3`，2026-09-30 / `O-123` 裁）：**去掉自报位** `affected_is_closure=True`
    #   —— 旧形态是**调用方自称**"我做过闭包了"，判据**无法验证**（那正是"看起来更硬的判据其实没读到"）。
    #   现改为：判定方拿**依赖图查询面**独立重算 ⇒ 与自报**逐项比对**，**不一致即拒收**。
    #   ⚠ 本域的实况（**实测**）：本域要判的是**产物 → 存储列**，而 `edges.yaml` 是**产物 → 产物**
    #     ⇒ **域不同**，把它当本域图面会**误拒**（实测：`--changed inventory/dialect.yaml` 会因
    #     `edges.yaml` 依赖 `dialect.yaml` 而被判"漏算" ⇒ 拒收，而那是**两个域各自的真话**）
    #     ⇒ 本域**没有**可用的图查询面 ⇒ 按裁的再触发条件**反转为「登记为边界 + 事后抽检」**。
    #     ★ 所以这里**显式传 `edges=None`**（**不是**"忘了传"，是"查过了、没有"）。
    closure_verdict, closure_detail = R.verify_affected_closure(
        changed_ids=changed_ids, affected=affected_labels, edges=None)
    print(f"[③a 闭包核验] verdict={closure_verdict}\n         {closure_detail}")
    if closure_verdict == "inconsistent":
        print("[FAIL] 自报影响面与判定方**独立重算**不一致 ⇒ **拒收**（不落盘、不改任何产物）")
        return EXIT_MISMATCH

    action, class_, reason = R.decide_invalidation(
        changed_ids=changed_ids,
        affected=affected_labels,
        # ★ 只有 `consistent` 才敢声称"已闭包"；`boundary`/`inconsistent` ⇒ **不声称**（fail-closed）
        affected_is_closure=(closure_verdict == "consistent"),
        incremental_equivalent=False,     # ⚠ H-1 的证明**不存在** ⇒ 不敢说 True（说 True 就是编）
        build_failed=False,
    )
    print(f"[③ 处置] action={action} · class={class_}\n         reason={reason}")

    # ④ 执行侧（A6，2026-09-29）：把决策落成【执行报告】—— 重算交给注册表 `EXECUTORS`；
    #   本仓注册表为空 ⇒ 有活时如实报 `not-executed`（不适用，带理由），**不假装已执行**。
    rep = R.execute_invalidation(action, class_, reason, affected=affected_labels, executors=EXECUTORS)
    agg = rep["aggregate"]
    print(f"[④ 执行] status={rep['status']} · 成功 {agg['n_success']} / 失败 {agg['n_failed']} / "
          f"不适用 {agg['n_na']} · 版本单调={agg['version_monotonic']}")
    if rep["status"] == "not-executed":
        print("⚠ 有活但**无注册执行器** ⇒ 整体未执行（**不适用，带理由**）—— 执行侧仍缺，**不假装已接**")
    elif rep["status"] == "no-op":
        print("· 无需动作（决策已判定：无变更 / 无下游）")
    for it in rep["items"]:
        print(f"      [{it['status']}] {it['target']} — {it['detail']}")
    return EXIT_OK


def _ns_of_project(project):
    """项目 → namespace。⚠ 这是**一张映射表**：它本身是"清单"，不是事实（见 `dialect.yaml`）。"""
    return {"Open_Data": "Open_Data", "Auto_Prover": "Auto_Prover"}.get(project, project)


def main():
    ap = argparse.ArgumentParser(description="ID 存储面普查 / affected 生产者（U-4）")
    ap.add_argument("--emit", action="store_true", help="重写 inventory/id-storage-census.yaml")
    ap.add_argument("--check", action="store_true", help="复算比对（默认行为）")
    ap.add_argument("--invalidate", action="store_true", help="★ 消费者：changed → affected → 处置 → 执行报告")
    ap.add_argument("--changed", action="append", default=[],
                    help="内容变了的文件（可多次；须带 `u1:` 声明）")
    a = ap.parse_args()
    if a.emit:
        return emit()
    if a.invalidate:
        return invalidate(a.changed)
    return check()


if __name__ == "__main__":
    sys.exit(main())
