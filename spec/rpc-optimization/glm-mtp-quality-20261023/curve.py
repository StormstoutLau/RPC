#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GLM reasoning_effort 质量-成本曲线（2026-10-23）。

读取多臂 jsonl（同 runner.py 产出），按题输出：
  finish / content 字符 / reasoning 字符 / completion_tokens / elapsed / decode tps
  + 语义通过（复用 verify.answer_sig 的判定口径）

用法（在本目录运行）：
    python curve.py --arm low=glm_low_on_r1.jsonl,glm_low_on_r2.jsonl \
                    --arm high=glm_high_r1.jsonl,glm_high_r2.jsonl \
                    --arm max=maxeffort_single_r1.jsonl,glm_max_r2.jsonl
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify import answer_sig  # noqa: E402


def load(paths):
    out = {}
    for p in paths:
        if not os.path.isfile(p):
            continue
        for line in io.open(p, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                out.setdefault(r["id"], []).append((os.path.basename(p), r))
    return out


def passed(qid, sig):
    """按题目的参考值判定语义是否通过（与 results-ledger 同口径）。"""
    try:
        if qid == "dmx-a3":
            return (sig.get("rel") == "same"
                    and abs(float(sig.get("gauss")) - 0.7071) <= 0.01
                    and abs(float(sig.get("t")) - 0.7071) <= 0.01)
        if qid == "dmx-b2":
            return (abs(float(sig.get("slope")) + 0.1575) <= 0.005
                    and "rho" in (sig.get("driver") or ""))
        if qid == "dmx-a1":
            return all(sig.get(k) for k in ("small_denom", "tranche", "independent"))
        if qid == "dmx-g1":
            return sig.get("separate") and sig.get("degenerate") and not sig.get("discount_trap")
        if qid == "dmx-c2":
            ex = sig.get("result") or {}
            return (sig.get("has_code") and ex.get("n") == 100
                    and abs((ex.get("min") or 0) - 98.35274) < 1e-3
                    and abs((ex.get("sum") or 0) - 100.0) < 1e-6
                    and ex.get("nan") is False)
    except (TypeError, ValueError):
        return False
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="label=file1,file2（可重复）")
    args = ap.parse_args()

    arms = []
    for spec in args.arm:
        label, files = spec.split("=", 1)
        arms.append((label, load([f for f in files.split(",") if f])))

    qids = sorted({q for _, a in arms for q in a})
    for qid in qids:
        print(f"\n== {qid} ==")
        for label, arm in arms:
            rows = arm.get(qid) or []
            for fname, r in rows:
                sig = answer_sig(qid, r)
                ok = passed(qid, sig)
                u = r.get("usage") or {}
                t = r.get("timings") or {}
                print(f"  {label:5s} {fname:26s} finish={str(r.get('finish')):6s} "
                      f"content={len(r.get('content','')):5d} reason={len(r.get('reasoning','')):6d} "
                      f"ctok={u.get('completion_tokens','?'):>6} elapsed={r.get('elapsed_s','?'):>8}s "
                      f"tps={t.get('predicted_per_second') and round(t['predicted_per_second'], 2)} "
                      f"pass={ok}")
        # 每臂汇总：通过率 / 完成率 / 平均 completion_tokens
        print("  -- arm summary --")
        for label, arm in arms:
            rows = arm.get(qid) or []
            if not rows:
                continue
            ok = sum(1 for _, r in rows if passed(qid, answer_sig(qid, r)))
            full = sum(1 for _, r in rows if r.get("finish") == "stop")
            toks = [((r.get("usage") or {}).get("completion_tokens") or 0) for _, r in rows]
            print(f"  {label:5s} pass={ok}/{len(rows)} complete={full}/{len(rows)} "
                  f"mean_ctok={sum(toks)/len(toks):.0f}")


if __name__ == "__main__":
    main()
