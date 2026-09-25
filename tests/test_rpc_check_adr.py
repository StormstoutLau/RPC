"""P2-2 `adr` 断言 正反夹测 —— 永久护栏（ADR 必留「考虑的替代方案」）

★ 关键性质：节体扫描**只到下一个二级标题为止** —— `### 替代方案 A` 是**子节**、属节体
  （ADR-0001/0002 的节体**全是**子节）⇒ 若按"任意标题"截断，会把它们判成**空节**（假红）。
★ 另一关键：节名比较前**规范化**（去括号内容 / 空白 / 全半角）⇒ 防"半角括号 typo"假红
  （ADR-0001 的历史形态就是 `…Considered)`）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402

CANON = "## 考虑的替代方案（Alternatives Considered）"


def main() -> int:
    fails = []

    def case(name, text, kw=None, want_pass=False):
        bad, _notes = R.validate_adr(text)
        ok = (not bad) if want_pass else any(kw in x for x in bad)
        shown = "PASS" if not bad else "; ".join(bad)[:108]
        print(f"  {'ok  ' if ok else 'FAIL'} [{name}] {shown}")
        if not ok:
            fails.append(f"{name}: want_pass={want_pass} kw={kw!r} got={bad}")

    # ① 规范化：全角 / 半角 / 无括号 / 多空格 ⇒ 同一节名（防 typo 假红）
    for h in ("## 考虑的替代方案（Alternatives Considered）",
              "## 考虑的替代方案(Alternatives Considered)",
              "##  考虑的替代方案 "):
        case(f"规范化 {h[:14]}…", f"{h}\n\n- 甲：否决\n", want_pass=True)

    # ② 列表体 ⇒ PASS
    case("列表体", f"{CANON}\n\n- 甲：否决，因为慢\n", want_pass=True)

    # ③ 表格体（表头 + 分隔 + 数据）⇒ PASS
    case("表格体", f"{CANON}\n\n| 方案 | 否决理由 |\n|---|---|\n| 甲 | 慢 |\n", want_pass=True)

    # ④ ★ 子节体（ADR-0001/0002 的真实形态）⇒ PASS —— 不能按"任意标题"截断
    case("子节体", f"{CANON}\n\n### 替代方案 A: 甲（否决）\n\n- 优点: 快\n\n### 替代方案 B: 乙（否决）\n\n- 优点: 稳\n",
         want_pass=True)

    # ⑤ 缺节 ⇒ 点名
    case("缺节", "## 决策\n\n- 做甲\n", kw="缺")

    # ⑥ 旧节名 ⇒ 点名
    case("旧节名", "## 否决/比较对象\n\n- 甲\n", kw="旧节名")

    # ⑦ 空节（只有标题）⇒ 点名
    case("空节", f"{CANON}\n\n## 决策\n\n- 做甲\n", kw="是空的")

    # ⑧ 重复节 ⇒ 点名
    case("重复节", f"{CANON}\n\n- 甲\n\n{CANON}\n\n- 乙\n", kw="只允许 1 个")

    # ⑨ 真实基线：8 份 ADR 全部通过（真实数据，非构造）
    fs = sorted((ROOT / "adr").glob(R.ADR_GLOB))
    bad_all = [(p.name, R.validate_adr(p.read_text(encoding="utf-8", errors="replace"))[0])
               for p in fs]
    bad_all = [(n, b) for n, b in bad_all if b]
    ok9 = len(fs) >= 8 and not bad_all
    print(f"  {'ok  ' if ok9 else 'FAIL'} [真实基线] {len(fs)} 份 ADR 全部含非空规范节"
          + (f"（违规 {bad_all}）" if bad_all else ""))
    if not ok9:
        fails.append(f"真实基线不干净: {len(fs)} 份 · {bad_all}")

    # ⑩ 结构护栏：登记就要有人跑
    if "adr" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='adr' ⇒ 登记了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'adr' 已在 CHECKS 注册")

    # ⑪ 范围护栏：只扫 adr/ADR-*.md（DECISIONS.md 是表格载体，列已结构保证 + 值可为 `—`）
    ok11 = R.ADR_DIR.name == "adr" and R.ADR_GLOB == "ADR-*.md"
    print(f"  {'ok  ' if ok11 else 'FAIL'} [范围] ADR_DIR={R.ADR_DIR.name} · GLOB={R.ADR_GLOB}（不含 DECISIONS.md）")
    if not ok11:
        fails.append(f"范围不符: {R.ADR_DIR} / {R.ADR_GLOB}")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
