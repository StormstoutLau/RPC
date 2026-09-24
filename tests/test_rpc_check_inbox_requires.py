"""`requires`（必需件）派生 + 手册/README 对账（#7/#8/#9）的正反注入 —— 永久护栏

⭐ **固化等价**：#7 落地前 `check_inbox` 有 4 处硬编码状态子集，落地后全部由真值 `requires` 派生 ——
   本测试把**重构前的原值**钉成 `EXPECT`，证明"派生结果 == 原硬编码值"（重构未改行为）。
⭐ **双向自证用真实数据**：取真 yaml / 真手册 / 真 README，篡改一处 ⇒ 必须点名。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

# 重构前 check_inbox 的 4 处硬编码"必需件"子集 —— 派生必须与之等价
EXPECT = {
    "decide": {"accepted", "plan-review", "plan-revise", "running", "release", "done",
               "accepted-by-requester", "rejected-by-requester"},
    "plan": {"plan-review", "plan-revise"},
    "evidence": {"release", "done", "accepted-by-requester", "rejected-by-requester"},
    "manifest": {"release", "done", "accepted-by-requester"},
}


def main() -> int:
    fails = []
    states = R.read_inbox_truth(R.INBOX_TRUTH_YAML)

    # ① ★ 固化等价：派生 == 重构前的硬编码值
    for k, want in EXPECT.items():
        got = R.inbox_requires_sets(states, k)
        if got != want:
            fails.append(f"requires[{k}] 派生 != 原硬编码: 多 {sorted(got - want)} / "
                         f"少 {sorted(want - got)}")
    if not fails:
        print("  ok   固化等价：4 个必需件子集派生 == 重构前硬编码值")

    # ② 真值自洽（每态有 group/next/requires，键合法）—— 由 validate_inbox_mirror 管
    bad = R.validate_inbox_mirror(states,
                                  R.INBOX_README.read_text(encoding="utf-8", errors="replace"))
    if bad:
        fails.append(f"validate_inbox_mirror 基线不干净: {bad}")
    else:
        print("  ok   真值自洽：12 态均有 group/next/requires，键均合法")

    # ③ #9 手册：真实基线干净
    manual = R.MANUAL.read_text(encoding="utf-8", errors="replace")
    if R.validate_manual_states(states, manual):
        fails.append("手册 §1.3 基线不干净")
    else:
        print("  ok   手册 §1.3 基线：12 态逐个提到")

    # ④ ★ 手册删掉 rejected 注记 ⇒ 必须点名（实测原图就是漏了它）
    manual2 = re.sub(r"（另有终止态 `rejected`，[^）]*）", "", manual)
    bad4 = R.validate_manual_states(states, manual2)
    ok4 = any("rejected" in b for b in bad4)
    print(f"  {'ok  ' if ok4 else 'FAIL'} [负例1] 手册删 `rejected` 注记 ⇒ 点名：{'在' if ok4 else '缺'}")
    if not ok4:
        fails.append(f"负例1 未点名: {bad4}")

    # ⑤ #7/README：交付态行基线干净
    readme = R.INBOX_README.read_text(encoding="utf-8", errors="replace")
    if R.validate_readme_requires(states, readme):
        fails.append("README §5.3 交付态行基线不干净")
    else:
        print("  ok   README §5.3「交付态强判据」行 == 真值 manifest 集")

    # ⑥ ★ 篡改交付态行 ⇒ 必须点名
    readme2 = re.sub(r"交付态强判据[^\n]*", "交付态强判据：`release` / `done` 两态", readme)
    bad6 = R.validate_readme_requires(states, readme2)
    ok6 = any("不一致" in b for b in bad6)
    print(f"  {'ok  ' if ok6 else 'FAIL'} [负例2] README 交付态行删 accepted-by-requester ⇒ 点名："
          f"{'在' if ok6 else '缺'}")
    if not ok6:
        fails.append(f"负例2 未点名: {bad6}")

    # ⑦ #8 同源护栏：cluster.py 交付态提示与真值 manifest 集同源
    import cluster  # noqa: E402
    got8 = {s for s, sp in cluster._inbox_truth().items()
            if "manifest" in ((sp or {}).get("requires") or [])}
    if got8 != EXPECT["manifest"]:
        fails.append(f"cluster._inbox_truth 交付态集与真值不一致: {sorted(got8)}")
    else:
        print("  ok   同源护栏：cluster.py seal 提示语状态集 == 真值 manifest 集")

    # ⑧ ★ #6 固化等价：徽章派生 == 重构前前端 JS 的硬编码分类（空串=中性）
    import cluster_web  # noqa: E402

    def old_badge(st):
        if st == "waiting":
            return "warn"
        if st in ("plan-review", "release"):
            return "warn"
        if st in ("running", "triage", "accepted", "plan-revise", "open"):
            return ""
        if st in ("done", "accepted-by-requester"):
            return "ok"
        if st in ("rejected-by-requester", "rejected"):
            return "err"
        return "err"

    got_badge = {s: ("" if b == "none" else b) for s, b in cluster_web._INBOX_BADGE.items()}
    want_badge = {s: old_badge(s) for s in states}
    if got_badge != want_badge:
        diff = {s: (want_badge[s], got_badge[s]) for s in states if want_badge[s] != got_badge[s]}
        fails.append(f"徽章派生 != 旧 JS 硬编码: {diff}")
    else:
        print("  ok   固化等价：12 态徽章派生 == 重构前 JS 硬编码分类")

    # ⑨ #6 页面注入：占位符必须被替换干净（否则前端 JS 会坏）
    page = cluster_web._build_page()
    left = [p for p in ("{{INBOX_BADGE}}", "{{BACKEND_OPTIONS}}") if p in page]
    if left:
        fails.append(f"_build_page 未替换占位符: {left}")
    else:
        print("  ok   页面注入：_build_page 已替换 {{INBOX_BADGE}}/{{BACKEND_OPTIONS}}")

    # ⑩ 结构护栏
    if "mirror" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='mirror'（断言写了没人跑）")
    else:
        print("  ok   结构护栏：'mirror' 已在 CHECKS 注册")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
