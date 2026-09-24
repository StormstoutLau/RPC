"""`mirror` 断言（D6-P1-2 M-1）的正反注入 —— 永久护栏（2026-09-24）

事实源 = `agent-cli.ps1` 的 `JUDGE_TABLE['main']`；镜像 = 手册 §1.3 的判官行。
⭐ **双向自证用真实数据**（取仓库真的事实源与真手册行，再篡改一个字 ⇒ 必须点名），
   从而证明判据在真数据上具辨别力，且**不碰任何文件**。

⚠ 首版踩的坑（留档）：判据统一按 `k=v` 查 ⇒ 对 `id` **假红**（手册写的是裸 `` `main-opencode-cli` ``，
   没有 `id=` 前缀）。⇒ 判据必须**尊重各键自然的书写形态**，否则"判据自己在制造不一致"。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _real():
    judge = R.read_judge_main(R.AGENT_CLI.read_text(encoding="utf-8", errors="replace"))
    row = next((l for l in R.MANUAL.read_text(encoding="utf-8", errors="replace").splitlines()
                if "JUDGE_TABLE['main']" in l), "")
    return judge, row


def main() -> int:
    fails = []
    judge, row = _real()
    print(f"  [真实事实源] {judge}")
    print(f"  [真实镜像行] {row[:96]}…")

    # ① 真实基线必须干净
    bad, st = R.validate_mirror(judge, row)
    if bad or st["n"] != 3 or not judge:
        fails.append(f"真实基线不干净: bad={bad} stats={st}")
    else:
        print("  ok   真实基线：0 bad（3 字段全一致）")

    # ② ★ 篡改镜像里的一格 ⇒ 必须点名（id 换成别的判官）
    bad2, _ = R.validate_mirror(judge, row.replace("main-opencode-cli", "some-other-judge"))
    ok2 = len(bad2) == 1 and "id" in bad2[0]
    print(f"  {'ok  ' if ok2 else 'FAIL'} [真实负例1] 镜像 id 被改成别的 ⇒ 报 {len(bad2)} 条，点名 id："
          f"{'在' if ok2 else '缺'}")
    if not ok2:
        fails.append(f"负例1 未点名: {bad2}")

    # ③ ★ egress 被翻转 ⇒ 必须点名（"改一处忘改另一处"的典型）
    bad3, _ = R.validate_mirror(judge, row.replace("egress=false", "egress=true"))
    ok3 = len(bad3) == 1 and "egress" in bad3[0]
    print(f"  {'ok  ' if ok3 else 'FAIL'} [真实负例2] 镜像 egress 翻转 ⇒ 报 {len(bad3)} 条，点名 egress："
          f"{'在' if ok3 else '缺'}")
    if not ok3:
        fails.append(f"负例2 未点名: {bad3}")

    # ④ 事实源不可读（表结构变了）⇒ 必须报，不得静默通过
    bad4, st4 = R.validate_mirror(None, row)
    if not bad4 or st4["n"] != 0:
        fails.append(f"事实源不可读时未报: {bad4}")
    else:
        print("  ok   事实源不可读 ⇒ 明确报错（不静默通过）")

    # ⑤ O-50：手册 §2.4 的断言计数声明 == 真实 CHECKS（把"手册计数会漂移"变成机判）
    manual = R.MANUAL.read_text(encoding="utf-8", errors="replace")
    badc = R.validate_manual_counts(manual, R.CHECKS)
    if badc:
        fails.append(f"手册计数基线不干净: {badc}")
    else:
        print(f"  ok   手册断言计数 == CHECKS（{len(R.CHECKS)} 项）")

    # ⑥ ★ 篡改手册计数 ⇒ 必须点名
    m0 = R.MANUAL_COUNT_RE.search(manual)
    n0 = m0.group(1) if m0 else "21"
    badc2 = R.validate_manual_counts(manual.replace(f"# {n0} 项断言", "# 99 项断言"), R.CHECKS)
    okc2 = any("99" in b for b in badc2)
    print(f"  {'ok  ' if okc2 else 'FAIL'} [真实负例3] 手册计数改成 99 ⇒ 点名：{'在' if okc2 else '缺'}")
    if not okc2:
        fails.append(f"负例3 未点名: {badc2}")

    # ⑦ ★ 手册塞回"真实剩余 open = N 项"枚举 ⇒ 必须点名（O-50 反向护栏）
    badc3 = R.validate_manual_counts(manual + "\n当前真实剩余 open issue = 4 项。\n", R.CHECKS)
    okc3 = any("枚举式声明" in b for b in badc3)
    print(f"  {'ok  ' if okc3 else 'FAIL'} [真实负例4] 手册塞回 open 枚举 ⇒ 点名：{'在' if okc3 else '缺'}")
    if not okc3:
        fails.append(f"负例4 未点名: {badc3}")

    # ⑧ ★ 手册塞回写死门禁计数 ⇒ 必须点名
    badc4 = R.validate_manual_counts(manual + "\n质量门：门禁 15 绿。\n", R.CHECKS)
    okc4 = any("写死了门禁计数" in b for b in badc4)
    print(f"  {'ok  ' if okc4 else 'FAIL'} [真实负例5] 手册写死门禁计数 ⇒ 点名：{'在' if okc4 else '缺'}")
    if not okc4:
        fails.append(f"负例5 未点名: {badc4}")

    # ⑨ 结构护栏
    if "mirror" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='mirror' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'mirror' 已在 CHECKS 注册")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
