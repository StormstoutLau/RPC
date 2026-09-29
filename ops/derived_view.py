#!/usr/bin/env python3
"""派生**只读视图**渲染器 + `--check` 重渲染逐字节比对 —— **A3**（2026-09-29）

## 这个文件解决什么

本仓有一条纪律：**同一事实不得两处表达**（第二定义点）。但有些"清单类"文档天生要
在**多处**出现（手册、README、看板）—— 手抄必漂。正解不是禁抄，而是把抄的那份变成
**派生件**：从真值**渲染**出来，并用 `--check` **逐字节**验证它没被手改、也没过期。

## 形态（照 `spec/d6-agent-standard/dogfood-cards/land-a3-derived-view.md` 的**已勘误**底稿）

- **输入**：`SOURCES` 里显式声明的真值文件集合（缺一不可）。
- **版本字段**：档内**只含确定性字段**（`source-hash` / `generator`）——
  ★ **`generated-at` 已移除**（勘误 §1.2）：逐字节一致要求档内**无任何非确定字段**；
  保留时间戳 ⇒ 每次渲染该行必变 ⇒ 比对永远失败；比对时"忽略该行" ⇒ 又引入**第二个定义点**
  （渲染器写、检查器跳）。⇒ 生成时间只进构建日志，**不入档、不参与比对**。
- **退出码（三态，互不混淆）**：`0` 一致 · `1` 过期/漂移（`source-hash` 不符 **或** 正文逐字节不一致）
  · `2` 渲染链路故障（读源失败 / 档缺 / 写失败）。

## 用法

    py ops/derived_view.py --emit      # 重渲染并落档（改真值后跑它）
    py ops/derived_view.py --check     # 只校验：0/1/2（默认）
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 声明的真值源（**单一真值**；渲染器只读它们，不读别的）──────────────────────
SOURCES = ("inventory/ports.yaml",)
# ── 落档视图 ────────────────────────────────────────────────────────────────
VIEW = ROOT / "docs" / "派生视图_端口分配.md"
GENERATOR = "derived_view.py v1"
MARKER = "<!-- DERIVED VIEW — DO NOT EDIT MANUALLY -->"
# 视图渲染的段落顺序（缺的段落不渲染；空段落不静默 —— 见 render 的返回）
GROUPS = ("managed", "third_party", "deprecated", "unmanaged", "dynamic")
HASH_LINE_RE = re.compile(r"^source-hash:\s*([0-9a-f]{64})\s*$", re.M)

EXIT_OK = 0
EXIT_STALE = 1
EXIT_FAULT = 2


class RenderFault(Exception):
    """渲染链路故障（读源 / 依赖缺失）⇒ 退出码 2，与"过期"区分。"""


def _canon_bytes(path: Path) -> bytes:
    """真值文件的**规范化字节**：去 UTF-8 BOM + 行尾归一到 LF。

    ★ **为什么必须归一**（否则 `source-hash` 不可复现）：`core.autocrlf=true` 时同一份真值
      在不同机器/不同 clone 上是 **CRLF**，`false` 时是 **LF** ⇒ 直接 `read_bytes()` 求哈希
      会**随检出配置变**，视图在两台机器上"互相过期"（本仓头号失败形态的机器版）。
      ⇒ 归一化在**生产端**（本函数）固化 —— 与 `inventory/determinism-noise.yaml` 的
      `line-ending: {normalize_to: LF}` 同一条纪律（比对端不妥协）。
    """
    b = path.read_bytes()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    return b.replace(b"\r\n", b"\n")


def source_hash(root: Path = ROOT) -> str:
    """真值文件集合的 SHA-256（**规范化后**字节，`\\0` 分隔，避免拼接歧义）。"""
    h = hashlib.sha256()
    for s in SOURCES:
        p = root / s
        if not p.is_file():
            raise RenderFault(f"真值源缺失: {s}")
        h.update(_canon_bytes(p))
        h.update(b"\0")
    return h.hexdigest()


def _cell(v) -> str:
    """单元格文本：`|` 转义（否则拆错格 —— 本仓 `md-tables` 判据的射程）、换行收成空格。"""
    if v is None:
        return "-"
    s = str(v).replace("\n", " ").strip()
    return s.replace("|", "\\|") or "-"


def _load(root: Path) -> dict:
    try:
        import yaml
    except Exception as e:                       # pragma: no cover
        raise RenderFault(f"缺 pyyaml: {e}") from e
    p = root / SOURCES[0]
    try:
        # ★ `utf-8-sig`：真值文件在 Windows 上可能带 BOM（`Add-Content -Encoding utf8` 就会加），
        #   带 BOM 时 `utf-8` 解码会把 BOM 当成正文首字符 ⇒ PyYAML 解析炸。与 `_canon_bytes` 同一条纪律。
        return yaml.safe_load(p.read_text(encoding="utf-8-sig")) or {}
    except Exception as e:
        raise RenderFault(f"真值源解析失败: {SOURCES[0]}: {type(e).__name__}: {e}") from e


def render(root: Path = ROOT) -> str:
    """**纯函数**：读真值 → 渲染视图全文（UTF-8 / LF / 无 BOM）。

    ★ 只含确定性字段（`source-hash` / `generator`）；**无时间戳**（勘误 §1.2）。
    ⚠ 段落为空 ⇒ 渲染成一行 `_（无条目）_`（**显式**，不静默留白）。
    """
    data = _load(root)
    h = source_hash(root)
    out = [
        MARKER,
        "",
        "# 派生视图：端口分配（只读）",
        "",
        "本文件由 `ops/derived_view.py` **渲染**，**不要手工编辑**。",
        "真值 = `inventory/ports.yaml`；改真值后跑 `py ops/derived_view.py --emit` 重渲染。",
        "",
        f"source-hash: {h}",
        f"generator: {GENERATOR}",
        "",
    ]
    for g in GROUPS:
        rows = data.get(g)
        out.append(f"## {g}")
        out.append("")
        if not rows:
            out += ["_（无条目）_", ""]
            continue
        out += ["| 端口 | proto | 用途 | owner |", "|---|---|---|---|"]
        for r in rows:
            if not isinstance(r, dict):
                continue
            out.append("| " + " | ".join((
                _cell(r.get("port", "(动态)")), _cell(r.get("proto")),
                _cell(r.get("purpose")), _cell(r.get("owner")),
            )) + " |")
        out.append("")
    return "\n".join(out)


def _rel(p: Path) -> str:
    """尽量给人读的相对路径；不在 ROOT 下（测试/异机）时退化为绝对路径 —— **绝不在报错路径上抛异常**
    （★ 本函数的存在理由：`check()` 的"档缺 ⇒ 2"分支曾用 `VIEW.relative_to(ROOT)`，
      当 VIEW 被指到仓外时会抛 `ValueError` ⇒ **故障分支自己崩**，把"该报 2"变成"未捕获异常"）。"""
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def check(root: Path = ROOT) -> tuple[int, str]:
    """重渲染并与落档视图**逐字节**比对 ⇒ `(退出码, 说明)`。

    顺序（**先 `source-hash` 后正文**）：① 读源/渲染失败 ⇒ 2；② 落档缺失 ⇒ 2；
    ③ 声明 `source-hash` ≠ 实际 ⇒ **1（短路，不再比正文）**；④ 正文逐字节不等 ⇒ 1；⑤ 否则 0。
    """
    try:
        rendered = render(root)
    except RenderFault as e:
        return EXIT_FAULT, f"ERROR: derived-view 渲染故障: {e}"
    if not VIEW.is_file():
        return EXIT_FAULT, f"ERROR: derived-view 落档视图缺失: {_rel(VIEW)}"
    archived = VIEW.read_text(encoding="utf-8")
    m = HASH_LINE_RE.search(archived)
    if not m:
        return EXIT_STALE, "FAIL: derived-view 落档视图**缺 `source-hash` 行**（不认这个档）"
    declared, actual = m.group(1), source_hash(root)
    if declared != actual:
        return EXIT_STALE, (f"FAIL: derived-view **过期**（真值已改，视图没重渲染）"
                            f"：声明 source-hash {declared[:12]}… ≠ 当前 {actual[:12]}…")
    if archived != rendered:
        return EXIT_STALE, "FAIL: derived-view 落档视图与重渲染**逐字节不一致**（被手改过？）"
    return EXIT_OK, f"PASS: derived-view（source-hash {actual[:12]}… · 逐字节一致）"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--emit", action="store_true", help="重渲染并落档")
    ap.add_argument("--check", action="store_true", help="只校验（默认）")
    args = ap.parse_args(argv)

    if args.emit:
        try:
            text = render(ROOT)
        except RenderFault as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return EXIT_FAULT
        VIEW.parent.mkdir(parents=True, exist_ok=True)
        VIEW.write_text(text, encoding="utf-8", newline="\n")
        print(f"PASS: derived-view 已重渲染 · {_rel(VIEW)}"
              f" · source-hash {source_hash(ROOT)[:12]}…")
        return EXIT_OK

    rc, msg = check(ROOT)
    print(msg, file=sys.stderr if rc == EXIT_FAULT else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())