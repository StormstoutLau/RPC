"""门面可达性（#8B 拆分）：拆分后 `rpc_check` 的**全部**顶层名仍可从门面取到。

基线名单 = `tests/fixtures/rpc_check_symbols.txt`（从拆分前 HEAD 的 AST 生成，412 个）；
45 个测试按 `R.<name>` 取用，任何漏导出都在这里当场断。

> 注意：`tests/test_rpc_check_facade.py` 是**另一个**断言（`cluster.py` 门面，P1-3）；
> 本文件只管 `rpc_check` 拆分后的重导出，勿混名。

用法: py tests\\test_rpc_check_split_facade.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "rpc_check_symbols.txt"
fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def main() -> int:
    chk("基线名单存在且非空", FIX.is_file())
    names = [ln.strip() for ln in FIX.read_text(encoding="utf-8").splitlines() if ln.strip()]
    chk("基线名单规模 = 412（防夹具空转）", len(names) == 412, len(names))

    missing = [n for n in names if not hasattr(R, n)]
    chk("门面可达全部基线符号", not missing, f"缺 {len(missing)} 个: {missing[:8]}")

    ids = [c["id"] for c in R.CHECKS]
    chk("CHECKS 数量 = 52", len(ids) == 52, len(ids))
    chk("CHECKS id 唯一", len(ids) == len(set(ids)), len(ids) - len(set(ids)))
    for key in ("secrets", "syntax", "scripts", "shell-strict", "station-layout", "py-tests"):
        chk(f"CHECKS 含 {key}", key in ids)
    chk("每项 fn 可调用", all(callable(c.get("fn")) for c in R.CHECKS))

    print(f"\nRESULT: {'ALL PASS' if not fails else f'FAIL ({len(fails)} 项)'}"
          f" · 失败: {', '.join(fails) if fails else '无'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
