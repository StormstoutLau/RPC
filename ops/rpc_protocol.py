#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U-1/U-2/U-3/U-4/U-5 与 D7 判据库（review-p2-split 8B-1）。

从 `rpc_check.py` 抽出，**行为不变**；函数名/语义与门面重导出逐项一致。
"""
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
from rpc_common import (ROOT, SENSITIVITY_INV, SENSITIVITY_SECTIONS, SENSITIVITY_TIERS)

# ── D7-P1-1 (2026-09-26)：U-2 证据强度字典 + 方言映射表 ──────────────────────
# 目的：同一个符号（`L1` / `A` / `R1` / `E1`）在九个项目里指互不相干的东西；
#   「建映射、不迁移权威源」缺了它就只能靠人读文档记忆。而**映射表自己**最容易出的两种病是：
#     · **漏项**（实测：`b1b` 的对照表漏了摘要族 2 的第三行 `Cpp_Hub Tier 1/2`）⇒ 用 `coverage` 逐族点行数（**双向**：多也红）；
#     · **静默漂移**（源词表改了，映射表还是旧的）⇒ 用**源切片指纹**比对（这就是 D7-P1-1 退出判据的「源词表变了下游红」）。
# ★ 为什么必须**真读源文件**而不是只信登记：D7-P1-1 的教训②原文 =「映射表本身要能被门禁校验
#   （源词表变了下游要红）」。⚠ 但源在**别的仓库**（他方项目）⇒ 本仓**只能对账、不能强制**，
#   ⇒ 本断言把"源"定义成**本仓内的两个投影**（原文切片 + 出站版摘要），对它们做指纹；
#     他方源本身的变化**抓不到**，此事已在 `regeneration.why_not_automated` 如实登记（不假装能同步）。
# ★ 三处硬要求各有出处（§11.4 的三条教训）：
#   ① 命名空间前缀 = **必填字段**（不靠人自觉写前缀）⇒ `namespace` 必填且 ∈ 白名单；
#   ② 未定轴**不许硬塞**：`axis=not-assigned` 必须写 `axis_note`（说明它属于什么轴）；
#   ③ `axis=evidence-strength` 而逐级对应未知时，只允许写 `axis_value: undefined` + 理由
#      —— 堵住"看着像就填"（`b1b` 实测把 RPC 的 E1–E5 猜成了「官方>社区>实测>推断>无据」，输入里没有）。
# ── ★★ `U1#5`（2026-10-01 裁）：**命名空间注册表**（`inventory/namespaces.yaml` = 取值域的**唯一真值**）──
# 背景（**实测**）：U1 spec §1.3 曾把身份取值域指向 `dialect.yaml` 的 `namespaces`，而那份文件自称**生成物**
#   （"禁止手工编辑语义 —— 一律改源头 → 重抽"）⇒ ★★ **两条纪律互斗**：想新增一个 namespace **没有合法路径**
#   （改它 = 违反生成物纪律；走重抽 = 源里根本没有这一节）⇒ **取值域不该挂在派生视图上**。
# ⇒ 剥出成独立真值文件；`dialect`（U-2 映射行）与 `u1-identity`（U-1 身份声明）**都只读它**。
NAMESPACE_REG = ROOT / "inventory" / "namespaces.yaml"
NS_STATUS = ("active", "reserved", "retired")

# ★ 2026-10-13（`$PROJECTS` 数据化）：**项目注册表** —— `$PROJECTS` 的**唯一真值**
#   （同 `namespaces.yaml` 范式；设计见 docs/2026-10-13_项目注册表_PROJECTS数据化_设计与实施方案.md）。
PROJECTS_REG = ROOT / "inventory" / "projects.yaml"
PROJ_STATUS = ("active", "retired")


def namespace_index(reg):
    """注册表 → `(by_id, alias2id)`。**唯一**解析点（消费者不许各自再建一份表）。"""
    by_id, a2i = {}, {}
    for n in ((reg or {}).get("namespaces") or []):
        if not isinstance(n, dict) or not n.get("id"):
            continue
        by_id[n["id"]] = n
        for a in (n.get("aliases") or []):
            a2i[a] = n["id"]
    return by_id, a2i


def validate_namespaces(reg):
    """**纯函数** → `(bad, notes)`：注册表自洽（三条治理规则的**机判本体**）。

    ① `id` 非空；② `status` ∈ `NS_STATUS`；③ `since` 形如 `YYYY-MM-DD`；
    ④ ★ **同一个字符串不许同时属于两条**（id 或 alias）—— 这是**唯一**会判红的**冲突**（治理规则②）。
    """
    bad, notes = [], []
    if not isinstance(reg, dict):
        return ["namespaces.yaml 顶层不是映射（结构改了？）"], notes
    items = reg.get("namespaces") or []
    if not items:
        bad.append("`namespaces` 为空 ⇒ 身份取值域没有内容（判据会退化成空判）")
    seen = {}
    for i, n in enumerate(items, 1):
        if not isinstance(n, dict):
            bad.append(f"`namespaces[{i}]` 不是映射: {n!r}")
            continue
        nid = n.get("id")
        if not nid:
            bad.append(f"`namespaces[{i}]` 缺 `id`")
            continue
        if n.get("status") not in NS_STATUS:
            bad.append(f"`namespaces[{i}]`({nid}) status={n.get('status')!r} 不在闭集 {list(NS_STATUS)}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(n.get("since") or "")):
            bad.append(f"`namespaces[{i}]`({nid}) `since` 必须是 `YYYY-MM-DD`: {n.get('since')!r}")
        for token in [nid] + list(n.get("aliases") or []):
            if token in seen and seen[token] != nid:
                bad.append(f"★ **命名空间冲突**：{token!r} 同时属于 {seen[token]!r} 与 {nid!r} "
                           f"⇒ 同一个串不许出现在两条里（治理规则②）")
            seen.setdefault(token, nid)
    notes.append(f"命名空间 {len(items)} 条 · active "
                 f"{sum(1 for n in items if isinstance(n, dict) and n.get('status') == 'active')} · 字符串位点 {len(seen)}")
    return bad, notes


def namespace_domain_error(ns, reg):
    """★★ `U1#5` 判据：一个 `namespace` 取值是否合法 ⇒ 错误串，或 `None`（合法）。

    ★ 规则比"在不在名单里"**严一档**：必须是 **canonical `id` 且 `status: active`**。
      · 写 **alias**（如 `Open_Data`）⇒ **拒**，并提示应改写成 canonical id ——
        身份 = 对 `["<ns>","<id>","<ver>"]` 的哈希，**吃的是原字符串** ⇒ 放行别名会让同一产物**有两个身份**；
      · `retired` ⇒ **拒**（历史身份仍可复算，但**新声明不许用**，治理规则③）；
      · 未登记 ⇒ **拒**（fail-closed）。
    ⚠ 匹配一律**精确**（不做大小写 / 分隔符归一）—— 归一化会把"两个身份"藏起来。
    """
    by_id, a2i = namespace_index(reg)
    if ns in by_id:
        st = by_id[ns].get("status")
        if st == "active":
            return None
        return f"`namespace`={ns!r} 的状态是 `{st}` ⇒ 不得用于**新**声明（治理规则③：退役不删，但不许新用）"
    if ns in a2i:
        return (f"`namespace`={ns!r} 是 **alias**，身份里必须写 canonical id `{a2i[ns]!r}` —— "
                f"⚠ 别名若放行，同一个产物会有**两个身份**（哈希吃原字符串）")
    return f"`namespace`={ns!r} **未登记** ⇒ 拒（fail-closed；要新增须先写进 `inventory/namespaces.yaml`）"


def namespace_for_project(project, reg):
    """`项目名 → canonical namespace`（**消费侧**用，如 `--invalidate` 的 affected 归集）。

    ⚠ 只在**有登记时**才换算（id 或 alias 精确命中）；**未登记 ⇒ 原样返回**（与旧行为一致 —— 不猜）。
    """
    by_id, a2i = namespace_index(reg)
    if project in by_id:
        return project
    return a2i.get(project, project)


# ── ★★ `O-162`（2026-10-20 裁「坐标语义进注册表字段」）：`identifier` / `version` 的**语义**登记 ──
# 缺口（`U1#5` 的邻居格）：取值域**已**进注册表，而**语义**此前只有 spec §1.3 的 prose 一张表
#   ⇒ "每处各自拼三元组"，且**新增一个 namespace 时没人逼它定语义**。
# 处置 = 注册表条目加 `identifier_rule` / `version_rule`（**闭集**，真值只在那一处）⇒ 门禁可判。
# ⚠ 如实标注射程：判的是**登记完整性**（有没有登记 · 值在不在闭集），**不是语义正确性** ——
#   后者无法机判，不许把本判据读成"坐标语义已验证"。
NS_ID_RULES = ("relpath", "biz-key", "composite", "unset")
NS_VER_RULES = ("semver-0.0.0-fallback", "unset")
NS_RULE_UNSET = "unset"


def validate_namespace_coords(reg, used_ns=()):
    """**纯函数** → `(bad, notes)`：每条 namespace 的**坐标语义**（`O-162` ② 的机判本体）。

    判四条（**只管 `active`** —— 退役/保留条目只解释历史身份，不强制）：
      ① `identifier_rule` / `version_rule` **必须登记**（缺 ⇒ 红，fail-closed）；
      ② 取值必须落在闭集 `NS_ID_RULES` / `NS_VER_RULES` 里（值域封闭）；
      ③ 登记成 `unset`（含义 = "尚无产物 ⇒ 坐标未定"）⇒ **必须**给 `coord_note` 说明
         —— 否则"没定"是**无声的**（本仓头号形态：判不了 ≠ 没事）；
      ④ ★★ 若该 namespace **已在用**（`used_ns` = `inventory/*.yaml` 里真实 `u1:` 声明的 namespace 集合）
         而坐标仍登记成 `unset` ⇒ **红**（"**用了却没定语义**" —— 这正是本判据存在的理由）。
    `notes` 里**报数**「坐标未定 N 条」（可见，不静默）。
    """
    bad, notes = [], []
    items = (reg or {}).get("namespaces") if isinstance(reg, dict) else None
    used = set(used_ns or ())
    n_active = n_unset = 0
    for i, n in enumerate(items or [], 1):
        if not isinstance(n, dict) or not n.get("id"):
            continue
        if n.get("status") != "active":
            continue
        nid = n["id"]
        n_active += 1
        ir, vr = n.get("identifier_rule"), n.get("version_rule")
        if ir not in NS_ID_RULES:
            bad.append(f"`namespaces[{i}]`({nid}) 的 `identifier_rule`={ir!r} 缺失或不在闭集 "
                       f"{list(NS_ID_RULES)} ⇒ `O-162`：坐标语义必须登记（真值只在注册表，别处不再各拼一份）")
        if vr not in NS_VER_RULES:
            bad.append(f"`namespaces[{i}]`({nid}) 的 `version_rule`={vr!r} 缺失或不在闭集 {list(NS_VER_RULES)}")
        if NS_RULE_UNSET in (ir, vr):
            n_unset += 1
            if not str(n.get("coord_note") or "").strip():
                bad.append(f"`namespaces[{i}]`({nid}) 的坐标登记成 `{NS_RULE_UNSET}` ⇒ **必须**写 `coord_note`"
                           f"（说明「尚无产物 / 何时补」）—— 否则「没定」是无声的")
            if nid in used:
                bad.append(f"`namespaces[{i}]`({nid}) **已在用**（`inventory/*.yaml` 有它的 `u1:` 声明）"
                           f"却把坐标登记成 `{NS_RULE_UNSET}` ⇒ **用了却没定语义**（`O-162` ④）")
    notes.append(f"坐标语义：active {n_active} 条 · `{NS_RULE_UNSET}`（坐标未定）{n_unset} 条")
    return bad, notes


def validate_projects(reg):
    """**纯函数** → `(bad, notes)`：项目注册表自洽（治理三规则的**机判本体**，2026-10-13）。

    ① `id` 非空；② `status` ∈ `PROJ_STATUS`；③ `since` 形如 `YYYY-MM-DD`；
    ④ `root` **非空字符串**（★ **只判形态，不判存在性** —— `F:`/`E:` 等外盘可能离线，
       判存在性会让门禁**常红（假红）**）；
    ⑤ ★ **同一个字符串不许同时属于两条**（`id` 或 `alias`）—— 唯一会判红的**冲突**；
    ⑥ ★★ **`id` 不许重复**（2026-10-13 · 本仓测试当场抓到）：两条同 `id` 时，
       `seen[token] != pid` 恒为 False ⇒ **静默通过** ⇒ `projects_index` 会**静默取后一条**
       （一条 = 一个项目 ⇒ 重复必须红）。⚠ 与 `namespaces` 的 ⑤ 同族（那边也有此漏，本批**未动**它）。
    """
    bad, notes = [], []
    if not isinstance(reg, dict):
        return ["projects.yaml 顶层不是映射（结构改了？）"], notes
    items = reg.get("projects") or []
    if not items:
        bad.append("`projects` 为空 ⇒ `$PROJECTS` 没有内容（判据会退化成空判）")
    seen, ids = {}, set()
    for i, n in enumerate(items, 1):
        if not isinstance(n, dict):
            bad.append(f"`projects[{i}]` 不是映射: {n!r}")
            continue
        pid = n.get("id")
        if not pid:
            bad.append(f"`projects[{i}]` 缺 `id`")
            continue
        if pid in ids:
            bad.append(f"★ **项目名冲突**：{pid!r} 出现了两条（同一串不许属两条 · 治理规则②；"
                       f"重复会让 `projects_index` 静默取后一条）")
        ids.add(pid)
        if n.get("status") not in PROJ_STATUS:
            bad.append(f"`projects[{i}]`({pid}) status={n.get('status')!r} 不在闭集 {list(PROJ_STATUS)}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(n.get("since") or "")):
            bad.append(f"`projects[{i}]`({pid}) `since` 必须是 `YYYY-MM-DD`: {n.get('since')!r}")
        if not (isinstance(n.get("root"), str) and n.get("root").strip()):
            bad.append(f"`projects[{i}]`({pid}) `root` 必须是非空字符串: {n.get('root')!r}")
        for token in [pid] + list(n.get("aliases") or []):
            if token in seen and seen[token] != pid:
                bad.append(f"★ **项目名冲突**：{token!r} 同时属于 {seen[token]!r} 与 {pid!r} "
                           f"⇒ 同一个串不许出现在两条里（治理规则②）")
            seen.setdefault(token, pid)
    notes.append(f"项目 {len(items)} 条 · active "
                 f"{sum(1 for n in items if isinstance(n, dict) and n.get('status') == 'active')} · 字符串位点 {len(seen)}")
    return bad, notes


def projects_index(reg):
    """**消费面**：`{id: root}` —— 只收 `status: active`（外壳载入 / `--list-projects` 用）。

    ⚠ 只收 `active`：`retired` 仍留登记（历史可解释），但**不再派发**（治理规则③）。
    """
    out = {}
    for n in (reg.get("projects") or []):
        if isinstance(n, dict) and n.get("id") and n.get("status") == "active":
            out[str(n["id"])] = str(n.get("root") or "")
    return out


def check_projects(ctx):
    """**项目注册表**（`$PROJECTS` 的真值）自洽 —— 2026-10-13 `$PROJECTS` 数据化。

    判什么：① 注册表可解析且 `projects` 非空（防空判）；② 自洽（`validate_projects`）。
    ★ **不判** `root` 存在性（外盘可能离线 ⇒ 判存在性会**假红**；同 `namespaces` 只判形态）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 projects 断言", []
    if not PROJECTS_REG.is_file():
        return "FAIL", "inventory/projects.yaml 缺失（`$PROJECTS` 起 2026-10-13 它是唯一真值）", []
    try:
        reg = yaml.safe_load(PROJECTS_REG.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"projects.yaml 解析失败: {type(e).__name__}: {e}", []
    bad, notes = validate_projects(reg)
    if bad:
        return "FAIL", "项目注册表自身不自洽（见明细）", bad
    return "PASS", " · ".join(notes), []


DIALECT_INV = ROOT / "inventory" / "dialect.yaml"
DIALECT_AXES = {"evidence-strength", "not-assigned"}
DIALECT_RELATIONS = {"独占", "冲突", "同名不同义-族内"}
DIALECT_UNKNOWN = "undefined"


def _dialect_norm(text):
    """与指纹登记**同口径**：CRLF→LF、逐行去尾空白、行尾统一 `\\n`。

    ⚠ 必须与写指纹时用的口径逐字一致 —— 差一个 `\\r` 就会让**每一次**跑都红（假红），
    而假红的下场是"把判据关掉"（比不判更坏）。
    """
    return "\n".join(l.rstrip() for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def _dialect_slice(text, start_marker, next_prefix):
    """取"从首个 `start_marker` 行 到 下一个 `next_prefix` 行（不含）"的切片；找不到 ⇒ None。"""
    lines = _dialect_norm(text).split("\n")
    i = next((k for k, l in enumerate(lines) if l.startswith(start_marker)), None)
    if i is None:
        return None
    j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith(next_prefix)), len(lines))
    return "\n".join(lines[i:j])


def validate_dialect(inv, read_text_fn, exists_fn, reg):
    """**纯函数** → `(bad, notes)`（离线可正反夹测，见 tests/test_rpc_check_dialect.py）。

    规则：① 轴是封闭枚举；★★ **命名空间白名单来自 `reg`（注册表），不再来自本文件**
             —— `U1#5`（2026-10-01）：取值域的真值唯一在 `inventory/namespaces.yaml`，本文件只是消费者；
          ② 每行映射的前缀必填；③ `coverage` 与实际行数**双向**相等（漏一行、多一行都红）；
          ④ `sources` 的 path 必须存在，且**复算指纹**必须与登记一致（源变 ⇒ 下游红）。
    """
    bad, notes = [], []
    if not isinstance(inv, dict):
        return ["dialect.yaml 顶层不是映射（结构改了？）"], notes

    # ── ① 轴 ────────────────────────────────────────────────────────────
    axis = inv.get("axis") or {}
    axis_id = axis.get("id")
    values = axis.get("values") or []
    vids = [v.get("id") for v in values if isinstance(v, dict)]
    if not axis_id:
        bad.append("`axis.id` 缺失")
    if not values:
        bad.append("`axis.values` 为空 ⇒ 字典没有轴（“单一轴字典”名不副实）")
    if len(vids) != len(set(vids)):
        bad.append(f"`axis.values` 的 id 有重复: {vids}")
    for v in values:
        if not (isinstance(v, dict) and v.get("id") and v.get("label")):
            bad.append(f"`axis.values` 有条目缺 id/label: {v!r}")

    # ── ② 命名空间白名单（前缀必填的值域）—— ★ `U1#5`：**从注册表读**，不从本文件读 ──
    #    ⚠ 只认 `status: active` 的 **canonical id**（alias 不许写进映射行 —— 同身份那条理由：
    #      "同一事实两处表达"的代价最大的一种就是别名放行 ⇒ 一个东西两个名字）。
    _by_id, _a2i = namespace_index(reg)
    ns_ids = [k for k, v in _by_id.items() if (v or {}).get("status") == "active"]
    if not ns_ids:
        bad.append("命名空间注册表 `inventory/namespaces.yaml` 里**没有 active 条目** ⇒ 「前缀必填」没有值域可查")

    # ── ③ 映射表 ────────────────────────────────────────────────────────
    mapping = inv.get("mapping") or []
    if not mapping:
        bad.append("`mapping` 为空 ⇒ 映射表不存在")
    seen_pair = {}
    for i, row in enumerate(mapping, 1):
        if not isinstance(row, dict):
            bad.append(f"`mapping[{i}]` 不是映射")
            continue
        ns, sym = row.get("namespace"), row.get("symbol")
        if not ns:
            bad.append(f"`mapping[{i}]` 缺 `namespace`（★ 前缀是**必填字段**，§11.4 教训①）")
        elif ns_ids and ns not in ns_ids:
            bad.append(f"`mapping[{i}]` 的 namespace={ns!r} **不在命名空间注册表"
                       f"（`inventory/namespaces.yaml`）的 active 白名单**里")
        if not sym:
            bad.append(f"`mapping[{i}]` 缺 `symbol`")
        if (ns, sym) in seen_pair:
            bad.append(f"`mapping[{i}]` ({ns}, {sym}) 与第 {seen_pair[(ns, sym)]} 行重复 "
                       f"⇒ 同一符号同一出处两处定义（本仓头号形态）")
        else:
            seen_pair[(ns, sym)] = i
        if row.get("relation") not in DIALECT_RELATIONS:
            bad.append(f"`mapping[{i}]` relation={row.get('relation')!r} 不在封闭枚举 {sorted(DIALECT_RELATIONS)}")
        ax = row.get("axis")
        if ax not in DIALECT_AXES:
            bad.append(f"`mapping[{i}]` axis={ax!r} 不在封闭枚举 {sorted(DIALECT_AXES)}")
            continue
        av, note = row.get("axis_value"), row.get("axis_note")
        if ax == "evidence-strength":
            if not av:
                bad.append(f"`mapping[{i}]` axis=evidence-strength 但缺 `axis_value`")
            elif av == DIALECT_UNKNOWN:
                if not note:
                    bad.append(f"`mapping[{i}]` axis_value=undefined **必须**写 `axis_note` 说明为何不可判 "
                               f"（不许“看着像就填”）")
            elif vids and av not in vids:
                bad.append(f"`mapping[{i}]` axis_value={av!r} 不在 `axis.values` 的 id 里")
        else:                                    # not-assigned
            if av not in (None, ""):
                bad.append(f"`mapping[{i}]` axis=not-assigned 却给了 `axis_value={av!r}` "
                           f"⇒ 既说不属此轴、又给了取值（自相矛盾）")
            if not note:
                bad.append(f"`mapping[{i}]` axis=not-assigned **必须**写 `axis_note`（说明它属于什么轴）")

    # ── ④ 覆盖对账（**双向**：漏行/多行都红）────────────────────────────
    cov = inv.get("coverage") or []
    if not cov:
        bad.append("`coverage` 缺失 ⇒ 没有“有没有漏项”的判据（`b1b` 漏过一行，正因缺这一段）")
    actual = {}
    for row in mapping:
        if isinstance(row, dict) and row.get("family"):
            actual[row["family"]] = actual.get(row["family"], 0) + 1
    for c in cov:
        if not isinstance(c, dict):
            bad.append(f"`coverage` 有条目不是映射: {c!r}")
            continue
        fam, want = c.get("family"), c.get("expected_rows")
        got = actual.get(fam, 0)
        if got != want:
            bad.append(f"`coverage` 不符: family={fam!r} 期望 {want} 行, 实际 {got} 行 "
                       f"⇒ 映射表**漏项**或 `coverage` 过期（两者必改其一）")
    for fam in sorted(set(actual) - {c.get("family") for c in cov if isinstance(c, dict)}):
        bad.append(f"`mapping` 里的 family={fam!r} 未在 `coverage` 登记 ⇒ 新增族没报行数")
    notes.append(f"映射 {len(mapping)} 行 / {len(actual)} 族")

    # ── ⑤ 冲突清单 / 不可判项（各自非空）─────────────────────────────────
    for key, need in (("conflicts", ("symbol", "sides", "why")), ("undecidable", ("item", "missing"))):
        items = inv.get(key) or []
        if not items:
            bad.append(f"`{key}` 为空 —— 这两节是“不许硬塞 / 不许猜”的落地处，空 = 没做")
            continue
        for i, it in enumerate(items, 1):
            if not isinstance(it, dict) or any(not it.get(f) for f in need):
                bad.append(f"`{key}[{i}]` 缺字段（须全有 {list(need)}）: {it!r}")
    notes.append(f"冲突 {len(inv.get('conflicts') or [])} 条 · 不可判 {len(inv.get('undecidable') or [])} 条")

    # ── ⑥ 源词表指纹（D7-P1-1 退出判据的「源词表变了下游红」）────────────
    srcs = inv.get("sources") or []
    if not srcs:
        bad.append("`sources` 为空 ⇒ 没有“源词表变了要红”的对象")
    n_ok = 0
    for s in srcs:
        if not isinstance(s, dict):
            bad.append(f"`sources` 有条目不是映射: {s!r}")
            continue
        p, want = s.get("path"), s.get("sha256")
        tag = s.get("id") or p
        if not p or not want:
            bad.append(f"`sources[{tag}]` 缺 path 或 sha256")
            continue
        if not exists_fn(p):
            bad.append(f"`sources[{tag}]` 的 path 不存在: {p} ⇒ 登记指向空物")
            continue
        try:
            text = read_text_fn(p)
        except Exception as e:                      # ⚠ 不静默跳过：读不到就是"判不了"，必须显式报
            bad.append(f"`sources[{tag}]` 读取失败（{type(e).__name__}）⇒ 本项**不可判**，"
                       f"不得当作通过: {p}")
            continue
        if s.get("whole_file"):
            got = hashlib.sha256(_dialect_norm(text).encode("utf-8")).hexdigest()
        else:
            sl = _dialect_slice(text, s.get("slice_start") or "", s.get("slice_next_prefix") or "# ")
            if sl is None:
                bad.append(f"`sources[{tag}]` 切片起点 {s.get('slice_start')!r} 在 {p} 里找不到 "
                           f"⇒ 结构改了（判据前提失效）")
                continue
            got = hashlib.sha256(sl.encode("utf-8")).hexdigest()
        if got != want:
            bad.append(f"`sources[{tag}]` **指纹不符** ⇒ 源词表变了下游没重抽。"
                       f"登记 {want[:12]}… / 实算 {got[:12]}… ⇒ 重抽映射表并更新 `sources[].sha256`")
        else:
            n_ok += 1
    notes.append(f"源 {len(srcs)} 处 · 指纹一致 {n_ok}")
    return bad, notes


def check_dialect(ctx):
    """D7-P1-1: U-2 证据强度字典 + 方言映射表（`inventory/dialect.yaml`）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 dialect 字典断言", []
    if not DIALECT_INV.exists():
        return "FAIL", "inventory/dialect.yaml 缺失（本断言的登记依据）", []
    try:
        inv = yaml.safe_load(DIALECT_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/dialect.yaml 解析失败: {type(e).__name__}: {e}", []

    # ★ `U1#5`（2026-10-01）：白名单改从**注册表**读 —— 它是取值域的真值，本文件只是消费者。
    #   ⚠ 注册表缺失/不可解析 ⇒ **FAIL**（不是跳过）：白名单是本条判据的**值域**，没有它映射行无从判。
    if not NAMESPACE_REG.is_file():
        return "FAIL", "inventory/namespaces.yaml 缺失（`U1#5` 起它是命名空间取值域的唯一真值）", []
    try:
        reg = yaml.safe_load(NAMESPACE_REG.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/namespaces.yaml 解析失败: {type(e).__name__}: {e}", []
    ns_bad, ns_notes = validate_namespaces(reg)
    if ns_bad:
        return "FAIL", "命名空间注册表自身不自洽（见明细）", ns_bad

    def _read(rel):
        return (ROOT / rel).read_text(encoding="utf-8", errors="replace")

    bad, notes = validate_dialect(inv, _read, lambda rel: (ROOT / rel).exists(), reg)
    return ("FAIL" if bad else "PASS"), " · ".join(notes + ns_notes), bad


# ── D7-P1-3 (2026-09-26)：U-3 依赖边格式（`inventory/edges.yaml`）────────────
# 目的：统一基座的**边**要有**唯一形状**（`src`/`dst`/`kind`/`provenance`），
#   而最该被机器盯住的是那个**最容易缺**的字段 —— Ontoly RFC-0002 的 invariant 原文：
#     **"Edges SHOULD contain provenance. Edges without provenance are invalid."**
# ★ `provenance` 缺 ⇒ 边**无效**：这是 D7-P1-3 退出判据里"可机判"那一半。
# ★ 本仓当前是**产出方**（不是消费方）⇒ 无效边的处置**不是"丢弃继续"**，而是 **FAIL** ——
#   依据 **D-26**「H-3 的降级必须有机判呈现位、**禁止静默 skip**」：
#   丢掉一条边 = 把一次"判不了"悄悄变成"没有这条边"。（消费方那一侧才走 H-3 强制降级。）
# ★ **空清单 ≠ 没事**：`edges` 为空时**不 FAIL**，但**必须**给出 `empty_reason`，
#   并在 note 里**显式报"0 条"** —— 否则"没有对象"会被读成"一切正常"（本仓头号形态）。
# ★ `src`/`dst` 必须是 **U-1 产物身份**形态 ⇒ 本断言把 U-1 与 U-3 **咬合**在一起：
#   写一条边就得先有一个合规身份（这正是 `edges.yaml` 现在为空的原因，见其 `empty_reason`）。
EDGES_INV = ROOT / "inventory" / "edges.yaml"
EDGE_REQUIRED = ("src", "dst", "kind", "provenance")
# ── U-1 产物身份：**本仓唯一真值实现**（D-23 / D-25 · `spec/d6-agent-standard/U1-ARTIFACT-IDENTITY.md`）──
# ★ 为什么实现放这里：此前门禁 `edges` 用**正则**判 U-1 形态，而规范里"取值维度 / 截断 / 前缀 / 算法"
#   是**四项取值** ⇒ 两处各写一份 ⇒ 必然漂移（本仓头号形态："同一事实两个定义点"）。
#   ⇒ 实现与校验**同源**：`edges` 改调 `u1_parse`，`u1-identity` 用它**复算**。
U1_ALGO = "sha256"
U1_TRUNC = 32                 # 128 bit。★ **2026-09-26 Scott 裁定：改 `32`（对齐蓝本）** —— 原为 16。
                              #   `16` 的原理由（"既有 7 处里 `factor_pipeline` 同为 16 ⇒ 兼容面最大"）
                              #   **已被两轮自查实测推翻**（见 O-84）：
                              #     · `factor_pipeline` 实测（口径化后 = **21 行**，见 `ops/id_site_census.py`）
                              #       截断**项目内并存 5 种**
                              #       （`[:8]` / `[:12]` / `[:16]` / `[:32]` / md5 **全 64**）⇒ **并非"同为 16"**；
                              #     · `Auto_Prover` 的 `verdict_id` 根本不是 16（= `v_` + md5 + **12**）
                              #       ⇒ 原依据的另一半是**把 `case_id` 与 `verdict_id` 读成了一个字段**。
                              #   ⇒ 剩下的唯一硬依据是**蓝本**：D-23 明裁"蓝本取 `Open_Data`"，而它是 **`[:32]`**
                              #     （`collectors/{blackmarble,portwatch,eia}/collector.py` 的
                              #      `sha256("ns|d1|d2")[:32]` —— 3 处逐行核过）
                              #     ⇒ "与权威蓝本一致"优先于"与某个**待迁移**的下游项目部分一致"。
                              #   ⚠ 代价（已履行）：本仓已落地的 2 个 `u1:` 声明**一并重算** ——
                              #     D-23 的"不追溯重算"只针对**历史产物**；这 2 个是**规范自身的元数据**，
                              #     且**从未被任何外部消费** ⇒ 重算无副作用（若已外发过，就必须另立兼容路径）。
                              #   128 bit ⇒ 碰撞阈值 ≈ 2⁶⁴，比 16（≈ 2³²）**强**，代价只是 ID 长一倍。
U1_PREFIX = f"u1:{U1_ALGO}:{U1_TRUNC}"
U1_DEFAULT_VERSION = "0.0.0"  # 无版本者（spec §1.3）
# ── ★★ `U1#8`（2026-09-30 裁 / `O-123`）：**截断长度变更的映射表**（唯一真值源 = 本表；规范只指向它，不复述）──
# 背景：上面对 `U1_TRUNC` 的注释自己写着「这 2 个身份**从未被任何外部消费** ⇒ 重算无副作用
#   （**若已外发过，就必须另立兼容路径**）」—— **本表就是那条兼容路径**（把"永不改长度"这条口头纪律换成判据）。
# ⚠ **只登记真实发生过的那一次**（`16 → 32`，`O-84`，2026-09-26）；**不预置没发生的行**（预置 = 编历史）。
U1_TRUNC_MAP = (
    {"from_length": 16, "to_length": U1_TRUNC, "algorithm": U1_ALGO, "effective_date": "2026-09-26"},
)
# "旧代"标注的**字段名唯一字面定义点**（声明里带它 = 承认这是历史长度的身份）
U1_LEGACY_MARK = "legacy"


def _u1_prefix(trunc):
    """`u1:<algo>:<trunc>` —— **唯一**拼前缀的地方（历史长度复算也要用同一处拼法）。"""
    return f"u1:{U1_ALGO}:{trunc}"


def u1_header_line(trunc=U1_TRUNC):
    """`# u1:<algo>:<trunc>` —— §1.4 的**头部注释行**（**唯一**拼它的地方）。

    ★ 2026-10-19 新增（`U1#7` 裁定落地）：`ops/cluster.py` 的 inbox 清单要写这条**文件级声明行**
      （声明"本清单带 u1 轨"），而算法 / 截断**只在本文件定义一次** ⇒ 拼法也必须只有一处
      （消费方自己拼 = 造出第二个定义点）。⚠ `trunc` 参数只为历史长度复用，日常不传。
    """
    return "# " + _u1_prefix(trunc)


def u1_canonical_bytes(namespace, identifier, version=U1_DEFAULT_VERSION) -> bytes:
    """U-1 的**哈希输入**：`["<ns>","<id>","<ver>"]` 的 RFC 8785 规范化 JSON 的 UTF-8 字节序列。

    ⚠⚠ **等价性边界（只在这一形状上声称，别外推）**：本实现用
      `json.dumps(..., ensure_ascii=False, separators=(',',':'))`，它与 RFC 8785（JCS）
      在本规范的输入形状 **`[str, str, str]`** 上等价：
        ① 无空白（`separators` 收紧）；
        ② 字符串转义只用 `\\b \\t \\n \\f \\r \\" \\\\` 与 `\\uXXXX`（**小写** hex）—— 这正是 JCS 对**字符串**的规定。
      ⚠ 本实现**不涉及** JCS 里更复杂的部分（数字的 ECMAScript 序列化、键的 UTF-16 排序）
        ⇒ 那两项**既不实现、也不声称**（输入已被限定为**字符串数组** ⇒ 用不到）。
      ⇒ 若将来有人把数字 / 字典塞进来，**先读这段**：那时它就不再是 JCS 了。
    """
    arr = [str(namespace), str(identifier), str(version)]
    return json.dumps(arr, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def u1_identity(namespace, identifier, version=U1_DEFAULT_VERSION, trunc=U1_TRUNC) -> str:
    """算出一个**合规的 U-1 产物身份**（形态 = `u1:<algo>:<trunc>` + `:` + `trunc` 位小写 hex）。

    ⚠ 取值（算法 / 截断）**只在本文件定义一次** ⇒ 这里**不重抄数字**（抄了就是第二个定义点）。
    ⚠ `trunc` 参数**只为** `U1#8` 的**历史长度复算**而存在（本函数每天都在 `U1_TRUNC` 上被调用，日常**不传**它）。
    """
    h = hashlib.sha256(u1_canonical_bytes(namespace, identifier, version)).hexdigest()[:trunc]
    return f"{_u1_prefix(trunc)}:{h}"


def u1_classify(identity, decl=None):
    """★★ `U1#8`（2026-09-30 裁 / `O-123`）：把身份串分类 ⇒ `(kind, info, reason)`。

    `kind` ∈ `('current', 'legacy', None)`：
      · `current` —— 前缀长度 = 当前 `U1_TRUNC` 且自描述一致（与 `u1_parse` 同口径）
      · `legacy`  —— 长度命中 `U1_TRUNC_MAP` 的 `from_length`，**且**声明里有"旧代"标注（`U1_LEGACY_MARK`）
      · `None`    —— 不合规（`reason` 给理由）

    ★ 两阶段（裁里的配套纪律，逐条落地）：
      ① **无"旧代"标注 ⇒ 【拒绝】**（**不是警告** —— 旧实现连"检测"都没有：它只会以格式为由静默失败，
         于是"该失败的旧身份"与"随手编的乱串"**同一种表现** ⇒ 无从区分）；
      ② **有标注 ⇒ 接受**，且 `info` **携带"旧代"标记**（`from_length`/`to_length`/`effective_date`），
         供消费方**自行降级**（= 结果里带得走的信息，而不是一句口头约定）。
    """
    if not isinstance(identity, str):
        return None, None, "身份不是字符串"
    m = re.match(r"^u1:([a-z0-9]+):(\d+):([0-9a-f]+)$", identity)
    if not m:
        return None, None, f"身份形态不合规（应形如 `{U1_PREFIX}:<{U1_TRUNC} 位小写 hex>`）: {identity!r}"
    algo, trunc, h = m.group(1), int(m.group(2)), m.group(3)
    if algo != U1_ALGO or len(h) != trunc:
        return None, None, (f"前缀自描述与实现不一致（algo={algo!r} 长度 {len(h)} ≠ 前缀写的 {trunc}）: {identity!r}")
    if trunc == U1_TRUNC:
        return "current", {"trunc": trunc, "legacy": False}, ""
    row = next((r for r in U1_TRUNC_MAP if r["from_length"] == trunc and r["algorithm"] == algo), None)
    if row is None:
        return None, None, (f"**从未作为 U-1 长度**的取值 `{trunc}`（也不在 `U1_TRUNC_MAP` 里）⇒ 拒收: {identity!r}")
    marked = bool(isinstance(decl, dict) and decl.get(U1_LEGACY_MARK))
    if not marked:
        return None, None, (f"★ 检测到**历史截断长度** `{trunc}`（现为 `{U1_TRUNC}`）**但声明缺「旧代」标注**"
                            f"（`{U1_LEGACY_MARK}`）⇒ **拒绝**（不是警告）：不标注会让旧身份被静默接受，"
                            f"标注则让结果携带旧代号、消费方可自行降级")
    info = {"trunc": trunc, "legacy": True, "from_length": row["from_length"],
            "to_length": row["to_length"], "effective_date": row["effective_date"]}
    return "legacy", info, ""


def u1_parse(s):
    """校验一个 U-1 身份字符串 ⇒ 返回 `(algo, trunc)`；不合规返回 `None`。

    ★ 判据里**唯一有信息量**的那部分 = **前缀自描述必须与实现一致**：
      前缀写的长度就得真的等于 hex 位数、写的算法就得是我们用的那个、hex 必须小写。
      ⇒ 若只判"有个 `u1:` 前缀"，那 D-25 的"前缀必须自描述"就退化成**装饰**。
    ⚠ 哈希**不可逆** ⇒ 本函数**只能**判形态与自描述一致性，**不能**判"这个身份是不是某个
      `(ns,id,ver)` 算出来的" —— 后者**必须**靠"声明 + 复算"（`u1_verify_declaration`）。
      （把这两件事混起来的后果是：任何人随手编一个**合规长度**的 hex 都能过。）
    """
    if not isinstance(s, str):
        return None
    m = re.match(r"^u1:([a-z0-9]+):(\d+):([0-9a-f]+)$", s)
    if not m:
        return None
    algo, trunc, h = m.group(1), int(m.group(2)), m.group(3)
    if algo != U1_ALGO or trunc != U1_TRUNC or len(h) != trunc:
        return None
    return algo, trunc


def u1_legacy_marker(decl):
    """★ `U1#8` ②：声明若是**旧代**（历史截断长度 + 带标注）⇒ 返回"旧代"标记；否则 `None`。

    供消费方**自行降级**用（标记 = `from_length`/`to_length`/`effective_date` —— 与 `U1_TRUNC_MAP` 同源）。
    """
    kind, info, _ = u1_classify((decl or {}).get("identity"), decl)
    return info if kind == "legacy" else None


def u1_verify_declaration(decl):
    """复算一个 `u1:` **声明**（`{namespace, identifier, version, identity}`）⇒ 返回错误串，或 `None` 表示通过。

    ★ 这才是"身份"这个词**唯一可判的含义**：身份不是一句自述，而是**能从 `(ns,id,ver)` 复算出来**。
      ⇒ 只判格式是**假绿**（编个 16 位 hex 就能过）；本条把"可复算"变成判据。
    ★★ **`U1#8`（2026-09-30 裁 / `O-123`）**：**历史截断长度**（`U1_TRUNC_MAP`）**必须带"旧代"标注**
      ⇒ 无标注**拒**（不是警告）；有标注 ⇒ 接受，但**结果携带旧代标记**（`u1_legacy_marker()`）。
    """
    if not isinstance(decl, dict):
        return "`u1` 必须是映射（namespace / identifier / version / identity）"
    miss = [k for k in ("namespace", "identifier", "version", "identity") if not decl.get(k)]
    if miss:
        return f"`u1` 缺字段: {miss} —— 四项都要写（只写 identity 就**无法复算**，那正是本条要防的）"
    # ★★ `U1#8`（2026-09-30 裁）：本行的旧写法是 `u1_parse(...) is None` ⇒ 历史长度会被**以格式为由**拦下
    #   （= 与"随手编的乱串"**同一种表现**，无从区分）。现改走 `u1_classify`：**历史长度只认"带旧代标注"的**，
    #   且**换把尺子再核一遍**（用历史长度复算）—— 即"接受"不等于"放行"，只是**兼容路径**。
    kind, info, why = u1_classify(decl["identity"], decl)
    if kind is None:
        return why
    want = u1_identity(decl["namespace"], decl["identifier"], decl["version"], trunc=info["trunc"])
    if want != decl["identity"]:
        return (f"`u1.identity` **复算不符** ⇒ 声明与取值自相矛盾："
                f"声明 {decl['identity']!r}；按 namespace={decl['namespace']!r} · "
                f"identifier={decl['identifier']!r} · version={decl['version']!r} 复算得 {want!r}")
    return None


U1_DECL_SCAN_DIR = ROOT / "inventory"
U1_HEADER_RE = re.compile(r"^#\s*u1:sha256:\d+\s*$")
# 与 U3-EDGE-FORMAT.md §4.2 的"视为缺"第 5 条同表
EDGE_DEAD_PROV = {"unknown", "none", "n/a", "null"}


def edge_provenance_invalid(prov, prefixes):
    """`(是否无效, 原因)` —— 按 `spec/d6-agent-standard/U3-EDGE-FORMAT.md` §4.1 的七条。

    ⚠ 切分**只按第一个 `:`** ⇒ 载荷**允许**含 `:`（`filetrack:v1:in=a,out=b` 是合法的）。
      这条是刻意留的：产物初稿既写"载荷禁含未转义 `:`"、又给了四条含 `:` 的示例 —— 自相矛盾。
    """
    if prov is None:
        return True, "字段不存在"
    if not isinstance(prov, str):
        return True, f"不是字符串（{type(prov).__name__}）"
    if prov == "":
        return True, "空串"
    if prov.strip() == "":
        return True, "仅含空白"
    if prov.strip().lower() in EDGE_DEAD_PROV:
        return True, f"命中禁用词 {prov.strip()!r}"
    if ":" not in prov:
        return True, "缺 `<前缀>:<载荷>` 形式"
    pref, _, payload = prov.partition(":")
    if prefixes and pref not in prefixes:
        return True, f"前缀 {pref!r} 不在封闭集 {sorted(prefixes)}"
    if payload.strip() == "":
        return True, "载荷为空（有前缀没有内容）"
    # ── ★ U3#3（2026-10-18）：`manual` 载荷必须是三段式 `<标识>:<日期>:reason=<理由>`（spec §3）──
    #   此前只判「前缀 ∈ 封闭集 + 载荷非空」⇒ `manual:operator-a:2026-09-26`（缺理由段）与
    #   `manual:C:/Users/admin:…`（作者标识是盘符路径）都被**放行** = 形态断言只做了一半。
    if pref == "manual":
        parts = payload.split(":")
        if len(parts) < 3:
            return True, f"`manual` 载荷不成**三段式** `<标识>:<日期>:reason=<理由>`（只切出 {len(parts)} 段）"
        ident, date, rest = parts[0].strip(), parts[1].strip(), ":".join(parts[2:]).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            return True, f"`manual` **日期段** {date!r} 不成 `YYYY-MM-DD`"
        if not rest.startswith("reason=") or not rest[len("reason="):].strip():
            return True, f"`manual` 第三段须以 `reason=<非空>` 起（实为 {rest!r}）"
        if (not ident) or re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", ident) or ("/" in ident) or ("\\" in ident):
            return True, (f"`manual` **作者标识** {ident!r} 不合规（不得是用户名/主机名/IP/盘符路径 ⇒ "
                          f"用角色标识或哈希短串，如 `operator-a`）")
    return False, ""


def edge_direction_error(e, identity_of):
    """`U3#9`：`filetrack` 边的**方向自洽性** → `(错误原因 或 None, 是否**已核**方向)`。

    spec §1.1：**`src` 依赖 `dst`** ⇒ `out=`（被写文件 = 依赖方产物）的身份应 == `src`；
    `in=`（被读文件 = 被依赖方产物）的身份应 == `dst`。
    ⚠ 方向反了**不报错、只静默多算/漏算**（U-4 失效传播全反）⇒ 必须机判（spec §未实测 9 的修法候选）。

    ⚠ `identity_of(relpath) -> u1 身份 或 None` 是**注入**的（本函数保持纯 ⇒ 可离线正反夹测）。
    ⚠ **解析不到身份 ⇒ 返回 `(None, False)`**（= 未核）—— 由调用方在 `notes` 里**显式报「未核 N 条」**，
      绝不静默判通过（D-26：降级要有呈现位）。
    """
    prov = str(e.get("provenance") or "")
    pref, _, payload = prov.partition(":")
    if pref != "filetrack":
        return None, False                       # 只对带 `in=`/`out=` 的 filetrack 可核
    kv = {}
    for tok in payload.split(","):
        k, sep, v = tok.partition("=")
        if not sep:
            continue
        # 形态是 `<版本>:in=…,out=…` ⇒ 键名取**最后一个 `:` 之后**那段（`in=` 前面还挂着版本号）
        kv[k.rsplit(":", 1)[-1].strip()] = v.strip()
    inp, outp = kv.get("in"), kv.get("out")
    if not inp or not outp:
        return (f"`filetrack` 载荷缺 `in=`/`out=`（spec §3 声明的形态）⇒ **无法核方向**（今 {kv}）"), False
    if identity_of is None:
        return None, False
    id_in, id_out = identity_of(inp), identity_of(outp)
    if id_in is None or id_out is None:
        return None, False                       # 未核：解析不到 ⇒ 交调用方报「未核」
    if id_out != e.get("src"):
        return (f"方向**不自洽**：`out=`({outp}) 的身份 {id_out!r} ≠ `src` {e.get('src')!r}"), True
    if id_in != e.get("dst"):
        return (f"方向**不自洽**：`in=`({inp}) 的身份 {id_in!r} ≠ `dst` {e.get('dst')!r}"), True
    return None, True


def _u1_identity_of_path(relpath):
    """读 `relpath`（相对仓根）yaml 的 `u1.identity`（U3 §5：`src`/`dst` 直接采用 U-1 身份）。"""
    try:
        import yaml
        p = (ROOT / str(relpath)).resolve()
        if not p.is_file():
            return None
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        u = d.get("u1") or {}
        return u.get("identity") if isinstance(u, dict) else None
    except Exception:
        return None


def validate_edges(doc):
    """**纯函数** → `(bad, notes)`（离线可正反夹测，见 tests/test_rpc_check_edges.py）。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["edges.yaml 顶层不是映射（结构改了？）"], notes

    kinds = doc.get("kinds") or []
    prefixes = doc.get("provenance_prefixes") or []
    if not kinds:
        bad.append("`kinds` 为空 ⇒ `kind` 没有封闭枚举可判（凭常识补的 kind 会静默通过）")
    if len(kinds) != len(set(kinds)):
        bad.append(f"`kinds` 有重复项: {kinds}")
    if not prefixes:
        bad.append("`provenance_prefixes` 为空 ⇒ `provenance` 没有封闭集可判")
    if len(prefixes) != len(set(prefixes)):
        bad.append(f"`provenance_prefixes` 有重复项: {prefixes}")

    if "edges" not in doc:
        bad.append("**缺 `edges` 字段** ⇒ 无法区分「清单为空」与「忘了写」（空必须显式）")
        return bad, notes
    edges = doc["edges"] or []
    if not isinstance(edges, list):
        bad.append(f"`edges` 不是列表（{type(edges).__name__}）")
        return bad, notes

    seen, n_invalid = {}, 0
    for i, e in enumerate(edges, 1):
        if not isinstance(e, dict):
            bad.append(f"`edges[{i}]` 不是映射")
            n_invalid += 1
            continue
        miss = [f for f in EDGE_REQUIRED if not e.get(f)]
        if miss:
            bad.append(f"`edges[{i}]` **缺字段** {miss} ⇒ 该边无效（★ 产出方**不许写出**无效边）")
            n_invalid += 1
            continue
        for f in ("src", "dst"):
            if u1_parse(e[f]) is None:
                bad.append(f"`edges[{i}].{f}` 不是 U-1 产物身份形态 `{U1_PREFIX}:<{U1_TRUNC} 位小写 hex>`: {e[f]!r} "
                           f"（判据 = `u1_parse`，与 U-1 实现**同源** —— 此前这里另写了一份正则 = 同一事实两个定义点）"
                           f"⇒ 「边指向谁」没有唯一答案（U-1 与 U-3 必须咬合）")
                n_invalid += 1
        if kinds and e["kind"] not in kinds:
            bad.append(f"`edges[{i}].kind`={e['kind']!r} 不在 `kinds` 封闭枚举里")
            n_invalid += 1
        inv, why = edge_provenance_invalid(e.get("provenance"), set(prefixes))
        if inv:
            bad.append(f"`edges[{i}].provenance` **无效**（{why}）⇒ 该边**无效**。"
                       f"⚠ 产出方的处置是 **FAIL**，不是「丢掉这条边继续」—— 依据 D-26「禁止静默 skip」；"
                       f"「丢弃 / 降级」是**消费方**那一侧的规则（H-3）")
            n_invalid += 1
        key = (e.get("src"), e.get("dst"), e.get("kind"))
        if key in seen:
            bad.append(f"`edges[{i}]` 与第 {seen[key]} 行重复 (src,dst,kind) ⇒ 同一事实两处定义")
        else:
            seen[key] = i

    if not edges:
        why = str(doc.get("empty_reason") or "").strip()
        if not why:
            bad.append("`edges` 为空**且没有 `empty_reason`** ⇒ 空得没说法"
                       "（空 ≠ 没事：必须写明“为什么空”，否则会被读成“一切正常”）")
        else:
            notes.append("清单为空已显式报出 (不静默通过; empty_reason 已给)")
    notes.append(f"边 {len(edges)} 条 · 无效 {n_invalid} 条 · kind {len(kinds)} 项 · 前缀 {len(prefixes)} 项")
    return bad, notes


def check_edges(ctx):
    """D7-P1-3: U-3 依赖边清单（`inventory/edges.yaml`）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 edges 边格式断言", []
    if not EDGES_INV.exists():
        return "FAIL", "inventory/edges.yaml 缺失（本断言的登记依据）", []
    try:
        doc = yaml.safe_load(EDGES_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/edges.yaml 解析失败: {type(e).__name__}: {e}", []
    bad, notes = validate_edges(doc)
    # ── ★ U3#9（2026-10-18）：**方向自洽性**（`src` 依赖 `dst`，spec §1.1）──
    #   此前**没有任何断言**检查"`src` 是否真的依赖 `dst`" ⇒ 方向反了不报错、只静默多算/漏算。
    dir_bad, n_unres = [], 0
    for i, e in enumerate((doc.get("edges") or []), 1):
        if not isinstance(e, dict):
            continue
        reason, checked = edge_direction_error(e, _u1_identity_of_path)
        if reason:
            dir_bad.append(f"`edges[{i}]` {reason} ⇒ 方向反了会**静默**多算/漏算（U-4 失效传播全反）")
        elif not checked and str(e.get("provenance") or "").startswith("filetrack"):
            n_unres += 1
    bad = bad + dir_bad
    if n_unres:
        notes.append(f"⚠ 方向**未核** {n_unres} 条（`filetrack` 解析不到身份 ⇒ 呈现位，不静默通过）")
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


def check_id_census(ctx):
    """O-85: 让"ID 站点计数"**可复算**（此前那一列没有口径 ⇒ 数字不可复现）。

    ★ 这条判据的对象不是"数字对不对"，而是**数字有没有定义** —— 它比对
      `inventory/id-site-census.yaml` 与 `ops/id_site_census.py` 的**当场复算**结果。
    ⚠ **项目目录不可达 ⇒ WARN（不是 FAIL）**：那些项目在**别的盘**（`F:` / `E:`），
      换一台机器就没有 ⇒ 硬红会把"我的环境"变成"仓库的规则"。
      但**必须可见**（D-26：降级要有呈现位）—— 所以报 `可达 N/M` + 逐项目标 `--`，
      **绝不静默通过**。
    ★★ **O-87（2026-09-26 补）：note 里列出"可达项目根清单"（`id@root`）** —— 理由：
      本仓两次"假缺口"（把"我没搜到"写成"它不存在"）都是**关于外部世界的存在性否定**，
      而**答案本来就在这张表里**（`Macro_Data` 一直在 `E:` 盘；Open_Data / Auto_Prover 的库一直在 `F:` 盘）。
      只报计数（"可达 10/10"）**不列名** ⇒ 写结论的人看不到 ⇒ 于是继续写假缺口。
      ⇒ 把清单**摆进每轮门禁输出**，让"它其实在 `F:`/`E:`"当场可见（把"我没搜到"从**隐性推论**
      变成**可见事实**的对账）。
    ⚠⚠ **射程（不许读过头）**：本判据**不判**"文档里的存在性结论是否为真" —— 那一半**不可能干净地文本机判**：
      「不存在」在规范文档里**有歧义** = **本仓没有实现/判据**（合法，且"未实测登记"节**必须**能这么写）
      vs **外部世界没有那个东西**（危险推论）⇒ 实测三次收窄**仍出假阳性**（13 → 2 → 仍含 1 条误报）
      ⇒ **已放弃文本扫描**，见 `DEV-LOG-014` §53.1。本判据只保证：**事实可见**，
      且**清单本身不会静默缺项**（某项目缺 `root` ⇒ FAIL）。
    """
    import importlib.util
    try:
        import yaml  # noqa: F401
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 id-census 断言", []
    script = ROOT / "ops" / "id_site_census.py"
    if not script.is_file():
        return "FAIL", "ops/id_site_census.py 缺失（本断言的登记依据）", []
    spec = importlib.util.spec_from_file_location("_id_site_census", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    doc = yaml.safe_load(mod.CENSUS.read_text(encoding="utf-8")) or {}
    m = doc.get("metric") or {}
    drift = []
    if m.get("name") != mod.METRIC_NAME:
        drift.append("name")
    if m.get("regex") != mod.METRIC_REGEX:
        drift.append("regex")
    for k, v in mod.scope().items():
        if m.get(k) != v:
            drift.append(k)

    now = {p["id"]: p for p in mod.census()}
    mism, unreach, ok = [], [], []
    for p in doc.get("projects") or []:
        cur = now.get(p["id"])
        if cur is None:
            continue
        if not cur.get("reachable"):
            unreach.append(p["id"])
        elif not p.get("reachable") or (p.get("hits"), p.get("files")) != (cur["hits"], cur["files"]):
            mism.append(f"{p['id']}: 真值 {p.get('hits')}行/{p.get('files')}文件 ≠ 实测 {cur['hits']}行/{cur['files']}文件")
        else:
            ok.append(p["id"])

    total = len(doc.get("projects") or [])
    # O-87：**可达项目根清单** —— 让"本机到底有什么"每轮可见（理由见 docstring）。
    #   缺 `root` 的项目会被**静默漏出**清单 ⇒ 可见性降级 ⇒ 故下面 fail-closed（不是只报数）。
    projs = doc.get("projects") or []
    missing_root = [str(p.get("id")) for p in projs if not p.get("root")]
    reach_roots = [f"{p['id']}@{p.get('root')}" for p in projs if p.get("reachable") and p.get("root")]
    note = (f"口径 {m.get('name')}（{m.get('unit')}）· 真值一致 {len(ok)} 个 · "
            f"不符 {len(mism)} 个 · 不可达 {len(unreach)}/{total} · "
            f"可达项目根 {len(reach_roots)} 个: " + " · ".join(reach_roots))
    if missing_root:
        note += f" · ⚠ 无 root {len(missing_root)} 个"
    if drift:
        # 口径漂移比数值漂移严重：口径一变，真值里所有数字立刻失去意义
        return "FAIL", note, [f"**口径已漂移**（真值是用旧口径生成的）: {drift} ⇒ 重跑 --emit 并复核下游结论"] + mism
    if missing_root:
        return "FAIL", note, [f"**项目根清单缺项**（`root` 缺失 ⇒ 该项**读不出可达性** ⇒ O-87 的可见化"
                              f"**静默降级**）: {', '.join(missing_root)} ⇒ 在 `inventory/id-site-census.yaml` 补 `root:`"]
    if mism:
        return "FAIL", note, mism
    if unreach:
        return "WARN", note, [f"不可达（本次无法复算，**不当作通过**）: {', '.join(unreach)}"]
    return "PASS", note, []


def check_id_storage(ctx):
    """U-4: **存储面**普查 —— `affected` 的**生产者**（此前是"开库手工数"）。

    ★ 判什么：
      ① **数值/形态**与真值一致（`inventory/id-storage-census.yaml`）；
      ② ★★ **声明的 `role` 必须回库里核过** —— 声明 `primary_key` 而实测不是 ⇒ **FAIL**
         （"声明 ≠ 事实"是这个脚本唯一能咬住自己的地方，也最容易被写成自说自话）；
      ③ **口径漂移**（形态档 / 取样上限 / role 取值域）⇒ 比数值不符**优先**判红。
    ⚠ 存储不可达 ⇒ **WARN 不 FAIL**（库在别的盘），但报 `不可达 N/M` ⇒ **不静默通过**（D-26）。
    """
    import importlib.util
    try:
        import yaml  # noqa: F401
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 id-storage 断言", []
    script = ROOT / "ops" / "id_storage_census.py"
    if not script.is_file():
        return "FAIL", "ops/id_storage_census.py 缺失（本断言的登记依据）", []
    spec = importlib.util.spec_from_file_location("_id_storage_census", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    doc = yaml.safe_load(mod.CENSUS.read_text(encoding="utf-8")) or {}
    m = doc.get("metric") or {}
    drift = []
    if m.get("shape_sample_limit") != mod.MAX_SHAPE_SAMPLE:
        drift.append("shape_sample_limit")
    if m.get("role_domain") != ["primary_key", "record_key"]:
        drift.append("role_domain")

    now = {(s["project"], s["path"], s["table"], s["column"]): s for s in mod.census()}
    mism, unreach, badrole, ok = [], [], [], 0
    for s in doc.get("stores") or []:
        cur = now.get((s["project"], s["path"], s["table"], s["column"]))
        if cur is None:
            continue
        if not cur.get("reachable"):
            unreach.append(f"{s['project']}.{s['column']}")
        elif s.get("declared_role") == "primary_key" and cur.get("is_primary_key") is not True:
            badrole.append(f"{s['project']}.{s['column']}: 声明 primary_key 但**库里不是**"
                           f"（实测 is_primary_key={cur.get('is_primary_key')}）")
        elif (s.get("rows"), s.get("distinct")) != (cur.get("rows"), cur.get("distinct")):
            mism.append(f"{s['project']}.{s['column']}: 真值 {s.get('rows')}行/{s.get('distinct')}distinct "
                        f"≠ 实测 {cur.get('rows')}行/{cur.get('distinct')}distinct")
        else:
            ok += 1
    total = len(doc.get("stores") or [])
    rows = sum(s.get("rows") or 0 for s in (doc.get("stores") or []) if s.get("reachable"))
    note = f"存储 {total} 处 · 一致 {ok} · 角色不实 {len(badrole)} · 不符 {len(mism)} · 不可达 {len(unreach)}/{total} · 存量 {rows} 行"
    if drift:
        return "FAIL", note, [f"**口径已漂移**: {drift} ⇒ 重跑 --emit 并复核下游结论"] + badrole + mism
    if badrole or mism:
        return "FAIL", note, badrole + mism
    if unreach:
        return "WARN", note, [f"不可达 ⇒ 本次 **affected 不完整**（可见，不静默）: {', '.join(unreach)}"]
    return "PASS", note, []


def u1_decl_conflicts(decls):
    """`U1#6`（2026-10-18）：**声明集合级**检查 → `(bad, n_fallback)`。

    - **身份冲突**：两个文件声明**同一 `u1.identity`** ⇒ 同一身份两处声明（"唯一答案"被破坏）⇒ 判红。
    - **兜底版本可见化**：`version == U1_DEFAULT_VERSION` 的声明计数 —— `0.0.0` 让「同一 identifier、
      不同版本」产生**相同哈希** ⇒ 该维度**实际失效**（spec §未实测 6）。
      ⚠ **刻意不判红、也不改默认值**：全仓两条真实身份都写 `0.0.0`，**改值会破坏复算**
      （哈希变 ⇒ 身份变 ⇒ `edges.yaml` 的 `src`/`dst` 全失效）⇒ 只做**报数可见**。

    `decls` = `[(文件名, decl_dict), ...]` —— **纯函数**（离线可正反夹测）。
    """
    bad, seen, n_fallback = [], {}, 0
    for name, decl in decls:
        if not isinstance(decl, dict):
            continue
        if str(decl.get("version")) == U1_DEFAULT_VERSION:
            n_fallback += 1
        iid = decl.get("identity")
        if isinstance(iid, str) and iid:
            if iid in seen:
                bad.append(f"{name}: `u1.identity` 与 {seen[iid]} **重复** ⇒ 同一身份两处声明（U-1 冲突）")
            else:
                seen[iid] = name
    return bad, n_fallback


def check_u1_identity(ctx):
    """D7-P1 实现侧（U-1 落地）：`inventory/*.yaml` 的 **U-1 身份声明必须可复算**。

    ★ 判什么（按信息量从高到低）：
      ① **复算**：文件声明 `u1: {namespace, identifier, version, identity}` ⇒ 按前三项重算**必须**等于 identity。
         只判格式是**假绿**（随手编一个 16 位 hex 就能过）—— 而"身份"这个词可判的含义只有"能从 (ns,id,ver) 复算"。
      ② **头部注释前缀**：既然声明了身份 ⇒ 前 5 行内必须**同时**有 `# u1:sha256:<N>` 头部注释行
         （D-25：前缀进头部注释、不进哈希行；U1 spec §1.4 要求"每文件首行"）。
      ③ ★ **至少 1 个声明**：一个都没有 ⇒ 本条判据**没有对象** ⇒ 判红。
         （否则它会**静默退化**成空判 —— 正是本仓头号失败形态"判据什么都没判"。）
      ★★ ④ **`namespace` 必须落在取值域里**（`U1#5`，2026-10-01）—— 取值域的真值 =
         `inventory/namespaces.yaml`（注册表）；**只认 `status: active` 的 canonical id**
         （写 alias / retired / 未登记 ⇒ 拒）。⚠ 本条此前**不存在**：旧判据只复算，
         于是 `namespace: 任何字符串` 都能过 ⇒ D-25 的"前缀必填 + 取值域封闭"**只有前半句落地了**。
         同时顺带判**注册表自身自洽**（`validate_namespaces`）。
      ★★ ⑤ **坐标语义必须登记**（`O-162`，2026-10-20）—— 判据 ④ 问的是"**能不能用**这个 namespace"，
         判据 ⑤ 问的是"**这个 namespace 的 identifier / version 怎么算**"。前者 `U1#5` 已落；
         后者此前只有 spec §1.3 的 prose ⇒ 现由注册表 `identifier_rule` / `version_rule`（**闭集**）承载，
         判据 = `validate_namespace_coords(reg, used_ns)`（`used_ns` = 上面扫到的声明的 namespace）
         ⇒ ★ **用了却没定语义**判红。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 u1-identity 断言", []
    if not U1_DECL_SCAN_DIR.is_dir():
        return "FAIL", "inventory/ 缺失（本断言的登记依据）", []
    # ★★ `U1#5` ④：取值域的真值 = 注册表；缺失/不自洽 ⇒ **FAIL**（不是跳过 —— 没有值域就无从判）
    if not NAMESPACE_REG.is_file():
        return "FAIL", "inventory/namespaces.yaml 缺失（`U1#5` 起它是 namespace 取值域的唯一真值）", []
    reg = yaml.safe_load(NAMESPACE_REG.read_text(encoding="utf-8")) or {}
    ns_bad, ns_notes = validate_namespaces(reg)
    if ns_bad:
        return "FAIL", "命名空间注册表自身不自洽（见明细）", ns_bad
    ns_note = " · ".join(ns_notes)
    bad, declared, ok_recalc = [], 0, 0
    pairs = []                                    # (`U1#6`) 供集合级冲突检查
    for p in sorted(U1_DECL_SCAN_DIR.glob("*.yaml")):
        text = p.read_text(encoding="utf-8")
        try:
            doc = yaml.safe_load(text) or {}
        except Exception as e:
            bad.append(f"{p.name}: YAML 解析失败 {type(e).__name__}: {e}")
            continue
        decl = doc.get("u1") if isinstance(doc, dict) else None
        if decl is None:
            continue
        declared += 1
        pairs.append((p.name, decl))                  # (`U1#6`)
        err = u1_verify_declaration(decl)
        # ★ `U1#5` ④：取值域 —— 与复算**分开报**（复算过不了 ≠ 取值域不对，反之亦然）
        if not err:
            err = namespace_domain_error(decl.get("namespace"), reg)
        if err:
            bad.append(f"{p.name}: {err}")
        else:
            ok_recalc += 1
        if not any(U1_HEADER_RE.match(l) for l in text.splitlines()[:5]):
            bad.append(f"{p.name}: 有 `u1:` 身份声明，但**前 5 行内没有** `# u1:sha256:{U1_TRUNC}` 头部注释行"
                       f"（D-25：前缀进头部注释；U1 spec §1.4 要求每文件首行）")
    # ── ★ U1#6（2026-10-18）：**集合级** —— 身份冲突判红 + 兜底版本可见化 ──
    cbad, n_fallback = u1_decl_conflicts(pairs)
    bad.extend(cbad)
    # ── ★★ `O-162`（2026-10-20 裁「进注册表字段」）：判据 ⑤ —— **坐标语义**必须登记 ──
    #   判据 ④ 问"能不能用这个 ns"；⑤ 问"这个 ns 的 identifier / version 怎么算"。
    #   `used_ns` 取**真实声明用到的**（= "**用了却登记 unset**" 判红的依据 ⇒ 用了就得定语义）。
    used_ns = {d.get("namespace") for _n, d in pairs if isinstance(d, dict)}
    cbad2, cnotes = validate_namespace_coords(reg, used_ns)
    bad.extend(cbad2)
    if declared == 0:
        bad.append("`inventory/*.yaml` 里**一个 `u1:` 身份声明都没有** ⇒ 本条判据**没有对象**（= 空判）⇒ 判红；"
                   "U-1 的落地以『至少一个可复算的声明』为可判形式")
    # ⚠ 这两个数**算出来**，不写死 —— 上一版我在这里硬编码了"复算 0 处不符"，
    #   那正是刚修掉的"标签在说谎"同族（标签比事实硬）。
    notes = (f"已声明 U-1 身份 {declared} 个 · 复算+值域通过 {ok_recalc} 个（扫描 inventory/*.yaml）"
             f" · ⚠ 兜底版本 {U1_DEFAULT_VERSION} 的声明 {n_fallback} 个"
             f"（version 维度**实际失效** · spec §未实测 6；刻意不改默认值以免破坏复算）"
             f" · {ns_note} · {' · '.join(cnotes)}")
    return ("FAIL" if bad else "PASS"), notes, bad


# ── D7-P1-4 (2026-09-26)：U-4 失效规则 H-1~H-4（**判据库**，不是门禁项）────────
# ⚠⚠ **本节不是 `CHECKS` 项** —— 它不判本仓的任何状态（本仓没有失效传播实现，九项目 **0/9**）。
#   它是**参考实现**：把四条 MUST 级规则写成**可执行判据**，供将来的失效传播实现调用/对照。
#   ⇒ 因此**它当前没有任何生产消费者**（这件事已如实登记在
#     `spec/d6-agent-standard/U4-INVALIDATION-RULES.md` 的末节，不假装已接）。
#   ⇒ 但 D7-P1 的批级判据要求"**通过先验红**"（方案 §7）⇒ 必须有可执行的判据 + 注入用例，
#     纯纸面表达式过不了那一条（`tests/test_rpc_check_u4.py`）。
#
# 依据（原文，Ontoly RFC-0002，RFC 2119 措辞）：
#   H-1 "Incremental builds MUST be clean-build equivalent."
#   H-2 "Dependency invalidation MUST be conservative."
#   H-3 "If affected regions cannot be determined safely, the compiler MUST broaden
#        invalidation or fall back to a clean build."   ← ★ 本批的核心
#   H-4 "A failed build MUST NOT partially overwrite the last valid canonical graph artifact."
# 已裁（台账）：D-26 四条全采（照 MUST 语义）· **只适用派生产物** · H-3 的"降级"必须有机判
#   呈现位（落进 D6-P0-1「非执行三分」，**禁止静默 skip**）；D-27 结构性事实须**可复算**才准入；
#   D-51 受理目录**不纳入**失效传播。
#
# ★ 与「非执行三分」的映射（这是 D-26 那句"必须有呈现位"的落地）：
#     · 确实**无变更** ⇒ `action=none` + **MODE_SKIP**（"调用方不给" —— 这是**真的没事**）
#     · **无法安全判定影响面** ⇒ `action=full_rebuild` + **WARN**（能力降级：保守全量，**可见、不阻断**）
#     · 增量等价性**未能证明** ⇒ `action=full_rebuild` + **WARN**（同上）
#     · 重算**失败** ⇒ `action=none` + **SKIP_FAILED**（**算失败**；不得部分覆盖 ⇒ 不落盘）
#   ⇒ **硬不变量**：任何"**判不了**"的情形都**不得**落到 `MODE_SKIP` ——
#     那正是"静默 skip"的形态（把"判不了"悄悄变成"没事"）。用例 `u4⑦` 专门钉这一条。
U4_ACTIONS = ("none", "incremental", "full_rebuild")
U4_CLASSES = (None, "MODE_SKIP", "SKIP_FAILED", "WARN")
# ── U-4 **执行侧**（2026-09-29，A6 / `U4-INVALIDATION-RULES.md` 未实测第 10 条）──────────────
U4_EXEC_STATUS = ("executed", "partial-failed", "not-executed", "no-op")
U4_ITEM_STATUS = ("success", "failed", "n/a")


def decide_invalidation(changed_ids=None, affected=None, affected_is_closure=False,
                        incremental_equivalent=None, build_failed=False):
    """U-4 的四条规则 → `(action, class, reason)`。

    参数（= 判据的**输入契约**；将来的实现只需提供这五个）：
      · `changed_ids`            上游变更集（**派生产物**；受理目录按 D-51 不在其内）
      · `affected`               影响面判定的**结果集**；`None` 表示**无法安全判定**（H-3 的触发条件）
        ⚠⚠ **`[]` 与 `None` 语义不同，别写成 `[...] or None`**（O-88，2026-09-26）：
        `[]` = "**已判定为空**"（下游确实为空 ⇒ 无动作，**不是**"判不了"）；
        `None` = "**判不了**"（⇒ H-3 强制全量）。
        写成 `affected or None` 会把"已知为空"错误升格成"判不了" ⇒ **白白付一次全量**。
      · `affected_is_closure`    该结果集是否**已传递闭包化**（H-2：必须保守 = 只许扩大）
      · `incremental_equivalent` 增量结果是否**已证**与全量等价；`None` = **未证**（H-1）
      · `build_failed`           本次重算是否失败（H-4）

    返回 `(action, class, reason)`；`class` 只在"未执行/降级"时给值（正常路径为 `None`）。
    """
    if not changed_ids:
        # 真的没有变更 ⇒ 这是**唯一**允许落到 MODE_SKIP 的情形
        return "none", "MODE_SKIP", "变更集为空：确实无需动作（不是「判不了」）"
    if build_failed:
        # H-4：失败不得部分覆盖 ⇒ 不落盘、不动上一份有效产物；且**算失败**
        return "none", "SKIP_FAILED", "H-4 重算失败 ⇒ 不得部分覆盖，保留上一份有效产物（算失败）"
    if affected is None:
        # H-3：无法安全判定 ⇒ 强制全量；**可见但不阻断**（WARN），绝不静默 skip
        return "full_rebuild", "WARN", "H-3 影响面无法安全判定 ⇒ 强制全量降级（可见，禁止静默 skip）"
    if not affected and affected_is_closure:
        # ★ O-88（2026-09-26）：**有变更、但影响面为空且已闭包化** = 已判定「**确实没有下游**」。
        #   ⇒ 既不需要增量、也不需要全量 —— **没有任何东西要重算**（DEV-LOG-014 §54）。
        #   为什么这是"已判定"而不是"判不了"：`affected` 是**列表**（`None` 才是判不了，见上一条），
        #     且调用方**显式声明**它已闭包化 ⇒ 与 `incremental_equivalent=True` 同族的**调用方断言**。
        #   ⚠ H-1 在此分支**不适用**：它的语义是"**增量**结果必须与全量等价"，而下游为空 ⇒ **没有增量**
        #     ⇒ 该维度**不存在**（旧实现把它算作"未证" ⇒ 白白付一次全量；改动前实测见 §54.1）。
        #   ⚠ 顺序：必须在 H-3（`None`）**之后**（`[]` ≠ `None`）、H-1 **之前**。
        return "none", "MODE_SKIP", ("有变更但影响面为空且已闭包化（= 已判定：确实无下游）⇒ 无动作"
                                     "（既不增量也不全量：没有下游要重算）")
    if incremental_equivalent is not True:
        # H-1：增量必须与全量等价；**未证**不等于"等价"（fail-closed）
        return "full_rebuild", "WARN", "H-1 增量等价性未证 ⇒ 不得用增量（付全量代价）"
    if not affected_is_closure:
        # H-2：失效必须保守 ⇒ 未闭包化的结果集只许扩大
        return "full_rebuild", "WARN", "H-2 影响面未闭包化 ⇒ 保守起见取全量（宁可多算）"
    return "incremental", None, "四条规则全过：可安全增量"


def execute_invalidation(action, class_, reason, affected=None, executors=None):
    """U-4 **执行侧**：把 `decide_invalidation()` 的决策落成一份**执行报告**（`A6`，2026-09-29）。

    ⚠ 与 `decide_invalidation` 同：**不是 CHECKS 项**（本仓没有可判的对象）。
    ⚠ 它**自己不重算** —— 重算由**注册表**里的执行器做；本仓与九项目 **0/9** ⇒ 调用方默认传**空注册表**
      ⇒ 有活时整体报 `not-executed`（**不适用，带理由**）—— **绝不**在无执行器时报成功（防假绿）。

    入参：
      · `action` / `class_` / `reason` = `decide_invalidation()` 的三元输出（**原样传入**，本函数不重算决策）
      · `affected` = 同一份结果集（**必须与决策同源**）；`None`/空 = 全量（`full_rebuild` 射程）
      · `executors` = `{action: callable}`；`callable(target) -> {"status": ..., "version": int|None, "detail": ...}`

    返回 dict（键名即契约）：
      · `status` ∈ `U4_EXEC_STATUS`（**封闭枚举**：`executed` / `partial-failed` / `not-executed` / `no-op`）
      · `items` = 逐项 `{"target", "status"(∈ U4_ITEM_STATUS), "detail"}`
      · `aggregate` = `{n_success, n_failed, n_na, version_monotonic}`

    ★ 防假绿硬约束（imp6 设计稿）：**整体成功**仅当
      「**所有受影响项均 `success`** ∧ 成功项 `version` **严格单调递增** ∧ 成功项数 > 0」；
      否则**一律** `partial-failed`（**禁报成功**）。⚠ 无动作（`action=none`）**不算**"执行成功" ⇒ 单列 `no-op`。
    """
    if action not in U4_ACTIONS:
        raise ValueError(f"action={action!r} 不在封闭枚举 {U4_ACTIONS}")
    if class_ not in U4_CLASSES:
        raise ValueError(f"class={class_!r} 不在封闭枚举 {U4_CLASSES}")

    rep = {"action": action, "class": class_, "reason": reason, "items": [],
           "aggregate": {"n_success": 0, "n_failed": 0, "n_na": 0, "version_monotonic": None}}

    if action == "none":
        # 三种 `action=none` 的决策**语义不同**，不能同档：`MODE_SKIP` = 无需动作；`SKIP_FAILED`(H-4) = **算失败**
        rep["status"] = "no-op" if class_ == "MODE_SKIP" else "partial-failed"
        return rep

    # 有活（incremental / full_rebuild）：先看有没有注册执行器 —— 没有就**整体未执行**（不假装）
    executors = executors or {}
    runner = executors.get(action)
    targets = list(affected) if affected else ["<全量>"]
    if runner is None:
        rep["items"] = [{"target": t, "status": "n/a", "detail": f"无注册执行器（action={action}）⇒ 未执行"}
                        for t in targets]
        rep["aggregate"]["n_na"] = len(targets)
        rep["status"] = "not-executed"
        return rep

    versions = []
    for t in targets:
        try:
            r = runner(t) or {}
        except Exception as e:                      # 执行器抛异常 = **算失败**（绝不静默吞）
            r = {"status": "failed", "detail": f"{type(e).__name__}: {e}"}
        st = r.get("status")
        if st not in U4_ITEM_STATUS:                # 非法/缺失状态 ⇒ 落失败（fail-closed）
            st = "failed"
            r = dict(r, detail=f"执行器返回非法状态 {r.get('status')!r} ⇒ 按失败处理")
        rep["items"].append({"target": t, "status": st, "detail": r.get("detail", "")})
        if st == "success":
            rep["aggregate"]["n_success"] += 1
            if isinstance(r.get("version"), int):
                versions.append(r["version"])
        elif st == "failed":
            rep["aggregate"]["n_failed"] += 1
        else:
            rep["aggregate"]["n_na"] += 1

    agg = rep["aggregate"]
    agg["version_monotonic"] = (all(a < b for a, b in zip(versions, versions[1:]))
                                if versions else None)
    agg["all_success"] = (agg["n_failed"] == 0 and agg["n_na"] == 0 and agg["n_success"] > 0)
    rep["status"] = ("executed" if (agg["all_success"] and agg["version_monotonic"] is True)
                     else "partial-failed")
    return rep


# ── ★ U-4 批 1（2026-09-30）：三条「已裁 + 实现待落地」落成**可机判纯函数** ─────────
# 来源 = `O-123` 的裁定 + 派工视图 `spec/d6-agent-standard/UNTESTED-TRIAGE-PLAN.md` §8 批 1。
# ★ **只实现裁定的方向，不重新裁定**：
#   #3 「自报位 `affected_is_closure`」⇒ **判定方独立重算**（主判据）+ **逐跳路径证据**（辅），
#      二者**不一致即拒收**（`verify_affected_closure`）
#   #4 「只适用派生产物」（D-26/D-51）⇒ **可核来源标记** / 显式非派生**硬拒** /
#      无标记**软警 + 审计**（灰度期；白名单 = 裁点名的「洗信号」避法）
#   #6 「以**证伪**替代**证明**」⇒ 测例集覆盖代数性质 + 反例清单**须含历史真实失效**
#      + 运行时抽样自检 + **可开增量白名单**（`check_falsification_suite` / `runtime_selfcheck`）
# ⚠ 三条**共用一个口径**：**「判不了」≠「通过」**（同 `O-22`/`O-119`）——
#   "取不到图查询面" / "抽样为空" 一律落 `boundary`/`inconclusive`/`insufficient`，
#   **绝不**落 `consistent`/`ok`（那正是本仓头号形态「静默变成没事」的入口）。
# ⚠ 与 `decide_invalidation` 同：**不是 CHECKS 项**（本仓没有可判的对象 ⇒ 不新增 gate id）。
U4_CLOSURE_VERDICTS = ("consistent", "inconsistent", "boundary")
U4_ORIGINS = ("derived", "non-derived")
U4_DERIVED_VERDICTS = ("ok", "soft-warn", "hard-reject")
U4_ALGEBRAIC_PROPS = ("boundary", "idempotence", "commutativity")
U4_FALSIFY_VERDICTS = ("ok", "insufficient", "blocked")
U4_SELFCHECK_VERDICTS = ("consistent", "mismatch", "inconclusive")


def _edge_pair(e):
    """边实例 → `(dependent, dependency)`；方向 = **`src` 依赖 `dst`**（照 `inventory/edges.yaml` 的约定）。

    ⚠ 该方向约定**尚未写进 U3 schema**（台账 `O-83` 已登记）⇒ 本函数把它**显式写在一处**，
      不留给下游各自理解（"同一事实两个定义点"是本仓头号形态）。
    """
    if isinstance(e, dict):
        return e.get("src"), e.get("dst")
    if isinstance(e, (list, tuple)) and len(e) == 2:
        return e[0], e[1]
    return None, None


def recompute_closure(changed_ids, edges):
    """★ `U4#3`：判定方**独立重算**影响面闭包（**主判据**）。

    方向：**`src` 依赖 `dst`** ⇒ 变了的是被依赖的一侧（`dst`）时，影响面 = **依赖它的 `src`**（反向遍历）。
    返回 `sorted(list)`；⚠ **不含** `changed_ids` 自身（那是变更集，不是影响面）。
    ⚠ `edges` 为 `None`/空 ⇒ 返回 `None` = **判不了**（**不是**"没有下游" —— 那个区分是本仓头号形态）。
    """
    if not edges:
        return None
    deps = {}                                        # dependency -> [dependents]
    for e in edges:
        dep, dty = _edge_pair(e)
        if dep is None or dty is None:
            continue
        deps.setdefault(dty, []).append(dep)
    seen, out = set(changed_ids or ()), set()
    stack = list(changed_ids or ())
    while stack:                                     # 反向 BFS：谁依赖它
        for d in deps.get(stack.pop(), ()):
            if d not in seen:
                seen.add(d)
                out.add(d)
                stack.append(d)
    return sorted(out)


def verify_affected_closure(changed_ids, affected, edges=None, hops=None):
    """★ `U4#3`：**双轨核验** —— 独立重算（主判据）+ 逐跳路径证据（辅）；**不一致即拒收**。

    返回 `(verdict, detail)`，`verdict ∈ U4_CLOSURE_VERDICTS`：
      · `consistent`   —— 重算结果与调用方 `affected` **逐项一致**（且路径证据无冲突）
      · `inconsistent` —— **拒收**（自报与重算不符 / 路径证据与图不符 —— 后者视为**伪造**）
      · `boundary`     —— **判不了**：① 取不到图查询面（`edges` 空）；② 图面与本域**无交集**
        （不同域 ⇒ 它不是能裁决本域的查询面）。照 `O-123` 的再触发条件，此时**反转为
        「登记为边界 + 事后抽检」**，**不算通过**。

    `hops` = 逐跳路径证据：`[[affected_id, ..., changed_id], ...]`（沿依赖方向**倒着走**：
    每一跳 `(p[i], p[i+1])` 须是图里的一条边 `src 依赖 dst`）。⚠ 它**只是辅** ——
    只在重算**通过**后才用来加严（重算过不了 ⇒ 直接 `inconsistent`，不看证据）。
    """
    if edges is None or not edges:
        return ("boundary", "取不到依赖图查询面（edges 为空/未提供）⇒ 按 `O-123` 反转为"
                            "「登记为边界 + 事后抽检」—— **不算通过**")
    nodes = {x for e in edges for x in _edge_pair(e) if x is not None}
    if (changed_ids or affected) and not (nodes & (set(changed_ids or ()) | set(affected or ()))):
        return ("boundary", "图查询面与本域**无交集**（不同域，如产物→产物 vs 产物→存储列）"
                            "⇒ 判不了闭包 ⇒ 登记边界 + 事后抽检（**不算通过**）")
    want = sorted(recompute_closure(changed_ids, edges) or ())
    got = sorted(set(affected or ()))
    if got != want:
        miss = [x for x in want if x not in got]
        extra = [x for x in got if x not in want]
        return ("inconsistent",
                f"自报 `affected`({len(got)}) 与判定方**独立重算**({len(want)}) 不一致 ⇒ **拒收**"
                f"（漏算 {miss[:5]} · 多算 {extra[:5]}）")
    if hops:
        pairs = {_edge_pair(e) for e in edges}
        ch, wa = set(changed_ids or ()), set(want)
        for path in hops:
            p = list(path or ())
            if len(p) < 2 or any((p[i], p[i + 1]) not in pairs for i in range(len(p) - 1)):
                return "inconsistent", f"逐跳路径证据与图不符（**伪造**）⇒ 拒收: {p[:6]}"
            if p[0] not in wa or p[-1] not in ch:
                return "inconsistent", f"路径端点不在 affected/changed 内 ⇒ 拒收: {p[:6]}"
    return "consistent", f"独立重算与自报逐项一致（{len(want)} 项）⇒ 闭包**已核验**"


def check_derived_boundary(items, whitelist=()):
    """★ `U4#4`：把「**只适用派生产物**」（D-26）落成**可机判形态**（含 D-51 的受理目录排除）。

    `items` 每项 = `str`（= 无标记）或 `dict`：`id` · `origin`(`U4_ORIGINS`) · `source`（**可核来源标记**，
    如 `hash:…` / `filetrack:…` / `tool:…`）。`whitelist` = **合法无标记产物**（`O-123` 点名的
    「**先建白名单**」避法 —— 防"一律驳回"把合法的无标记产物一起挡掉，即**洗信号**风险）。

    规则（照裁定逐条）：
      · 显式 **`non-derived`** ⇒ **`hard-reject`**（上游变更集只能指派生产物）
      · `derived` **且有** `source` ⇒ 计入 ok
      · **无标记**（缺 `origin` / `derived` 但无 `source`）⇒ 灰度期 **`soft-warn` + 审计**；
        在**白名单**内 ⇒ 放行（不告警）
    返回 `(verdict, hard, unmarked, notes)`；`verdict` 取**最重**的一档（hard > soft > ok）。
    ⚠ **已知边界（如实记）**：`origin`/`source` 仍是**调用方自报** —— 本判据只判"**有没有**可核标记"，
      **不判标记真假**（那要另一条链，未裁未做）。
    """
    hard, unmarked, notes = [], [], []
    wl = set(whitelist or ())
    for it in items or ():
        if isinstance(it, dict):
            iid, origin, src = it.get("id"), it.get("origin"), it.get("source")
        else:
            iid, origin, src = it, None, None
        if origin == "non-derived":
            hard.append(iid)
            notes.append(f"{iid}: 显式标为**非派生产物** ⇒ **硬拒**（D-26/D-51）")
        elif origin == "derived" and src:
            continue
        elif iid in wl:
            notes.append(f"{iid}: 无标记但在**白名单**内 ⇒ 放行（不告警）")
        else:
            unmarked.append(iid)
            notes.append(f"{iid}: **无可核来源标记** ⇒ 软警 + 审计（灰度期，收敛后收紧为硬拒）")
    if hard:
        return "hard-reject", hard, unmarked, notes
    if unmarked:
        return "soft-warn", hard, unmarked, notes
    return "ok", hard, unmarked, notes


def check_falsification_suite(cases, counterexamples, transform=None, whitelist=()):
    """★ `U4#6`：**以「证伪」替代「证明」**（不证 H-1 的"等价"，改证"**不等价会失败**"）。

    三件（照裁定逐条）：
      ① **测例集** `cases` = `[{"id":…, "prop": <boundary|idempotence|commutativity>}, …]`
         —— 三类**代数性质须全覆盖**（否则测例集不足以证伪）
      ② **反例清单** `counterexamples` = `[{"id":…, "historical": bool, "kind": "real-failure"}, …]`
         —— ★ 须含**至少一条「历史真实失效」**（凭空造的反例不算；"新失效必入"是纪律，机判不了）
      ③ **白名单** `whitelist` 限定**可开增量**的变换；`transform` 不在其中 ⇒ **`blocked`**
    返回 `(verdict, missing_props, notes)`，`verdict ∈ U4_FALSIFY_VERDICTS`。
    ⚠ `cases` 空 / 反例缺历史项 ⇒ `insufficient`（**不算通过**）。
    """
    props = {c.get("prop") for c in (cases or ()) if isinstance(c, dict)}
    missing = [p for p in U4_ALGEBRAIC_PROPS if p not in props]
    hist = [c for c in (counterexamples or ()) if isinstance(c, dict)
            and c.get("historical") and c.get("kind") == "real-failure"]
    notes = []
    if missing:
        notes.append(f"测例集未覆盖代数性质 {missing} ⇒ 不足以证伪")
    if not hist:
        notes.append("反例清单**没有**「历史真实失效」项 ⇒ 不足以证伪（凭空造的反例不算）")
    if missing or not hist:
        return "insufficient", missing, notes
    if transform is not None and transform not in set(whitelist or ()):
        notes.append(f"变换 {transform!r} 不在**可开增量白名单**内 ⇒ 不得开增量（blocked）")
        return "blocked", missing, notes
    return "ok", missing, notes


def runtime_selfcheck(sample_full, sample_incr):
    """★ `U4#6` ②：**运行时自检**（第二道防线）—— 增量前后在受影响子图上**抽样核全量**。

    `sample_full` / `sample_incr` = `{key: value}`。返回 `(verdict, detail)`：
      · `consistent`   —— 抽样逐键相等
      · `mismatch`     —— **不一致 ⇒ 增量结果不可信**（须回落全量）
      · `inconclusive` —— **抽样为空 ⇒ 判不了**（**不算通过**！"没抽到" ≠ "没问题"）
    """
    sf, si = dict(sample_full or {}), dict(sample_incr or {})
    if not sf and not si:
        return "inconclusive", "抽样为空 ⇒ 自检**判不了**（**不是通过**）"
    bad = [k for k in set(sf) | set(si) if sf.get(k) != si.get(k)]
    if bad:
        return "mismatch", f"抽样不一致 {sorted(bad)[:5]} ⇒ 增量结果**不可信**（回落全量）"
    return "consistent", f"抽样 {len(sf)} 项一致"


# ── ★ D7 协议契约（A 段 · 2026-10-01）：三信封 + 六相状态机 + 8 条纯函数拦截 ──────────
# 真值源 = `spec/d6-agent-standard/D7-PROTOCOL-CONTRACT.md`（**唯一**；本库**逐字照其 §1**）。
# 性质 = **纯函数判据库** —— 与 `decide_invalidation` / `verify_affected_closure` 同族：
#   **不是 CHECKS 项**、**不新增 gate id**（协议链路的对象在站上，本仓**零个真实信封**
#   ⇒ 眼下**没有可判的对象** ⇒ 只能判「**给一份信封 / 一次状态迁移 / 一次动作，它合法吗**」）。
# ★ 三段式定位（用户 2026-10-01 裁）：**A 离线契约化 → B 外壳接线 → C 站上真跑**。
#   A 段把"文档约束"变成"**可被机械拒绝的规则**" ⇒ B/C 段才有判据可接。本批 = **只做 A**。
# ⚠⚠ 与规范 §未实测 1–6 的关系（**如实，不冒充实测**）：A 段**不动**六相真跑那 6 条
#   （它们要真的站上跑，属 B/C）⇒ A 段只收口 **7 / 8 / 9**（三红线 / 三不变量 / 角色禁项）。
# ⚠ 契约自身的两处含糊在 A 段**已裁**（落回规范 §1.1 / §1.5）：① `verdict` 词义冲突；
#   ② §2 五行"依据不足"的处置 = **只判键在不在、不判内部结构**（射程到此为止，**不补齐**）。

# 六相状态名序列（§1 末行逐字）+ 出边（照 §1 表的"相 → 产出/动作"）。
D7_PHASES = ("drafted", "dispatched", "claimed", "executing", "collected",
             "mech_verified", "sem_verified", "accepted", "rejected")
D7_TERMINAL = ("accepted", "rejected")
D7_TRANSITIONS = {
    "drafted":       ("dispatched",),
    "dispatched":    ("claimed",),
    "claimed":       ("executing",),
    "executing":     ("collected",),
    "collected":     ("mech_verified",),
    # P4b 可选：`mech_verified` 既可进语义复核，也可**直接**裁决（跳过 P4b）
    "mech_verified": ("sem_verified", "accepted", "rejected"),
    "sem_verified":  ("accepted", "rejected"),
    "accepted":      (),
    "rejected":      (),
}
# §1 每相的"谁"⇒ 迁移的**驱动角色**（P1/P2/P3 由工作站，其余由主控站）。
D7_MASTER, D7_WORKER = "master", "worker"
D7_TRANSITION_ACTOR = {
    ("drafted", "dispatched"):        D7_MASTER,   # P0 立契
    ("dispatched", "claimed"):        D7_WORKER,   # P1 领取
    ("claimed", "executing"):         D7_WORKER,   # P2 执行
    ("executing", "collected"):       D7_WORKER,   # P3 回收（工作站产出 RunReport）
    ("collected", "mech_verified"):   D7_MASTER,   # P4a 机械验证
    ("mech_verified", "sem_verified"): D7_MASTER,  # P4b 语义复核（可选）
    ("mech_verified", "accepted"):    D7_MASTER,   # P5（跳过 P4b）
    ("mech_verified", "rejected"):    D7_MASTER,
    ("sem_verified", "accepted"):     D7_MASTER,   # P5
    ("sem_verified", "rejected"):     D7_MASTER,
}

# 三信封（字段级，§1.1 逐字）。`nested` **只收摘要在字面上给出的子键**
# （`golden{ref,checksum}` / `inputs{ref,digest}` / `evidence_budget{anchors,tool_calls}` /
#  `artifact{digest,size}`）—— 摘要**没给**的一律**不判、不补**（§2 五行的处置）。
D7_ENVELOPES = {
    "TaskContract": {
        "required": ("task_id", "task_desc", "accept", "golden", "inputs",
                     "evidence_budget", "constraints", "timeout_s", "sensitivity", "readonly"),
        "nested": {"golden": ("ref", "checksum"),
                   "inputs": ("ref", "digest"),
                   "evidence_budget": ("anchors", "tool_calls")},
        "forbidden": (),
    },
    "RunReport": {
        "required": ("run_id", "attempt", "artifact", "inputs_digest", "exit_code",
                     "decisions", "evidence", "usage"),
        "nested": {"artifact": ("digest", "size")},
        # ★★ 红线「产出方不得自评」的**机判形态**：`RunReport` 刻意不含 verdict 字段（§1.1 ★）
        "forbidden": ("verdict",),
    },
    "Verdict": {
        "required": ("verdict", "phase", "l1_results", "recorded_at", "seq"),
        "nested": {},
        "forbidden": (),
    },
}
# 判官**四值**（属**结论契约** `D7-PROTOCOL-CONCLUSION-CONTRACT`；承载 = `judge-prompt.tmpl` +
# `Test-ConclusionContract` 的 `$enum`）—— ★ 与 D7 信封**顶层**的 `verdict`（exit code）**同名不同物**；
# A 段裁 = 靠**载体 + 值类型**机械切分：★ 本仓 `review.json` **顶层没有 `verdict` 键**，
# 四值落在**嵌套**的 `review.json.contract.verdict`（E1 读码：`Invoke-Review` 的 `$ccSection`）
# ⇒ 顶层键集**不相交**；即便有人把四值提到顶层，它是字符串 ⇒ 仍落拒。
D7_VERDICT_WORDS = ("accept", "revise", "reject", "uncertain")
D7_ENV_VERDICTS = ("ok", "reject")


def validate_envelope(kind, env):
    """★ D7 三信封的**离线校验器**（缺字段即拒；`RunReport` 含 `verdict` 即拒）。

    返回 `(verdict, reason)`，`verdict ∈ D7_ENV_VERDICTS`（**封闭两值**）。
    ⚠ **fail-closed**：`kind` 不在闭集 / `env` 不是对象 ⇒ **reject**（**不是**"跳过"）。
    ⚠ **射程（= §2 五行「依据不足」的处置，落回规范 §1.5）**：只判**顶层必需键在不在** +
      **摘要逐字给出的子键**；`constraints` / `decisions[]`（八字段）/ `sensitivity` /
      `redispatch?` 的内部结构**一律不判、不补** —— 摘要没给 ⇒ 补它就是**编真值**。
    ★ **红线 3 的机判入口**：`TaskContract.accept[]` 每项须同时有判据与 `criteria_hash`
      （§1.1 逐字「判据 + `criteria_hash`」）—— 没有它，"判据在 P0 固化"无从机判。
    """
    if kind not in D7_ENVELOPES:
        return "reject", (f"未知信封 kind={kind!r}（闭集 {tuple(D7_ENVELOPES)}）"
                          f" ⇒ 拒（fail-closed：未知一律不放行）")
    if not isinstance(env, dict):
        return "reject", f"信封 {kind} 不是对象（{type(env).__name__}）⇒ 拒"
    spec = D7_ENVELOPES[kind]
    miss = [k for k in spec["required"] if k not in env]
    if miss:
        return "reject", f"{kind} 缺必需字段 {miss} ⇒ 拒（缺字段即拒）"
    for k, sub in spec["nested"].items():
        v = env.get(k)
        if not isinstance(v, dict):
            return "reject", f"{kind}.{k} 不是对象（摘要逐字给出子键 {sub}）⇒ 拒"
        smiss = [s for s in sub if s not in v]
        if smiss:
            return "reject", f"{kind}.{k} 缺子键 {smiss} ⇒ 拒（逐字列出，不得省）"
    hit = [k for k in spec["forbidden"] if k in env]
    if hit:
        return "reject", (f"{kind} 含禁字段 {hit} ⇒ **拒** —— 产出方不得自评"
                          f"（§1.1 ★：`RunReport` 刻意不含 verdict 字段）")
    if kind == "TaskContract":
        acc = env.get("accept")
        if not isinstance(acc, list) or not acc:
            return "reject", "TaskContract.accept 必须**非空列表**（无判据 = 无从裁决）⇒ 拒"
        for i, item in enumerate(acc):
            if not isinstance(item, dict) or not item.get("criteria") or not item.get("criteria_hash"):
                return "reject", (f"TaskContract.accept[{i}] 须**同时**给判据与 `criteria_hash`"
                                  f" ⇒ 拒（红线 3 的机判入口：判据与 golden 哈希在 P0 固化）")
    if kind == "RunReport" and not isinstance(env.get("decisions"), list):
        return "reject", "RunReport.decisions 必须是列表（八字段在**每项**里；内部结构不判）⇒ 拒"
    if kind == "Verdict":
        v = env.get("verdict")
        if isinstance(v, bool) or not isinstance(v, int):
            return "reject", (f"Verdict.verdict 必须是**整数**（= exit code）；实得 {v!r}"
                              f" ⇒ 拒（★ 词义冲突的机械切分：判官四值 {list(D7_VERDICT_WORDS)}"
                              f" 属**结论契约**（嵌套落在 `review.json.contract.verdict`），**不属**本信封）")
    return "ok", f"{kind} 信封**字段级合法**（顶层 {len(spec['required'])} 项齐）"


def d7_transition(state, to_state, actor):
    """★ D7 六相状态机（P0–P5）的**纯函数**：合法迁移给下一态，非法给**拒绝理由**。

    返回 `(ok, next_state, reason)`；`next_state` 仅在 ok 时非 None。
    规则（照 §1 的状态名序列 + 每相的"谁"）：
      · **单链**：`drafted→dispatched→claimed→executing→collected→mech_verified`
      · `mech_verified` 分叉：`→sem_verified`（P4b **可选**）或**直接** `→accepted|rejected`
      · `sem_verified →accepted|rejected` · 终态**无出边**
      · ★ **角色约束**：P1/P2/P3 段由**工作站**驱动，P0/P4a/P4b/P5 由**主控站**驱动
        —— 角色不对 ⇒ **拒**（角色禁项的机判入口）。
      · ⚠ **不得跳过 L1**：`collected` **不能**直落 `accepted|rejected`（红线 2）。
      · ⚠ **fail-closed**：未知态 / 未知目标 / `actor` 不在闭集 ⇒ **拒**（不静默放行）。
    """
    if state not in D7_PHASES:
        return False, None, f"未知当前态 {state!r}（闭集 {D7_PHASES}）⇒ 拒（fail-closed）"
    if to_state not in D7_PHASES:
        return False, None, f"未知目标态 {to_state!r} ⇒ 拒（fail-closed）"
    allowed = D7_TRANSITIONS[state]
    if not allowed:
        return False, None, f"{state} 是**终态**（无出边）⇒ 拒绝任何迁移（到 {to_state}）"
    if to_state not in allowed:
        why = ("**不得跳过 L1 机械门**（红线 2：L1 先于 L2/裁决）"
               if (state == "collected" and to_state in D7_TERMINAL) else f"合法出边只有 {allowed}")
        return False, None, f"{state} → {to_state} **不是合法迁移**：{why} ⇒ 拒"
    if actor not in (D7_MASTER, D7_WORKER):
        return False, None, (f"未知角色 actor={actor!r}（闭集 {D7_MASTER}/{D7_WORKER}）"
                             f" ⇒ 拒（fail-closed）")
    want = D7_TRANSITION_ACTOR.get((state, to_state))
    if want is not None and actor != want:
        return False, None, f"{state} → {to_state} 应由**{want}**驱动，实为 {actor} ⇒ 拒（角色不对）"
    return True, to_state, f"{state} → {to_state} 合法（{want} 驱动）"


# ★ 8 条纯函数拦截 = **三红线 + 三不变量 + 两角色禁项**（§1.2 / §1.3 / §1.4 逐字）。
# ⚠ 红线 1 与不变量 I-3 **内容相同**（完成信号权在主控站）⇒ **同一实现登记两个规则 id**，
#   不写两份实现（"同一事实两处表达"是本仓头号失败形态）。
D7_BLOCK_RULES = (
    ("RL1", "红线 1 · 完成信号权只在主控站"),
    ("RL2", "红线 2 · L1 机械门先于 L2 且 L2 无权改写"),
    ("RL3", "红线 3 · 判据与 golden 哈希在 P0 固化"),
    ("I1",  "不变量 I-1 · 单写者（事件流只有主控站可写）"),
    ("I3",  "不变量 I-3 · 完成信号权在主控站"),
    ("I6",  "不变量 I-6 · fail-closed"),
    ("PRM", "角色禁项 · 主控站不执行任务本体"),
    ("PRW", "角色禁项 · 工作站不自评/不写 verdict/不重派/不合并"),
)
D7_WORKER_FORBIDDEN = ("self_accept", "write_verdict", "redispatch", "merge")


def _d7_blk_completion(actor=None):
    """RL1 ≡ I-3：**完成信号权只在主控站**（同一实现登记两个 id）。"""
    if actor == D7_MASTER:
        return True, "主控站发出完成信号（accepted/rejected）⇒ 合法"
    return False, f"{actor!r} 不得发出完成信号 ⇒ 拒（红线 1 / 不变量 I-3：完成信号权只在主控站）"


def _d7_blk_l1_l2(l1_results=None, l2_marks=None, l2_rewrites_l1=False):
    """RL2：**L1 机械门先于 L2，且 L2 无权改写 L1**。"""
    if l2_rewrites_l1:
        return False, "L2 改写了 L1 结果 ⇒ 拒（红线 2：L2 无权改写 L1）"
    if l2_marks and not l1_results:
        return False, "有 L2 结果却**无** L1 结果 ⇒ 拒（红线 2：L1 必须先于 L2）"
    return True, "L1 先于 L2 且 L2 未改写 L1 ⇒ 合法"


def _d7_blk_frozen(hash_p0=None, hash_now=None):
    """RL3：**判据与 golden 哈希在 P0 固化**（= "判据不能事后改"）。"""
    if not hash_p0 or not hash_now:
        return False, ("P0 固值或现值缺失 ⇒ **判不了** ⇒ 拒（fail-closed：取不到固值就不能"
                       "声称「未改」—— 红线 3 要求判据与 golden 哈希在 P0 固化）")
    if hash_p0 != hash_now:
        return False, (f"判据/golden 哈希与 P0 固值不符（{hash_p0!r} ≠ {hash_now!r}）"
                       f" ⇒ 拒（红线 3：判据不能事后改）")
    return True, "判据/golden 哈希与 P0 固值一致 ⇒ 合法"


def _d7_blk_single_writer(actor=None, target=None):
    """I-1：**单写者** —— 事件流只有主控站可写，工作站只产出不落账。"""
    if target != "events":
        return True, f"目标 {target!r} 不在本约束射程内（约束只覆盖 `events` 事件流）"
    if actor == D7_MASTER:
        return True, "主控站写事件流 ⇒ 合法"
    return False, f"{actor!r} 不得写 `events` 事件流 ⇒ 拒（不变量 I-1：单写者）"


def _d7_blk_fail_closed(decision=None):
    """I-6：**fail-closed** —— 判不了 ⇒ 拒，**绝不**落通过。"""
    if decision == "pass":
        return True, "决策**显式** `pass` ⇒ 放行"
    return False, (f"决策 {decision!r} 不是显式 `pass` ⇒ 拒（不变量 I-6：缺失 / 未知 / `reject`"
                   f" 一律**不得**静默通过）")


def _d7_blk_master_scope(actor=None, action=None):
    """角色禁项：**主控站「不执行任务本体」**。"""
    if actor == D7_MASTER and action == "execute_task":
        return False, "主控站**执行任务本体** ⇒ 拒（角色禁项：主控站只立契/验证/裁决，不执行）"
    return True, f"主控站未执行任务本体（action={action!r}）⇒ 合法"


def _d7_blk_worker_scope(actor=None, action=None):
    """角色禁项：**工作站「不自评通过、不写 verdict、不重派、不合并」**。"""
    if actor == D7_WORKER and action in D7_WORKER_FORBIDDEN:
        return False, f"工作站执行禁项 {action!r} ⇒ 拒（禁项集 {D7_WORKER_FORBIDDEN}）"
    return True, f"工作站未触禁项（action={action!r}）⇒ 合法"


# 规则 id → 实现（RL1 与 I3 **共用** `_d7_blk_completion`，见上）
D7_BLOCK_FNS = {
    "RL1": _d7_blk_completion, "I3": _d7_blk_completion,
    "RL2": _d7_blk_l1_l2,      "RL3": _d7_blk_frozen,
    "I1":  _d7_blk_single_writer, "I6": _d7_blk_fail_closed,
    "PRM": _d7_blk_master_scope, "PRW": _d7_blk_worker_scope,
}


def d7_block(rule, **ctx):
    """**统一入口**：按规则 id 调 8 条拦截之一 ⇒ `(ok, reason)`。

    ⚠ 未知规则 id ⇒ **拒**（fail-closed；**不**静默返回 ok）。
    """
    fn = D7_BLOCK_FNS.get(rule)
    if fn is None:
        return False, (f"未知规则 id {rule!r}（闭集 {[r for r, _ in D7_BLOCK_RULES]}）"
                       f" ⇒ 拒（fail-closed）")
    return fn(**ctx)


# ── ★★ D7 判据的**消费面**（B 段 · 2026-10-01）────────────────────────────────────
# 为什么要有：判据本体是**纯函数**（上面那一段），而**调用方是外壳**
#   （`ops/station-bin/agent-cli.ps1`）⇒ 若外壳**重写一份**判据，就是"同一事实两处表达"
#   （本仓头号失败形态）。⇒ 这里给一个**薄 CLI**：外壳把「信封 / 迁移 / 动作」喂进来，
#   判据**只在这一处**（同 `Invoke-GateCheck` 调 `py ops/rpc_check.py` 的既有形态）。
# ⚠ **不是 CHECKS 项、不新增 gate id**（同 A 段）；它**不读写仓库文件**（只读入参）
#   ⇒ 不进任何门禁的射程 —— 它的护栏是 `tests/test_rpc_check_d7_protocol.py` 的 CLI 用例。
# 退出码（三态，**不可混**）：`0` = ok · `1` = **reject**（判据给了拒绝理由）·
#   `2` = **无法判**（入参读不到 / 解析失败 ⇒ fail-closed，**不是** ok，也不冒充 reject）。
D7_CLI_EXIT_UNDECIDABLE = 2


def _d7_cli_read(src):
    """读一个 JSON 入参：`'-'` = stdin，其余 = 文件路径（`utf-8-sig` 容忍 BOM）。"""
    raw = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8-sig")
    return json.loads(raw)


# ── ★★ B3（2026-10-01）：角色**同机**可见性判据 `PRH`（**不是拦截**，是"看得见"）──────────
# 裁定依据（用户 2026-10-01 裁【甲】；落点 = 契约 §1.4 的角色化 + §1.6 的三句裁）：
#   §1.4 的「主控站 / 工作站」= **角色**（主控角色驱动 P0/P4a/P4b/P5；工作站角色驱动 P1/P2/P3），
#   **不是机器** ⇒ 主控机器上的出网通道以 `worker` 角色登记，**不触** `PRM`。
#   ★ **但**"同一台机器既产出又裁决"这件事**必须被看见** —— 它直接影响裁决独立性
#     （红线 1「完成信号权只在主控站」真正想保的是"**产出方不得自评**"）。
# ⚠⚠ **它刻意不进 `D7_BLOCK_RULES` / `D7_BLOCK_FNS`**：那 8 条的口径是"三红线 + 三不变量 +
#   两角色禁项"，本项**不属于**其中任何一类；把"报数"混进"拦截"会让 8 条的计数失去意义
#   （同 `inventory/ops.yaml` 把 `entry_modules` 从 `entry` 拆出的理由）。
# ⚠ **不设阈值**（`O-126`：不许用凭空数值满足可机判）—— **先量后定档**：读数出来再由人裁
#   要不要把它升级为**拒**（= PRM 分析里的方案②「物理分离」）。
#   ★ 收紧条件（写死）：**同机占比有读数 + 用户裁「升级为拒」** ⇒ 才改调用方，**不改本判据**。★ **已定档（2026-10-10 · 用户裁）**：前置（≥1 次同机形态）**2026-10-08 已满足**（同机 1 次）⇒ 裁 = **维持报数**（`PRH` 仍只到"同不同机"、**不改调用方**）；★ 日后若取「拦」，两条硬前置 = **先落「判官与产出者是否同模型」读数**（否则拦的是代理量）+ 按 `O-140` 形状配**显式通道 + 留痕**（**不新造机制**）。
D7_HOST_SEP_RULE = "PRH"


def d7_host_separation(exec_host=None, arbiter_host=None):
    """`PRH`：**产出机 vs 裁决机**的同机可见性 ⇒ `(same, reason)`，`same ∈ {True, False, None}`。

    ⚠ **fail-closed 的方向在这里是"不可判"而不是"拒"**：缺任一 host ⇒ `same=None`
      （**不可判**）⇒ 调用方必须**如实报出**，**不许**静默读成"不同机"
      （本仓口径：判不了 ≠ 通过，同 `O-22` / `O-119`）。
    ⚠ 本判据**只判"是否同一台机器"**：它**不判**"该形态合不合规"（那是用户的裁）。
    """
    e = str(exec_host or "").strip()
    a = str(arbiter_host or "").strip()
    if not e or not a:
        return None, (f"判不了（exec_host={exec_host!r} / arbiter_host={arbiter_host!r}）"
                      f" ⇒ **不可判**（缺一即不可判，不得静默读成「不同机」）")
    if e == a:
        return True, (f"**同机**：产出机 == 裁决机 == {e} ⇒ 裁决独立性打折"
                      f"（红线 1 想保的「产出方不得自评」，此形态下**只有角色分离、无机器分离**）")
    return False, f"**分离**：产出机 {e} ≠ 裁决机 {a} ⇒ 机械独立"


def d7_cli(args):
    """**消费面**：按 `args` 跑对应判据 ⇒ 退出码（见上）。命中则返回 int，未命中返回 `None`。"""
    if not (args.d7_envelope or args.d7_transition or args.d7_block or args.d7_host_sep):
        return None
    try:                                  # 只在本入口改编码：门禁自身的输出行为**零改动**
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if args.d7_envelope:
        kind, src = args.d7_envelope
        try:
            env = _d7_cli_read(src)
        except Exception as e:
            print(f"D7_ENVELOPE undecidable {kind}: 读不到/解析失败 "
                  f"{type(e).__name__}: {e} ⇒ fail-closed")
            return D7_CLI_EXIT_UNDECIDABLE
        v, why = validate_envelope(kind, env)
        print(f"D7_ENVELOPE {v} {kind}: {why}")
        return 0 if v == "ok" else 1
    if args.d7_transition:
        a, b, actor = args.d7_transition
        ok, _nxt, why = d7_transition(a, b, actor)
        print(f"D7_TRANSITION {'ok' if ok else 'reject'} {a} -> {b} ({actor}): {why}")
        return 0 if ok else 1
    if args.d7_host_sep:
        # ★ 三态不可混：0 = 分离 · 1 = **同机**（判据确实给出了结论）· 2 = 不可判（缺 host）。
        #   ⚠ 调用方（外壳）对 `1` 按 **WARN** 处理（灰度，同 B1 的 gaps）—— 那是**调用方的政策**，
        #   不是本判据的语义（本判据只说"同不同机"）。
        e, a = args.d7_host_sep
        same, why = d7_host_separation(e, a)
        if same is None:
            print(f"D7_HOSTSEP undecidable: {why}")
            return D7_CLI_EXIT_UNDECIDABLE
        print(f"D7_HOSTSEP {'same' if same else 'separate'}: {why}")
        return 1 if same else 0
    try:
        ctx = _d7_cli_read(args.d7_ctx) if args.d7_ctx else {}
    except Exception as e:
        print(f"D7_BLOCK undecidable {args.d7_block}: ctx 解析失败 {type(e).__name__}: {e}"
              f" ⇒ fail-closed")
        return D7_CLI_EXIT_UNDECIDABLE
    if not isinstance(ctx, dict):
        print(f"D7_BLOCK undecidable {args.d7_block}: ctx 不是对象 ⇒ fail-closed")
        return D7_CLI_EXIT_UNDECIDABLE
    try:
        ok, why = d7_block(args.d7_block, **ctx)
    except Exception as e:
        # ★★ B2 实测抓到的**真缺陷**：`ctx` 与判据的**输入契约不符**（多传/拼错键）时，
        #   `**ctx` 展开会抛 `TypeError` ⇒ 进程**非零退出（1）** —— 而 1 在本 CLI 的语义是
        #   **reject**（判据给出了拒绝理由）⇒ **崩溃被冒充成"判据拒绝了"**（三态不可混被破坏）。
        #   ⇒ 归 **`undecidable`（2）**：这不是"判据说不行"，是"**判据没能跑**"（同 O-22/`O-119` 口径）。
        print(f"D7_BLOCK undecidable {args.d7_block}: ctx 与判据的输入契约不符 "
              f"（{type(e).__name__}: {e}）⇒ fail-closed —— **不是 reject**")
        return D7_CLI_EXIT_UNDECIDABLE
    print(f"D7_BLOCK {'ok' if ok else 'reject'} {args.d7_block}: {why}")
    return 0 if ok else 1


# ── D7-P1-5 (2026-09-26)：U-5 信任基座四问 V-1~V-4 + 晋升门 schema ────────────
# 两部分：
#   ① **四问各一条可机判判据**（`v1_definition_correspondence` / `v2_bridge_completeness` /
#      `v3_axiom_whitelist` / `v4_build_reproducible`）—— 纯函数，**不是** `CHECKS` 项
#      （本仓没有形式化信任基座的对象可判：**V-2 真空** · V-1/V-4 各仅 1 项目 · V-3 仅关键词级，见 D-37）；
#   ② **晋升门 schema**（`inventory/promotion.yaml`）—— ★ **这一半是 `CHECKS` 项**（`promotion`），
#      因为**被判的对象真实存在**（schema 自身 + 三处实现的映射）⇒ **不是空判**。
#
# ★ 已裁（台账 D-38）：把三处独立发明的晋升门**统一为一个 schema**（判据 = 成功率 / 复发次数 /
#   验证状态，**并存于同一 schema 的不同字段**），**不许发明第四种**。
#   ⇒ 本断言的**核心规则是"映射闭包"**：schema 里**不许有孤儿字段 / 孤儿判据** ——
#     一个没被任何一处实现用到的字段，就是**变相发明的第四种**。
# ★ 依据：合并稿 §6.3（V-1~V-4 规格书）· §11.5（三处晋升门实测）· §11.7（不得自审只能靠结构）
#   · 台账 D-37（四问列为验收项）· D-38（统一 schema）。
PROMOTION_INV = ROOT / "inventory" / "promotion.yaml"
PROMO_OPS = (">=", "<=", "==", ">", "<", "!=")
PROMO_POLICIES = ("lru", "fifo")
# D-38 的落地：这三种判据**必须并存**（各自来自一处真实实现）
PROMO_REQUIRED_CRITERIA = ("success_rate", "recurrence", "verified")


def _promo_cmp(lhs, op, rhs):
    """*纯*比较器（`op ∈ PROMO_OPS`）；类型不合 ⇒ `False`（**不抛** —— 一条脏条目不该炸掉整份判定）。"""
    try:
        if op == ">=":
            return lhs >= rhs
        if op == "<=":
            return lhs <= rhs
        if op == "==":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        if op == ">":
            return lhs > rhs
        if op == "<":
            return lhs < rhs
    except TypeError:
        return False
    return False


def promotion_entry_verdict(entry, gate):
    """★ `U5#5`（2026-09-30 · 批 4）：把**一条真实条目**喂给 `gate` ⇒ `(ok, reasons, satisfied)`。

    ⚠⚠ **本批补的是一个真缺口，不只是"扩样例"**：此前 `validate_promotion` 只判 **schema 自身**
      （字段 / 判据 / 映射闭包 / `entries` 是不是列表）—— **从不把任何条目喂给 `gate.required` / `gate.criteria`**
      ⇒ 「实例 0 条」比它看起来更糟：**即便加一条，也没有任何东西会检查它**（schema 是"**只可读、不可走**"的）。
    ⇒ 本函数把 `gate` 变成**可走的**：`required` 缺 ⇒ 不可晋升；`criteria` **任一满足** ⇒ 可晋升；
      「字段没给」⇒ 该判据**不满足**（**不是**"跳过"、更**不是**"默认满足"）。
    ⚠ **不给阈值就不能假定**：`ref` 指向的门槛字段未给 ⇒ 该判据**不满足**（阈值未定 = `unverified` 已登记）
      —— **不许**替它填一个数（那正是 `O-126` 点名的"用凭空数值满足可机判"）。
    """
    if not isinstance(entry, dict):
        return False, [f"条目不是映射: {entry!r}"], []
    hard = []
    for f in (gate.get("required") or []):
        v = entry.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            hard.append(f"缺必填字段 `{f}`（Spec_Workflow 原文：**缺锚点不得登记**）")
    satisfied, crit_note = [], []
    for c in (gate.get("criteria") or []):
        fld, op, ref = c.get("field"), c.get("op"), c.get("ref")
        if isinstance(ref, str) and ref.startswith("$"):
            rhs = entry.get(ref[1:])
            if rhs is None:
                crit_note.append(f"判据 `{c.get('id')}` **不满足**：门槛 `{ref[1:]}` 未给（阈值未定 ⇒ 不许假定）")
                continue
        else:
            rhs = ref
        lhs = entry.get(fld)
        if lhs is None:
            crit_note.append(f"判据 `{c.get('id')}` **不满足**：条目未给 `{fld}`")
            continue
        if _promo_cmp(lhs, op, rhs):
            satisfied.append(c.get("id"))
    if hard:
        return False, hard, satisfied
    if not satisfied:
        return False, crit_note + ["**没有任何判据满足** ⇒ 不得晋升（三种判据**任一**满足才可；"
                                   "并列语义本身仍是 `unverified` 登记项）"], []
    return True, [], satisfied


def validate_promotion(doc):
    """**纯函数** → `(bad, notes)`：晋升门 schema 的自洽 + **映射闭包** + ★ **逐条目走一遍门**。"""
    bad, notes = [], []
    if not isinstance(doc, dict):
        return ["promotion.yaml 顶层不是映射（结构改了？）"], notes

    fields = doc.get("fields") or []
    fids = [f.get("id") for f in fields if isinstance(f, dict)]
    if not fields:
        bad.append("`fields` 为空 ⇒ 判据没有字段可引用")
    if len(fids) != len(set(fids)):
        bad.append(f"`fields` 的 id 有重复: {fids}")
    for f in fields:
        if not (isinstance(f, dict) and f.get("id") and f.get("type")):
            bad.append(f"`fields` 有条目缺 id/type: {f!r}")
    ftype = {f["id"]: f.get("type") for f in fields if isinstance(f, dict) and f.get("id")}

    gate = doc.get("gate") or {}
    req = gate.get("required") or []
    if not req:
        bad.append("`gate.required` 为空 ⇒ 没有“必填”就没有门（Spec_Workflow 的『缺锚点不得登记』落不下）")
    for r in req:
        if r not in fids:
            bad.append(f"`gate.required` 的 {r!r} 不在 `fields` 里")

    cap = gate.get("capacity") or {}
    if not cap:
        bad.append("`gate.capacity` 缺失 ⇒ 容量件套没落地（Textbook `FixMemory` 的三件套之一）")
    else:
        if cap.get("field") not in fids:
            bad.append(f"`gate.capacity.field`={cap.get('field')!r} 不在 `fields` 里")
        if not isinstance(cap.get("max"), int) or cap.get("max", 0) <= 0:
            bad.append(f"`gate.capacity.max` 必须是正整数: {cap.get('max')!r}")
        if cap.get("policy") not in PROMO_POLICIES:
            bad.append(f"`gate.capacity.policy`={cap.get('policy')!r} 不在封闭集 {PROMO_POLICIES}")

    crit = gate.get("criteria") or []
    cids = [c.get("id") for c in crit if isinstance(c, dict)]
    if not crit:
        bad.append("`gate.criteria` 为空 ⇒ 没有任何晋升判据")
    if len(cids) != len(set(cids)):
        bad.append(f"`gate.criteria` 的 id 有重复: {cids}")
    for c in crit:
        if not isinstance(c, dict):
            bad.append(f"`gate.criteria` 有条目不是映射: {c!r}")
            continue
        cf, ref = c.get("field"), c.get("ref")
        if cf not in fids:
            bad.append(f"`criteria[{c.get('id')}].field`={cf!r} 不在 `fields` 里")
        if c.get("op") not in PROMO_OPS:
            bad.append(f"`criteria[{c.get('id')}].op`={c.get('op')!r} 不在封闭集 {PROMO_OPS}")
        if isinstance(ref, str) and ref.startswith("$"):
            tgt = ref[1:]
            if tgt not in fids:
                bad.append(f"`criteria[{c.get('id')}].ref` 引用了不存在的字段 {tgt!r}")
            elif cf in ftype and ftype.get(tgt) != ftype.get(cf):
                bad.append(f"`criteria[{c.get('id')}]` 的类型不匹配: {cf}({ftype.get(cf)}) "
                           f"{c.get('op')} {tgt}({ftype.get(tgt)})")
    miss_crit = [x for x in PROMO_REQUIRED_CRITERIA if x not in cids]
    if miss_crit:
        bad.append(f"**D-38 要求三种判据并存**，但缺 {miss_crit} ⇒ 那等于**发明第四种**或丢掉一种")

    struct = gate.get("structure") or []
    if not struct:
        bad.append("`gate.structure` 为空 ⇒ §11.7『不得自审只能靠结构』没落地")

    # ── ★ 映射闭包（本断言的核心：不许孤儿字段 / 孤儿判据）───────────────
    maps = doc.get("mapping_closure") or []
    if not maps:
        bad.append("`mapping_closure` 为空 ⇒ D-38『schema 须能被三处各自映射』**没有被判**")
    used_fields, used_crit = set(), set()
    for m in maps:
        if not isinstance(m, dict):
            bad.append(f"`mapping_closure` 有条目不是映射: {m!r}")
            continue
        mid = m.get("id")
        u = m.get("uses") or []
        cu = m.get("criteria_used") or []
        if not u:
            bad.append(f"`mapping_closure[{mid}]` 没声明 `uses`")
        if not cu:
            bad.append(f"`mapping_closure[{mid}]` 没声明 `criteria_used`（映射了却不用任何判据？）")
        for x in u:
            if x not in fids:
                bad.append(f"`mapping_closure[{mid}].uses` 含**不存在的字段** {x!r}")
        for x in cu:
            if x not in cids:
                bad.append(f"`mapping_closure[{mid}].criteria_used` 含**不存在的判据** {x!r}")
        used_fields |= set(u)
        used_crit |= set(cu)
    orphan_f = [f for f in fids if f not in used_fields]
    if orphan_f:
        bad.append(f"**孤儿字段** {orphan_f} ⇒ 没有任何一处实现用到它（= 变相发明第四种，D-38 不许）")
    orphan_c = [c for c in cids if c not in used_crit]
    if orphan_c:
        bad.append(f"**孤儿判据** {orphan_c} ⇒ 没有一处实现用它")
    notes.append(f"字段 {len(fids)} · 判据 {len(cids)} · 三处映射 {len(maps)}")

    if "entries" not in doc:
        bad.append("**缺 `entries` 字段** ⇒ 无法区分「没有条目」与「忘了写」")
    else:
        ents = doc["entries"] or []
        if not isinstance(ents, list):
            bad.append(f"`entries` 不是列表（{type(ents).__name__}）")
        elif not ents and not str(doc.get("empty_reason") or "").strip():
            bad.append("`entries` 为空**且没有 `empty_reason`** ⇒ 空得没说法")
        elif not ents:
            notes.append("实例 0 条 (空已显式报出, 不静默通过)")
        else:
            # ★ `U5#5`（批 4）：**逐条目走一遍门** —— 容量件套 + `gate.required` + `criteria`（任一满足）
            cap_max = (gate.get("capacity") or {}).get("max")
            if isinstance(cap_max, int) and len(ents) > cap_max:
                bad.append(f"`entries` {len(ents)} 条 > `gate.capacity.max`={cap_max} ⇒ 容量件套被绕过")
            n_ok = 0
            for i, e in enumerate(ents):
                ok_e, why, _sat = promotion_entry_verdict(e, gate)
                if ok_e:
                    n_ok += 1
                    continue
                eid = (e or {}).get("id", "?") if isinstance(e, dict) else repr(e)
                bad.append(f"`entries[{i}]`({eid}) **不可晋升**: " + " ; ".join(why))
            notes.append(f"实例 {len(ents)} 条 · **可晋升 {n_ok} · 拦截 {len(ents) - n_ok}**"
                         f"（判据 = `gate.required` + `gate.criteria` **任一满足**）")

    if not (doc.get("unverified") or []):
        bad.append("`unverified` 为空 ⇒ 本 schema 里**新设**的东西没被如实登记（新设项 = 最像“第四种”的地方）")
    return bad, notes


def check_promotion(ctx):
    """D7-P1-5: U-5 晋升门 schema（`inventory/promotion.yaml`）。"""
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 promotion 晋升门断言", []
    if not PROMOTION_INV.exists():
        return "FAIL", "inventory/promotion.yaml 缺失（本断言的登记依据）", []
    try:
        doc = yaml.safe_load(PROMOTION_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"inventory/promotion.yaml 解析失败: {type(e).__name__}: {e}", []
    bad, notes = validate_promotion(doc)
    return ("FAIL" if bad else "PASS"), " · ".join(notes), bad


# ── U-5 的**四问判据**（V-1~V-4）—— 判据库，不是 CHECKS 项 ──────────────────
# ⚠ 不判本仓状态：**V-2 真空 · V-1/V-4 各仅 1 项目 · V-3 仅关键词级**（D-37 的实况）
#   ⇒ 本仓没有对象 ⇒ 只被测试驱动（与 U-4 的 `decide_invalidation` 同形）。
# ★ 四条判据各自对上一处"最接近"的实现（§6.3），并把它从"人看"升为"机判"——
#   尤其 V-3：原文要求「从**关键词级**升为**白名单级**」，本判据就是白名单比对。
def v3_axiom_whitelist(axioms, whitelist=None):
    """V-3 信任基座：**公理集必须 ⊆ 显式声明的白名单**。

    ★★ **`U5#4`（2026-09-30 裁 / `O-123`）：裁掉"默认名单"这一形态。**
      · `whitelist is None` = **根本没声明** ⇒ **判不通过**（fail-closed）。
        旧实现回落到 `("propext","Classical.choice","Quot.sound")` —— 而那是**原文举例**；
        本规范自己写着「**取自举例 ≠ 裁定**」⇒ 拿它当缺省 = **把举例升格成裁定**（本仓最典型的一类**假精确**）。
      · `whitelist == []` = **显式空声明** ⇒ **合法**（语义 = 「**确实不需要额外公理**」）。
        ★ 这正是本裁要区分的那对：**「确实不需要额外公理」 vs 「根本没声明」**（旧实现里二者**同值** ⇒ 无法区分）。
    ⚠ 空声明**不是**"判据恒真"：此时任何公理都落在白名单外 ⇒ 仍会红（见 `extra` 分支）。
    ⚠ 本函数第一版的自伤（历史，见 `docs/2026-09-23_D6-D7分阶段执行方案.md`）：把 `whitelist=[]` 与 `None` 混同
      ⇒ "白名单为空 ⇒ fail" 那段**永远到不了**。
    """
    if whitelist is None:
        return False, ["**未声明公理白名单** ⇒ 判不通过（本题已裁掉「默认名单」形态："
                       "「取自原文举例」**不等于裁定**；缺声明 = 判不了 ⇒ fail-closed）"]
    wl = tuple(whitelist)                       # 显式空 ⇒ 合法（"确实不需要额外公理"）
    extra = sorted(set(axioms or []) - set(wl))
    if extra:
        return False, [f"白名单外公理 {extra}（V-3 要求白名单级，不许关键词级放过）"]
    return True, []


def v4_build_reproducible(deps, ledger=None):
    """V-4 构建可复现性：**每个依赖都钉到 rev**，且 ledger 记版本与 input-hash。"""
    bad = []
    for d in (deps or []):
        if not isinstance(d, dict) or not d.get("name"):
            bad.append(f"依赖条目缺 name: {d!r}")
        elif not d.get("rev"):
            bad.append(f"依赖 {d.get('name')!r} **未钉 rev** ⇒ 第三方无法复现（V-4）")
    if not (ledger or {}).get("tool_versions"):
        bad.append("ledger 缺 `tool_versions`（构建工具/库版本）⇒ V-4 要求的可追溯缺失")
    if not (ledger or {}).get("input_hash"):
        bad.append("ledger 缺 `input_hash` ⇒ 无法判定“这份产物对应哪次输入”")
    return (not bad), bad


def v1_definition_correspondence(rows):
    """V-1 定义对应性：**官方陈述 ↔ 形式化定义**逐条对应，且每条**带锚点**。

    ⚠ 判据只能判"**对应关系被逐条写明且可追溯**"；"对应得对不对"仍需人 ——
       这条边界必须写进结论（不许把"有对照表"说成"定义正确"）。
    """
    bad = []
    if not rows:
        bad.append("对应表为空 ⇒ 无法判定定义对应性（形式化了别的东西也算通过）")
    for i, r in enumerate(rows or [], 1):
        if not isinstance(r, dict):
            bad.append(f"对应表第 {i} 行不是映射")
            continue
        miss = [k for k in ("claim", "formal", "anchor") if not r.get(k)]
        if miss:
            bad.append(f"对应表第 {i} 行缺 {miss} ⇒ 该条对应**不可追溯**")
    return (not bad), bad


def v2_bridge_completeness(steps):
    """V-2 桥接完整性：正文 → Lean 定理之间**每一跳都有记录**，且**首尾连续**（无缺失的一跳）。

    ⚠ D-37 实测 **V-2 真空**（九项目**没有一个**做这件事）⇒ 本判据是**新造的形式**，
       不是对既有实现的机判化（这一条必须与 V-1/V-3/V-4 区别对待）。
    """
    bad = []
    if not steps:
        bad.append("跳表为空 ⇒ 桥接完整性无从判定（而 V-2 实测是**真空**）")
        return False, bad
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict):
            bad.append(f"跳表第 {i} 条不是映射")
            continue
        miss = [k for k in ("from", "to", "evidence") if not s.get(k)]
        if miss:
            bad.append(f"跳表第 {i} 条缺 {miss} ⇒ 这一跳**没有记录**")
    for i in range(1, len(steps)):
        a, b = steps[i - 1], steps[i]
        if isinstance(a, dict) and isinstance(b, dict) and a.get("to") and b.get("from") \
                and a["to"] != b["from"]:
            bad.append(f"跳表**断链**：第 {i} 条到 {a['to']!r}，第 {i+1} 条从 {b['from']!r} 起")
    return (not bad), bad


# ── O-66 (2026-09-25)：卡面 `input-provenance` 义务（`CROSS-PROJECT-WORK-STANDARD §4` 的**机判**）──
# 义务原文：卡声明 `public`/`sanitized` **且带输入** ⇒ ① `input-provenance` 必填（逐项本仓相对路径）
#   ② 每项须在 `sensitivity.yaml` 有 `tier` ③ 卡的 `sensitivity` **不得宽于**该项的 `tier`。
#
# ★ 触发条件为什么用 `attach-egress` 而不是"实际附件数"（**覆盖等价，非权宜**）：
#   运行时 `Get-AttachEgressReject` 已强制"**有附件 ∧ 后端出网 ⇒ 必须声明 `attach-egress: ok`**"
#   ⇒ "出网带附件"这一 population 恰好是"声明了 `attach-egress`"的**子集**
#   ⇒ 以**声明**为条件做**静态**判 = 覆盖同一人群（且是**超集** ⇒ 保守 ⇒ sound），并**在提交时就拦**。
#   ⚠ 另一条路（派发时按真实 `$attach.Count` 判）需要 PowerShell 读 `sensitivity.yaml` ——
#     **PS 5.1 无 YAML 解析**（实测 `agent-cli.ps1` 全域零 YAML 用法）⇒ 得额外建"生成物 + 查表"链路。
#     静态侧**更简单且更早**，故选定。（决策与实测见 DEV-LOG-014 §32.6 的"就地更正"）
CARD_GLOB = "spec/**/*cards*/**/*.md"      # 卡区目录名含 `cards`（`dogfood-cards/` · `test-cards/`）
# tier 序（**不得宽于** = 卡 rank 必须 ≤ 输入 rank）；`unverified` 按 `local-only` 处置（表头 fail-closed）
TIER_RANK = {"local-only": 0, "unverified": 0, "sanitized": 1, "public": 2}
PROVENANCE_NONE = "none"                   # 显式"输入不来自本仓"（唯一认可的 token，刻意不收 n/a·null）
# ── O-69（2026-09-26）：规则 ④b 的两个常量 —— **都来自实测**（DEV-LOG-014 §56）──────────
# ④b 要补的盲区：④ 只看得见 **registry**（"已登记"）⇒ **未登记**的本仓敏感文件**完全不可见**。
#   实现时的两条过滤，每条都对应 §56 的一个实测数：
#     ① `PROVENANCE_OUTPUT_PREFIXES` = **产物面** —— 实测 20 张卡扫出 25 个候选，其中 **14 个是 `out/*`**
#        （那是**卡的产物**，不是读进来的输入）⇒ 不排除就是 **≥56% 误报**；
#     ② 判"是不是本仓"用 **事实**（`(ROOT / token).is_file()`），**不用**"顶层段像不像 registry"
#        —— 后者会**漏** `inventory/sensitivity.yaml` 这类（它是本仓文件，但顶层段不在 registry 里）
#        同族教训 = **O-87**："用'像不像'代替'是不是'"。
PROVENANCE_OUTPUT_PREFIXES = ("out/", "batches/", "golden/")
PROV_PATH_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|yaml|yml|json|jsonl|py|ps1|sh|csv|txt|db|duckdb)")


_FM_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")


def _card_frontmatter(path):
    """提取卡面 front-matter（首个 `---` 包夹块）⇒ dict；**首行不是 `---` ⇒ None（不是卡）**。

    ★ 用**行式提取**而不是 `yaml.safe_load` —— 两条理由**都是本轮实测出来的**：
      · **严格 YAML 会炸**：实测 2 张卡（`t1-attach-shared-probe` · `cpphub-001`）的 `task:`/`note:` 值里含
        `": "` ⇒ `yaml.safe_load` 抛 `ScannerError`（与 2026-09-24 `sensitivity.yaml` 那次**同一个坑**）。
        第一版据此**静默 `return None`（= 跳过该卡）** ⇒ 把本该触发的 `t1` 漏过去了 = **我判据自己的假绿**
        （"什么都没判所以通过"—— 本仓头号形态，这次长在我当天新写的判据里）。
      · **权威读取器（PS 侧 `Get-FrontMatter`）本来就是行式的** ⇒ 行式提取与运行时**同口径**，
        避免"Python 说这卡坏、PS 却读得动"的**双标**（双标会把可派的卡判红）。
    ⇒ 同时支持**块式列表**（键后跟缩进 `- `）：否则 `input-provenance:` 写成列表会被读成空串 ⇒ **假红**。
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    out, key = {}, None
    for ln in lines[1:]:
        if ln.strip() == "---":
            return out
        if not ln.strip():
            continue
        if key and re.match(r"^\s+-\s+", ln):               # 块式列表项
            cur = out.get(key)
            if not isinstance(cur, list):
                cur = [] if not cur else [cur]
                out[key] = cur
            cur.append(ln.split("-", 1)[1].strip().strip('"').strip("'"))
            continue
        m = _FM_KEY_RE.match(ln)
        if m:
            key = m.group(1)
            out[key] = m.group(2).strip().strip('"').strip("'")
        else:
            key = None                                       # 非键非列表行 ⇒ 当前键结束
    return out                                               # 无闭合 `---`：PS 侧同样宽容 ⇒ 按已读到的算


def _sens_registry(inv):
    """`sensitivity.yaml` → `{path: tier}`（只取显式登记项；缺省档不在内）。"""
    reg = {}
    for sec in SENSITIVITY_SECTIONS:
        for it in (inv.get(sec) or []):
            p = (it or {}).get("path")
            if p:
                reg[p] = (it or {}).get("tier")
    return reg


def validate_input_provenance(cards, sensitivity_inv):
    """O-66：卡面 `input-provenance` 义务的**纯函数**判定（⇒ 离线可正反夹测）。

    `cards` = `[(label, frontmatter_dict, full_text)]`。返回 `(bad, stats)`；
    `bad` 里**两类后果不同**（故分桶返回给上层取最严）：
      · **FAIL 级**（规则 ① 缺字段 / ② 项未登记 / ③ 档位过宽）——**契约违规**
      · **WARN 级**（规则 ④ / **④b**）——"提到 ≠ 读到"，机械判不出，**只报不拦**
        · ④ = 正文出现 **tier 严于本卡**的**已登记**路径；
        · **④b（O-69，2026-09-26）** = 正文引用了**未登记**且**确实存在于本仓**的文件
          （④ 只看得见 registry ⇒ 未登记者原先**完全不可见**）
    """
    reg = _sens_registry(sensitivity_inv)
    default_tier = str(sensitivity_inv.get("default_tier") or "local-only")
    fail, warn = [], []
    n_trig = n_ok = n_none = 0
    for label, fm, body in cards:
        if not isinstance(fm, dict):
            continue
        ae = str(fm.get("attach-egress") or "").strip().lower()
        if ae not in ("ok", "yes", "true"):
            continue                                  # 未声明 ⇒ 运行时根本不放行出网附件 ⇒ 不触发
        tier = str(fm.get("sensitivity") or "").strip().lower() or default_tier
        if tier not in ("public", "sanitized"):
            continue                                  # local-only / unverified 本就不出网
        n_trig += 1
        prov = fm.get("input-provenance")
        if prov in (None, "", []):
            fail.append(f"{label}: 声明 `attach-egress` 且 `sensitivity={tier}` ⇒ **`input-provenance` 必填**"
                        f"（确无本仓输入请显式写 `input-provenance: {PROVENANCE_NONE}`）")
            continue
        entries = [str(e).strip() for e in (prov if isinstance(prov, list) else [prov]) if str(e).strip()]
        if len(entries) == 1 and entries[0].lower() == PROVENANCE_NONE:
            n_none += 1
            # 规则 ④（WARN 级）：`none` 必须**可证伪** —— 正文不得出现 tier **严于本卡**的已登记路径。
            #   ⚠ 只判"严于本卡"：卡天然会引用自身所在目录（实测 A2 写了 `dogfood-cards/...`，
            #     而该目录登记为 `public`）⇒ 若判"任何已登记路径"会**假红**（本轮实测踩到并收窄）。
            hits = sorted({p for p in reg
                           if TIER_RANK.get(reg.get(p) or default_tier, 0) < TIER_RANK.get(tier, 0)
                           and p.rstrip("/") in body})
            if hits:
                warn.append(f"{label}: 声明 `input-provenance: {PROVENANCE_NONE}`，但正文出现 **tier 严于本卡"
                            f"（{tier}）** 的已登记路径 {hits} ⇒ `{PROVENANCE_NONE}` 的可证伪性不成立"
                            f"（要么把该路径列进 `input-provenance`，要么把档位降到不宽于它）")
            # ★★ 规则 ④b（O-69，2026-09-26；仍属 **WARN 级 = 只报不拦**）：
            #   ④ 的盲区是"**只看得见 registry**" ⇒ 一张 `public` 卡声明 `none`、正文却引用了
            #   **未登记**的本仓文件时，④ **不触发** ⇒ 门禁全程 PASS（b3 的原始反例即此）。
            #   ④b 把它变可见：扫正文里的**路径样式 token**（**必须含 `/`** ⇒ 排除"裸文件名"这类
            #   散文里的普通词），再过两道过滤（**都来自 §56 的实测**）：
            #     ① 排除 `PROVENANCE_OUTPUT_PREFIXES`（卡的**产物**，不是输入）—— 实测消掉 14/25 误报；
            #     ② **事实**判"是不是本仓"：该路径在仓内**确实存在**（`is_file()`）
            #        ⚠ 刻意**不用**"顶层段 ∈ registry" —— 那会漏 `inventory/sensitivity.yaml` 这类
            #        （本仓文件，但顶层段不在 registry 里）。
            #   ⚠ 射程：只判"**提到**了未登记的本仓文件"，**不判**"真的读了它"（提到 ≠ 读到 ⇒ 故 WARN 不 FAIL）。
            cand = set()
            for tok in PROV_PATH_TOKEN_RE.findall(body):
                if "/" not in tok or tok in reg:
                    continue
                if tok.startswith(PROVENANCE_OUTPUT_PREFIXES):
                    continue                       # ① 卡的产物面
                if (ROOT / tok).is_file():
                    cand.add(tok)                  # ② 事实：确实是本仓**存在**的文件
            if cand:
                warn.append(f"{label}: 声明 `input-provenance: {PROVENANCE_NONE}`，但正文引用了 **未登记**且"
                            f"**确实存在于本仓**的文件 {sorted(cand)} ⇒ 未登记 = `{default_tier}`（fail-closed，"
                            f"严于本卡 `{tier}`）⇒ 要么把它列进 `input-provenance`，要么说明这些只是**提及**")
            continue
        n_ok += 1
        for e in entries:
            if e not in reg:
                fail.append(f"{label}: `input-provenance` 项 `{e}` **未登记**于 sensitivity.yaml"
                            f"（未登记 = `{default_tier}`，fail-closed）⇒ 先立项登记或改档位")
                continue
            et = reg[e] or default_tier
            if TIER_RANK.get(et, 0) < TIER_RANK.get(tier, 0):
                fail.append(f"{label}: 卡档位 `{tier}` **宽于**输入 `{e}` 的 tier `{et}`"
                            f" ⇒ 档位不得比它读的输入更宽")
    return fail, warn, {"cards": len(cards), "triggered": n_trig, "ok": n_ok, "none": n_none}


def check_input_provenance(ctx):
    """O-66：卡面 `input-provenance` 义务（规则见 `validate_input_provenance`）。

    为什么这条**非有不可**：`sensitivity` 是**卡作者的声明**，不是**内容的属性**（不写 = 默认 `public`）
    ⇒ 缺本判据时，"一张写 `public` 的卡带未发表内容出网"**没有任何机制知道**（§13.2 的实测结论）。
    """
    try:
        import yaml
    except Exception:
        return "WARN", "缺 pyyaml, 跳过 input-provenance 断言", []
    if not SENSITIVITY_INV.exists():
        return "FAIL", "inventory/sensitivity.yaml 缺失（本断言的登记依据）", []
    try:
        inv = yaml.safe_load(SENSITIVITY_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return "FAIL", f"sensitivity.yaml 解析失败: {type(e).__name__}: {e}", []
    cards = []
    for p in sorted(ROOT.glob(CARD_GLOB)):
        if p.name.lower() == "readme.md":
            continue
        fm = _card_frontmatter(p)
        if fm is None:
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            body = ""
        cards.append((p.relative_to(ROOT).as_posix(), fm, body))
    fail, warn, st = validate_input_provenance(cards, inv)
    note = (f"卡 {st['cards']} 张 · 触发 {st['triggered']} 张（attach-egress ∧ public/sanitized）"
            f" · 合规 {st['ok']} · 声明 {PROVENANCE_NONE} {st['none']}")
    if fail:
        return "FAIL", note, fail + (["", "⚠ 以下为 WARN 级（不阻断）："] + warn if warn else [])
    if warn:
        # 规则 ④ 属"提到≠读到"⇒ 只报不拦（本仓 WARN 语义：执行后有非阻断发现）
        return "WARN", note + " · ⚠ none 可证伪性存疑 " + str(len(warn)), warn
    return "PASS", note, []



