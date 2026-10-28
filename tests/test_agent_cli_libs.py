"""#8C 边界：`agent-cli.ps1` 的判据库拆分（`agent-cli-lib/{10-tables,20-scrub,30-d7}.ps1`）。

钉住四件事（每一件都对应一种**已实测过**的失败形态）：
  ① **三处清单逐项相同** —— 入口 `$Script:AGENT_CLI_LIBS`（dot-source 顺序）与三个夹具的拼接清单。
     清单不一致 ⇒ 入口加载的与夹具测的**不是同一份文件集** ⇒ 夹具全绿而线上少一个函数（假绿）。
  ② **函数总数守恒** —— 拼接后仍 ≥ 116（基线），且**无重名**。少一个 = 搬家搬丢了；重名 = 后者静默
     覆盖前者（PS 里"后定义者胜"），入口与 lib 各一份时**没有任何症状**。
  ③ **lib 带 UTF-8 BOM** —— 无 BOM 的中文 .ps1 在 PS5.1 按 ANSI 解码 ⇒ 中文注释乱码导致**假解析错误**
     （门禁 `ps1-bom` 也钉这条，这里再从"新文件必带"这一面守一次）。
  ④ **lib 不得用 `$PSScriptRoot`** —— dot-source 里 `$PSScriptRoot` 指向**调用方**；`split` 的 BOM 副本
     落在 TEMP ⇒ 靠它找兄弟文件会算错根（O-161 同源）。

用法: py tests\\test_agent_cli_libs.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "ops" / "station-bin"
CLI = BIN / "agent-cli.ps1"
LIB_DIR = BIN / "agent-cli-lib"
FIXTURES = ["_fm_golden_test.ps1", "_probe_fallback.ps1", "_scrubber_coverage_test.ps1"]
MIN_FUNCS = 116            # 拆分前的基线（2026-10-28 实测）

LIST_RE = re.compile(r"\$(?:Script:AGENT_CLI_LIBS|libNames)\s*=\s*@\(([^)]*)\)")
FN_RE = re.compile(r"(?m)^\s*function\s+([\w-]+)")

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig", errors="replace")


def _names(text: str):
    m = LIST_RE.search(text)
    if not m:
        return None
    return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]


def main() -> int:
    # ① 三处清单逐项相同（入口 + 三个夹具）
    entry = _names(_read(CLI))
    chk("入口声明了 `$Script:AGENT_CLI_LIBS`", entry is not None, entry)
    for fx in FIXTURES:
        p = BIN / fx
        if not p.is_file():
            chk(f"{fx} 存在", False)
            continue
        got = _names(_read(p))
        chk(f"{fx} 的拼接清单 == 入口（逐项、同序）", got == entry, f"{got} vs {entry}")

    names = entry or []
    chk("清单非空", bool(names), names)

    # ①b 清单里的文件都在盘上
    for n in names:
        chk(f"lib 存在: {n}", (LIB_DIR / n).is_file())

    # ② 函数总数守恒 + 无重名
    texts = [(CLI, _read(CLI))] + [(LIB_DIR / n, _read(LIB_DIR / n)) for n in names if (LIB_DIR / n).is_file()]
    all_fns = []
    per_file = {}
    for p, t in texts:
        f = FN_RE.findall(t)
        per_file[p.name] = len(f)
        all_fns += f
    chk(f"拼接后函数数 ≥ {MIN_FUNCS}（搬家没搬丢）", len(all_fns) >= MIN_FUNCS,
        f"{len(all_fns)} · {per_file}")
    dup = sorted({x for x in all_fns if all_fns.count(x) > 1})
    chk("函数名无重名（后定义者胜 ⇒ 重名会静默覆盖）", not dup, dup)

    # ③ 新 lib 必须带 UTF-8 BOM
    for n in names:
        p = LIB_DIR / n
        if not p.is_file():
            continue
        chk(f"{n} 带 UTF-8 BOM", p.read_bytes().startswith(b"\xef\xbb\xbf"))

    # ④ lib 不得用 $PSScriptRoot（TEMP 副本场景会算错根）
    for n in names:
        p = LIB_DIR / n
        if not p.is_file():
            continue
        body = "\n".join(ln for ln in _read(p).splitlines() if not ln.lstrip().startswith("#"))
        chk(f"{n} 不含 $PSScriptRoot", "$PSScriptRoot" not in body)

    # ⑤ dot-source 必须排在 `$Script:REPO_ROOT` 之后（否则根还没有值）
    cli = _read(CLI)
    i_root = cli.find("$Script:REPO_ROOT =")
    i_dot = cli.find("Join-Path $Script:REPO_ROOT \"ops\\station-bin\\agent-cli-lib")
    chk("dot-source 排在 REPO_ROOT 定义之后", 0 <= i_root < i_dot, f"root@{i_root} dot@{i_dot}")

    print(f"\nRESULT: {'ALL PASS' if not fails else f'FAIL ({len(fails)} 项)'}"
          f" · 失败: {', '.join(fails) if fails else '无'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
