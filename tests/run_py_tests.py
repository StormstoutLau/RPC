"""Python 测试统一入口 —— 一次跑完 tests/ 下全部 `test_*.py` 独立脚本。

为什么要有它：
    `tests/` 下有若干**独立可跑**的 Python 测试（各自 `chk()` + 退出码，不依赖 pytest），
    shell 集成测试在 `tests/b5q/` 另有自己的 `run_all.sh`。缺一个统一的 Python 侧入口时，
    改动后容易"只跑了记得的那一个" —— 而本仓的教训正是**漏跑一条测试就等于没验证**
    （例：2026-09-23 拆模块时漏导入只在实跑时才炸，门禁全绿）。

设计取舍（照本仓纪律）：
  · **不引入 pytest / 任何第三方**：直接以子进程跑各脚本，各自的 sys.path 注入与退出码语义不变。
  · **每个测试一个独立子进程** ⇒ 互不污染（有的测试会 monkeypatch `cluster.*` 全局）。
  · 以**退出码**为通过与否的权威（不靠解析文本）；文本只用来出人读摘要。
  · ★★ **但 `rc == 0` 还不够**（**O-89**，2026-09-26 落地）：**还必须有 `RESULT:` 汇总行** ——
    否则"被 import、定义一堆 `test_*`、正常退出 0"的文件会**静默通过**，而**一条断言都没跑**。
    ⚠ 本仓**实际发生过一次**（`test_rpc_check_u1.py` 整整一个版本 0 执行）；更刺眼的是
    下面那句"入口本身坏了"的警告**当时就写在本 docstring 里** —— 只是**没有判据**去管它。
    ⇒ 教训：**警告不是判据**（本仓已有 O-70 同族讨论）。现已把它变成 `run_one` 里的一行判断。
  · 子进程强制 `PYTHONIOENCODING=utf-8`，避免 Windows 控制台编码把中文输出打乱。

用法（退出码 0 = 全过）：
    py tests\\run_py_tests.py              # 跑全部；默认只打印摘要 + 失败明细
    py tests\\run_py_tests.py -v           # 顺带流式打印每个测试的完整输出
    py tests\\run_py_tests.py --list       # 只列出发现到的测试
    py tests\\run_py_tests.py -k seal      # 只跑名字含 "seal" 的
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
TIMEOUT_S = 300


def discover(pattern: str = "test_*.py"):
    """tests/ 顶层（不含子目录）的 test_*.py，按名排序，排除自身。"""
    me = Path(__file__).resolve()
    return sorted(p for p in TESTS_DIR.glob(pattern)
                  if p.is_file() and p.resolve() != me)


def parse_result(out: str):
    """从输出里取该测试自报的 RESULT 行，仅用于人读摘要（权威仍是退出码）。"""
    m = re.search(r"^RESULT:\s*(.+)$", out, re.M)
    return m.group(1).strip() if m else ""


def run_one(path: Path, verbose: bool):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, str(path)],
                           capture_output=True, timeout=TIMEOUT_S, env=env)
        out = (p.stdout + p.stderr).decode("utf-8", "replace")
        rc = p.returncode
    except subprocess.TimeoutExpired:
        out, rc = f"超时 (> {TIMEOUT_S}s): {path.name}", 124
    dt = time.time() - t0
    summary = parse_result(out)
    # ★★ O-89（2026-09-26）：`rc == 0` 但**没有 `RESULT:` 汇总行** ⇒ **判红**。
    #   为什么必须有这条：门禁**只认退出码** ⇒ 一个"被 import、定义一堆 test_*、
    #   然后正常退出 0"的文件会**静默通过**，而它**一条断言都没跑**。
    #   本仓实际发生过一次（`test_rpc_check_u1.py` 整整一个版本 0 执行）——
    #   而下面那句警告**当时就已经写在 docstring 里**，只是**没有判据**去管它。
    #   ⇒ 现在把它变成可机判：**"没报汇总" = "没跑"**。
    missing = (rc == 0 and not summary)
    ok = (rc == 0) and not missing
    if missing:
        print(f"  FAIL  {path.name:<28} {dt:5.1f}s   "
              f"⚠ 无 `RESULT:` 汇总行 ⇒ 判红（它可能**一条断言都没跑**；见 O-89）")
    else:
        print(f"  {'PASS' if ok else 'FAIL'}  {path.name:<28} {dt:5.1f}s   {summary}")
    if verbose or not ok:
        if not verbose:
            print(f"  ── {path.name} 输出 ──")
        for line in out.splitlines():
            print("      " + line)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每个测试的完整输出")
    ap.add_argument("--list", action="store_true", help="只列出发现到的测试")
    ap.add_argument("-k", default="", help="只跑名字含该子串的测试")
    args = ap.parse_args()

    tests = discover()
    if args.k:
        tests = [t for t in tests if args.k in t.name]

    if not tests:
        print("未发现测试" + (f"（-k {args.k} 无匹配）" if args.k else ""))
        return 1

    if args.list:
        for t in tests:
            print(f"  {t.name}")
        print(f"共 {len(tests)} 个")
        return 0

    print(f"Python 测试统一入口 · {TESTS_DIR} · 共 {len(tests)} 个"
          f"{'（-k ' + args.k + '）' if args.k else ''}\n")
    t0 = time.time()
    results = [(t.name, run_one(t, args.verbose)) for t in tests]
    dt = time.time() - t0

    bad = [n for n, ok in results if not ok]
    print()
    print(f"结果: {len(results) - len(bad)}/{len(results)} 通过 · 用时 {dt:.1f}s")
    if bad:
        print("失败:" + ", ".join(bad))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
