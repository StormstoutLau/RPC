"""`D7-P3-1` 消费者：**producer ↔ judge 配对审计**（只读，2026-09-26）。

★ 为什么需要它：`J-1`（跨族）/ `J-2`（输入独立）的**判定本体**已在 `ops/rpc_check.py`
（`cross_family_verdict` / `cross_input_verdict`），但**被判的对象在【站上 runDir】**
（`run.json` 与 `review.json`）⇒ 本仓门禁读不到 ⇒ 它一直是"**判据库、无消费者**"。
本脚本就是**最小消费者**：遍历**可达项目**的 runDir，把两侧配对后跑判定 ⇒ **报数 + 点名**。

★★ **只读，且不判灯**（按本仓纪律"**先量后定档**"，同 O-69/O-97）：
   先看真实分布（多少 `cross` / `same` / `unknown`），**再**决定要不要接门禁。
   ⚠ 尤其：`unknown` **不是"问题"** —— 它是"**不可判**"（端点别名 / 未登记的出网模型）⇒ 只报数。

★ 配对定义（两侧都按**同一 runDir**取，保证是"同一次派发"）：
   · producer 侧 = `runDir/.agent-run.json` 的 `model` 与 `prompt_sha256`
   · judge 侧    = `runDir/review.json` 的 `metadata.judge_model` 与 `metadata.prompt_hash`
   ⇒ 只有**两侧都在**才算一对（缺一侧 ⇒ 记 `no_pair`，不硬凑）。

用法：
    py ops/agent_pair_audit.py            # 报数 + 点名样例
    py ops/agent_pair_audit.py --json     # 机器可读
    py ops/agent_pair_audit.py --max 10   # 每条明细最多打印 N 行
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))

import rpc_check as R                                    # noqa: E402


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:                                    # noqa: BLE001
        return None


def collect():
    """扫可达项目 ⇒ `[(proj, run_id, producer_model, judge_model, p_sha, j_sha)]` + 计数。"""
    import cluster as C
    roots, note = C._agent_proj_roots()
    pairs, n_rec, n_rev, n_no_pair = [], 0, 0, 0
    for proj, root in sorted(roots.items()):
        d = root / "agent-out"
        if not d.is_dir():
            continue
        for sub in sorted(d.iterdir()):
            if not sub.is_dir():
                continue
            rec = _read(sub / ".agent-run.json")
            if rec is None:
                continue
            n_rec += 1
            rev = _read(sub / "review.json")
            if rev is None:
                n_no_pair += 1
                continue
            n_rev += 1
            md = (rev.get("metadata") or {})
            pm, jm = rec.get("model"), md.get("judge_model")
            ps, js = rec.get("prompt_sha256"), md.get("prompt_hash")
            if not pm or not jm:
                n_no_pair += 1
                continue
            pairs.append((proj, sub.name, pm, jm, ps, js))
    return roots, note, pairs, {"run_records": n_rec, "with_review": n_rev, "no_pair": n_no_pair}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max", type=int, default=6)
    a = ap.parse_args()

    idx = R.load_family_index()
    roots, note, pairs, cnt = collect()

    t1, t2, same, unknown, j2_same = {}, {}, [], [], []
    for proj, rid, pm, jm, ps, js in pairs:
        v1 = R.cross_family_verdict(pm, jm, idx)
        t1[v1["verdict"]] = t1.get(v1["verdict"], 0) + 1
        if v1["verdict"] == "same":
            same.append((proj, rid, pm, jm, v1["reason"]))
        elif v1["verdict"] == "unknown":
            unknown.append((proj, rid, pm, jm, v1.get("unknown")))
        v2 = R.cross_input_verdict(ps, js)
        t2[v2["verdict"]] = t2.get(v2["verdict"], 0) + 1
        if v2["verdict"] == "same":
            j2_same.append((proj, rid))

    print(f"[范围] 可达项目 {len(roots)} 个 · run 记录 {cnt['run_records']} · "
          f"有 review {cnt['with_review']} · **可配对 {len(pairs)}** · 缺一侧 {cnt['no_pair']}")
    print(f"[J-1 跨族] " + " · ".join(f"{k}={v}" for k, v in sorted(t1.items())))
    print(f"   ⚠ `same` = **判据红**（同族 ⇒ 不构成异构）: {len(same)} 对")
    for x in same[:a.max]:
        print(f"      · {x[0]}/{x[1]}  {x[2]}  ×  {x[3]}")
    print(f"   ⚠ `unknown` = **不可判**（端点别名 / 未登记出网模型）: {len(unknown)} 对")
    for x in unknown[:a.max]:
        print(f"      · {x[0]}/{x[1]}  查不到: {x[4]}")
    print(f"[J-2 输入独立] " + " · ".join(f"{k}={v}" for k, v in sorted(t2.items())))
    if j2_same:
        print(f"   ⚠ 两侧输入摘要**相同**（⇒ 判据红）: {len(j2_same)} 对 · 例 {j2_same[:3]}")
    print("[口径] 只读报数，**不判灯**（先量后定档，同 O-69/O-97）；`unknown` 不等于失败")
    if a.json:
        print(json.dumps({"t1": t1, "t2": t2, "pairs": len(pairs),
                          "same": same[:20], "unknown": unknown[:20]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
