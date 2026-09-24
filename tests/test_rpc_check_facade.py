"""`facade` 断言（P1-3）的正反注入 —— 永久护栏（2026-09-24）

P1-3 的定性：本仓已拆出 5 个模块，`cluster.py` 是**统一门面**，`cluster_web.py` / `tests/*`
以 `import cluster [as C]` 复用其符号 ⇒ **跨文件隐式契约**，而此前门禁**无任何一项检查它**。

⭐ **双向自证（真实数据，且不碰任何文件）**：
   取仓库**真**的 `consumer_refs` 与 `names` ⇒ 基线无 bad；
   再把 `names` 里**抽掉一个符号**（= 模拟"有人在 cluster.py 里删了那个重导出"）
   ⇒ 必须**恰好报出那个符号 + 引用它的消费者**。⇒ 证明判据在**真数据上**具辨别力。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def _real(monkeypatch_names=None):
    """复算真实仓库的 (consumer_refs, names 集合)，可选把某个符号从 names 里抽掉。"""
    refs = {}
    for d in R._FACADE_DIRS:
        for p in sorted((ROOT / d).glob("*.py")):
            if p.name == R.FACADE.name or p.name.startswith("cluster_"):
                continue
            txt = R._strip_py_prose(p.read_text(encoding="utf-8", errors="replace"))
            m = R._FACADE_CONSUMER_RE.search(txt)
            if not m:
                continue
            alias = m.group(1) or "cluster"
            got = {x for x in __import__("re").findall(rf"\b{alias}\.([A-Za-z_]\w*)", txt)
                   if not x.startswith("__")}
            if got:
                refs[f"{d}/{p.name}"] = got
    names = R.facade_names(R._strip_py_prose(R.FACADE.read_text(encoding="utf-8", errors="replace")))
    if monkeypatch_names:
        names = {n for n in names if n != monkeypatch_names}
    return refs, names


def main() -> int:
    fails = []

    # ── ① 真实数据基线 ────────────────────────────────────────────────
    refs, names = _real()
    bad, st = R.validate_facade(refs, names)
    print(f"  [真实基线] 消费者 {st['consumers']} · 引用符号 {st['syms']} · 不可达 {len(bad)}")
    if bad or st["consumers"] == 0 or st["syms"] == 0:
        fails.append(f"真实基线不干净或范围为空: bad={bad[:3]} stats={st}")

    # ── ② ★ 真实数据 + 抽掉一个符号 ⇒ 必须点名（双向自证）───────────────
    victim = sorted({s for r in refs.values() for s in r})[0]
    who = next(k for k, v in sorted(refs.items()) if victim in v)
    bad2, _ = R.validate_facade(refs, _real(victim)[1])
    hit = len(bad2) == 1 and victim in bad2[0] and who in bad2[0]
    print(f"  {'ok  ' if hit else 'FAIL'} [真实负例] 抽掉 cluster.{victim} ⇒ "
          f"报 {len(bad2)} 条 · 点名 '{victim}'+'{who}':{'在' if hit else '缺'}")
    if not hit:
        fails.append(f"真实负例未点名: victim={victim} who={who} bad={bad2}")

    # ── ③ 合成用例：别名 / 缺符号 ──────────────────────────────────────
    synth = {"x.py": {"A", "B"}}
    if R.validate_facade(synth, {"A", "B"})[0]:
        fails.append("合成正例误报")
    b3, _ = R.validate_facade({"y.py": {"Z"}}, {"A"})
    if not (len(b3) == 1 and "Z" in b3[0] and "y.py" in b3[0]):
        fails.append(f"合成负例未点名: {b3}")
    print(f"  ok   合成用例（正例不报 / 负例点名）· 别名处理: "
          f"{'ok' if R._FACADE_CONSUMER_RE.search('import cluster as C') else '缺'}")

    # ── ④ 结构护栏 ────────────────────────────────────────────────────
    if "facade" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='facade' ⇒ 断言写了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'facade' 已在 CHECKS 注册")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
