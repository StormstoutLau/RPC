"""【**手工运行**，勿自动收集】D6-P1-1 `artifacts` 断言的**跨文件**负向验证。

与 `tests/test_rpc_check_artifacts.py` 的分工（**别混**）：
  · `tests/…`  = **持久护栏**，monkeypatch `ARTIFACTS_INV` ⇒ **不碰受版本控制的文件**，随 `run_py_tests.py` 自动跑；
  · **本脚本**   = 覆盖 `tests/` **覆盖不到**的那一条 ——
    「**手工改一处生成物 ⇒ 应 FAIL**」（路线总表 §3 P1-1 给本批定的验证判据），
    它**必须**改真文件（`inventory/ops.yaml`），故**刻意不进 `tests/`**（避免被自动跑时中断而留下脏工作区）。

安全措施（本仓对"破坏性操作"的既有纪律）：
  改动前记 sha256 → 改动 → 验证 → **finally 还原** → **校验 sha256 逐字节复原**。

用法（从仓库根）：
    py -3.12 spec/d6-agent-standard/fixtures/negtest_artifacts.py
"""
import hashlib
import sys
from pathlib import Path

# 从本文件向上找到含 ops/rpc_check.py 的仓库根（不依赖目录层级硬编码）
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "ops" / "rpc_check.py").exists())
sys.path.insert(0, str(ROOT / "ops"))
import rpc_check as R  # noqa: E402

A = ROOT / "inventory" / "artifacts.yaml"
OPS = ROOT / "inventory" / "ops.yaml"

# ④ 的锚点：ops.yaml 里相邻的两条 frozen 登记（改动/还原都以此为准）
_OPS_A = "  - ops/lm-download/speedtest_asset.sh\n  - ops/lm-download/speedtest_codeload.sh"
_OPS_B = "  - ops/lm-download/speedtest_codeload.sh"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def mutate(p, old, new):
    s = p.read_text(encoding="utf-8")
    assert old in s, f"锚点未找到（源文件可能已变，需同步本脚本）: {old!r}"
    p.write_text(s.replace(old, new), encoding="utf-8", newline="")


CASES = [
    ("① 挂名假判：check 指向不存在的断言 id", R.check_artifacts, "不是真实断言 id",
     lambda: mutate(A, "check: scripts", "check: no_such_gate"),
     lambda: mutate(A, "check: no_such_gate", "check: scripts")),
    ("② 静默缺口：抽掉 exempt", R.check_artifacts, "静默缺口",
     lambda: mutate(A, 'exempt: "由 ops/rpc.ps1', 'xempt: "由 ops/rpc.ps1'),
     lambda: mutate(A, 'xempt: "由 ops/rpc.ps1', 'exempt: "由 ops/rpc.ps1')),
    ("③ 前提失效：inventory yaml 解析不了", R.check_artifacts, "解析失败",
     lambda: mutate(A, "version: 1", "version: 1\nbad: [unclosed"),
     lambda: mutate(A, "version: 1\nbad: [unclosed", "version: 1")),
    ("④ ★手工改生成物：删 ops.yaml 一条 frozen 登记 ⇒ scripts 应红", R.check_scripts, "未登记",
     lambda: mutate(OPS, _OPS_A, _OPS_B),
     lambda: mutate(OPS, _OPS_B + "\n", _OPS_A + "\n")),
]


def main() -> int:
    fails = []
    base = {p: sha(p) for p in (A, OPS)}

    for name, fn in (("artifacts", R.check_artifacts), ("scripts", R.check_scripts)):
        v, note, _ = fn(None)
        print(f"  [基线] {name}: {v}")
        if v != "PASS":
            fails.append(f"基线不绿: {name}={v}")

    for desc, fn, kw, do, undo in CASES:
        try:
            do()
            v, note, detail = fn(None)
            blob = note + " " + " ".join(detail)
            ok = (v == "FAIL") and (kw in blob)
            print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        verdict={v}(期望 FAIL) · "
                  f"'{kw}':{'在' if kw in blob else '缺'} · note={note[:110]}")
            if not ok:
                fails.append(f"{desc} ⇒ v={v} blob={blob[:160]}")
        finally:
            undo()

    for p in (A, OPS):
        now = sha(p)
        if now != base[p]:
            fails.append(f"未复原: {p.name} {base[p][:12]} -> {now[:12]}")
        else:
            print(f"  [复原] {p.name} sha256={now[:12]} ✓")
    for name, fn in (("artifacts", R.check_artifacts), ("scripts", R.check_scripts)):
        v, note, _ = fn(None)
        print(f"  [复原后] {name}: {v} · {note[:90]}")
        if v != "PASS":
            fails.append(f"复原后不绿: {name}={v}")

    total = len(CASES) + 4
    if fails:
        print(f"RESULT: 失败 {len(fails)}/{total}")
    else:
        print(f"RESULT: ALL PASS ({total}/{total})")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
