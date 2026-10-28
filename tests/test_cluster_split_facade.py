"""`cluster.py` 门面可达性（评审 #8「核心文件过大」→ 按域拆模块）：拆分前后**全部**顶层名仍可从门面取到。

基线名单 = `tests/fixtures/cluster_symbols.txt`（从拆分**前** HEAD 静态提取，296 个：含
`from cluster_const/cluster_ssh import` 的重导出名 —— 与门禁 `facade` 的 `facade_names` 同口径，
所以"门禁看得见的名字"与"运行时可取到的名字"不会各说各话）。

> 注意：`tests/test_rpc_check_facade.py` 是 **P1-3 的 `facade` 门禁**自测（消费者契约）；
> 本文件是 **#8 拆分的重导出护栏**。两者互补，勿合并。

判据：`hasattr` 逐个 + `facade_names(cluster.py)` ⊇ 基线（静态面不许比运行时面窄）+ `main` 可调用。

用法: py tests\\test_cluster_split_facade.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "cluster_symbols.txt"
fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def main() -> int:
    chk("基线名单存在且非空", FIX.is_file())
    names = [ln.strip() for ln in FIX.read_text(encoding="utf-8").splitlines() if ln.strip()]
    chk("基线名单规模 = 296（防夹具空转）", len(names) == 296, len(names))

    import cluster as C  # noqa: E402  （运行时可取性）
    missing = [n for n in names if not hasattr(C, n)]
    chk("门面可达全部基线符号（运行时）", not missing, f"缺 {len(missing)} 个: {missing[:8]}")

    static = R.facade_names(R._strip_py_prose(R.FACADE.read_text(encoding="utf-8", errors="replace")))
    lost = sorted(set(names) - static)
    chk("静态可达名 ⊇ 基线（门禁 `facade` 的视角）", not lost, f"缺 {len(lost)} 个: {lost[:8]}")

    chk("`main` 仍在门面且可调用", callable(getattr(C, "main", None)))
    chk("`ssh_run` 仍可从门面取到（cluster_web 依赖）", callable(getattr(C, "ssh_run", None)))
    chk("`STATIONS` / `ROUTE` 仍在门面（常量层重导出）",
        hasattr(C, "STATIONS") and hasattr(C, "ROUTE"))

    print(f"\nRESULT: {'ALL PASS' if not fails else f'FAIL ({len(fails)} 项)'}"
          f" · 失败: {', '.join(fails) if fails else '无'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
