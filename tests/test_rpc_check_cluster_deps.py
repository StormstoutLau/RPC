"""P2-1 `cluster_*.py` 依赖方向 正反夹测 —— 永久护栏（D6-P2-1）

★ 核心性质：**模块级 import**（导入期依赖 ⇒ 真环）与**函数内懒加载**（刻意打破环的手段）
  必须被**分开**（正则分不清"这行 in 不 in 函数里"，会把两类混成一个桶 = 本仓头号失败形态）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def main() -> int:
    fails = []

    # ① ★ 真实数据抽特征：`cluster.py` 里 `import cluster_const` 在**顶层**，
    #    而 `import cluster_web` 在**函数内**（`cmd_web`）⇒ 必须分别落进 top / lazy（正则做不到）
    csrc = (ROOT / "ops" / "cluster.py").read_text(encoding="utf-8", errors="replace")
    top, lazy = R.cluster_dep_edges(csrc)
    ok1 = ("cluster_const" in top) and ("cluster_web" in lazy) and ("cluster_web" not in top)
    print(f"  {'ok  ' if ok1 else 'FAIL'} [AST 分两类] cluster_const∈top · cluster_web∈lazy 且∉top "
          f"（{ok1}）")
    if not ok1:
        fails.append(f"模块级/懒加载未分开: top={sorted(top)} lazy={sorted(lazy)}")

    # ② 成环：a→b→a ⇒ 报 1 环，且首尾同名
    cyc = R.find_cycles({"a": {"b"}, "b": {"a"}})
    ok2 = len(cyc) == 1 and cyc[0][0] == cyc[0][-1] and set(cyc[0]) == {"a", "b"}
    print(f"  {'ok  ' if ok2 else 'FAIL'} [成环] a→b→a ⇒ {cyc}")
    if not ok2:
        fails.append(f"成环检测不对: {cyc}")

    L2 = [["ops/cluster_const.py"], ["ops/cluster_egress.py"]]

    # ③ ★ 计划里的先验红场景：const(L0) → egress(L1) 且反向 ⇒ **既成环又越层**（两条都要点名）
    g3 = {"top": {"cluster_const": {"cluster_egress"}, "cluster_egress": {"cluster_const"}}, "lazy": {}}
    bad3, _n3, _u3 = R.validate_cluster_deps(g3, L2, [])
    ok3 = any("成环" in b for b in bad3) and any("层序越界" in b for b in bad3)
    print(f"  {'ok  ' if ok3 else 'FAIL'} [成环+越层] const↔egress ⇒ 两条都点名")
    if not ok3:
        fails.append(f"未点名: {bad3}")

    # ④ 新模块未登记层次 ⇒ FAIL（否则依赖方向无人约束）
    g4 = {"top": {"cluster_new": set()}, "lazy": {}}
    bad4, _n4, _u4 = R.validate_cluster_deps(g4, L2, [])
    ok4 = any("未在" in b and "cluster_new" in b for b in bad4)
    print(f"  {'ok  ' if ok4 else 'FAIL'} [未登记模块] cluster_new ⇒ 点名")
    if not ok4:
        fails.append(f"未登记模块未点名: {bad4}")

    # ⑤ ★ 真实现状的形状：cluster_web→cluster(模块级) + cluster→cluster_web(懒加载) ⇒ 顶层双向
    L5 = [["ops/cluster.py"], ["ops/cluster_web.py"]]
    g5 = {"top": {"cluster_web": {"cluster"}}, "lazy": {"cluster": {"cluster_web"}}}
    bad5, _n5, _u5 = R.validate_cluster_deps(g5, L5, [])
    ok5a = any("未登记的反向懒加载" in b for b in bad5)
    bad5b, notes5b, unhit5b = R.validate_cluster_deps(
        g5, L5, [["ops/cluster.py", "ops/cluster_web.py", "入口派发(避导入环)"]])
    ok5b = (not bad5b) and any("已登记" in n for n in notes5b) and unhit5b == []
    print(f"  {'ok  ' if (ok5a and ok5b) else 'FAIL'} [反向懒加载] 未登记⇒FAIL / 登记后⇒PASS+note")
    if not (ok5a and ok5b):
        fails.append(f"反向懒加载处置不对: bad={bad5} / bad2={bad5b} notes={notes5b}")

    # ⑥ 登记的懒加载**未命中** ⇒ 自报"已可移除"（同 P0-2 防腐化纪律）
    g6 = {"top": {"cluster_egress": {"cluster_const"}}, "lazy": {}}
    _b6, _n6, u6 = R.validate_cluster_deps(g6, L2, [["ops/cluster.py", "ops/cluster_web.py", "早已不存在"]])
    ok6 = u6 == [("cluster", "cluster_web")]
    print(f"  {'ok  ' if ok6 else 'FAIL'} [未命中] 陈旧登记 ⇒ unhit={u6}")
    if not ok6:
        fails.append(f"未命中未自报: {u6}")

    # ⑦ 真实基线：现网代码 + ops.yaml 自洽 ⇒ PASS
    fn = next(c["fn"] for c in R.CHECKS if c["id"] == "deps")
    st, note, _det = fn({})
    ok7 = st == "PASS"
    print(f"  {'ok  ' if ok7 else 'FAIL'} [真实基线] deps → {st} · {note}")
    if not ok7:
        fails.append(f"真实基线非 PASS: {st} · {note}")

    # ⑧ 结构护栏：登记就要有人跑（否则 `cluster_layers` 是零执行的空头承诺）
    if "deps" not in {c["id"] for c in R.CHECKS}:
        fails.append("CHECKS 里没有 id='deps' ⇒ 登记了但没人跑（挂名假判）")
    else:
        print("  ok   结构护栏：'deps' 已在 CHECKS 注册")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
