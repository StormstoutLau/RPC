"""D6-P0-2「豁免未命中自报」的注入用例 —— 永久护栏（防腐化）

纯函数 `allow_unhit`（**唯一实现**）+ 两处消费者（`SECRET_ALLOW` / `DOCLINK_ALLOW`）。
⚠ 关键性质：**按 set 去重** —— 同一豁免被**命中多次**（如同一 md 里两条链接指向同一失效目标）
   仍是"命中"，**不得**被算成"未命中"（doclinks 的真实情形就是 `已登记例外 2` 而清单只有 1 条）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R  # noqa: E402


def main() -> int:
    fails = []

    # ① 纯函数：全部命中 ⇒ 空
    if R.allow_unhit(["a", "b"], {"a", "b"}) != []:
        fails.append("全命中时应为空")
    else:
        print("  ok   全命中 ⇒ 无未命中")

    # ② 纯函数：有假豁免 ⇒ 点名
    got = R.allow_unhit(["a", "b", "ghost"], {"a", "b"})
    if got != ["ghost"]:
        fails.append(f"应点名 ghost: {got}")
    else:
        print("  ok   假豁免 ⇒ 点名 ['ghost']")

    # ③ ★ 命中多次仍算命中（set 语义）—— doclinks 的真实情形（同目标两条链接）
    if R.allow_unhit({("m", "t")}, {("m", "t"), ("m", "t")}) != []:
        fails.append("重复命中被误判为未命中（必须按 set 去重）")
    else:
        print("  ok   重复命中 ⇒ 仍算命中（set 去重）")

    # ④ 消费者：两处都接进了（改坏任一 ⇒ 该清单重新开始腐化）
    src = (ROOT / "ops" / "rpc_check.py").read_text(encoding="utf-8", errors="replace")
    n_call = src.count("allow_unhit(")
    ok4 = n_call >= 3          # 1 处定义 + 2 处消费
    print(f"  {'ok  ' if ok4 else 'FAIL'} [消费者] allow_unhit 定义+消费 = {n_call} 处（期望 ≥3）")
    if not ok4:
        fails.append(f"allow_unhit 调用点不足: {n_call}")

    # ⑤ 两处 fix 文案都给了"下一步"（黄灯必须能照做）
    ok5 = ("从 SECRET_ALLOW 删掉" in src) and ("从 DOCLINK_ALLOW 删掉" in src)
    print(f"  {'ok  ' if ok5 else 'FAIL'} [处置建议] 两处 fix 都写明『把该豁免删掉』")
    if not ok5:
        fails.append("fix 文案缺『删掉该豁免』指引")

    # ⑥ 真实基线：现状**没有**未命中（若哪天有了 ⇒ 本条立刻指出，属**真实发现**而非误报）
    stale = []
    for cid in ("secrets", "doclinks"):
        fn = next(c["fn"] for c in R.CHECKS if c["id"] == cid)
        _st, note, det = fn({})
        if "豁免未命中" in note or any("豁免**未命中**" in d for d in det):
            stale.append(cid)
    if stale:
        fails.append(f"现状存在未命中豁免（应删）: {stale}")
    else:
        print("  ok   真实基线：SECRET_ALLOW / DOCLINK_ALLOW 现状**无**未命中豁免")

    print(f"RESULT: {'ALL PASS' if not fails else f'失败 {len(fails)} 条'}")
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
