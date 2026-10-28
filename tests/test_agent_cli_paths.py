"""`agent-cli.ps1` 兄弟路径派生断言 —— 先验红（review-p2-big 8A 前置）。

守的是什么：
  入口脚本对同目录运行时件（`_station_ready.sh` / `_slot_gate.sh` / `_oc_session_meta.sh`）
  与账本（`agent-runs.log`）的引用，必须从 `$Script:REPO_ROOT` 派生；
  不能再写死 `D:\\RPC\\...`（换机器/CI checkout 根不是 `D:\\RPC` 时整条链失效）。

判据只扫**代码面**（剥 `#` 注释）—— 说明性注释里的路径不算。

用法: py tests\\test_agent_cli_paths.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "ops" / "station-bin" / "agent-cli.ps1"
fails = []

BASENAMES = ("_station_ready.sh", "_slot_gate.sh", "_oc_session_meta.sh", "agent-runs.log")
LITERAL = re.compile(r"[dD]:\\RPC")


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def strip_comments(text):
    """逐行剥 `#` 注释（引号内不剥；本文件的目标行不含引号内 `#`）。"""
    out = []
    for line in text.splitlines():
        quote = None
        cut = None
        for i, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "'\"":
                quote = ch
            elif ch == "#":
                cut = i
                break
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def validate_agent_cli_paths(text):
    code = strip_comments(text)
    problems = []
    hits = [(i + 1, ln.strip()) for i, ln in enumerate(code.splitlines()) if LITERAL.search(ln)]
    if hits:
        problems.append(f"代码面仍有 D:\\RPC 字面 {len(hits)} 处: {hits[:3]}")
    # 只看"仓库内路径引用"的行（同时含 basename 与 `ops\\station-bin\\`）；
    # 纯文件名（如 TMP_ROOT 下的临时副本、保留名元组）不是仓库路径，不参与判定。
    refs = {b: [] for b in BASENAMES}
    for i, ln in enumerate(code.splitlines()):
        if "ops\\station-bin\\" not in ln and "ops/station-bin/" not in ln:
            continue
        for b in BASENAMES:
            if b in ln:
                refs[b].append((i + 1, ln.strip()))
    for b, rows in refs.items():
        if not rows:
            problems.append(f"未找到对 {b} 的仓库路径引用")
            continue
        bad = [r for r in rows if "$Script:REPO_ROOT" not in r[1]]
        if bad:
            problems.append(f"{b} 的引用未走 $Script:REPO_ROOT: {bad[:2]}")
    return problems


def main() -> int:
    if not CLI.is_file():
        chk(f"{CLI.relative_to(ROOT)} 存在", False)
        print(f"\nRESULT: FAIL ({len(fails)} 项) · 失败: {', '.join(fails)}")
        return 1

    text = CLI.read_text(encoding="utf-8", errors="replace")
    problems = validate_agent_cli_paths(text)
    chk("agent-cli 路径全部从 REPO_ROOT 派生", not problems, "; ".join(problems[:4]))
    for p in problems[:6]:
        print("      - " + p)

    # ── 负向夹具：写死路径必须被判出 ────────────────────────────────
    bad_text = (
        "$local = 'D:\\RPC\\ops\\station-bin\\_station_ready.sh'\n"
        "$x = Join-Path $Script:REPO_ROOT 'ops\\station-bin\\_slot_gate.sh'\n"
        "$y = Join-Path $Script:REPO_ROOT 'ops\\station-bin\\_oc_session_meta.sh'\n"
        "$z = Join-Path $Script:REPO_ROOT 'ops\\station-bin\\agent-runs.log'\n"
    )
    bad = validate_agent_cli_paths(bad_text)
    chk("负向夹具：写死 D:\\RPC ⇒ FAIL", any("字面" in b for b in bad), bad)

    # ── 注释里的路径不算（说明性文字保留）──────────────────────────
    commented = (
        "# 历史: $local = 'D:\\RPC\\ops\\station-bin\\_station_ready.sh'\n"
        "$a = Join-Path $Script:REPO_ROOT 'ops\\station-bin\\_station_ready.sh'\n"
        "$b = Join-Path $Script:REPO_ROOT 'ops\\station-bin\\_slot_gate.sh'\n"
        "$c = Join-Path $Script:REPO_ROOT 'ops\\station-bin\\_oc_session_meta.sh'\n"
        "$d = Join-Path $Script:REPO_ROOT 'ops\\station-bin\\agent-runs.log'\n"
    )
    chk("剥注释逻辑：注释里的写死路径不参与判定", not validate_agent_cli_paths(commented),
        validate_agent_cli_paths(commented))

    print(f"\nRESULT: {'ALL PASS' if not fails else f'FAIL ({len(fails)} 项)'}"
          f" · 失败: {', '.join(fails) if fails else '无'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
