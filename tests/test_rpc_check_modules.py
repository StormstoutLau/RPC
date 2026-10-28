"""#8B 模块边界：域模块不得反向 import 门面；行数上限；entry_modules 登记。

阶段语义：
  · 8B-1 只有 `rpc_common` + `rpc_protocol` ⇒ 只查这两个；
  · 六个域模块齐了以后，才启用门面 ≤ 500 行的终态断言（DESIGN §3.1）。

用法: py tests\\test_rpc_check_modules.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import yaml  # noqa: E402

OPS = ROOT / "ops"
MODULES = ["rpc_common.py", "rpc_protocol.py", "rpc_docs.py", "rpc_d6.py", "rpc_stations.py", "rpc_governance.py"]
DOMAIN = MODULES[1:]
IMPORT_RPC = re.compile(r"(?m)^\s*(?:from|import)\s+rpc_check\b")
fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def bad_imports(text):
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    return IMPORT_RPC.findall(code)


def main() -> int:
    existing = [m for m in MODULES if (OPS / m).is_file()]
    chk("rpc_common / rpc_protocol 已存在", {"rpc_common.py", "rpc_protocol.py"} <= set(existing), existing)

    for m in existing:
        text = (OPS / m).read_text(encoding="utf-8")
        n = len(text.splitlines())
        chk(f"{m} ≤ 3000 行", n <= 3000, n)
        chk(f"{m} 不反向 import rpc_check", not bad_imports(text), bad_imports(text)[:2])

    fixture = "# 注释里 import rpc_check 不算\nimport rpc_check\n"
    chk("负向夹具：反向 import 能被抓到", bad_imports(fixture) == ["import rpc_check"], bad_imports(fixture))

    inv = yaml.safe_load((ROOT / "inventory" / "ops.yaml").read_text(encoding="utf-8")) or {}
    entry = set(inv.get("entry_modules") or [])
    for m in existing:
        chk(f"entry_modules 含 ops/{m}", f"ops/{m}" in entry)

    if all((OPS / m).is_file() for m in MODULES):
        n = len((OPS / "rpc_check.py").read_text(encoding="utf-8").splitlines())
        chk("终态：门面 ≤ 500 行", n <= 500, n)
    else:
        print("        （阶段 8B-1/2：门面行数终态断言尚未启用）")

    print(f"\nRESULT: {'ALL PASS' if not fails else f'FAIL ({len(fails)} 项)'}"
          f" · 失败: {', '.join(fails) if fails else '无'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
