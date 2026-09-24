"""`sensitivity` 断言（O-51）的正反注入 —— 永久护栏（2026-09-24）

O-51 的定性：`inventory/sensitivity.yaml` 是**权威源在自身**的真值表，但建成后 `ops/` 全域零命中
⇒ "**存在但无人读**"的活标本。本护栏保护把它接上义务的那 4 条判据。

⭐ **真实世界的双向自证已经发生过**（比合成用例更强）：
   该断言**首跑即报红** —— `docs/2026-09-23_D7统一基座_数理证明与知识提取三线调研.md`
   **曾入库后被改名**（`cdec317` → 并入 `...D7调研_立项·机制·统一基座.md`）⇒ 登记**指向空物**。
   删除陈旧别名后**转绿**。⇒ 证明该断言**非恒真**、且**真能抓东西**。

本文件补的是**离线可重放**的那部分：4 条规则各自的判别力（不依赖真文件）。
"""
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

EXISTS = {"docs/ok.md": True}


def _inv(**sections):
    base = {"default_tier": "local-only", "documents": [], "contracts": [], "code": []}
    base.update(sections)
    return base


CASES = [
    ("正例 一条 local-only，路径存在",
     _inv(documents=[{"path": "docs/ok.md", "tier": "local-only"}]),
     True, "条目 1 条"),
    ("★反例 路径不存在（登记指向空物）",
     _inv(documents=[{"path": "docs/ghost.md", "tier": "local-only"}]),
     False, "路径不存在"),
    ("★反例 tier 不在封闭枚举",
     _inv(documents=[{"path": "docs/ok.md", "tier": "pbulic"}]),
     False, "不在封闭枚举"),
    ("★反例 同一 path 两处不同 tier",
     _inv(documents=[{"path": "docs/ok.md", "tier": "local-only"}],
          code=[{"path": "docs/ok.md", "tier": "public"}]),
     False, "同一路径两处不同 tier"),
    ("正例 同一 path 两处**同** tier（允许：不矛盾）",
     _inv(documents=[{"path": "docs/ok.md", "tier": "public"}],
          code=[{"path": "docs/ok.md", "tier": "public"}]),
     True, "条目 2 条"),
    ("反例 条目缺 path",
     _inv(documents=[{"tier": "local-only"}]),
     False, "缺 `path`"),
]


def main() -> int:
    fails = []
    for desc, inv, want_ok, kw in CASES:
        bad, st = R.validate_sensitivity_inv(inv, lambda p: EXISTS.get(p, False))
        blob = " ".join(bad) + f" 条目 {st['n']} 条"
        got_kw = kw in blob
        ok = ((not bad) == want_ok) and got_kw
        print(f"  {'ok  ' if ok else 'FAIL'} {desc}\n        bad={len(bad)} · '{kw}':"
              f"{'在' if got_kw else '缺'}")
        if not ok:
            fails.append(f"{desc} ⇒ bad={bad} stats={st}")

    # 结构护栏：函数存在**且已注册**（"写了函数忘了进 CHECKS" = 挂名假判）
    if "sensitivity" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='sensitivity' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'sensitivity' 已在 CHECKS 注册")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
