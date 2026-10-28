#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rpc_check 共享层：路径/常量/IO 小工具（review-p2-split 8B）。

只放**被多个域模块共用**的顶层定义；域逻辑不在这里。
门面 `rpc_check.py` 显式重导出本模块的全部公共名。
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

ROOT = Path(__file__).resolve().parent.parent

SENSITIVITY_INV = ROOT / "inventory" / "sensitivity.yaml"
# 封闭枚举 —— 与 `sensitivity.yaml` 表头第 29-33 行、及 `agent-cli.ps1` 的 `--Sensitivity` 三档一致
SENSITIVITY_TIERS = ("public", "sanitized", "local-only", "unverified")
SENSITIVITY_SECTIONS = ("documents", "contracts", "code")

CHECKS = []


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

def allow_unhit(allow_keys, hit_keys):
    """**纯函数**（D6-P0-2）：豁免白名单里**未被命中**的项 ⇒ 应提示"该豁免已可移除"。

    为什么需要（**防腐化**）：豁免**失效后不会被告知** ⇒ 清单长期腐化（豁免留着、实际已不需要），
    而"**登记这个动作本身要在 review 里可见**"（ADR-0004 D2 纪律）⇒ 未命中必须**自报** ——
    **WARN（不阻断）**，因为"豁免多留一条"不是缺陷，但**必须被看见**（否则没人删）。
    """
    return sorted(set(allow_keys) - set(hit_keys))

AGENT_CLI = ROOT / "ops" / "station-bin" / "agent-cli.ps1"

ADR_GLOB = "ADR-*.md"

ADR_DIR = ROOT / "adr"

ADR_CANON = "考虑的替代方案"

ADR_LEGACY = ("否决/比较对象", "被否的方案")

def _norm_head(s):
    """规范化标题用于比较：去括号内容 + 去空白 + 统一全半角括号 ⇒ 只留中文核心词。"""
    s = s.replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", re.sub(r"\(.*?\)", "", s))

def validate_adr(text):
    """**纯函数** → `(bad, notes)`。

    规则（P2-2）：① **恰 1 个**规范节 `考虑的替代方案`；② 节体**非空**（≥1 列表项 **或** ≥2 表格行 = 表头+数据）；
    ③ **不得**留旧节名（`否决/比较对象` / `被否的方案`）。
    ⚠ 节体扫描**只到下一个二级标题为止** —— `### 替代方案 A` 是**子节**、属节体（ADR-0001/0002 的节体**全是**子节），
      若按"任意标题"截断会把它们判成空节。
    """
    lines = text.splitlines()
    heads = [(i, ln.strip()) for i, ln in enumerate(lines)
             if ln.startswith("## ") and not ln.startswith("### ")]
    canon = [(i, raw) for i, raw in heads if _norm_head(raw[3:]) == ADR_CANON]
    bad, notes = [], []
    for i, raw in heads:
        if _norm_head(raw[3:]) in {_norm_head(x) for x in ADR_LEGACY}:
            bad.append(f"第 {i + 1} 行仍是**旧节名** `{raw}` ⇒ "
                       f"统一为 `## {ADR_CANON}（Alternatives Considered）`")
    if not canon:
        bad.append(f"**缺** `## {ADR_CANON}（Alternatives Considered）` 节 ⇒ "
                   f"非平凡改动必须写明**考虑过 / 否决了哪些方案**")
        return bad, notes
    if len(canon) > 1:
        bad.append(f"有 **{len(canon)}** 个规范节（行 {[i + 1 for i, _ in canon]}）⇒ "
                   f"只允许 1 个（改名后残留旧节？）")
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
        bad.append(f"第 {i0 + 1} 行 `## {ADR_CANON}…` 节**是空的**（列表项 {n_item} · 表格行 {n_row}）"
                   f"⇒ 只写了标题没写内容（需 ≥1 列表项 **或** ≥2 表格行 = 表头+数据）")
    else:
        notes.append(f"列表项 {n_item} · 表格行 {n_row}")
    return bad, notes

def _decode_out(b: bytes) -> str:
    """PS 5.1 重定向时的输出编码随控制台（zh-CN 常见 cp936）⇒ 先 utf-8 再 cp936，最后兜底替换。"""
    for enc in ("utf-8", "cp936"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")

def _s(v):
    """取字符串（非字符串一律当空）—— 避免 `42.strip()` 这类调用把判据打崩。"""
    return v.strip() if isinstance(v, str) else ""

def _ds(v):
    """日期字段取串：**接受 yaml 把裸日期解析出的 `date` / `datetime`**。

    ★ 为什么单独一个函数：`updated: 2026-09-27` 会被 yaml 解析成 **`datetime.date`**，
    而 `_s()` 对非字符串一律返回空 ⇒ 判据会报「缺 `updated`」，**而人看表里明明有** ——
    这是**口径陷阱**（同族：O-93 的『同一棵树三种口径三个结果』）。
    ⇒ 判据对**同一事实的不同合法写法**要宽容（裸日期 / 带引号都收），只对**真的没有**严格。
    """
    if isinstance(v, str):
        return v.strip()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return ""


INVENTORY_DIR = ROOT / "inventory"

def load_inventory():
    """读 inventory/*.yaml。返回 (ports: {int: 条目}, models: {str: 条目})。"""
    try:
        import yaml
    except Exception:
        return None, None
    ports, models = {}, {}
    if not INVENTORY_DIR.is_dir():
        return ports, models
    for f in sorted(INVENTORY_DIR.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for group, items in doc.items():
            # 纯登记用的段不参与"已声明真值"计算 (否则 known_broken_conf 里的 alias
            # 会被当成正常模型键, 掩盖它其实是坏的)
            if group in ("known_issues", "known_drift", "known_broken_conf"):
                continue
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                if isinstance(it.get("port"), int):
                    ports[it["port"]] = {**it, "_group": group, "_file": f.name}
                for key in ("alias", "engine_id"):
                    if it.get(key):
                        models[str(it[key])] = {**it, "_group": group, "_file": f.name}
    return ports, models
