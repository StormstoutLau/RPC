"""失败 run 的可重放缺口口径（2026-10-23）。

背景：evidence 门禁报 90 条新增可重放 gap。逐条归因后 88 条来自 8 次**同一张失败探针卡**
（`exit 1` / `status=failed`，`accept_golden` 未过）⇒ 11 个**框架基线** subject 在失败路径上
天然不产出。若仍按 `missing-artifact` 记，**每次失败 run 都会再灌 11 条**噪声
⇒ 判据被整体忽略（与 O-61 当时"锁占用 run 灌噪声"同族）。

口径（与 O-61 `exit 3` 的 `locked-out-by-design` 同族，**第三态**）：
  run 本身未完成（`status` 存在且 != `completed`；`status` 缺时退回 `exit_code not in (0,3)`）
  ⇒ 其 `missing-artifact` 记 `failed-run-by-design`：**单列、不计入缺口、不计入可离线复算**。
  ★ 正向对照：`completed` 的 run 缺件**仍记** `missing-artifact`（不得一刀切）。

用法（退出码 0 = 全过）：
    py tests\\test_agent_audit_failed_run.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
sys.path.insert(0, str(ROOT / "tests"))
from _cluster_proxy import cluster_proxy  # noqa: E402  ★ 拆分后打桩须落到定义模块
C = cluster_proxy()

fails = []


def chk(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("   " + extra if extra else ""))
    if not cond:
        fails.append(name)


MANIFEST = {"version": "1", "framework_version": "2", "subjects": [
    {"name": "agent-output", "path": "agent-output.txt", "collect": "", "digest": "sha256",
     "ephemeral": False, "state": ""},
    {"name": "prompt", "path": "prompt.txt", "collect": "", "digest": "sha256",
     "ephemeral": False, "state": ""},
]}


def mk_run(root, ts, meta):
    d = Path(root) / "proj" / "agent-out" / ts
    d.mkdir(parents=True, exist_ok=True)
    (d / ".agent-run.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (d / "agent-output.txt").write_text("ok\n", encoding="utf-8")
    return d


tmp = tempfile.mkdtemp(prefix="audit-failed-")
try:
    proj_root = Path(tmp) / "proj"
    (proj_root / "agent-out").mkdir(parents=True)
    failed_dir = mk_run(tmp, "202601010000000001",
                        {"exit_code": 1, "status": "failed", "evidence_manifest": MANIFEST})
    ok_dir = mk_run(tmp, "202601010000000002",
                    {"exit_code": 0, "status": "completed", "evidence_manifest": MANIFEST})

    real_roots, real_runs = C._agent_proj_roots, C._chain_runs
    C._agent_proj_roots = lambda: ({"proj": str(proj_root)}, "")
    C._chain_runs = lambda roots: [("202601010000000001", "proj", failed_dir),
                                   ("202601010000000002", "proj", ok_dir)]
    try:
        r = C.agent_audit()
    finally:
        C._agent_proj_roots, C._chain_runs = real_roots, real_runs

    texts = "\n".join(r["gaps"])
    chk("A1 失败 run 的缺件**不再**记 missing-artifact",
        "202601010000000001" not in texts, texts[:200])
    chk("A2 失败 run 的 readiness = failed-run-by-design",
        any(s["readiness"] == "failed-run-by-design"
            for run in r["runs"] if run["label"].endswith("202601010000000001")
            for s in run["subjects"] if s["name"] == "prompt"))
    chk("A3 totals 单列计数 failed_run_absent",
        r["totals"].get("failed_run_absent") == 1, f"totals={r['totals']}")
    chk("A4 coverage 显式声明不计入缺口/不计入可离线复算",
        any("失败 run 缺席" in x and "不计入可离线复算" in x for x in r["coverage"]))
    chk("A5 正向对照：completed run 缺件**仍**记 missing-artifact",
        "202601010000000002" in texts and "subject 'prompt'" in texts, texts[:300])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED -> {fails}")
sys.exit(1 if fails else 0)
