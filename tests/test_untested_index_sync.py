#!/usr/bin/env python3
r"""未实测索引 ↔ 规范节的双向对账 + 字段闭集校验（2026-09-30）

为什么要有这条测试：`inventory/untested-index.yaml` 是 6 份规范 `## 未实测登记` 节的
**分诊索引**。它一旦与原文漂移（少一条 / 多一条 / 编号写错），"可机读"就变成"**可机读的错**"
—— 门禁 `spec-untested` **不判**这种漂移（它 2026-09-30 起只**消费**分诊：报分布 +
`needs_decision: true` ⇒ WARN；**不**重做对账/闭集校验 —— 判据只在一处，就在这里）。

真值源分工（**不造第二份真值**）：
  · 条目的**存在与编号** ⇒ 真值在**各规范的节**（本测试**双向对账**：编号集合必须相等）；
  · **分诊字段**（`state` / `needs_decision` / `refs` / `blocker`）⇒ 真值**只在索引里**
    （规范节里**不写**分诊 ⇒ 不存在"同一事实两处表达"）。

覆盖：① 6 份规范**每份**都要在索引里出现；② 编号集合**双向相等**（缺 / 多都报）；
      ③ `state` 闭集 · `needs_decision` 必须是 bool · `gist` 非空 · `refs` 元素形如 `O-\d+` / `D-\d+`
         · `blocker` 闭集（★ 2026-09-30 新增，`O-123`：区分「**没跑**」与「**没实现**」）；
      ④ 读数（条目数 / state 分布 / needs_decision 数 / blocker 分布）**算出来打印**，不写死。

⚠⚠ **本文件自带 `__main__` 入口**：门禁 `py-tests` 以**脚本**方式调用（只认退出码）。
  没有它 ⇒ 被 import、正常退出 0 ⇒ 门禁报 PASS 而**一条都没跑**（O-89 实测过一次）。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec" / "d6-agent-standard"
INDEX = ROOT / "inventory" / "untested-index.yaml"
GLOBS = ("U[0-9]-*.md", "D7-PROTOCOL-*.md")

SECTION = re.compile(r"^##\s*未实测登记\s*$")
ITEM = re.compile(r"^\s{0,3}(\d+)\.\s")
STATES = ("todo", "partial", "retired", "boundary")
BLOCKERS = ("run", "implementation", "decision", "external", "none")
REF = re.compile(r"^[OD]-\d+$")


def spec_items() -> dict:
    """从各规范的 `## 未实测登记` 节抽条目编号 ⇒ {规范名: {编号,…}}"""
    out = {}
    files = sorted({p for g in GLOBS for p in SPEC.glob(g)})
    for f in files:
        lines = f.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        start = [i for i, ln in enumerate(lines) if SECTION.match(ln)]
        if len(start) != 1:
            raise AssertionError(f"{f.name}: `## 未实测登记` 应恰 1 个，实得 {len(start)}")
        end = len(lines)
        for j in range(start[0] + 1, len(lines)):
            if re.match(r"^##\s", lines[j]):
                end = j
                break
        nums = {int(m.group(1))
                for ln in lines[start[0] + 1:end]
                if (m := ITEM.match(ln))}
        out[f.stem] = nums
    return out


def main() -> int:
    try:
        import yaml
    except Exception as e:                       # 缺 pyyaml ⇒ **不可判 ≠ 通过**
        print(f"RESULT: FAIL 缺 pyyaml（{type(e).__name__}: {e}）⇒ 索引不可对账")
        return 1
    if not INDEX.is_file():
        print(f"RESULT: FAIL 缺 {INDEX.relative_to(ROOT)}（本测试的对账对象）")
        return 1

    fails = []
    items = (yaml.safe_load(INDEX.read_text(encoding="utf-8")) or {}).get("items") or []
    if not items:
        print("RESULT: FAIL 索引条目为 0 ⇒ 判据没有对象（防空判）")
        return 1

    got = {}
    for it in items:
        miss = [k for k in ("spec", "n", "gist", "state", "needs_decision", "refs", "blocker") if k not in it]
        if miss:
            fails.append(f"条目缺字段 {miss}: {it}")
            continue
        sp, n = it["spec"], it["n"]
        if it["state"] not in STATES:
            fails.append(f"{sp}#{n}: state={it['state']!r} 不在闭集 {list(STATES)}")
        if it["blocker"] not in BLOCKERS:
            fails.append(f"{sp}#{n}: blocker={it['blocker']!r} 不在闭集 {list(BLOCKERS)}")
        if not isinstance(it["needs_decision"], bool):
            fails.append(f"{sp}#{n}: needs_decision 必须是 bool，实得 {type(it['needs_decision']).__name__}")
        if not str(it["gist"] or "").strip():
            fails.append(f"{sp}#{n}: gist 为空")
        if not isinstance(it["refs"], list):
            fails.append(f"{sp}#{n}: refs 必须是列表")
        else:
            for r in it["refs"]:
                if not REF.match(str(r)):
                    fails.append(f"{sp}#{n}: refs 元素 {r!r} 不是 O-/D- 编号")
        got.setdefault(sp, set()).add(n)

    want = spec_items()
    for sp, nums in want.items():
        if sp not in got:
            fails.append(f"规范 {sp} 在索引里一条都没有")
            continue
        miss, extra = sorted(nums - got[sp]), sorted(got[sp] - nums)
        if miss:
            fails.append(f"{sp}: 索引**缺**条目 {miss}（原文有、索引没写）")
        if extra:
            fails.append(f"{sp}: 索引**多**条目 {extra}（索引有、原文没有 ⇒ 第二份真值的入口）")
    for sp in sorted(set(got) - set(want)):
        fails.append(f"索引里的 spec={sp!r} 不是规范文件（拼写？）")

    tot = sum(len(v) for v in got.values())
    dist = {s: sum(1 for i in items if i["state"] == s) for s in STATES}
    bdist = {b: sum(1 for i in items if i["blocker"] == b) for b in BLOCKERS}
    dec = sum(1 for i in items if i["needs_decision"])
    print(f"  规范 {len(want)} 份 · 索引条目 {tot} · state 分布 {dist} · needs_decision {dec}")
    print(f"  blocker 分布 {bdist}")
    print()
    if fails:
        print("FAIL:")
        for x in fails:
            print("  ✗ " + x)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())