# -*- coding: utf-8 -*-
"""文档索引生成与状态筛选（甲案，2026-11-03）。

为什么单列而不并入 cluster.py：本工具**纯本地、幂等、不连站**，
是「文档治理」的生成器 + 筛选器，与 cluster.py 的站上管理面无关。

用法:
    py -3 ops/rpc_doc_index.py --write      # 重新生成 docs/INDEX.md
    py -3 ops/rpc_doc_index.py --check      # 重算并与磁盘比对（不一致 exit 1）
    py -3 ops/rpc_doc_index.py --type research
    py -3 ops/rpc_doc_index.py --status todo
    py -3 ops/rpc_doc_index.py --dir spec

纪律: docs/INDEX.md 是**生成物，禁止手工编辑** —— 改文档头 → 重跑 --write。
"""
import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC_DIRS = ("docs", "spec", "adr")
SKIP_PARTS = {"dogfood-cards", "test-cards", "inputs", "archive"}
INDEX_PATH = ROOT / "docs" / "INDEX.md"

FM_OPEN = re.compile(r"^---\s*$")
FM_CLOSE = re.compile(r"^-{10,}\s*$")
KEY_VAL = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")
TITLE = re.compile(r"^#\s+(.+)$")


def _norm(val: str) -> str:
    """状态值只取首个标记（如 'done（结论已出…）' ⇒ 'done'），保留括号前主干。"""
    v = val.strip().strip("\\[]").strip()
    if v.startswith('"') and v.endswith('"') and len(v) >= 2:
        v = v[1:-1].strip()
    for sep in ("（", "(", " ", "；", ";"):
        if sep in v:
            v = v.split(sep, 1)[0].strip()
    return v


def parse_doc(path: Path) -> dict:
    """读 front-matter：开界/闭界都是 `---` 或 `-------`（本仓两种写法并存）。"""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    sep = re.compile(r"^-{3,}\s*$")
    meta, title, started = {}, "", False
    for line in lines[:60]:
        if not title:
            m = TITLE.match(line)
            if m:
                title = m.group(1).strip()
        if not started:
            if sep.match(line):
                started = True
            continue
        if sep.match(line):
            if meta:
                break
            continue
        m = KEY_VAL.match(line)
        if m:
            meta[m.group(1)] = m.group(2).strip()
        elif line.strip() and meta:
            break
    meta["_title"] = title or path.stem
    meta["_path"] = path.relative_to(ROOT).as_posix()
    if "type" not in meta:
        meta["type"] = path.relative_to(ROOT).parts[0]
    return meta


def collect() -> list:
    out = []
    for d in DOC_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(ROOT).as_posix()
            if any(part in SKIP_PARTS for part in p.relative_to(ROOT).parts):
                continue
            if p.name in ("README.md", "INDEX.md"):
                continue
            meta = parse_doc(p)
            if meta:
                out.append(meta)
    return out


def render(items: list) -> str:
    lines = [
        "# 文档索引（生成物）",
        "",
        "> ⚠ 本文件由 `py -3 ops/rpc_doc_index.py --write` **自动生成**，**禁止手工编辑**。",
        "> 权威源 = 各文档的 YAML front-matter（`id` / `type` / `version` / `status` / `date`）。",
        "> 改文档头 → 重跑 `--write`；校验用 `--check`（不一致 exit 1）。",
        "",
        f"共 **{len(items)}** 篇（不含 README / INDEX / 卡片目录 / archive）。",
        "",
    ]
    cur = None
    for it in sorted(items, key=lambda x: (x["_path"].split("/")[0], x["_path"])):
        top = it["_path"].split("/")[0]
        if top != cur:
            if cur is not None:
                lines.append("")
            cur = top
            lines += [f"## {cur}/", "", "| 文档 | id | type | status | date |", "|---|---|---|---|---|"]
        link = posixpath.relpath(it["_path"], "docs")
        lines.append(
            "| [{}]({}) | `{}` | {} | {} | {} |".format(
                it["_title"].replace("|", "/"),
                link,
                it.get("id", "—"),
                _norm(it.get("type", "—")) or "—",
                _norm(it.get("status", "—")) or "—",
                _norm(it.get("date", "—")) or "—",
            )
        )
    return "\n".join(lines) + "\n"


def main(argv: list) -> int:
    items = collect()
    status = _norm
    if "--write" in argv:
        INDEX_PATH.write_text(render(items), encoding="utf-8", newline="\n")
        print(f"写入 {INDEX_PATH.relative_to(ROOT)}（{len(items)} 篇）")
        return 0
    if "--check" in argv:
        want = render(items)
        got = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else ""
        if want.replace("\r\n", "\n") == got.replace("\r\n", "\n"):
            print(f"PASS: docs/INDEX.md 与重算结果逐字节一致（{len(items)} 篇）")
            return 0
        print("FAIL: docs/INDEX.md 与重算结果不一致 ⇒ 跑 --write 重生成")
        return 1
    flt_type = next((argv[i + 1] for i, a in enumerate(argv) if a == "--type" and i + 1 < len(argv)), None)
    flt_status = next((argv[i + 1] for i, a in enumerate(argv) if a == "--status" and i + 1 < len(argv)), None)
    flt_dir = next((argv[i + 1] for i, a in enumerate(argv) if a == "--dir" and i + 1 < len(argv)), None)
    if flt_type or flt_status or flt_dir:
        for it in sorted(items, key=lambda x: x["_path"]):
            if flt_type and _norm(it.get("type", "")) != flt_type:
                continue
            if flt_status and _norm(it.get("status", "")) != flt_status:
                continue
            if flt_dir and not it["_path"].startswith(flt_dir.rstrip("/") + "/"):
                continue
            print(f"{it['_path']}\t{_norm(it.get('type', '—'))}\t{_norm(it.get('status', '—'))}")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
