"""`artifacts`（生成物清单，D6-P1-1）的正反注入 —— 永久护栏（2026-09-24）

被保护的两类病（本仓"假绿"家族的两个变体）：
  · **静默缺口**：某文件是推导出来的，**既没人判、也没说明为什么不判**；
  · **挂名假判**：清单写了 `check: xxx`，但 `xxx` **不是真实断言 id**（改名/删除后无人发现）。

为什么用 monkeypatch 而不是真改文件：本判据的**注入面**只有"清单文件内容"一处
（`R.ARTIFACTS_INV` 是模块级全局）⇒ 指向临时文件即可**离线**覆盖全分支，
**不必碰任何受版本控制的文件**（与 `test_rpc_check_engine_bands.py` 同法）。
⚠ 交叉验证（"手工改一处生成物 ⇒ FAIL"）需改真文件，故**不**放本护栏 ——
   那次已作为一次性实验记录在 DEV-LOG-014（含逐字节复原校验）。
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

GOOD = """version: 1
items:
  - path: archive/evidence-chain/agent-chain.json
    authority: "cluster.py agent chain"
    check: evidence
  - path: .git/hooks/pre-commit
    exempt: "由 ops/rpc.ps1 install-hooks 生成"
"""

BAD_FAKE_ID = """version: 1
items:
  - path: x.json
    check: no_such_gate
"""

BAD_SILENT = """version: 1
items:
  - path: x.json
    authority: "某处推导"
"""

BAD_BOTH = """version: 1
items:
  - path: x.json
    check: evidence
    exempt: "又想判又写豁免"
"""

CASES = [
    ("正例 一条 check + 一条 exempt", GOOD, "PASS", "有断言覆盖 1 · 显式豁免 1"),
    ("★反例 挂名假判（check 不是真实 id）", BAD_FAKE_ID, "FAIL", "不是真实断言 id"),
    ("★反例 静默缺口（既无 check 也无 exempt）", BAD_SILENT, "FAIL", "静默缺口"),
    ("★反例 check 与 exempt 互斥", BAD_BOTH, "FAIL", "互斥"),
    ("反例 清单文件缺失", None, "FAIL", "artifacts.yaml 缺失"),
]


def _run(content, tmpdir):
    p = Path(tmpdir) / "artifacts.yaml"
    if content is None:
        if p.exists():
            p.unlink()
    else:
        p.write_text(content, encoding="utf-8", newline="")
    orig = R.ARTIFACTS_INV
    R.ARTIFACTS_INV = p
    try:
        return R.check_artifacts(None)
    finally:
        R.ARTIFACTS_INV = orig


def main() -> int:
    fails = []
    with tempfile.TemporaryDirectory() as td:
        for desc, content, want, kw in CASES:
            v, note, detail = _run(content, td)
            blob = note + " " + " ".join(detail)
            ok = (v == want) and (kw in blob)
            print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        verdict={v}(期望 {want}) · "
                  f"'{kw}':{'在' if kw in blob else '缺'}")
            if not ok:
                fails.append(f"{desc} ⇒ v={v} blob={blob[:140]}")

    # 结构护栏：函数存在**且已注册**（"写了函数忘了进 CHECKS" 正是挂名假判的真实形态）
    ids = {c["id"] for c in R.CHECKS}
    if "artifacts" not in ids:
        fails.append("CHECKS 里没有 id='artifacts' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'artifacts' 已在 CHECKS 注册")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
