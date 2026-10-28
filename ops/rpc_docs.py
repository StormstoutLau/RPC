#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档类检查器：doclinks / md-tables / determinism / derived-view / executor-trace / doc-status / spec-untested / 台账状态（review-p2-split 8B-2；从 `rpc_check.py` 整段抽出，行为不变）。"""
import argparse
import ast
import concurrent.futures
import fnmatch
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from rpc_common import (
    ADR_CANON, ADR_DIR, ADR_GLOB, ADR_LEGACY, AGENT_CLI, CHECKS, ROOT, SENSITIVITY_INV,
    SENSITIVITY_SECTIONS, SENSITIVITY_TIERS, _decode_out, _ds, _norm_head, _read_text, _s,
    allow_unhit, validate_adr,
)

DOCLINK_ALLOW = {
    # (相对仓库根的 md 路径, 失效目标) -> 原因
    ("ops/agent-skills/what-if-oracle/SKILL.md", "references/scenario-templates.md"):
        "vendored 技能只收 SKILL.md, 其 references/ 未随仓库分发 (非本仓库文档漂移)",
}
DOCLINK_SKIP_PARTS = {".git", "node_modules", ".trae", "archive", "tmp"}
DOCLINK_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
def _doclink_bad(p, base):
    """返回 (是否失效, 是否可判定, 原因)。可判定=解析后落在仓库内，**或相对链接越出仓库根**。

    ⚠ 2026-09-22（决策简报 A）：原先"越界 ⇒ 不可判定"把**两类东西混进同一个桶** ——
      (a) 合法但不可判的：http/占位词/Windows 绝对盘符/指向仓库外的**绝对**路径；
      (b) **真错误：相对链接的 `..` 写多了、越出仓库根**。
    (b) 用**纯路径运算**就能判（与目标文件是否存在无关），而 09-16 那 27 条 `../../` 漏网**正是落在它里**
    ⇒ 故拆开：(b) 判 FAIL，(a) 仍保持不可判。**影响面实测 = 2 条、误报面 = 0**（"越界的非相对形态" 0 例）。
    """
    if base.startswith(("http://", "https://", "mailto:", "file:///", "#")):
        return False, False, ""
    if not base or " " in base or "..." in base or base in ("url", "path", "link"):
        return False, False, ""
    if len(base) > 1 and base[1] == ":":          # Windows 绝对盘符
        return False, False, ""
    q = os.path.normpath(str(p.parent / base))
    root = os.path.normpath(str(ROOT))
    if not q.lower().startswith(root.lower() + os.sep):
        flat = base.replace("\\", "/")
        if flat.startswith("..") or "/.." in flat:
            return True, True, "越出仓库根(相对链接层级写多)"
        return False, False, ""                   # 落到仓库外的**非相对**形态 ⇒ 不可判定
    return (not Path(q).exists()), True, ("目标不存在" if not Path(q).exists() else "")
def check_doclinks(ctx):
    """文档链接可达: md 里的仓库内相对链接不得指向不存在的路径。"""
    n_md = n_link = n_bad = n_allow = n_skip = 0
    bad = []
    allow_hit = set()          # D6-P0-2: 记录**实际命中**的豁免键（未命中的要自报）
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT)
        if any(s in rel.parts for s in DOCLINK_SKIP_PARTS):
            continue
        n_md += 1
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in DOCLINK_LINK.finditer(line):
                base = m.group(2).strip().split("#")[0]
                n_link += 1
                hit, judgeable, reason = _doclink_bad(p, base)
                if not judgeable:
                    n_skip += 1
                    continue
                if not hit:
                    continue
                if (rel.as_posix(), base) in DOCLINK_ALLOW:
                    n_allow += 1
                    allow_hit.add((rel.as_posix(), base))
                    continue
                n_bad += 1
                bad.append((f"{rel.as_posix()}:{i}", base, reason))

    detail = []
    for loc, base, why in bad:
        detail.append(f"{loc}  ->  {base}" + (f"   【{why}】" if why else ""))
    # D6-P0-2: 豁免**未命中**（该处已不再失效）⇒ **自报**，否则清单腐化无人知
    _unhit = allow_unhit(list(DOCLINK_ALLOW), allow_hit)
    for key in _unhit:
        detail.append(f"(豁免**未命中**) {key[0]}  ->  {key[1]} —— {DOCLINK_ALLOW[key]} ⇒ "
                      f"该链接已不再失效 ⇒ **该豁免已可移除**")
    note = (f"扫描 {n_md} 个 md · 链接 {n_link} 条 (其中非仓库内相对链接/占位词 {n_skip} 条不判) "
            f"· 已登记例外 {n_allow} · 失效 {n_bad}")
    if _unhit:
        note += f" · ⚠ 豁免未命中 {len(_unhit)} 条（已可移除，见明细）"
    return ("FAIL" if n_bad else ("WARN" if _unhit else "PASS")), note, detail
SPEC_DIR = ROOT / "spec" / "d6-agent-standard"
SPEC_UNTESTED_GLOBS = ("U[0-9]-*.md", "D7-PROTOCOL-*.md")
SPEC_UNTESTED_HEAD = "未实测登记"
SPEC_EMARK_DIRS = (SPEC_DIR, ROOT / "adr")
SPEC_EMARK_RE = re.compile(r"（(E[1-5])([^）]*)）")
UNTESTED_INDEX = ROOT / "inventory" / "untested-index.yaml"
def validate_spec_untested(text):
    """**纯函数**：一份规范类文档是否满足"恰 1 个 `## 未实测登记` ∧ 节体非空"⇒ 返回 (bad, note)。

    ⚠ 节体扫描**只到下一个二级标题**为止（`### …` 是子节、**属节体**）—— 与 `validate_adr` 同规则；
      按"任意标题"截断会把子节判成空节。
    """
    lines = text.splitlines()
    heads = [(i, ln.strip()) for i, ln in enumerate(lines)
             if ln.startswith("## ") and not ln.startswith("### ")]
    canon = [(i, raw) for i, raw in heads if _norm_head(raw[3:]) == _norm_head(SPEC_UNTESTED_HEAD)]
    if not canon:
        return ([f"**缺** `## {SPEC_UNTESTED_HEAD}` 节 ⇒ 新规范必须给出「尚未被真实运行验证」的清单"
                 f"（⚠ 它**只**保证这一节存在，**不**保证「正文里没有无证据断言」）"], "")
    bad = []
    if len(canon) > 1:
        bad.append(f"有 **{len(canon)}** 个 `## {SPEC_UNTESTED_HEAD}` 节"
                   f"（行 {[i + 1 for i, _ in canon]}）⇒ 只允许 1 个")
    i0 = canon[0][0]
    body = []
    for ln in lines[i0 + 1:]:
        if ln.startswith("# ") or (ln.startswith("## ") and not ln.startswith("### ")):
            break
        body.append(ln)
    n_item = sum(1 for b in body if re.match(r"^\s*(?:[-*+]|\d+\.)\s+\S", b))
    n_row = sum(1 for b in body
                if b.strip().startswith("|") and not re.match(r"^\s*\|[\s:|-]+\|\s*$", b))
    if n_item == 0 and n_row < 2:
        bad.append(f"第 {i0 + 1} 行 `## {SPEC_UNTESTED_HEAD}` 节**是空的**"
                   f"（列表项 {n_item} · 表格行 {n_row}）⇒ 只写了标题没写内容"
                   f"（需 ≥1 列表项 **或** ≥2 表格行 = 表头+数据）")
        return bad, ""
    return bad, f"列表项 {n_item} · 表格行 {n_row}"
LEDGER = ROOT / "spec" / "d6-agent-standard" / "OPEN-ISSUES.md"
LEDGER_ROW_RE = re.compile(r"^\|\s*(O-\d+)\s*\|")
LEDGER_LEAD_RE = re.compile(r"^[\s*_]*(✅|◐|⏳|🔵)")
LEDGER_CLOSED_MARK = "✅"
def parse_ledger_rows(text):
    """**纯函数**：解析台账行 ⇒ `[{id, line, status, cells}]`。`status` = 第一个格首带标记的格。

    ⚠⚠ **`status` 存的是「归一后」的文本**（剥掉前导 `**`/`_`/空白）—— 否则 `startswith('✅')` 对
      `**✅ …**` 会返回 False ⇒ **15 行被算成「仍开着」**（= 又一次假开；本批实测踩到，
      是靠"判据报数与独立探针报数不一致"抓出来的：判据 57/35 vs 探针 72/20）。
      ⇒ **教训：归一必须同时用于"匹配"和"比较"**，只对匹配归一照样会错。
    """
    rows = []
    for i, ln in enumerate(text.splitlines(), 1):
        m = LEDGER_ROW_RE.match(ln)
        if not m:
            continue
        cells = ln.split("|")[1:-1]
        status = ""
        for c in cells:
            if LEDGER_LEAD_RE.match(c.strip()):
                status = LEDGER_LEAD_RE.sub(r"\1", c.strip())   # 归一：只留标记开头
                break
        rows.append({"id": m.group(1), "line": i, "status": status, "cells": cells})
    return rows
def normalize_model_id(raw) -> str:
    """把产物里的 `model` 取值**归一到模型短名**（`D7-P3-1` 前置，2026-09-26）。

    ★★ **为什么必须归一（实测取的口径，不是设计出来的）**：取样 6 个真实 runDir，
      `run.json` 的 `model` 字段有**四种前缀形态** ——
        `local/gpt-oss-20b` · `cluster-litellm/gpt-oss-20b` ·
        `station:A/thinkingmachines/inkling:free` · `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`
      ⇒ 不归一就**没法和 `inventory/models.yaml` 的 `alias` 对上**。
    ★ 规则（**只剥外壳，不猜语义**）：① 取**最后一个 `/` 之后**的段；
      ② **再**去掉 `:` 之后的**尾参**。
    ⚠⚠ **顺序不能反（本批实测踩到）**：`station:A/thinkingmachines/inkling:free` 里 `:` 出现在
      **前缀中间**，若"先去尾参再取末段"会得到 `station`（整段被腰斩）⇒ 必须**先定位末段、再剥尾参**。
    """
    s = str(raw or "").strip()
    if not s:
        return ""
    return s.split("/")[-1].split(":", 1)[0].strip()
def model_key_variants(raw) -> list:
    """把 `model` 串展开成**候选键**（按优先级），供族表查询（`D7-P3-1`，2026-09-26）。

    ★★ **为什么不能只用一个键（实测 246 个真实 run 后得出）**：真实取值里既有
      `local/gpt-oss-20b`（本机档）也有 `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`（出网档）。
      · 只取**末段** ⇒ 丢掉 **vendor** ⇒ 而"谁家的"**正是族判定的依据**；
      · 只取全串 ⇒ 本地 alias（`m27-q4ks`）与出网串**不同形** ⇒ 一边对不上。
      ⇒ 展开成**多候选**、按"信息量从多到少"依次查，**首个命中者胜**；**全不命中 ⇒ 不可判**。
    候选顺序：① 剥掉已知**传输前缀**后的剩余路径（`nvidia/nemotron-…`）· ② 末段 · ③ 原串。
    ★ 只剥**已知**前缀（`local`/`cluster-litellm`/`opencode`/`openrouter`/`station:<X>`），
      **不猜**别的前缀语义（猜会把 `nvidia/…` 的 vendor 一起剥掉）。
    """
    s = str(raw or "").strip()
    if not s:
        return []
    parts = [x for x in s.split("/") if x]
    if not parts:
        return []
    known = {"local", "cluster-litellm", "opencode", "openrouter"}
    if parts[0] == "station" and len(parts) >= 2:
        rest = parts[2:]
    elif parts[0] in known:
        rest = parts[1:]
    else:
        rest = parts
    rest = [r.split(":", 1)[0] for r in rest]
    out = []
    if len(rest) >= 2:
        out.append("/".join(rest[-2:]))
    if rest:
        out.append(rest[-1])
    out.append(s)
    seen, res = set(), []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            res.append(x)
    return res
def family_of(raw, index):
    """按**候选键**查族 ⇒ `(family_id | None, 命中的键)`。全不命中 ⇒ `(None, '')`。"""
    for k in model_key_variants(raw):
        if k in index:
            return index[k], k
    return None, ""
def load_family_index():
    """读 `inventory/model-families.yaml` ⇒ `{候选键: family_id}`（供 J-1 用）。

    ⚠ **覆盖边界以 yaml 为准，本函数不复制它**（防"同一事实两个定义点"）：
      覆盖 = `families[].members`（本地 alias）+ `outbound_models[].keys`（**出网/传输档**已登记键）
      + `endpoint_aliases_na` **不在索引里**（端点别名 ⇒ 查不到 ⇒ J-1 恒 `unknown`，是**有意**的）。
      2026-09-29 实测 `len(index)=21`；夹具 `tests/test_rpc_check_cross_family.py` 的 `C5` 就钉这一条。
    """
    import yaml
    F = yaml.safe_load((ROOT / "inventory" / "model-families.yaml").read_text(encoding="utf-8")) or {}
    idx = {}
    for fam in (F.get("families") or []):
        fid = str(fam.get("id") or "")
        for a in (fam.get("members") or []):
            idx[str(a)] = fid
    for ob in (F.get("outbound_models") or []):
        fid = str(ob.get("family") or "")
        if not fid:
            continue
        for k in (ob.get("keys") or []):
            idx[str(k)] = fid
    return idx
def cross_family_verdict(producer_raw, judge_raw, index) -> dict:
    """**J-1（跨族）** 的判定本体（`D7-P0-3` 的判据之一 ⇒ `D7-P3-1` 落地）。

    判据原式：`lookup_family(judge.model) != lookup_family(producer.model)`。
    三态（**禁止"基本通过"**）：
      · `cross`   ⇒ 跨族 ✅（异构成立）
      · `same`    ⇒ **同族 ⇒ 判据红**（"同族多实例"不构成认知多样性 —— Courtroom-MAD 的实测）
      · `unknown` ⇒ **任一模型不在族表里 ⇒ 不可判**；★ **fail-closed：绝不默认算"跨族"**
        （默认放行 = 把"没判"读成"通过"，本仓最防的形态）。
    """
    p, j = str(producer_raw or "").strip(), str(judge_raw or "").strip()
    if not p or not j:
        return {"verdict": "unknown", "reason": "缺 producer/judge 的 model", "unknown": []}
    fp, kp = family_of(p, index)
    fj, kj = family_of(j, index)
    if fp is None or fj is None:
        miss = [model_key_variants(x)[0] for x, f in ((p, fp), (j, fj)) if f is None]
        return {"verdict": "unknown",
                "reason": f"查不到族: {'; '.join(miss)}（多为**端点别名**或**未登记的出网模型**"
                          f" ⇒ **不可判，不是通过**）",
                "unknown": miss}
    if fp == fj:
        return {"verdict": "same", "reason": f"producer={p}({fp}) · judge={j}({fj}) **同族**",
                "producer": p, "judge": j, "family": fp}
    return {"verdict": "cross", "reason": f"{fp} vs {fj}", "producer": p, "judge": j,
            "families": [fp, fj]}
def cross_input_verdict(producer_sha, judge_sha) -> dict:
    """**J-2（输入独立）** 的判定本体：`hash(judge.input) != hash(producer.input)`。

    原料 = `run.json.prompt_sha256`（产出者输入）与 `review.json.metadata.prompt_hash`（判官输入）
    —— ★ 两者**都已在产物里**（2026-09-26 实测），故 J-2 **不需要新登记**。
    ⚠ **诚实边界**：摘要**不等**只能证明"送入的载荷不同"，**不能**证明"信息独立"
      （判官可能收到同一份内容的不同包装）⇒ 本判据是**下界**，如实登记。
    """
    p, j = str(producer_sha or "").strip(), str(judge_sha or "").strip()
    if not p or not j:
        return {"verdict": "unknown", "reason": "缺 producer/judge 的输入摘要"}
    if p == j:
        return {"verdict": "same", "reason": "**两侧输入摘要相同** ⇒ 判官看到的就是产出者看到的（不独立）"}
    return {"verdict": "cross", "reason": "两侧输入摘要不同（**下界证据**，不等于信息独立）"}
def check_model_families(ctx):
    """`D7-P3-1` 前置：模型**家族**表 ↔ `models.yaml` **双向对账**（2026-09-26）。

    判什么：① 本表可解析且族非空（防空判）；② `members` 里的 alias **必须**在 `models.yaml` 存在
            （否则 = **孤儿引用**）；③ **`models.yaml` 的每个 alias 恰属 1 族**（**漏项与重复都红** ——
            只做单向包含会漏掉「新模型没归类」，而那正是本表最容易腐化的方向）；
            ④ 每族必须有**非空 `basis`**（族划分依据）⇒ 堵「看着像就填」（与 `dialect.yaml` 同纪律）。
    ⚠ **不判什么**：**不判族分得对不对**（那要人读权重血统）。本判据只保证「**没有一个 alias 没被归类**」
       与「引用不悬空」。
    ⚠ **不提供什么**：它**不提供**「站↔**已加载**模型」—— 那是 `D7-P0-3` 判据 J-1 的**第二个输入**，
       与 `models.yaml` 的 `stations`（库中有）/ `conf`（配过实例）**不是一回事**（见 yaml 的 `linked_state`）。
    """
    try:
        import yaml
    except Exception as e:                                   # noqa: BLE001
        return ("WARN", f"缺 pyyaml（{type(e).__name__}）⇒ 本项不判", [])
    fam_p = ROOT / "inventory" / "model-families.yaml"
    mod_p = ROOT / "inventory" / "models.yaml"
    try:
        F = yaml.safe_load(fam_p.read_text(encoding="utf-8")) or {}
        M = yaml.safe_load(mod_p.read_text(encoding="utf-8")) or {}
    except Exception as e:                                   # noqa: BLE001
        return ("FAIL", f"yaml 不可解析: {type(e).__name__}: {e}", [])
    fams = F.get("families") or []
    aliases = [str(m.get("alias")) for m in (M.get("models") or []) if m.get("alias")]
    if not fams:
        return ("FAIL", "`families` 为空 ⇒ 空判（防『什么都没判』）", [])
    if not aliases:
        return ("FAIL", "`models.yaml` 无 alias ⇒ 空判", [])
    bad, owner = [], {}
    for f in fams:
        fid = str(f.get("id") or "?")
        if len(str(f.get("basis") or "").strip()) < 4:
            bad.append(f"族 `{fid}` 缺 `basis`（族划分依据）⇒ 堵『看着像就填』")
        mem = [str(x) for x in (f.get("members") or [])]
        if not mem:
            bad.append(f"族 `{fid}` 无成员 ⇒ 空族")
        for a in mem:
            if a not in aliases:
                bad.append(f"族 `{fid}` 的成员 `{a}` **不在 `models.yaml`**（孤儿引用）")
            elif a in owner:
                bad.append(f"`{a}` 同时属 `{owner[a]}` 与 `{fid}`（**重复归类**）")
            owner[a] = fid
    miss = [a for a in aliases if a not in owner]
    if miss:
        bad.append(f"**未归类**的 alias {len(miss)} 个：{', '.join(miss)} ⇒ 新模型必须归类")
    # 出网段同样要**对账**（2026-09-26 补：登记了没人查 = "存在但无人读"）
    obs = (F.get("outbound_models") or [])
    ob_owner = {}
    for ob in obs:
        fid = str(ob.get("family") or "")
        keys = [str(x) for x in (ob.get("keys") or [])]
        if not keys:
            bad.append(f"outbound 条目无 `keys`（family={fid or '?'}）⇒ 空条目")
        if not fid:
            bad.append(f"outbound 条目缺 `family`（keys={keys[:2]}）")
        if not str(ob.get("basis_from") or "").strip():
            bad.append(f"outbound `{keys[:1] or ['?']}` 缺 `basis_from`（口径来源）⇒ 堵『看着像就填』")
        for k in keys:
            if k in owner:
                bad.append(f"outbound 键 `{k}` 与本地族 `{owner[k]}` 的成员**同名** ⇒ **键冲突**"
                           f"（同一模型两处定义，查表结果取决于顺序）")
            if k in ob_owner:
                bad.append(f"outbound 键 `{k}` 被两条记录占用（`{ob_owner[k]}` 与 `{fid}`）")
            ob_owner[k] = fid
    note = (f"族 {len(fams)} · 成员覆盖 {len(owner)}/{len(aliases)} · "
            f"未归类 {len(miss)} · 出网 {len(obs)}/{len(ob_owner)}键 · 问题 {len(bad)}")
    detail = list(bad)
    if detail:
        return ("FAIL", note, detail)
    return ("PASS", note, [f"族: {', '.join(str(f.get('id')) for f in fams)}"])
def check_ledger_status(ctx):
    """O-93: 台账每行**状态可机读**（格首标记自证）—— 并报出「仍开着 N 条 + 清单」。

    ★ 判什么：① 每行都要有状态格（缺 ⇒ FAIL = 该行状态**读不出来**）；② 数据行 ≥1（防空判）。
    📊 **报数（不判）**：`✅ 闭环 X · 仍开着 Y` + 仍开着的 ID 清单 ⇒ **排优先级不再依赖人读**。
    ⚠⚠ **不判什么**：「应该闭环多少」**不判** —— 「开着」**不是错误**；本判据只保证「**读得到**」。
      也**不判**状态写得对不对（那仍要人读）—— 别把本判据读成"台账已被审计"。
    """
    if not LEDGER.is_file():
        return "WARN", f"{LEDGER.name} 不存在（本断言的登记依据）", []
    rows = parse_ledger_rows(_read_text(LEDGER))
    if not rows:
        return "FAIL", "**台账数据行 0 条** ⇒ 判据没有对象（表头/格式被改动过？防退化成空判）", []
    bad = [f"{r['id']}(L{r['line']})" for r in rows if not r["status"]]
    closed = [r["id"] for r in rows if r["status"].startswith(LEDGER_CLOSED_MARK)]
    opened = [r["id"] for r in rows if r["status"] and not r["status"].startswith(LEDGER_CLOSED_MARK)]
    note = (f"数据行 {len(rows)} · 状态可机读 {len(rows) - len(bad)} · "
            f"✅ 闭环 {len(closed)} · **仍开着 {len(opened)}**")
    detail = []
    if opened:
        detail.append("仍开着：" + " ".join(opened))
    if bad:
        detail.append("状态不可机读（缺格首标记 ⇒ 补 `✅`/`◐`/`⏳`/`🔵`）：" + " ".join(bad))
    return ("FAIL" if bad else "PASS"), note, detail
LEDGER_PENDING_MARK = "待裁"
def ledger_pending_ids(rows):
    """**纯函数**：从台账行取「**自述面明写「待裁」**」的 id 集合（`O-144` 甲）。

    `rows` = `parse_ledger_rows` 的产物（`[{id, line, status, cells}]`）。
    ⚠ **射程（如实）**：只扫 `cells[3]`（简述）+ `cells[4]`（状态）；只认「待裁」。
      ★ **已知误报面**：若某行正文**历史性地**提到"待裁"（如"曾待裁、已裁"），会被读成当前待裁 ——
        当前实测 0 例，但**该形态存在**（与 `O-153` 同族的"射程被读宽"风险）。
    """
    out = set()
    for r in (rows or []):
        if not isinstance(r, dict):
            continue
        cells = r.get("cells") or []
        txt = " ".join(str(c) for c in cells[3:5]) if len(cells) >= 5 else str(r.get("line") or "")
        if LEDGER_PENDING_MARK in txt:
            out.add(r.get("id"))
    return out
def _ledger_rows_for_triage():
    """读台账行供 `O-144` 甲用；★ **读不出 ⇒ `None`**（退回旧口径，不阻断）。

    ⚠ 为什么这里可以"静默退回"而不违 fail-closed：**台账自身的可读性另有判据**
      （`ledger-status`：缺状态格即 FAIL）⇒ **判据只在一处**，此处不回重复判。
    """
    try:
        return parse_ledger_rows(_read_text(LEDGER))
    except Exception:
        return None
def summarize_untested_triage(items, ledger_rows=None):
    """**纯函数**：消费 `untested-index.yaml` 的**分诊**（O-123 · 2026-09-30）⇒ 返回 `(warn, stats)`。

    ★ **这是该索引的【首个消费者】**（此前它是叶子节点：只有它自己和它自己的同步测试引用它）。
    ★ **判据**：某条被认定为「**待裁**」⇒ 点名 —— 口径 = 「**未裁项不许静默**」。
      而"待裁"有**两个来源**（`O-144` 甲，2026-10-06）：
        ① `needs_decision: true`（索引里**手写**的 —— 原口径，只在**规范文档明写**时填）；
        ② ★ **`refs` 指向的台账条目【明写「待裁」】**（新口径，`ledger_rows` 非 None 时才生效）。
      ⇒ 为什么必须补 ②（`O-144` 的根因）：台账里写的"待裁"原**反映不到索引** ⇒
        `needs_decision: 0` 会被**误读成"本仓没有待裁项"**（本仓 fail-closed 精神；同 `O-119` 的"不可判 ≠ 通过"）。
      ⚠ `ledger_rows=None`（缺参 / 台账读不出）⇒ **退回旧口径**（只认 ①），**不阻断**。
    📊 `stats` = 报数（`state` / `blocker` / `needs_decision` 分布）—— **只报不判**（本仓"标签比事实硬"教训）。
    ⚠⚠ **不判什么**（防读过头）：
      · 不判"**该闭环多少条**"（开着不是错误）；
      · 不判分诊**写得对不对**（那是人工判断）；
      · **不重做**闭集/对账校验 —— 那是 `tests/test_untested_index_sync.py` 的职责（**判据只在一处**）。
    """
    warn = []
    n = 0
    by_state, by_blocker, n_dec, n_via = {}, {}, 0, 0
    pending = ledger_pending_ids(ledger_rows) if ledger_rows is not None else set()
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        n += 1
        st = str(it.get("state") or "?")
        bl = str(it.get("blocker") or "?")
        by_state[st] = by_state.get(st, 0) + 1
        by_blocker[bl] = by_blocker.get(bl, 0) + 1
        whose = f"{it.get('spec')}#{it.get('n')}"
        if it.get("needs_decision") is True:
            n_dec += 1
            warn.append(f"{whose}: `needs_decision: true` ⇒ **未裁项不许静默**"
                        f"（要么裁掉并落回规范本体，要么在索引里写明为何仍是 true）")
            continue
        via = [r for r in (it.get("refs") or []) if isinstance(r, str) and r in pending]
        if via:
            n_dec += 1
            n_via += 1
            warn.append(f"{whose}: `needs_decision` 字段为 false，但它 `refs` 指向的台账条目"
                        f"（{', '.join(via)}）**明写「待裁」** ⇒ **未裁项不许静默**"
                        f"（`O-144` 甲：来源已扩到台账 —— 请裁掉并落回规范本体，或把该行措辞改准）")
    stats = {"n": n, "state": by_state, "blocker": by_blocker,
             "needs_decision": n_dec, "needs_decision_via_ledger": n_via}
    return warn, stats
def check_spec_untested(ctx):
    """O-91: 规范类文档（`U[0-9]-*.md` / `D7-PROTOCOL-*.md`）必须带**非空**的 `## 未实测登记` 节。

    ★ 判什么：① **命中集 ≥1**（否则判据**没有对象** ⇒ FAIL，防退化成空判）；
      ② 每份**恰 1 个**该节；③ 节体**非空**；
      ④ ★ **O-123（2026-09-30）**：顺带**消费** `inventory/untested-index.yaml` 的分诊 ——
         **报数**（state / blocker / needs_decision 分布）+ **一条判据**（任一条 `needs_decision: true` ⇒ **WARN**，
         口径 = 「**未裁项不许静默**」）。⇒ 该索引由此**不再是叶子节点**（此前只有它自己的同步测试引用它）。
    ⚠⚠ **不判**：正文里有没有**无证据断言** —— 那不可机判、**仍是纪律**（见上方那段注释）。
      ⚠ 也**不判**分诊**写得对不对**，更**不重做**索引的对账/闭集校验（那是 `py-tests` 的职责 —— 判据只在一处）。
    📊 **附一条报数（不判）**：E 级内联标注里"带具体取证 vs 裸"的分布。
      ⚠ 为什么是**报数而不是判据**：实测 ADR 侧 **57% 是裸标**（`（E1）`），而"裸"**不等于"错"**
        （有的结论句本身不必带命令，命令写在同段别处）；且**连计数都口径敏感** ——
        同一棵树、两个正则（`（E[1-5]` vs 完整括号对）在 spec 侧数出 **4 vs 8**。
        ⇒ 做成 FAIL 会立刻造一批**假红**，而假红的结局是**被加进例外名单**（判据失效，O-70 同族）。
      ⚠ 也**不新开一个恒 PASS 的报数断言** —— 那正是"**判据什么都没判**"。
    """
    files = sorted({p for g in SPEC_UNTESTED_GLOBS for p in SPEC_DIR.glob(g)})
    if not files:
        return ("FAIL",
                f"spec/{SPEC_DIR.name} 下无匹配（{' / '.join(SPEC_UNTESTED_GLOBS)}）—— **判据无对象**", [])
    bad, summ, em_detail, em_bare, em_files = [], [], 0, 0, 0
    for p in files:
        text = _read_text(p)
        b, note = validate_spec_untested(text)
        bad += [f"{p.name}: {x}" for x in b]
        if note:
            summ.append(f"{p.stem}: {note}")
    # 📊 报数（**不判**）：射程 = "放断言的两个地方"（见 SPEC_EMARK_DIRS 的注释）
    for d in SPEC_EMARK_DIRS:
        for p in sorted(d.glob("*.md")):
            em_files += 1
            for m in SPEC_EMARK_RE.finditer(_read_text(p)):
                if m.group(2).strip(" ，,;；:："):
                    em_detail += 1
                else:
                    em_bare += 1
    n_bad_file = len({x.split(":", 1)[0] for x in bad})
    # ★ O-123（2026-09-30）：**索引分诊的消费者**（本条判据的第三件事，也是"叶子节点"缺口的另一半）。
    #   形态：**报数**（分布进 note）+ **一条判据**（`needs_decision: true` ⇒ WARN）。
    #   ⚠ 索引坏了/缺了 ⇒ **WARN 而非 FAIL**：本判据的对象是"规范的那一节"，索引是**附加消费对象**；
    #     索引自身的完整性/对账由 `py-tests`（`tests/test_untested_index_sync.py`）判 ⇒ **不在此处重复判**。
    tri_note, tri_warn = "", []
    try:
        import yaml
    except Exception:
        tri_warn = ["缺 pyyaml ⇒ **分诊无从消费**（本判据新增射程跳过；规范侧判定不受影响）"]
    else:
        if not UNTESTED_INDEX.is_file():
            tri_warn = [f"`inventory/{UNTESTED_INDEX.name}` 不存在 ⇒ **分诊无从消费**"]
        else:
            try:
                inv = yaml.safe_load(_read_text(UNTESTED_INDEX)) or {}
                tri_warn, tri = summarize_untested_triage(inv.get("items"), _ledger_rows_for_triage())
                _fmt = lambda d: " · ".join(f"{k}={v}" for k, v in sorted(d.items()))
                tri_note = (f" · **索引分诊** 条目 {tri['n']}"
                            f"（state {_fmt(tri['state'])}；blocker {_fmt(tri['blocker'])}；"
                            f"needs_decision {tri['needs_decision']}"
                            f"（其中 **{tri['needs_decision_via_ledger']} 条由台账 `refs` 推出**））")
                if tri["n"] == 0:
                    tri_warn = ["索引 `items` **为 0 条** ⇒ 分诊消费没有对象（防退化成空判）"]
            except Exception as e:
                tri_warn = [f"`inventory/{UNTESTED_INDEX.name}` 不可消费: {type(e).__name__}: {e}"]
    note = (f"规范 {len(files)} 份 · 违规 {n_bad_file} 份 · "
            f"E 标报数 带取证 {em_detail} / 裸 {em_bare}"
            f"（**报数，不判**；射程 = spec/d6-agent-standard/*.md + adr/ADR-*.md 共 {em_files} 份）" + tri_note)
    if not bad:
        note += f"（全部含 `## {SPEC_UNTESTED_HEAD}` 且非空）"
    if bad:
        return "FAIL", note, summ + bad
    if tri_warn:
        # 未裁项不许静默 ⇒ 非阻断发现（本仓 WARN 语义：执行后有发现、不拦提交）
        return "WARN", note, summ + tri_warn
    return "PASS", note, summ
def check_adr(ctx):
    """P2-2: `adr/ADR-*.md` 必须有"考虑的替代方案"节（恰 1 个 · 非空 · 不留旧节名）。"""
    files = sorted(ADR_DIR.glob(ADR_GLOB))
    if not files:
        return "WARN", f"adr/{ADR_GLOB} 无匹配（本断言的登记依据）", []
    bad, summ = [], []
    for p in files:
        b, notes = validate_adr(_read_text(p))
        bad += [f"{p.name}: {x}" for x in b]
        if notes:
            summ.append(f"{p.stem}: {notes[0]}")
    detail = summ + bad
    n_bad_file = len({x.split(":", 1)[0] for x in bad})
    note = f"ADR {len(files)} 份 · 节名统一 `{ADR_CANON}` · 违规 {n_bad_file} 份"
    if not bad:
        note += f"（全部含 `{ADR_CANON}` 节且非空）"
    return ("FAIL" if bad else "PASS"), note, detail
DOC_STATUS_INV = ROOT / "inventory" / "doc-status.yaml"
DOC_STATUS_DIRS = ("spec", "adr")
DOC_STATUS_HEAD = 20          # ★ 射程**写死**：文档头 N 行（口径是判据的一部分，见 DEV-LOG-014 §90.4）
_DOC_FM_RE = re.compile(r"^status:\s*(.+)$")
_DOC_BODY_RE = re.compile(r"^>\s*\*\*状态\*\*:\s*(.+)$")
_DOC_NORM = {
    "草稿": "draft", "review 中": "in-review", "review": "in-review",
    "已验证": "verified", "已作废": "superseded",
    "待验收": "pending", "验收中": "in-review",
    "已验收": "accepted", "已验收通过": "accepted", "验收通过": "accepted",
}
def _doc_token(v):
    """状态 token：去粗体 / 括注后归一。

    ★ 与 `_ds()` 同族 —— 对**合法写法差异**宽容（`draft` / `草稿` / `**draft**` 是同一事实），
    只对**真的不等**严格（否则判据会红一片**假阳性**）。
    """
    t = _s(v).strip("*").strip()
    t = re.split(r"[（(—\s]", t)[0].strip("*:：")
    return _DOC_NORM.get(t.lower(), _DOC_NORM.get(t, t.lower()))
def _doc_raw_token(v):
    """状态 token 的**原文**（O-109）—— ★ 与 `_doc_token` 不同：**不做中文↔英文归一**。

    ★ 词表校验必须用**原文**：若拿归一后的 token 去比词表，`草稿` 会等于 `draft`
    `Review 中` 会等于 `in-review` ⇒ 明明是**词表外**的写法也会被判为合规（假绿）。
    ★ 归一只用于**两处比对**（fm ↔ 正文 是同一事实的两种合法写法）。
    """
    t = _s(v).strip("*").strip()
    return re.split(r"[（(—\s]", t)[0].strip("*:：")
def _parse_template_vocab(path):
    """从模板的「状态」行解析词表：以 `/` 拆分，每段取 `（` 之前的 token。

    ★ 例 `draft（草稿）/ in-review（Review 中）/ …` ⇒ `[draft, in-review, …]`；
    纯中文段（checklist 档 `待验收 / 验收中 / 已验收`）⇒ **中文 token 即词表项**。
    """
    for line in _read_text(path).splitlines():
        m = _DOC_BODY_RE.match(line)
        if not m:
            continue
        toks = []
        for seg in m.group(1).split("/"):
            tok = re.split(r"[（(]", seg.strip())[0].strip().strip("*:：")
            if tok:
                toks.append(tok)
        return toks
    return []
def _vocab_tokens(tokens):
    """词表 token 集（原文 + **归一形**）。

    ★ 词表侧补归一形（如 checklist 档的 `待验收` ⇒ 也认 `pending`），而**实例 token 侧不归一**
    （见 `_doc_raw_token`）—— 于是 fm 写 `accepted` / 正文写 `已验收` **都算合词表**，
    但**词表外的写法**（如 design 档写 `草稿`、写 `active`）仍会被抓出来。
    """
    out = set()
    for t in tokens:
        t = _s(t).strip()
        if t:
            out.add(t)
            out.add(_doc_token(t))
    return out
def load_kind_vocab(root=None, doc=None):
    """**纯函数**（O-109）：档位 → 词表 token 集 `{kind: set(tokens)}`。

    · **有模板的档**（design / checklist / adr）：真值在**模板链** ⇒ 解析
      `kind_source.by_kind[kind].ref` 指向的模板文件的「状态」行（★ **不把这些词抄进 yaml**）。
    · **无模板的档**（ledger / process）：本仓特有、**无模板** ⇒ 直接取 `by_kind[kind].vocab`。
    """
    root = Path(root) if root else ROOT
    if doc is None:
        try:
            import yaml
            doc = yaml.safe_load(_read_text(root / "inventory" / "doc-status.yaml")) or {}
        except Exception:
            return {}
    ks = doc.get("kind_source") if isinstance(doc, dict) else None
    by_kind = ks.get("by_kind") if isinstance(ks, dict) else None
    if not isinstance(by_kind, dict):
        return {}
    out = {}
    for kind, spec in by_kind.items():
        if not isinstance(spec, dict):
            continue
        src = _s(spec.get("from"))
        if src == "here":
            toks = [str(t) for t in (spec.get("vocab") or [])]
        elif src == "template":
            ref = _s(spec.get("ref"))
            toks = _parse_template_vocab(root / ref) if ref else []
        else:
            toks = []
        out[str(kind)] = _vocab_tokens(toks)
    return out
def _doc_kind(fname, kinds_reg):
    """判档（`kind_source.kind_rule`）：

    ① `adr/**` → adr；② 文件名含 `CHECKLIST` → checklist；
    ③ 命中 `kinds:` 登记 → 按登记；④ 其余 → design。
    """
    f_ = _s(fname)
    fl = f_.lower()
    base = fl.rsplit("/", 1)[-1]
    if fl.startswith("adr/") or "/adr/" in fl:
        return "adr"
    if "checklist" in base:
        return "checklist"
    if f_ in (kinds_reg or {}):
        return kinds_reg[f_]
    return "design"
def scan_doc_status(root=ROOT, dirs=DOC_STATUS_DIRS, head=DOC_STATUS_HEAD):
    """扫两处状态声明（★ **纯读，不判**）：返回 `(pairs, n_template, sites)`。

    · `pairs` 只收**两处都有**的**实例**文档 —— `*_TEMPLATE.md` 的正文行是**词表**而非实例值
      ⇒ **不入对**，只报数。
    · `sites` 收**每个位点**（fm / 正文各一条，含模板）—— O-109 的**词表校验按位点**判；
      模板位点由判据侧**跳过**（见 `validate_doc_status`）。

    ★ 射程**写死 `head` 行**：本仓实测，同一测量不写死会把「正文里描述**别的对象**的
    `**状态**:`」（如"某对象状态 = A/B/C"）也算进来 ⇒ 数从 **95 涨到 110**（§90.4）。
    """
    pairs, sites, n_tpl = [], [], 0
    for d in dirs:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(root).as_posix()
            is_tpl = p.name.upper().endswith("_TEMPLATE.MD")
            if is_tpl:
                n_tpl += 1
            fm = body = None
            for i, line in enumerate(_read_text(p).splitlines(), 1):
                if i > head:
                    break
                m = _DOC_FM_RE.match(line)
                if m:
                    if fm is None:
                        fm = m.group(1).strip()
                    sites.append({"file": rel, "slot": "fm",
                                  "value": m.group(1).strip(), "template": is_tpl})
                m2 = _DOC_BODY_RE.match(line)
                if m2:
                    if body is None:
                        body = m2.group(1).strip()
                    sites.append({"file": rel, "slot": "body",
                                  "value": m2.group(1).strip(), "template": is_tpl})
            if fm is not None and body is not None and not is_tpl:
                pairs.append({"file": rel, "fm": fm, "body": body})
    return pairs, n_tpl, sites
def validate_doc_status(pairs, doc, n_template=0, sites=None):
    """**纯函数**（O-108 / O-109）：① 两处状态声明（一个真值 fm + 一个派生位正文）；
    ② **词表符合性（按档）**。

    ★★ ① 为什么它**不是**"被 I-10 禁掉的对账"：**唯一写入点是 front matter**，正文行是**渲染**
    ⇒ 判据检的是「**派生是否过期**」，而**不是**「两处谁对」；★ **修法唯一**（改正文，不改 fm）。
    ⚠ 但**严格读 I-10，本面仍是两个位点** ⇒ 本表是**降格处置**、非完全实现
    （彻底消除 = `O-108` 案①，仍开着）—— 这句如实写在 `semantics.i10_note` 里，**不藏**。

    ★ ② O-109：**每个位点按其「档」**校验 token 是否在**该档词表**内（档 → 词表读取位点见
    `kind_source`）。★ token 取**原文**（`_doc_raw_token`，**不归一**）；★ 模板文件**跳过**
    （其「状态」行是**词表本身**）。`sites` 缺省时由 `pairs` 反推两个位点（兼容旧调用）。
    """
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["顶层不是映射（yaml 根应是 mapping）"], notes

    sem = doc.get("semantics")
    if not isinstance(sem, dict) or not (_s(sem.get("single_write")) and _s(sem.get("derived"))):
        bad.append("缺 `semantics.single_write` / `semantics.derived` ⇒ **本表会退化成一张豁免清单**："
                   "没声明「谁是真值、谁是派生」（而那恰是 I-10 要的那一句）")
    if not _ds(doc.get("updated")):
        bad.append("缺 `updated` ⇒ 没有读数日期（读者无法判断这是哪一天的树）")
    unv = doc.get("unverified")
    if not isinstance(unv, list) or not unv:
        bad.append("`unverified` 为空 ⇒ 本项自己未实测 / 未定的部分没登记")

    fr = doc.get("freeze") or []
    if not isinstance(fr, list):
        return bad + ["`freeze` 不是列表"], notes
    froze = {}
    for i, e in enumerate(fr):
        at = f"freeze[{i}]"
        if not isinstance(e, dict):
            bad.append(f"{at} 不是映射")
            continue
        f_ = _s(e.get("file"))
        if not f_ or not (ROOT / f_).exists():
            bad.append(f"{at} 的 `file`={f_!r} **不在仓里** ⇒ 登记腐化（文件已删 / 改名）")
            continue
        if not _s(e.get("why")):
            bad.append(f"{at} 缺 `why` ⇒ **冻结是一种豁免，必须写理由**"
                       f"（照 `inventory/ops.yaml` 的「冻结存量」）")
        froze[f_] = e

    eq, ne = 0, []
    for p in pairs:
        f_, a, b = _s(p.get("file")), _doc_token(p.get("fm")), _doc_token(p.get("body"))
        if a == b:
            eq += 1
        else:
            ne.append((f_, a, b))
    new_ne = [x for x in ne if x[0] not in froze]
    frz_ne = [x for x in ne if x[0] in froze]
    for f_, a, b in new_ne:
        bad.append(f"★ `{f_}` 两处状态声明**不等**：front matter `{a}` ↔ 正文 `{b}` ⇒ "
                   f"**判为「派生过期」**（唯一写入点是 fm ⇒ **改正文行**；"
                   f"**别**改 fm 去迁就正文）")

    seen = {_s(p.get("file")) for p in pairs}
    eq_files = {_s(p.get("file")) for p in pairs
                if _doc_token(p.get("fm")) == _doc_token(p.get("body"))}
    healed = sorted(f for f in froze if f in eq_files)
    gone = sorted(f for f in froze if f not in seen)
    if healed:
        bad.append(f"冻结清单里 {len(healed)} 项**已自愈**（两处已一致）："
                   f"{', '.join(healed[:5])}{' …' if len(healed) > 5 else ''} ⇒ **删掉它们**"
                   f"（留着会把本表烂成垃圾桶 —— 同 `secrets` 的「豁免未命中」防腐化）")
    if gone:
        bad.append(f"冻结清单里 {len(gone)} 项**已不再是「两处都有」**："
                   f"{', '.join(gone[:5])}{' …' if len(gone) > 5 else ''} ⇒ **删掉它们**"
                   f"（少了一处 ⇒ 该面已只剩一个位点）")

    # ── O-109 ②：词表符合性（**按档**判 token 是否在档内）──────────────────────
    v_note = ""
    ks = doc.get("kind_source")
    if not isinstance(ks, dict):
        bad.append("缺 `kind_source`（档 → 词表的**读取位点**，O-109）⇒ 判据无法按档校验 token"
                   "（`by_kind` / `kind_rule` / `kinds` 都无从取）")
    else:
        vocab = load_kind_vocab(doc=doc)
        reg = {_s(e.get("file")): _s(e.get("kind"))
               for e in (doc.get("kinds") or []) if isinstance(e, dict)}
        if sites is None:                       # 兼容旧调用：由 pairs 反推两个位点
            sites = []
            for p in pairs:
                f_ = _s(p.get("file"))
                sites.append({"file": f_, "slot": "fm", "value": p.get("fm"), "template": False})
                sites.append({"file": f_, "slot": "body", "value": p.get("body"), "template": False})
        n_ok = n_site = n_tpl_site = 0
        vbad = []
        for s in sites:
            if not isinstance(s, dict):
                continue
            f_ = _s(s.get("file"))
            if s.get("template") or f_.upper().endswith("_TEMPLATE.MD"):
                # ★★ 模板位点**不入分母**：其「状态」行是**词表本身**，判它 = 自己判自己。
                #   ⚠ 但**跳过 ≠ 判过且通过**（本仓头号形态：报数型假绿）⇒ 单独报数，不并进分子。
                n_tpl_site += 1
                continue
            n_site += 1
            kind = _doc_kind(f_, reg)
            toks = vocab.get(kind)
            tok = _doc_raw_token(s.get("value"))
            if toks is None:
                vbad.append((f_, _s(s.get("slot")), tok, kind, None))
            elif tok in toks:
                n_ok += 1
            else:
                vbad.append((f_, _s(s.get("slot")), tok, kind, sorted(toks)))
        for f_, slot, tok, kind, toks in vbad[:20]:
            if toks is None:
                bad.append(f"★ `{f_}`（{slot} 位点）token=`{tok}` 属档 `{kind}`，"
                           f"但 `kind_source.by_kind` **没有这一档** ⇒ 无词表可判（**词表缺档**）")
            else:
                bad.append(f"★ `{f_}`（{slot} 位点）token=`{tok}` **不在档 `{kind}` 的词表**"
                           f" {toks} 内 ⇒ 状态位写了**词表外**的值")
        if len(vbad) > 20:
            bad.append(f"…另有 {len(vbad) - 20} 处词表不符（略）")
        v_note = f" · 词表符合 {n_ok}/{n_site}"
        if n_tpl_site:
            v_note += f"（另有模板 {n_tpl_site} 位点**跳过、不入分母**——其「状态」行是词表本身）"

    notes.append(f"两处都有 {len(pairs)} · 一致 {eq} · 不等 {len(ne)}"
                 f"（冻结 {len(frz_ne)} / **新增 {len(new_ne)}**）"
                 f" · 模板 {n_template}（正文行是词表，不入对）{v_note}"
                 f" · 读数 {_ds(doc.get('updated'))}")
    return bad, notes
def check_doc_status(ctx=None, doc=None, pairs=None, sites=None):
    """O-108 / O-109: ① 同一文档两处状态声明（判「**派生是否过期**」）+ ② **词表符合性（按档）**。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 doc-status 断言", []
    if doc is None:
        if not DOC_STATUS_INV.exists():
            return "FAIL", "inventory/doc-status.yaml 缺失（本断言的登记依据）", []
        try:
            doc = yaml.safe_load(_read_text(DOC_STATUS_INV)) or {}
        except Exception as e:
            return "FAIL", f"inventory/doc-status.yaml 解析失败: {type(e).__name__}: {e}", []

    n_tpl = 0
    if pairs is None:
        pairs, n_tpl, sites = scan_doc_status()

    bad, notes = validate_doc_status(pairs, doc, n_template=n_tpl, sites=sites)
    if bad:
        return "FAIL", " · ".join(notes) if notes else "见明细", bad
    return "PASS", " · ".join(notes), []
MD_TABLES_INV = ROOT / "inventory" / "md-tables.yaml"
def _md_cols(line):
    """一行 markdown 表格的**格数**（**含空单元格**）。`\\|` 计为内容，不拆格。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    parts, cur, esc = [], "", False
    for ch in s:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return len(parts)
def _md_is_sep(line):
    """分隔行（`|---|:--:|`）：只由 `-`/`|`/`:`/空白组成且**含** `---`。"""
    s = line.strip()
    return "---" in s and all(c in "|-: \t" for c in s)
def _md_is_fence(line):
    """代码围栏开/关行（``` 或 ~~~ —— 后者是底稿勘误①补入的形态）。"""
    t = line.lstrip()
    return t.startswith("```") or t.startswith("~~~")
def md_table_scan(text):
    """**纯函数**：扫一篇 md 的表格 → `(violations, n_tables)`。

    violations = `[(行号(1 起), kind, 格数, 表头格数)]`，kind ∈ `{"sep", "row"}`。
    ★ 先验红点（A4）：往某数据行塞一个**未转义**竖线 ⇒ 本函数**必须**报出该行（见 `tests/`）。
    """
    lines = text.splitlines()
    out, i, in_code, n_tbl = [], 0, False, 0
    while i < len(lines):
        raw = lines[i]
        if _md_is_fence(raw):
            in_code = not in_code
            i += 1
            continue
        if in_code or raw[:4] == "    ":          # 围栏内 / GFM 缩进码块 ⇒ **不是**表格
            i += 1
            continue
        head = raw.strip()
        if not head.startswith("|") or _md_cols(head) == 0:
            i += 1
            continue
        if i + 1 >= len(lines) or not _md_is_sep(lines[i + 1].strip()):
            i += 1
            continue                              # 口径②：分隔行必须**紧邻**表头
        n_tbl += 1
        hc = _md_cols(head)
        sc = _md_cols(lines[i + 1].strip())
        if sc != hc:
            out.append((i + 2, "sep", sc, hc))
        k = i + 2
        while k < len(lines) and lines[k].strip().startswith("|"):
            s = lines[k].strip()
            if not _md_is_sep(s) and _md_cols(s) != hc:
                out.append((k + 1, "row", _md_cols(s), hc))
            k += 1
        i = k
    return out, n_tbl
def _md_line_hash(raw):
    """违规**原始行**（不含换行）的 sha256 前 16 位 —— 冻结的指纹键（**不用行号**，防漂移）。"""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
def check_md_tables(ctx):
    """A4: md 表格**列数守恒** —— 防「某行被拆错格」这类**静默错位**。

    ★ 判什么：同一张表里 **分隔行 / 数据行** 的格数 == **表头**格数；不符 ⇒ 该行**错位**。
    📊 报数：`扫描 N 篇 · 表 T 张 · 违规 V（冻结 F · **新增 D**）` —— 命中冻结的**不判 FAIL**。
    ⚠⚠ **不判什么**：不判表格**内容**对不对，也不判「文档该不该有表」。
      ★ 但 **`表 T 张` 为 0 ⇒ FAIL**（判据**没有对象** = 退化空判，本仓头号形态）——
      因此**「整篇没有表格 ⇒ 空集恒真」这类假绿在本项被显式堵住**（底稿 §假绿 第 1 条）。
    ⚠ 假绿（完整清单见 `dogfood-cards/land-a4-cell-safety.md`）：缩进码块 / `~~~` 围栏内的伪表格
      —— 已按 GFM 跳过（**跳过 ≠ 判过且通过**，故底稿要求它们显式登记）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 md 表格列数断言", []
    if not MD_TABLES_INV.exists():
        return "FAIL", "inventory/md-tables.yaml 缺失（本断言的**存量冻结**依据）", []
    try:
        inv = yaml.safe_load(_read_text(MD_TABLES_INV)) or {}
    except Exception as e:
        return "FAIL", f"inventory/md-tables.yaml 解析失败: {type(e).__name__}: {e}", []

    fr = inv.get("frozen")
    if not isinstance(fr, list):
        return "FAIL", "`frozen` 不是列表（本表退化成一张豁免清单？）", []
    inv_bad, frozen = [], {}
    for idx, e in enumerate(fr):
        at = f"frozen[{idx}]"
        if not isinstance(e, dict):
            inv_bad.append(f"{at} 不是映射")
            continue
        f_ = str(e.get("file") or "")
        lh = str(e.get("line_sha256") or "")
        if not f_ or not (ROOT / f_).exists():
            inv_bad.append(f"{at} 的 `file`={f_!r} **不在仓里** ⇒ 登记腐化（已删 / 改名 / 路径写错）")
            continue
        if not lh or not str(e.get("why") or ""):
            inv_bad.append(f"{at} 缺 `line_sha256` 或 `why` ⇒ **冻结是一种豁免，两样都要写**")
            continue
        frozen[(f_, lh)] = str(e.get("why"))

    n_md = n_tbl = 0
    new_v, hit = [], set()
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT)
        if any(s in rel.parts for s in DOCLINK_SKIP_PARTS):
            continue
        n_md += 1
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        vs, nt = md_table_scan("\n".join(lines))
        n_tbl += nt
        rp = rel.as_posix()
        for (ln, kind, dc, hc) in vs:
            lh = _md_line_hash(lines[ln - 1])
            if (rp, lh) in frozen:
                hit.add((rp, lh))
            else:
                new_v.append((rp, ln, kind, dc, hc))

    detail = []
    for (rp, ln, kind, dc, hc) in new_v[:20]:
        detail.append(f"★ {rp}:{ln} **{kind} 行 {dc} 格 ≠ 表头 {hc} 格** ⇒ 该行**错位**"
                      f"（单元格里的裸竖线多半没转义 —— 写成反斜杠 + 竖线）")
    if len(new_v) > 20:
        detail.append(f"…另有 {len(new_v) - 20} 处（略）")
    detail += inv_bad

    missing = [(f_, lh) for (f_, lh) in frozen if (f_, lh) not in hit]
    rot = sorted(f_ for (f_, _) in missing if not (ROOT / f_).exists())
    healed = sorted({f_ for (f_, _) in missing if (ROOT / f_).exists()})
    if rot:
        detail.append(f"冻结条目**指向已不存在的文件** {len(rot)} 条 ⇒ 删掉它们（登记腐化）: "
                      + ", ".join(rot[:6]) + (" …" if len(rot) > 6 else ""))
    if healed:
        detail.append(f"冻结条目**已失配** {len(healed)} 处（那行已改：修好了，或又改坏成别的指纹）"
                      f" ⇒ **请从 inventory/md-tables.yaml 删掉对应条目**（只减不增，防腐化）: "
                      + ", ".join(healed[:6]) + (" …" if len(healed) > 6 else ""))

    note = (f"扫描 {n_md} 篇 · 表 {n_tbl} 张 · 违规 {len(new_v) + len(hit)}"
            f"（冻结 {len(hit)} · **新增 {len(new_v)}**）")
    if rot or healed:
        note += f" · 冻结失配 {len(rot) + len(healed)}"
    if n_tbl == 0:
        return "FAIL", note + " · **表 0 张 ⇒ 判据无对象**（防退化空判）", detail
    fail = bool(new_v) or bool(inv_bad) or bool(rot) or bool(healed)
    return ("FAIL" if fail else "PASS"), note, detail
DET_NOISE_INV = ROOT / "inventory" / "determinism-noise.yaml"
_DET_SAMPLES = {
    "timestamp": ["2026-09-29T12:00:00", "1700000000"],
    "run-id": ["550e8400-e29b-41d4-a716-446655440000", "01ARZ3NDEKTSV4RRFFQ69G5FAV"],
    "absolute-path": ["/home/u/x", "/tmp/abc123", r"C:\Users\x"],
    "temp-dir": ["tmpabc123", "temp_xyz789"],
    "env-context": ["PWD=/work", "HOSTNAME=node1", "USER=me"],
}
def det_manifest_diff(a, b):
    """**纯函数**：两份 `{路径: sha256}` **逐字节**比对 → 差异清单（**不排序、不归一化换行符**）。

    ★ 先验红点（A5）：把**时间戳写进产物** ⇒ 两份哈希不等 ⇒ 本函数**必须**报出该路径（见 `tests/`）。
    ⚠ CRLF→LF 的归一化**只允许在生产端固化** —— 比对端妥协 = 把噪声洗成假绿（本仓已踩过一次）。
    """
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            out.append({"path": k, "a": a.get(k), "b": b.get(k)})
    return out
def det_scan_noise(text, entries):
    """**纯函数**：按噪声表扫一段文本 → 命中的噪声类 `id` 清单（供先验红 / 自检）。"""
    hits = []
    for e in entries:
        for p in (e.get("match") or []):
            try:
                if re.search(p, text):
                    hits.append(e["id"])
                    break
            except re.error:
                hits.append(str(e.get("id")) + "(正则非法)")
                break
    return hits
def _det_walk_na(node, path, bad):
    """递归找 `determinism: n/a` 声明 ⇒ 返回条数；缺 `reason` 的追加进 `bad`。"""
    n = 0
    if isinstance(node, dict):
        if str(node.get("determinism") or "").strip().lower() in ("n/a", "na"):
            n += 1
            if not str(node.get("reason") or "").strip():
                bad.append(f"{path}: `determinism: n/a` 缺 `reason` ⇒ 判违规（天然不可双跑者必须写理由，禁止静默跳过）")
        for k, v in node.items():
            n += _det_walk_na(v, f"{path}.{k}", bad)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            n += _det_walk_na(v, f"{path}[{i}]", bad)
    return n
def check_determinism(ctx):
    """A5: 确定性 —— 噪声口径**单一真值表**的健康 + **`n/a` 纪律**的机械义务。

    ★ 判什么：① 表结构（7 类噪声各带 `id/why/applies_to` · 行尾策略 · `updated` 读数日期）；
      ② `applies_to` 的**消费者 id 必须真实存在**（**孤儿消费者** = 无消费者的真值表会腐化，本仓纪律）；
      ③ **每类可机检噪声的正则必须真能匹配代表样本**（防表里塞一条永远匹配不上的坏正则而无人察觉）；
      ④ `determinism: n/a` 声明**必须带 `reason`**（`n/a` 不是静默通过的许可）。
    📊 报数：`噪声 N 类（可机检 M · 无字面模式 K）· 消费者 C 个 · 正则样本自证 P/Q · n/a 声明 A 条`。
    ⚠⚠ **不判什么**：本项**不**真的跑某条管线双跑（那要具体管线接入）——
      只钉住**口径单一真值 + 表的可用性**；`match` 为空的类（并发键序 / 文件系统元数据）
      **无字面模式** ⇒ **单列报数**（跳过 ≠ 判过且通过）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过确定性噪声表断言", []
    if not DET_NOISE_INV.exists():
        return "FAIL", "inventory/determinism-noise.yaml 缺失（本断言的**噪声口径单一真值**依据）", []
    try:
        tbl = yaml.safe_load(_read_text(DET_NOISE_INV)) or {}
    except Exception as e:
        return "FAIL", f"inventory/determinism-noise.yaml 解析失败: {type(e).__name__}: {e}", []

    detail = []
    if not str(tbl.get("updated") or ""):
        detail.append("表头缺 `updated`（读数日期）⇒ 增长型真值表必须带（否则无法判断读数时效）")
    le = tbl.get("line-ending") or {}
    if str(le.get("normalize_to") or "").upper() != "LF":
        detail.append("`line-ending.normalize_to` 必须是 `LF`（逐字节比对要求二进制一致；归一化在生产端固化）")
    if not str(le.get("why") or ""):
        detail.append("`line-ending` 缺 `why`（归一化/豁免必须写理由）")

    types = tbl.get("noise_types")
    if not isinstance(types, list) or not types:
        return "FAIL", "`noise_types` 缺失或为空（噪声表退化成空 ⇒ 恒真）", detail

    known = {c["id"] for c in CHECKS}
    consumers, machine, no_match, sample_ok, sample_tot = set(), 0, 0, 0, 0
    seen = set()
    for i, e in enumerate(types):
        at = f"noise_types[{i}]"
        if not isinstance(e, dict):
            detail.append(f"{at} 不是映射")
            continue
        tid = str(e.get("id") or "")
        if not tid:
            detail.append(f"{at} 缺 `id`")
        elif tid in seen:
            detail.append(f"{at} 的 `id`={tid!r} **重复**（同一噪声两个定义点）")
        seen.add(tid)
        if not str(e.get("why") or ""):
            detail.append(f"{at}({tid}) 缺 `why`（为什么排除它必须写）")
        ap = e.get("applies_to")
        if not isinstance(ap, list) or not ap:
            detail.append(f"{at}({tid}) 缺 `applies_to` ⇒ 消费者未声明（适用面必须**由表声明**）")
        else:
            for cid in ap:
                consumers.add(cid)
                if cid not in known:
                    detail.append(f"{at}({tid}) 的 `applies_to` 含 {cid!r} —— **不是真实断言 id**"
                                  f"（孤儿消费者 = 无消费者的真值表会腐化）")
        pats = e.get("match") or []
        if not pats:
            no_match += 1
            continue
        machine += 1
        for p in pats:
            try:
                re.compile(p)
            except re.error as ex:
                detail.append(f"{at}({tid}) 的正则 {p!r} **非法**: {ex}")
        samples = _DET_SAMPLES.get(tid)
        if not samples:
            detail.append(f"{at}({tid}) 有 `match` 但**无自证样本** ⇒ 无法证明该正则真能匹配"
                          f"（防塞一条永远匹配不上的正则）")
            continue
        for s in samples:
            sample_tot += 1
            if tid in det_scan_noise(s, [e]):
                sample_ok += 1
            else:
                detail.append(f"{at}({tid}) 正则**匹配不上代表样本** {s!r} ⇒ 该噪声类实际检不出（坏正则）")

    if not consumers:
        detail.append("`applies_to` 全空 ⇒ **无消费者的真值表**（会腐化：没人用就没人维护）")

    # n/a 纪律：扫 inventory/*.yaml 里声明的 `determinism: n/a`（目前应为 0 条 ⇒ **显式报出**，不静默）
    na_items, na_bad = 0, []
    for p in sorted((ROOT / "inventory").glob("*.yaml")):
        try:
            data = yaml.safe_load(_read_text(p)) or {}
        except Exception:
            continue
        na_items += _det_walk_na(data, p.name, na_bad)
    detail += na_bad

    note = (f"噪声 {len(types)} 类（可机检 {machine} · 无字面模式 {no_match}）"
            f" · 消费者 {len(consumers)} 个 · 正则样本自证 {sample_ok}/{sample_tot}"
            f" · `determinism: n/a` 声明 {na_items} 条（缺 reason {len(na_bad)} 条）"
            f" · updated={tbl.get('updated')}")
    if sample_tot == 0:
        return "FAIL", note + " · **样本自证 0 条 ⇒ 判据无对象**（防退化空判）", detail
    fail = bool(detail)
    return ("FAIL" if fail else "PASS"), note, detail
DERIVED_VIEW = ROOT / "ops" / "derived_view.py"
def check_derived_view(ctx):
    """A3: 跑 `ops/derived_view.py --check`（重渲染 vs 落档视图**逐字节**比对）—— **退出码 0 才算过**。

    子进程而非 import：视图渲染器是**独立可跑**的工具（人也会手跑 `--emit`），门禁只做**消费者**，
    复用它的三态退出码 ⇒ 口径**单一定义点**（不在这里再实现一遍比对 —— 那正是本仓头号形态）。
    """
    if not DERIVED_VIEW.is_file():
        return "WARN", f"{DERIVED_VIEW.name} 不存在（本断言的登记依据）", []
    try:
        p = subprocess.run([sys.executable, str(DERIVED_VIEW), "--check"], cwd=ROOT,
                           capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return "FAIL", "派生视图校验超时（>120s）⇒ 可能挂死", []
    out = _decode_out(p.stdout or b"") + _decode_out(p.stderr or b"")
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    msg = lines[-1] if lines else "（无输出）"
    rc = p.returncode
    if rc == 0:
        return "PASS", msg, lines[-5:]
    kind = "渲染链路故障(rc=2)" if rc == 2 else f"视图过期/漂移(rc={rc})"
    return "FAIL", f"{msg} · **{kind}**", lines[-8:]
EXEC_TRACE_SECTIONS = (
    ("[cmd] cmd=",               "命令执行记录（执行体外壳）"),
    ("[env] caught_at=launcher", "环境快照（执行体启动器 fork 前）"),
    ("[fs] diff_pointer=",       "文件系统写入集合（既有 find -newer 派生）"),
    ("[tool] chain=uncore",      "工具调用链（执行体内部 ⇒ 如实标不可核）"),
    ("[artifact] hashes=",       "产物哈希清单（主控侧回收时算）"),
)
def check_executor_trace(ctx):
    """A2: 执行侧过程留痕 —— 机制里五采集点齐备；落到 runDir 的留痕件**须含全部五段**。

    三部分（**判的东西不同，不许混**）：
      · **机制**：`agent-cli.ps1` 里 5 个采集点标记**逐个在位**，且不可核项**如实标 `uncore`**
        （出现 `chain=core` / `chain=verified` ⇒ **伪称执行体内部可核** ⇒ FAIL）。
      · **覆盖**：扫到的 runDir 若**有** `executor-trace.txt` ⇒ 内容**须含全部五段**
        （缺段 = 真缺陷 ⇒ FAIL）；**一个都没有** ⇒ **报数不入分母**（本件尚未经真派发 ⇒
        覆盖率是"没验到"，不是"验出问题" —— 不得把它算成通过，也不得算成失败）。
      · **锚定**（2026-09-30 补：A2 的 runtime 验收要求 = "留痕件齐 **+ 与产物哈希交叉锚定**"，
        上面两部分只判"五段在不在"、**不判锚**）：① `[artifact] hashes=` 必须是 `main-side`
        （执行体自报哈希 ⇒ 伪称可核 ⇒ FAIL）；② 留痕件 `ts=` 必须 == runDir 名（归属不符 ⇒ FAIL）；
        ③ 主控侧须有该 run 的哈希记录（`.agent-run.json` 的 `content_digest` 形如 `sha256:<64hex>`）
        —— **缺 ⇒ 只报数**（"没验到 ≠ 验出问题"）。
        ⚠ **不判什么**：**不判留痕内容真伪**（`[cmd]`/`[env]` 的值对不对）、**不判门的效力**。
    """
    detail = []
    if not AGENT_CLI.is_file():
        return "FAIL", "缺 agent-cli.ps1 ⇒ 留痕机制不可判（**不可判 ≠ 通过**）", []
    txt = _read_text(AGENT_CLI)
    mech_ok = 0
    for lit, why in EXEC_TRACE_SECTIONS:
        if lit in txt:
            mech_ok += 1
        else:
            detail.append(f"缺采集点标记 {lit!r} ⇒ {why} **没被采集**"
                          f"（假绿：看着有留痕，实际缺该维度）")
    for fake in ("chain=core", "chain=verified"):
        if fake in txt:
            detail.append(f"出现 {fake!r} ⇒ **伪称执行体内部可核**"
                          f"（工具调用链在执行体内部，executor 可篡改 / 漏报 / 伪造 ⇒ 只能 `uncore`）")

    # ── 覆盖：落到 runDir 的留痕件（存在则须齐段；一个都没有只报数）──────────────────
    sys.path.insert(0, str(ROOT / "ops"))
    try:
        import cluster
        roots, _note = cluster._agent_proj_roots()
        runs = cluster._chain_runs(roots)
    except Exception as e:
        st = "FAIL" if detail else "WARN"
        return st, (f"机制：采集点 {mech_ok}/{len(EXEC_TRACE_SECTIONS)}"
                    f" · cluster 不可用({type(e).__name__}) ⇒ 覆盖断言跳过"), detail
    n_run, n_ok, n_bad = 0, 0, []
    # 锚定段（2026-09-30）：① 执行体不得自报哈希 ② 留痕件必须属这一次 ③ 主控侧须有哈希记录。
    #   实测（2026-09-30 · 11 个含件 runDir）：ts 11/11 相符 · content_digest 11/11 规范 ·
    #   hashes 11/11 = main-side ⇒ **存量零违规**（先量后定档）⇒ ①② 判 FAIL；③ 只报数。
    n_tsok, n_self, n_tsbad, n_noanch = 0, [], [], []
    for ts, proj, run_dir in runs:
        f = run_dir / "executor-trace.txt"
        if not f.is_file():
            continue
        n_run += 1
        t = f.read_text(encoding="utf-8", errors="replace")
        miss = [lit for lit, _ in EXEC_TRACE_SECTIONS if lit not in t]
        if miss:
            n_bad.append(f"{proj}/{ts} 的 executor-trace.txt 缺段 {', '.join(miss)}")
        else:
            n_ok += 1
        lbl = f"{proj}/{ts}"
        ma = re.search(r"\[artifact\]\s+hashes=(\S+)", t)
        if ma and ma.group(1) != "main-side":
            n_self.append(f"{lbl} 的 executor-trace.txt 写 `[artifact] hashes={ma.group(1)}`"
                          f" ⇒ **执行体自报产物哈希**（执行体不可信 ⇒ 哈希只能由主控侧回收时算；"
                          f"伪称可核，与 `chain=uncore` 同族）")
        mt2 = re.search(r"#\s*executor-trace v1 ts=(\S+)", t)
        if mt2 and mt2.group(1) != ts:
            n_tsbad.append(f"{lbl} 的 executor-trace.txt 记 `ts={mt2.group(1)}` ≠ runDir 名"
                           f" ⇒ **归属不符**（留痕件不属于这一次；与 O-57「归属核对」同族）")
        else:
            n_tsok += 1
        try:
            _aj = json.loads((run_dir / ".agent-run.json").read_text(
                encoding="utf-8-sig", errors="replace"))
        except Exception:
            _aj = {}
        if not re.match(r"^sha256:[0-9a-f]{64}$", str(_aj.get("content_digest") or "")):
            n_noanch.append(lbl)
    detail += n_bad + n_self + n_tsbad
    note = (f"机制：采集点 {mech_ok}/{len(EXEC_TRACE_SECTIONS)}"
            f" · 覆盖：runDir 含该件 {n_run} 个（齐段 {n_ok}"
            + (f" · **缺段 {len(n_bad)}**" if n_bad else "") + "）"
            + f" · 锚定：ts 相符 {n_tsok} · 自报 {len(n_self)} · ts 不符 {len(n_tsbad)}"
              f" · 无锚记录 {len(n_noanch)}")
    if n_run == 0:
        note += " · 0 个 ⇒ 本件尚未经真派发，覆盖率**未验**（报数不入分母）"
    return ("FAIL" if detail else "PASS"), note, detail
