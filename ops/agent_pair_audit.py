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
    """扫可达项目 ⇒ `[(proj, run_id, producer_model, judge_model, p_sha, j_sha)]` + 计数。

    ★★ 2026-10-01（`O-136` 的 `PRH` 定档前置）：**同一趟遍历顺带取 `exec_host`/`arbiter_host`**
      ⇒ `PRH`（产出机 vs 裁决机同机可见性）的读数**不需要新落点、不需要新件**：
      两侧事实早在 B3 就随 `.agent-run.json` 落盘了（见 `Resolve-D7Hosts`）。
      ⚠ 这一条正是"**读侧必须与写侧同源**"（同 C 段那次教训的形态）—— 缺的从来不是落点，是**读侧**。
    """
    import cluster as C
    roots, note = C._agent_proj_roots()
    pairs, hosts, guards, tguards, n_rec, n_rev, n_no_pair = [], [], [], [], 0, 0, 0
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
            hosts.append((proj, sub.name, rec.get("exec_host"), rec.get("arbiter_host")))
            # ★ task 侧报数（`.agent-run.json` 的 `d7_guard`）—— `P0`/`P3`/`I-1` 的码；
            #   ⚠ 与 review 侧**分开装**：两侧 tag 名不同、分母也不同（run 数 ≠ review 数）。
            if isinstance(rec.get("d7_guard"), dict):
                tguards.append((proj, sub.name, rec["d7_guard"]))
            rev = _read(sub / "review.json")
            if isinstance(rev, dict) and isinstance(rev.get("d7_guard"), dict):
                guards.append((proj, sub.name, rev["d7_guard"]))
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
    return (roots, note, pairs,
            {"run_records": n_rec, "with_review": n_rev, "no_pair": n_no_pair}, hosts, guards, tguards)


def prh_distribution(hosts):
    """`PRH` 的**分层读数**（`O-136` 定档前置）。

    ⚠⚠ **判据本体不在这里** —— 逐字比与三态由 `rpc_check.d7_host_separation` 给（`O-134` 落的本体）。
      本函数只做**计数与分层标注**（消费侧），**不重写一份判据**（本仓头号失败形态）。

    ★★ **为什么必须分层，而不能只报一个"总占比"**：`exec_host` 只有**三种来源**，而其中两种
      **按构造就是必然结论** ⇒ 混在一起算出来的占比**没有信息量**：
        · `exec_host` = **站 host** ⇒ 站上跑 ⇒ **必然分离**（送分样本，不能当"机械独立"的证据）
        · `exec_host` = **裁决机名** ⇒ 主控本地跑 ⇒ **必然同机**（★ 这才是 `PRH` 要看见的形态，
          `O-124` 实测批 `20260930145220`：「出网档 且 无站路由 ⇒ 主控本地 spawn」）
        · `exec_host` 为空 / 缺 ⇒ **不可判**（早于 B3 的 run 没这个键 ⇒ 单独一桶，不混入分母）
      ⇒ 三桶**就是**分层；★ 每桶都带"为什么必然"的标注，免得"分离 9/9"被误读成安全证明。
    """
    buckets = {"station": [], "local": [], "unknown": [], }
    for proj, rid, eh, ah in hosts:
        same, _why = R.d7_host_separation(eh, ah)
        if same is None:
            buckets["unknown"].append((proj, rid, eh))
        elif same is True:
            buckets["local"].append((proj, rid, eh, ah))
        else:
            buckets["station"].append((proj, rid, eh, ah))
    return buckets


# ⚠ 这些键存的是**计数**（不是 CLI 的三态码）⇒ 报数时**不得**套三态图例，否则误导读者。
_COUNT_KEYS = {"transition.hops", "transition.rejected"}


def d7_guard_tally(guards):
    """**D7 判据报数**的聚合（`O-136` 测收益的 ②）。

    ★ 这是"每千次 review 拦了多少"的**分母与分子**：`review.json.d7_guard`（本批新增的**报数落点**）
      里记着每台判据的**三态码**（`0` ok / `1` reject / `2` 不可判，与 CLI 一致）。
    ⚠⚠ **必须报"多少份 review 真的跑过这段"**（`covered`）：否则「**没跑**」与「**跑了且全 ok**」
      在聚合里**都表现为 0 个 reject** —— 那是最典型的假绿。
    ⚠ 本函数**只计数**，不判灯（同本文件其余部分；`PRH` 的三态照原码报，不合并）。
    """
    keys, covered, n = {}, 0, 0
    for _proj, _rid, g in guards:
        n += 1
        if g.get("completed") == 1:
            covered += 1
        for k, v in g.items():
            if k == "completed":
                continue
            d = keys.setdefault(k, {})
            d[str(v)] = d.get(str(v), 0) + 1
    return keys, covered, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max", type=int, default=6)
    a = ap.parse_args()

    idx = R.load_family_index()
    roots, note, pairs, cnt, hosts, guards, tguards = collect()

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
    # ── ★★ PRH（同机可见性）分层读数（2026-10-01 · O-136 定档前置）────────────────────────────
    # 判据本体 = `R.d7_host_separation`（本文件只计数、只分层）；读数落在 `.agent-run.json` 上。
    ph = prh_distribution(hosts)
    n_st, n_lo, n_un = len(ph["station"]), len(ph["local"]), len(ph["unknown"])
    n_ok = n_st + n_lo
    print(f"[PRH 同机可见性] 可判 {n_ok}（**同机 {n_lo}** / 分离 {n_st}）· 不可判 {n_un}")
    print(f"   ★ 分离桶（{n_st}）= `exec_host` 是**站 host** ⇒ 站上跑 ⇒ **按构造必然分离**"
          f"（送分样本，**不构成「机械独立」的证据**）")
    for x in ph["station"][:a.max]:
        print(f"      · {x[0]}/{x[1]}  {x[2]}  ≠  {x[3]}")
    print(f"   ★★ 同机桶（{n_lo}）= `exec_host` **等于裁决机** ⇒ **主控本地跑** ⇒ 这才是 `PRH` 要看见的形态"
          f"（`O-124`：出网档 且 无站路由 ⇒ 主控本地 spawn）")
    for x in ph["local"][:a.max]:
        print(f"      · {x[0]}/{x[1]}  {x[2]}  ==  {x[3]}")
    print(f"   ⚠ 不可判桶（{n_un}）= 无 `exec_host`（早于 B3 的 run 没有这个键）⇒ **不入分母**、也不读成「不同机」")
    # ── ★★ D7 判据报数聚合（2026-10-01 · 测收益的 ②）────────────────────────────────────────
    # 这是"**每千次 review 拦了多少**"的分子/分母。★ 分母必须报 `covered`（见 `d7_guard_tally`）。
    gk, g_covered, g_n = d7_guard_tally(guards)
    print(f"[D7 判据报数 · review 侧] 有 d7_guard 的 review {g_n} 份 · **其中跑完 guard 段的 {g_covered}**")
    if g_n == 0:
        print("   ⚠ **零份** ⇒ 本项**算不出来**（不是「零拦截」）：报数落点是本批才加的 ⇒ "
              "旧的 review.json 里没有 `d7_guard`（**不可回溯**：那些行当时只走了 stdout）")
    else:
        for k in sorted(gk):
            dist = " · ".join(f"code={v} × {c}" for v, c in sorted(gk[k].items()))
            # ⚠⚠ **不要给计数键套三态码的图例**：`transition.hops`/`transition.rejected` 存的是
            #   **计数**（跳数 / 被拒跳数），不是 CLI 的三态码 ⇒ 套上"0=ok/1=reject/2=不可判"
            #   会**把读者引到错误结论**（例如 hops=2 被读成"不可判"）。
            legend = "" if k in _COUNT_KEYS else "   （0=ok / 1=reject / 2=不可判，与 CLI 同码）"
            print(f"   · {k}: {dist}{legend}")
    # ── task 侧（`P0`/`P3`/`I-1`）—— 与 review 侧**分开报**（tag 不同、分母也不同：run 数 ≠ review 数）
    tk, _t_covered, t_n = d7_guard_tally(tguards)
    print(f"[D7 判据报数 · task 侧] 有 d7_guard 的 run {t_n} 份 / run 记录 {cnt['run_records']} 份")
    if t_n == 0:
        print("   ⚠ **零份** ⇒ 同样**算不出来**（task 侧落点也是本批才加；旧 run 记录没有这个键）")
    else:
        for k in sorted(tk):
            dist = " · ".join(f"code={v} × {c}" for v, c in sorted(tk[k].items()))
            legend = "" if k in _COUNT_KEYS else "   （0=ok / 1=reject / 2=不可判，与 CLI 同码）"
            print(f"   · {k}: {dist}{legend}")
    print("[口径·报数] ★ 聚合**只计数、不判灯**；⚠ 「没跑」必须与「跑了且全 ok」分得开 "
          "（故单列 covered）——否则 0 个 reject 会被读成「很干净」（假绿）")
    print("[口径] 只读报数，**不判灯**（先量后定档，同 O-69/O-97）；`unknown` 不等于失败")
    print("[口径·PRH] ★ 定档**不看占比阈值**（`O-126` 禁凭空数值）：三桶按构造就有结论 ⇒ "
          "先看**同机桶是否非空**（= 该形态是否真出现过），再裁「要不要把这一路升级为拒」")
    if a.json:
        print(json.dumps({"t1": t1, "t2": t2, "pairs": len(pairs),
                          "same": same[:20], "unknown": unknown[:20],
                          "prh": {"station": n_st, "local": n_lo, "unknown": n_un,
                                  "local_examples": ph["local"][:10]},
                          "d7_guard": {"reviews": g_n, "covered": g_covered, "tally": gk},
                          "d7_guard_task": {"runs": t_n, "tally": tk}},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
