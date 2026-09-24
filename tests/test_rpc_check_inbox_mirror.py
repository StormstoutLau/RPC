"""`mirror` 断言 M-5/M-6（受理状态机真值 ↔ README §3 + 真值自洽）的正反注入 —— 永久护栏

事实源 = `inventory/inbox.yaml` 的 `states:`；镜像 = `inbox/README.md` §3 的白名单/状态表。
⭐ **双向自证用真实数据**（取仓库真的 yaml 与真的 README，再篡改一处 ⇒ 必须点名），
   从而证明判据在真数据上具辨别力，且**不碰任何文件**。

⚠ 收敛后（两处代码都消费 yaml）"两端白名单相等"退化为**恒真** ⇒ 判据的实质只剩
   「真值自洽」+「README §3 对账」。本测试正是钉住这两条。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _real():
    return (R.read_inbox_truth(R.INBOX_TRUTH_YAML),
            R.INBOX_README.read_text(encoding="utf-8", errors="replace"))


def _edit_whitelist_line(readme, old, new):
    """只改 §3 的『合法取值白名单』那一行（避免波及状态表同名字符串）。"""
    lines = readme.splitlines(True)
    for i, l in enumerate(lines):
        if "合法取值白名单" in l:
            lines[i] = l.replace(old, new)
            break
    return "".join(lines)


def main() -> int:
    fails = []
    states, readme = _real()
    print(f"  [真实真值源] {len(states)} 态：{sorted(states)}")

    # ① 真实基线必须干净
    bad = R.validate_inbox_mirror(states, readme)
    if bad:
        fails.append(f"真实基线不干净: {bad}")
    else:
        print(f"  ok   真实基线：0 bad（{len(states)} 态 · 白名单/表/自洽全一致）")

    # ② ★ README 白名单少一态 ⇒ 必须点名（"改一处忘改另一处"的入口）
    r2 = _edit_whitelist_line(readme, "`waiting` ", "")
    bad2 = R.validate_inbox_mirror(states, r2)
    ok2 = any("白名单与真值不一致" in b and "waiting" in b for b in bad2)
    print(f"  {'ok  ' if ok2 else 'FAIL'} [负例1] README 白名单删 `waiting` ⇒ 点名：{'在' if ok2 else '缺'}")
    if not ok2:
        fails.append(f"负例1 未点名: {bad2}")

    # ③ ★ README 状态表少一行 ⇒ 必须点名
    r3 = "".join(l for l in readme.splitlines(True) if not l.startswith("| `triage` |"))
    bad3 = R.validate_inbox_mirror(states, r3)
    ok3 = any("状态表与真值不一致" in b and "triage" in b for b in bad3)
    print(f"  {'ok  ' if ok3 else 'FAIL'} [负例2] README 表删 `triage` 行 ⇒ 点名：{'在' if ok3 else '缺'}")
    if not ok3:
        fails.append(f"负例2 未点名: {bad3}")

    # ④ ★ 真值里某态缺 group ⇒ 必须点名（否则静默落进 closed = 真静默缺口）
    s4 = dict(states)
    s4["open"] = {"next": "x"}
    bad4 = R.validate_inbox_mirror(s4, readme)
    ok4 = any("group" in b and "open" in b for b in bad4)
    print(f"  {'ok  ' if ok4 else 'FAIL'} [负例3] 真值 open 缺 group ⇒ 点名：{'在' if ok4 else '缺'}")
    if not ok4:
        fails.append(f"负例3 未点名: {bad4}")

    # ⑤ ★ 真值里某态缺 next ⇒ 必须点名（M-6 的键集缺口）
    s5 = dict(states)
    s5["done"] = {"group": "closed"}
    bad5 = R.validate_inbox_mirror(s5, readme)
    ok5 = any("缺 next" in b and "done" in b for b in bad5)
    print(f"  {'ok  ' if ok5 else 'FAIL'} [负例4] 真值 done 缺 next ⇒ 点名：{'在' if ok5 else '缺'}")
    if not ok5:
        fails.append(f"负例4 未点名: {bad5}")

    # ⑥ 结构护栏：断言已注册（否则写了没人跑）
    if "mirror" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='mirror' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'mirror' 已在 CHECKS 注册")

    # ⑦ 两处代码与真值同源（防回归硬编码）
    sys.path.insert(0, str(ROOT / "ops"))
    import cluster_web  # noqa: E402
    if set(cluster_web.INBOX_STATES) != set(states) or set(cluster_web._INBOX_NEXT) != set(states):
        fails.append("cluster_web 的白名单/下一动作与真值不同源")
    else:
        print("  ok   同源护栏：cluster_web.INBOX_STATES / _INBOX_NEXT 均 == 真值键集")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
