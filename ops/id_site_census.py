#!/usr/bin/env python3
"""ID 站点普查 —— **可复算的口径**（2026-09-26 新增 · O-85）

## 为什么有这个文件

`spec/d6-agent-standard/U4-INVALIDATION-RULES.md` §1 表有一列"ID 站点（命中数）"，
但**那个数没有口径**。实测（同一台机器、同一批项目，只换口径）：

| 口径 | `Open_Data` 的实测值 |
|---|---|
| 列头所写 `hexdigest()[...]` / `md5(` / `sha256(` | **12** |
| `hexdigest` 单独 | **14** |
| `hashlib` | **117** |
| 再放宽范围（含 `.venv` + `archive`） | **139 处 / 40 文件** |

⇒ **没有一个是表里写的 `34`**。所以那一列的问题不是"数错了"，而是**"数字没有定义"** ——
它同时缺 ① **正则口径** ② **文件范围** ③ **计量单位**。

## 这个文件做什么

把那三件**写死成代码**，输出固定三件套：**口径 + 范围 + 数值**。
- `--emit`：把当前实测结果写进 `inventory/id-site-census.yaml`（**真值**）。
- 默认（或 `--check`）：**复算**并与真值比对 —— 用于门禁 `id-census`。

## 边界（别读成"它解决了影响面问题"）

- 它只回答"**有多少处哈希用法**"，**不回答**"哪些是**产物 ID**"（那是 U-4 的 `affected`，仍未解）。
- 项目目录**不可达**时**显式报 `reachable: false`**，并在退出码上区分
  ⇒ 门禁把它降级为 **WARN**，**不静默跳过**（D-26：降级必须有呈现位）。
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CENSUS = ROOT / "inventory" / "id-site-census.yaml"

# ── 口径 ①：正则（**只有一个定义点**）─────────────────────────────────────────
METRIC_NAME = "id_site_hit_lines"
METRIC_UNIT = "命中行数（一行内多个匹配只计 1）"
METRIC_REGEX = r"hexdigest\(\)|md5\(|sha256\(|sha1\("

# ── 口径 ②：范围 ────────────────────────────────────────────────────────────
FILE_GLOB = "*.py"
EXCLUDE_DIRS = (".venv", "venv", "archive", "__pycache__", ".git", "node_modules", "site-packages")
EXCLUDE_TESTS = True          # 测试不是"ID 产出点"⇒ 默认排除（改了这里必须重跑 --emit）

# ── 口径 ③：单位 = 上面的 METRIC_UNIT（"行"而不是"匹配次数"，也不是"文件数"）──────

# 被普查的项目（`id` 与 U4 §1 表保持一致；root 用绝对路径，**不做相对化** —— 它们在别的盘）
PROJECTS = (
    ("Open_Data", r"F:\Open_Data"),
    ("factor_pipeline", r"F:\Coding\factor_pipeline"),
    ("Auto_Prover", r"F:\Auto_Prover"),
    ("Textbook", r"D:\Textbook"),
    ("Fin_Agent", r"F:\Fin_Agent"),
    ("Cpp_Hub", r"F:\Cpp_Hub"),
    ("Spec_Workflow", r"F:\Spec_Workflow"),
    ("Full_Weather", r"F:\Full_Weather"),
    ("Macro_Data", r"E:\Macro_Data"),
    ("RPC", r"D:\RPC"),
)

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_DEGRADED = 2          # 有项目不可达 ⇒ 门禁降级为 WARN（不是 FAIL）


def scope() -> dict:
    """范围三件套（目录排除 + 文件 glob + 是否含测试）—— 原样写进真值，便于复现。"""
    skip = list(EXCLUDE_DIRS) + (["tests"] if EXCLUDE_TESTS else [])
    return {"glob": FILE_GLOB, "exclude_dirs": sorted(set(skip)), "exclude_tests": EXCLUDE_TESTS}


def measure(root: Path) -> tuple:
    """在 `root` 下按口径计数 ⇒ `(files, hits)`。`hits` = 命中**行数**。"""
    rx = re.compile(METRIC_REGEX)
    skip = set(scope()["exclude_dirs"])
    files = hits = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if not fnmatch.fnmatch(fn, FILE_GLOB):
                continue
            try:
                text = (Path(dirpath) / fn).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            n = sum(1 for line in text.splitlines() if rx.search(line))
            if n:
                files += 1
                hits += n
    return files, hits


def census() -> list:
    """逐项目实测。**不可达的项目照样出现在结果里**（`reachable: false`），不静默丢。"""
    out = []
    for pid, root_s in PROJECTS:
        root = Path(root_s)
        if not root.is_dir():
            out.append({"id": pid, "root": root_s, "reachable": False})
            continue
        files, hits = measure(root)
        out.append({"id": pid, "root": root_s, "reachable": True, "files": files, "hits": hits})
    return out


def _header() -> str:
    return (
        "# ID 站点普查真值（**可复算**）—— 口径 / 范围 / 数值三件套\n"
        "#\n"
        "# 生成：`py ops/id_site_census.py --emit`   ·   复算比对（门禁）：`id-census`\n"
        "# 口径的**唯一实现**在 `ops/id_site_census.py`；本文件只是它的一次输出快照。\n"
        "# ⚠ 读法：`hits` = 命中**行数**，**不等于**「产物 ID 的处数」——\n"
        "#   它只回答「有多少处哈希用法」；「哪些是产物 ID」是 U-4 的 `affected`，仍未解。\n"
    )


def emit() -> int:
    import yaml

    data = {"metric": {"name": METRIC_NAME, "unit": METRIC_UNIT, "regex": METRIC_REGEX, **scope()},
            "projects": census()}
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200, default_flow_style=False)
    CENSUS.write_text(_header() + body, encoding="utf-8")
    print(f"[emit] 写入 {CENSUS.relative_to(ROOT)} · 项目 {len(data['projects'])} 个")
    for p in data["projects"]:
        if p.get("reachable"):
            print(f"  {p['id']:<16} {p['hits']:>5} 行 / {p['files']:>3} 文件   ({p['root']})")
        else:
            print(f"  {p['id']:<16} {'不可达':>7}                ({p['root']})")
    return EXIT_OK


def check() -> int:
    import yaml

    if not CENSUS.is_file():
        print(f"[FAIL] 真值文件缺失: {CENSUS.relative_to(ROOT)} ⇒ 先跑 --emit")
        return EXIT_MISMATCH
    doc = yaml.safe_load(CENSUS.read_text(encoding="utf-8")) or {}
    m = doc.get("metric") or {}
    # ★ 口径漂移 = 比数值漂移更严重：口径一变，真值里所有数字立刻失去意义
    drift = [k for k, v in (("regex", METRIC_REGEX), ("name", METRIC_NAME)) if m.get(k) != v]
    for k, v in scope().items():
        if m.get(k) != v:
            drift.append(k)
    print(f"[口径] {m.get('name')} · 单位={m.get('unit')} · 正则={m.get('regex')}")
    print(f"[范围] glob={m.get('glob')} · 排除目录={m.get('exclude_dirs')} · 排除测试={m.get('exclude_tests')}")
    if drift:
        print(f"[FAIL] **口径已漂移**（真值是用旧口径生成的）: {drift} ⇒ 重跑 --emit 并复核下游结论")

    now = {p["id"]: p for p in census()}
    mism, unreach = [], []
    for p in doc.get("projects") or []:
        pid = p.get("id")
        cur = now.get(pid)
        if cur is None:
            continue
        if not cur.get("reachable"):
            unreach.append(pid)
            print(f"  [--]  {pid:<16} 不可达（{cur['root']}）⇒ 本次**无法复算**（降级，不当作通过）")
            continue
        if not p.get("reachable"):
            mism.append(f"{pid}: 真值记不可达，现在可达（真值需重跑 --emit）")
            continue
        if (p.get("hits"), p.get("files")) != (cur["hits"], cur["files"]):
            mism.append(f"{pid}: 真值 {p.get('hits')} 行/{p.get('files')} 文件 ≠ 实测 {cur['hits']} 行/{cur['files']} 文件")
            print(f"  [≠]  {pid:<16} {p.get('hits')} ≠ {cur['hits']}")
        else:
            print(f"  [ok] {pid:<16} {cur['hits']} 行 / {cur['files']} 文件")

    if drift or mism:
        for x in drift + mism:
            print(f"[FAIL] {x}")
        return EXIT_MISMATCH
    if unreach:
        print(f"[WARN] 不可达 {len(unreach)}/{len(doc.get('projects') or [])} ⇒ 本次结论**不完整**（可复算面已缩小）")
        return EXIT_DEGRADED
    print(f"[PASS] 全部 {len(now)} 个项目均可复算，且与真值一致")
    return EXIT_OK


def main() -> int:
    ap = argparse.ArgumentParser(description="ID 站点普查（口径可复算）")
    ap.add_argument("--emit", action="store_true", help="重写 inventory/id-site-census.yaml")
    ap.add_argument("--check", action="store_true", help="复算并与真值比对（默认行为）")
    a = ap.parse_args()
    if a.emit:
        return emit()
    return check()


if __name__ == "__main__":
    sys.exit(main())
