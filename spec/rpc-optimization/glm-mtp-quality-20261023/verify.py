#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比 GLM MTP on/off 的 5 题输出：确定性 + 数值/锚点。

用法:
    python verify.py --on mtp_on_r1.jsonl mtp_on_r2.jsonl --off mtp_off_r1.jsonl mtp_off_r2.jsonl
输出:
    · 每臂每题的 content 长度 / finish / decode t/s / draft 接受率
    · 同臂两遍与跨臂的逐题一致性（normalized 全等 + 首个差异位置）
    · A3/B2 的数值抽取、A1/G1 的锚点命中、C2 代码块长度与可执行性（可选 --exec）
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile


def load(paths):
    out = {}
    for p in paths:
        if not os.path.isfile(p):
            continue
        for line in io.open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out.setdefault(r["id"], {})[os.path.basename(p)] = r
    return out


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def first_diff(a, b):
    a, b = norm(a), norm(b)
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return -1 if len(a) == len(b) else min(len(a), len(b))


def num(run, pat):
    m = re.search(pat, run.get("content", ""), re.I)
    return m.group(1) if m else None


def ratios(run):
    t = run.get("timings") or {}
    d, a = t.get("draft_n"), t.get("draft_n_accepted")
    return t.get("predicted_per_second"), (a / d if d else None)


def summarize_arm(label, arm):
    print(f"\n== {label} ==")
    for qid in sorted(arm):
        r = arm[qid]
        tps, acc = ratios(r)
        print(f"{qid:8s} finish={r.get('finish'):5s} content={len(r.get('content','')):5d} "
              f"reason={len(r.get('reasoning','')):5d} tps={tps and round(tps,2)} "
              f"draft_acc={acc and round(acc,3)}")
        if qid == "dmx-a3":
            g = num(r, r"GAUSS_RHO\s*=\s*([-0-9.]+)")
            t = num(r, r"T_RHO\s*=\s*([-0-9.]+)")
            rel = num(r, r"RELATION\s*=\s*([A-Za-z]+)")
            print(f"         A3 GAUSS={g} T={t} REL={rel}")
        if qid == "dmx-b2":
            s = num(r, r"SLOPE\s*=\s*([-0-9.]+)")
            drv = num(r, r"SIGN_DRIVER\s*=\s*([^,\n]+)")
            print(f"         B2 SLOPE={s} DRIVER={drv}")
        c = r.get("content", "")
        if qid in ("dmx-a1", "dmx-g1"):
            print(f"         sig={answer_sig(qid, r)}")
        if qid == "dmx-c2":
            print(f"         code_chars={len(extract_code(r))}")


def compare(label, a, b):
    print(f"\n-- {label} --")
    for qid in sorted(set(a) | set(b)):
        if qid not in a or qid not in b:
            print(f"{qid:8s} MISSING")
            continue
        ca, cb = a[qid].get("content", ""), b[qid].get("content", "")
        print(f"{qid:8s} identical={norm(ca) == norm(cb)} first_diff={first_diff(ca, cb)} "
              f"len={len(ca)}/{len(cb)}")


def extract_code(run):
    c = run.get("content", "")
    m = re.search(r"```(?:python)?\s*\n(.*?)```", c, re.S)
    return (m.group(1) if m else c).strip()


def exec_c2(run):
    code = extract_code(run)
    if not code:
        return "no-code"
    harness = (
        "import json, numpy as np\n"
        "ns = {}\n"
        "exec(compile(open('c2.py', encoding='utf-8').read(), 'c2.py', 'exec'), ns)\n"
        "fn = ns.get('solve_execution')\n"
        "assert callable(fn), 'solve_execution missing'\n"
        "v = np.asarray(fn(), dtype=float)\n"
        "dt = 1.0 / 100\n"
        "print(json.dumps({'n': int(v.size), 'min': float(v.min()), 'sum_x': float(v.sum()*dt), "
        "'has_nan': bool(np.isnan(v).any())}))\n"
    )
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "c2.py")
        io.open(p, "w", encoding="utf-8").write(code + "\n")
        h = os.path.join(td, "h.py")
        io.open(h, "w", encoding="utf-8").write(harness)
        try:
            r = subprocess.run([sys.executable, h], cwd=td, capture_output=True,
                               text=True, timeout=120)
            return (r.stdout.strip() or r.stderr.strip())[-300:]
        except Exception as e:  # noqa: BLE001
            return f"ERR {e}"


def r4(x):
    try:
        return round(float(x), 4)
    except (TypeError, ValueError):
        return x


def answer_sig(qid, run):
    """语义答案签名：跨 run 文本会漂移，但数值/锚点应稳定。"""
    c = run.get("content", "")
    if qid == "dmx-a3":
        return {"gauss": r4(num(run, r"GAUSS_RHO\s*=\s*([-0-9.]+)")),
                "t": r4(num(run, r"T_RHO\s*=\s*([-0-9.]+)")),
                "rel": (num(run, r"RELATION\s*=\s*([A-Za-z]+)") or "").lower()}
    if qid == "dmx-b2":
        return {"slope": r4(num(run, r"SLOPE\s*=\s*([-0-9.]+)")),
                "driver": (num(run, r"SIGN_DRIVER\s*=\s*([^,\n]+)") or "").strip().lower()}
    if qid == "dmx-a1":
        return {"small_denom": ("分母" in c or "趋小" in c or "趋于0" in c or "趋近于0" in c),
                "tranche": ("夹层" in c or "tranche" in c.lower()),
                "independent": ("独立" in c or "无关" in c or "而非" in c
                                or ("绝对" in c and "相对" in c) or "different" in c.lower())}
    if qid == "dmx-g1":
        return {"separate": ("psi" in c.lower() or "ψ" in c) and ("gamma" in c.lower() or "γ" in c),
                "degenerate": bool(re.search(
                    r"(psi\s*[*·]?\s*gamma\s*=\s*1|1\s*/\s*psi\s*=\s*gamma|gamma\s*=\s*1\s*/\s*psi"
                    r"|ψ\s*[·*]?\s*γ\s*=\s*1|ψ\s*=\s*1\s*/\s*γ|ψ\s*=\s*\\frac\{1\}\{\\gamma\}"
                    r"|互为倒数)", c, re.I)),
                "discount_trap": ("折现率不同" in c)}
    if qid == "dmx-c2":
        code = extract_code(run)
        try:
            result = json.loads(exec_c2(run)) if code else {}
            result = {"n": result.get("n"), "min": round(result.get("min", 0), 6),
                      "sum": round(result.get("sum_x", 0), 6), "nan": result.get("has_nan")}
        except Exception:  # noqa: BLE001 — 保留原始错误文本
            result = {"raw": exec_c2(run)[:160]} if code else {}
        return {"has_code": bool(code), "result": result}
    return {"content": norm(c)}


def sig_compare(label, a, b):
    print(f"\n== 语义签名: {label} ==")
    for qid in sorted(set(a) & set(b)):
        sa, sb = answer_sig(qid, a[qid]), answer_sig(qid, b[qid])
        print(f"{qid:8s} same={sa == sb}")
        if sa != sb:
            print(f"         A={sa}")
            print(f"         B={sb}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--on", nargs="+", required=True)
    ap.add_argument("--off", nargs="+", required=True)
    ap.add_argument("--exec", action="store_true", dest="do_exec")
    args = ap.parse_args()

    on, off = load(args.on), load(args.off)
    on_files = sorted({f for v in on.values() for f in v})
    off_files = sorted({f for v in off.values() for f in v})

    summarize_arm("MTP ON", {q: on[q][on_files[0]] for q in on})
    summarize_arm("MTP OFF", {q: off[q][off_files[0]] for q in off})

    if len(on_files) > 1:
        compare("ON r1 vs r2",
                {q: on[q][on_files[0]] for q in on},
                {q: on[q][on_files[1]] for q in on})
    if len(off_files) > 1:
        compare("OFF r1 vs r2",
                {q: off[q][off_files[0]] for q in off},
                {q: off[q][off_files[1]] for q in off})
    compare("ON r1 vs OFF r1", {q: on[q][on_files[0]] for q in on},
            {q: off[q][off_files[0]] for q in off})
    if len(on_files) > 1:
        sig_compare("ON r1 vs ON r2",
                    {q: on[q][on_files[0]] for q in on},
                    {q: on[q][on_files[1]] for q in on})
    if len(off_files) > 1:
        sig_compare("OFF r1 vs OFF r2",
                    {q: off[q][off_files[0]] for q in off},
                    {q: off[q][off_files[1]] for q in off})
    sig_compare("ON r1 vs OFF r1", {q: on[q][on_files[0]] for q in on},
                {q: off[q][off_files[0]] for q in off})

    if args.do_exec:
        print("\n-- C2 executable --")
        for qid in ("dmx-c2",):
            print("ON :", exec_c2(on[qid][on_files[0]]) if qid in on else "MISSING")
            print("OFF:", exec_c2(off[qid][off_files[0]]) if qid in off else "MISSING")


if __name__ == "__main__":
    main()
