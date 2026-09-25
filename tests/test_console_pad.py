"""D6-P3-1 显示宽度/填充 正反夹测 —— 永久护栏（`cluster_console` 是**唯一实现**）

★ 核心：Python 的格式宽度数的是**码点**，我们要的是**显示列** ——
   `明文扫描` = 4 码点 / **8 显示列** ⇒ 旧 `f'{t:16s}'` 补 **12** 个空格（多 4）⇒ 整张表右移 4 列。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import cluster_console as C  # noqa: E402


def main() -> int:
    fails = []
    before = len(fails)

    # ① 实测复现：CJK/全角(W/F) = 2 列，ASCII = 1 列
    #    ⚠ `①②` = **East Asian Ambiguous**(`A`) ⇒ 本规则按 **1** 列（= ds `ambiguousIsNarrow: true`，**刻意**）。
    #      代价（如实记下）：在 CJK 宽上下文里 `①②③ § ± → ✓` 这类歧义字符实际占 2 列 ⇒ 含它们的列**会少算**。
    #      本仓输出以 W/F 汉字 + ASCII 为主 ⇒ 不受影响；若将来大量用歧义符号，需改这条规则。
    for s, want in {"明文扫描": 8, "ab": 2, "模型": 4, "a模": 3, "": 0, "①②": 2}.items():
        got = C.disp_width(s)
        if got != want:
            fails.append(f"disp_width({s!r}) = {got}，期望 {want}")
    print(f"  {'ok  ' if len(fails) == before else 'FAIL'} [disp_width] 6 例（含 `明文扫描` = 8 / 歧义 `①②` = 2）")

    # ② 左填充：结果的**显示宽度**必须恰为 max(w, 自身) —— 这才叫"对齐"
    before = len(fails)
    for s in ("明文扫描", "abc", "模型目录", ""):
        for w in (4, 16, 46):
            out = C.pad(s, w)
            want = max(w, C.disp_width(s))
            if C.disp_width(out) != want:
                fails.append(f"pad({s!r},{w}) 显示宽 {C.disp_width(out)} ≠ {want}")
    print(f"  {'ok  ' if len(fails) == before else 'FAIL'} [pad 左] 显示宽度恒 == max(w, 自身)")

    # ③ 右填充同理
    before = len(fails)
    for s in ("明文扫描", "9", "12"):
        out = C.pad(s, 10, True)
        if C.disp_width(out) != 10:
            fails.append(f"pad({s!r},10,right) 显示宽 {C.disp_width(out)} ≠ 10")
    print(f"  {'ok  ' if len(fails) == before else 'FAIL'} [pad 右] 显示宽度恒 == 10")

    # ④ ★ 反例：旧写法（Python 格式宽度按**码点**）对 CJK **必然不齐** —— 这就是要修的 bug
    old = f"{'明文扫描':16s}"
    if C.disp_width(old) == 16:
        fails.append("反例失效：旧格式宽度竟按显示列对齐（不可能）")
    else:
        print(f"  ok   [反例] 旧 `{{'明文扫描':16s}}` 显示宽 = {C.disp_width(old)}（应 16，**多 {C.disp_width(old) - 16} 列**）")
    if C.disp_width(C.pad("明文扫描", 16)) != 16:
        fails.append("新写法也没对齐（那就白改了）")

    # ⑤ 超宽**不截断**（截断才会切出"半个双宽字符" —— ds 规则 2）
    if C.pad("明文扫描超宽超宽", 4) != "明文扫描超宽超宽":
        fails.append("pad 对超宽内容做了截断（不得截断）")
    else:
        print("  ok   [不截断] 超宽原样返回")

    # ⑥ 唯一实现：cluster.py 只 alias，不得留第二份 `def`
    cl = (ROOT / "ops" / "cluster.py").read_text(encoding="utf-8", errors="replace")
    ok6 = ("from cluster_console import disp_width as _dw" in cl
           and "from cluster_console import pad as _pad" in cl
           and "def _dw(" not in cl and "def _pad(" not in cl)
    print(f"  {'ok  ' if ok6 else 'FAIL'} [唯一实现] cluster.py 只 alias，无第二份 def")
    if not ok6:
        fails.append("cluster.py 里仍有 _dw/_pad 的第二份定义")

    # ⑦ 层序登记：cluster_console ∈ L0（**这才是"下沉"的理由** —— 否则 deps 会 FAIL）
    import yaml  # noqa: E402
    inv = yaml.safe_load((ROOT / "inventory" / "ops.yaml").read_text(encoding="utf-8")) or {}
    l0 = (inv.get("cluster_layers") or [[]])[0]
    ok7 = any("cluster_console" in x for x in l0)
    print(f"  {'ok  ' if ok7 else 'FAIL'} [层序] cluster_console ∈ L0（{l0}）")
    if not ok7:
        fails.append(f"cluster_console 未登记在 L0: {l0}")

    # ⑧ ★ 站点转换（Batch 1）静态钉住：**含 CJK 的表头不得再用码点宽度**
    banned = ["{'模型目录':<46}", "{'原生ctx':>9}", "{'量化':<15}", "{'加载ctx':>9}", "{'后端':<13}",
              "{'站':<3}", "{'样本':>4}", "{'跨度':>7}", "{'忙占比':>7}", "{'峰值并发':>8}",
              "{'期望':<7}", "{'第1轮':<8}", "{'倒序':<8}", "{'改写':<8}", "{'目录':<30}",
              '"-" * (len(hdr) - 2)']          # ← 分隔线也必须按显示宽度
    left = [b for b in banned if b in cl]
    print(f"  {'ok  ' if not left else 'FAIL'} [站点] 已转换的表头无一处残留码点宽度"
          + (f"（残留 {left}）" if left else ""))
    if left:
        fails.append(f"站点回退到码点宽度: {left}")
    need = ["_pad('模型目录', 46)", "_pad('站', 3)", "_pad('期望', 7)", "_pad('目录', 30)", "_dw(hdr)"]
    miss = [n for n in need if n not in cl]
    print(f"  {'ok  ' if not miss else 'FAIL'} [站点] 新写法都在" + (f"（缺 {miss}）" if miss else ""))
    if miss:
        fails.append(f"站点未改用 _pad/_dw: {miss}")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
