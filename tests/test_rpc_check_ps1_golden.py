"""P3-2 `ps1-golden` 断言 护栏 —— 钉住"出站硬闸的正反用例必须一直在夹具里"

为什么需要：本断言只负责**跑**夹具。若有人把夹具里的"该拒 / 放行"用例删掉，断言**仍会 PASS**
（判据变成恒真）⇒ 必须静态钉住那几条**非空转**用例的存在（同 O-40「登记无出口 ⇒ 腐化」家族）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

FIX = ROOT / "ops" / "station-bin" / "_fm_golden_test.ps1"
CLI = ROOT / "ops" / "station-bin" / "agent-cli.ps1"


def main() -> int:
    fails = []
    src = FIX.read_text(encoding="utf-8", errors="replace")

    # ① 接线：夹具在 · CHECKS 引用它 · **quick**（⇒ 由 pre-commit 钩子强制，才叫真接线）
    entry = next((c for c in R.CHECKS if c["id"] == "ps1-golden"), None)
    ok1 = FIX.is_file() and entry is not None and bool(entry.get("quick"))
    print(f"  {'ok  ' if ok1 else 'FAIL'} [接线] 夹具在 · CHECKS 有 'ps1-golden' 且为 quick")
    if not ok1:
        fails.append(f"接线不对: exists={FIX.is_file()} entry={entry}")

    # ② ★ 非空转：出站硬闸的**四类**用例必须都在（删任一条 ⇒ 判据恒真 / 误杀 P3）
    cases = {
        "① 该拒": "local-only + 出网后端 => 'local-only+egress'",
        "② 放行(本地引擎)": "local-only + 本地引擎(不出网) => 放行",
        "③ 放行(防恒真)": "public + 出网后端 => 放行",
        "④ claude 运行时判": "-backendEgress (-not $backendLocal)",
    }
    for label, needle in cases.items():
        hit = needle in src
        print(f"  {'ok  ' if hit else 'FAIL'} [用例] {label}: {'在' if hit else '缺'}")
        if not hit:
            fails.append(f"夹具缺用例 {label}（needle={needle!r}）")

    # ③ fail-closed 判据仍在：只有 `local/` 不出网，其余（含未知/空）一律视为出网
    ok3 = "-not ($id -match '^local/')" in CLI.read_text(encoding="utf-8", errors="replace")
    print(f"  {'ok  ' if ok3 else 'FAIL'} [fail-closed] Get-BackendEgress 仍是「只有 local/ 不出网」")
    if not ok3:
        fails.append("Get-BackendEgress 的 fail-closed 判据不见了")

    # ④ 实跑一次（本机有 powershell 才跑）—— 退出码 0 才算 PASS
    st, note, _det = R.check_ps1_golden({})
    ok4 = st in ("PASS", "WARN")          # WARN = 本机无 powershell ⇒ 不算失败
    print(f"  {'ok  ' if ok4 else 'FAIL'} [实跑] {st} · {note}")
    if not ok4:
        fails.append(f"实跑非 PASS/WARN: {st} · {note}")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
