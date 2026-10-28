"""`station_bin_layout` 断言 —— 先验红（review-p2-big #8A）。

守的是什么：
  `ops/station-bin/` 根目录只放 部署件 / 入口运行时件 / 在跑夹具；
  一次性 `_*` 探针必须在 `archive/station-bin-probes/`；登记表不得残留根级探针路径。

判据本体在 `ops/rpc_check.py` 的 `validate_station_layout`（单一实现）；
本文件只负责跑真实树 + 负向夹具。

用法: py tests\\test_station_bin_layout.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

import yaml  # noqa: E402

OPS_INV = ROOT / "inventory" / "ops.yaml"
STATION_BIN = ROOT / "ops" / "station-bin"
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


def _root_files():
    """范围 = git 跟踪文件（与 `check_station_layout` 同一真值；工作区残留不参与）。"""
    return sorted(Path(rel).name for rel, _p in R._iter_source_files()
                  if rel.startswith("ops/station-bin/") and rel.count("/") == 2)


def _archive_files(rel):
    if not rel:
        return []
    prefix = rel.rstrip("/") + "/"
    out = []
    for r, _p in R._iter_source_files():
        if r.startswith(prefix) and "/" not in r[len(prefix):]:
            out.append(r[len(prefix):])
    return sorted(out)


def main() -> int:
    try:
        validate = R.validate_station_layout
    except AttributeError:
        chk("rpc_check 提供 validate_station_layout", False, "AttributeError（判据未实现）")
        print(f"\nRESULT: FAIL ({len(fails)} 项) · 失败: {', '.join(fails)}")
        return 1

    doc = _load()
    section = doc.get("station_bin_layout")
    chk("inventory/ops.yaml 有 station_bin_layout 段", isinstance(section, dict), type(section).__name__)
    if not isinstance(section, dict):
        print(f"\nRESULT: FAIL ({len(fails)} 项) · 失败: {', '.join(fails)}")
        return 1

    frozen = [str(p) for p in (doc.get("frozen_ops_scripts") or [])]
    root_files = _root_files()
    archive_files = _archive_files(str(section.get("probes_dir") or ""))

    bad, notes = validate(section, root_files, archive_files, frozen)
    chk("真实布局合规", not bad, "; ".join(bad[:6]))
    print("        " + " · ".join(notes))

    entry = next((c for c in R.CHECKS if c["id"] == "station-layout"), None)
    chk("CHECKS 有 'station-layout' 且为 quick",
        entry is not None and bool(entry.get("quick")) and callable(entry.get("fn")))

    # ── 负向夹具 ─────────────────────────────────────────────────────
    good = {"probes_dir": "archive/fake-probes", "root_keep": ["_keep.sh"]}
    rf = ["_keep.sh", "infer-load", "README.md"]
    af = ["_old.sh"]
    fz = ["ops/infer-load", "ops/cluster.py"]

    bad0, _ = validate(good, rf, af, fz)
    chk("负向夹具：正例应全过", not bad0, "; ".join(bad0))

    bad1, _ = validate(good, rf + ["_stray.sh"], af, fz)
    chk("负向夹具：根目录多一个 _* ⇒ FAIL",
        any("_stray.sh" in b for b in bad1), bad1)

    bad2, _ = validate(good, rf, [], fz)
    chk("负向夹具：归档目录为空 ⇒ FAIL",
        any("归档" in b or "probes" in b for b in bad2), bad2)

    bad3, _ = validate(good, rf, af, fz + ["ops/station-bin/_old.sh"])
    chk("负向夹具：登记表残留根级探针 ⇒ FAIL",
        any("登记" in b or "frozen" in b for b in bad3), bad3)

    bad4, _ = validate(good, ["infer-load"], af, fz)
    chk("负向夹具：白名单文件不存在（腐化）⇒ FAIL",
        any("_keep.sh" in b for b in bad4), bad4)

    bad5, _ = validate(good, rf, af + ["_keep.sh"], fz)
    chk("负向夹具：根目录与归档同名 ⇒ FAIL",
        any("同名" in b or "_keep.sh" in b for b in bad5), bad5)

    print(f"\nRESULT: {'ALL PASS' if not fails else f'FAIL ({len(fails)} 项)'}"
          f" · 失败: {', '.join(fails) if fails else '无'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
