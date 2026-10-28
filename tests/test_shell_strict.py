"""`shell_strict` 策略断言 —— 先验红（review-p2-big #5）。

守的是什么：
  站上 13 个 shell 执行件必须 `set -euo pipefail`；2 个被 `source` 的库**不得**改调用方选项；
  唯一豁免（`load-gate`）必须带 why，且"豁免失效"（文件已变严格）要自报 ⇒ 防腐化。

判据本体在 `ops/rpc_check.py` 的 `validate_shell_strict`（单一实现）；
本文件只负责跑真实 yaml + 负向夹具，证明判据**不是恒真**。

用法: py tests\\test_shell_strict.py
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

import yaml  # noqa: E402

OPS_INV = ROOT / "inventory" / "ops.yaml"
fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


def _load():
    try:
        return yaml.safe_load(OPS_INV.read_text(encoding="utf-8")) or {}
    except Exception as e:                                   # noqa: BLE001
        print(f"FAIL  inventory/ops.yaml 不可读: {type(e).__name__}: {e}")
        sys.exit(1)


def _read_text(rel):
    p = ROOT / rel
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def _fixture_text(strict=True):
    prologue = "#!/bin/bash\nset -euo pipefail\n" if strict else "#!/bin/bash\nset -u\n"
    return prologue + "echo ok\n"


def main() -> int:
    try:
        validate = R.validate_shell_strict
    except AttributeError:
        chk("rpc_check 提供 validate_shell_strict", False, "AttributeError（判据未实现）")
        print(f"\nRESULT: FAIL ({len(fails)} 项) · 失败: {', '.join(fails)}")
        return 1

    doc = _load()
    section = doc.get("shell_strict")
    chk("inventory/ops.yaml 有 shell_strict 段", isinstance(section, dict), type(section).__name__)
    if not isinstance(section, dict):
        print(f"\nRESULT: FAIL ({len(fails)} 项) · 失败: {', '.join(fails)}")
        return 1

    bad, notes = validate(section, _read_text)
    chk("真实 shell_strict 全合规", not bad, "; ".join(bad[:6]))
    print("        " + " · ".join(notes))

    # ── 接线：CHECKS 必须有 quick=True 的 shell-strict ─────────────────
    entry = next((c for c in R.CHECKS if c["id"] == "shell-strict"), None)
    chk("CHECKS 有 'shell-strict' 且为 quick",
        entry is not None and bool(entry.get("quick")) and callable(entry.get("fn")))

    # ── 负向夹具：判据必须能红（否则是恒真）─────────────────────────
    good = {
        "exec": ["fake/a.sh"],
        "libs": ["fake/lib.sh"],
        "allow": [],
    }

    def fake(files):
        return lambda rel: files.get(rel)

    files = {"fake/a.sh": _fixture_text(True), "fake/lib.sh": "#!/bin/bash\nf(){ :; }\n"}
    bad1, _ = validate(good, fake(files))
    chk("负向夹具：正例应全过", not bad1, "; ".join(bad1))

    m = copy.deepcopy(good)
    files2 = dict(files, **{"fake/a.sh": _fixture_text(False)})
    bad2, _ = validate(m, fake(files2))
    chk("负向夹具：执行件缺 set -euo pipefail ⇒ FAIL",
        any("set -euo pipefail" in b for b in bad2), bad2)

    m = copy.deepcopy(good)
    files3 = dict(files, **{"fake/lib.sh": "#!/bin/bash\nset -e\n"})
    bad3, _ = validate(m, fake(files3))
    chk("负向夹具：库里有 set -e ⇒ FAIL",
        any("库" in b or "lib" in b for b in bad3), bad3)

    m = copy.deepcopy(good)
    files4 = dict(files, **{"fake/b.sh": _fixture_text(True)})
    m["allow"] = [{"file": "fake/b.sh", "why": "x"}]
    bad4, _ = validate(m, fake(files4))
    chk("负向夹具：豁免未命中（文件已严格）⇒ FAIL",
        any("豁免未命中" in b for b in bad4), bad4)

    m = copy.deepcopy(good)
    m["libs"] = ["fake/a.sh"]
    bad5, _ = validate(m, fake(files))
    chk("负向夹具：同一文件双列 ⇒ FAIL",
        any("双列" in b or "重复" in b for b in bad5), bad5)

    m = copy.deepcopy(good)
    m["exec"] = ["fake/nope.sh"]
    bad6, _ = validate(m, fake(files))
    chk("负向夹具：执行件路径不存在 ⇒ FAIL",
        any("不存在" in b for b in bad6), bad6)

    m = copy.deepcopy(good)
    m["allow"] = [{"file": "fake/a.sh", "why": "x"}]
    bad7, _ = validate(m, fake(files))
    chk("负向夹具：豁免与 exec 重叠 ⇒ FAIL",
        any("重叠" in b for b in bad7), bad7)

    m = copy.deepcopy(good)
    m["allow"] = [{"file": "fake/nope.sh", "why": "x"}]
    bad8, _ = validate(m, fake(files))
    chk("负向夹具：豁免文件不存在 ⇒ FAIL",
        any("不存在" in b for b in bad8), bad8)

    print(f"\nRESULT: {'ALL PASS' if not fails else f'FAIL ({len(fails)} 项)'}"
          f" · 失败: {', '.join(fails) if fails else '无'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
