"""证据流判据回归测试（ADR-0007 批 A：A1 verdict-chain / A2 golden-identity）。

为什么要有这条测试：A1 首版曾把**显示标签** `proj/ts` 当成 `TASK_ID` 的比对对手，
导致 `meta.TASK_ID != label` 恒真 ⇒ 判据静默降级为"永远跳过"，而命令仍返回 PASS
（覆盖率假报 0/67）。T3 专门守住该回归 —— 它是本案唯一"通过但什么都没判"的实例。

用法（退出码 0 = 全过）：
    py tests\\test_evidence_judges.py
"""
import sys
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import cluster as C                                    # noqa: E402

fails = []
BASE = dict(proj="t", exit_code=0, status="completed",
            accept={"cmd": [], "passed": True},
            accept_golden={"cmd": [], "passed": True},
            queue_s=2, run_s=5)
META_OK = ("TASK_ID={ts}\nQUEUE_S=2\nRUN_S=5\nTASK_RC=0\nACCEPT_OK=1\n"
           "ACCEPT_GOLDEN_OK=1\nREVIEW_NEEDED=0\n")


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


def mk(d, meta_text, run_json):
    d.mkdir(parents=True, exist_ok=True)
    (d / "judgment-record.txt").write_text(meta_text, encoding="utf-8")
    (d / ".agent-run.json").write_text(json.dumps(run_json), encoding="utf-8")
    return d


tmp = Path(tempfile.mkdtemp(prefix="evidence-judges-"))
try:
    # ── A1 verdict-chain ──
    d = mk(tmp / "t1", META_OK.format(ts="1111"), BASE)
    bad, gap, ok = C._verdict_check(d, "1111", "t/1111")
    chk("T1 consistent => judged", ok and not bad and not gap, f"bad={bad} gap={gap}")

    d = mk(tmp / "t2", META_OK.format(ts="9999"), BASE)
    bad, gap, ok = C._verdict_check(d, "1111", "t/1111")
    chk("T2 META_STALE => gap not fail", (not bad) and (not ok) and gap and "残留" in gap[0],
        f"bad={bad} ok={ok}")

    d = mk(tmp / "t3", META_OK.format(ts="1111"), BASE)
    bad, gap, ok = C._verdict_check(d, "1111", "t/1111")
    chk("T3 lang=ts separated => judged", ok and not gap, f"ok={ok} gap={gap}")

    d = mk(tmp / "t4", META_OK.format(ts="1111").replace("ACCEPT_OK=1", "ACCEPT_OK=0"), BASE)
    bad, gap, ok = C._verdict_check(d, "1111", "t/1111")
    chk("T4 accept mismatch => issue", bool(bad) and "ACCEPT_OK" in bad[0], f"bad={bad}")

    d = mk(tmp / "t5", META_OK.format(ts="1111"), dict(BASE, exit_code=1))
    bad, gap, ok = C._verdict_check(d, "1111", "t/1111")
    chk("T5 rc map violation => issue", bool(bad) and "TASK_RC" in bad[0], f"bad={bad}")

    d = mk(tmp / "t6", META_OK.format(ts="1111").replace("TASK_RC=0", "TASK_RC=9"),
           dict(BASE, exit_code=1))
    bad, gap, ok = C._verdict_check(d, "1111", "t/1111")
    chk("T6 rc 9 -> exit 1 allowed", ok and not bad, f"bad={bad}")

    d = mk(tmp / "t7", META_OK.format(ts="1111").replace("TASK_RC=0", "TASK_RC=9"),
           dict(BASE, exit_code=0))
    bad, gap, ok = C._verdict_check(d, "1111", "t/1111")
    chk("T7 rc 9 with exit 0 => issue", bool(bad), f"bad={bad}")

    d = tmp / "t8"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".agent-run.json").write_text("{}", encoding="utf-8")
    bad, gap, ok = C._verdict_check(d, "1111", "t/1111")
    chk("T8 no meta => not_applicable", (not ok) and gap and gap[0].endswith(":not_applicable"),
        f"gap={gap}")

    d = mk(tmp / "t9", "TASK_ID=1111\n", dict(BASE, accept={"cmd": []}, exit_code=None))
    bad, gap, ok = C._verdict_check(d, "1111", "t/1111")
    chk("T9 uncomparable => not judged (no coverage inflation)",
        (not ok) and (not bad), f"ok={ok} bad={bad}")

    # ── A2 golden-identity ──
    d = mk(tmp / "t10", META_OK.format(ts="1111"),
           dict(BASE, accept_golden={"cmd": [], "passed": True,
                                     "base": "no_such_golden_zzz.py", "sha256": "ab" * 32}))
    gb, gg, gok = C._golden_identity_check(d, "t/1111")
    chk("T10 A2 missing source => gap, never FAIL",
        (not gb) and gg and gok and "不在仓库" in gg[0], f"gb={gb} gg={gg}")

    d = mk(tmp / "t11", META_OK.format(ts="1111"),
           dict(BASE, accept_golden={"cmd": [], "passed": True,
                                     "base": "agent-cli.ps1", "sha256": "cd" * 32}))
    gb, gg, gok = C._golden_identity_check(d, "t/1111")
    chk("T11 A2 hash changed => gap, never FAIL",
        (not gb) and gg and gok and "需人判" in gg[0], f"gb={gb} gg={gg}")

    real = ROOT / "ops" / "station-bin" / "agent-cli.ps1"
    d = mk(tmp / "t12", META_OK.format(ts="1111"),
           dict(BASE, accept_golden={"cmd": [], "passed": True,
                                     "base": real.name, "sha256": C._sha256_file(real)}))
    gb, gg, gok = C._golden_identity_check(d, "t/1111")
    chk("T12 A2 hash match => clean", (not gb) and (not gg) and gok, f"gb={gb} gg={gg}")

    d = mk(tmp / "t13", META_OK.format(ts="1111"), dict(BASE, accept_golden=None))
    gb, gg, gok = C._golden_identity_check(d, "t/1111")
    chk("T13 A2 non-golden card => n/a", (not gb) and (not gg) and (not gok), f"gok={gok}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("RESULT:", "ALL PASS (13/13)" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
