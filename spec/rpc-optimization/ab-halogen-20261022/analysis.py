#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarize tmp/ab_*.jsonl (local controller)."""
import glob
import json
import os
import statistics

BASE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line.startswith("RESULT "):
                rows.append(json.loads(line[7:]))
    return rows


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "n/a"
    return "mean %.3f (min %.3f, max %.3f, n=%d)" % (
        statistics.mean(vals),
        min(vals),
        max(vals),
        len(vals),
    )


print("== PREFILL ==")
for arm, tag in [
    ("0.18.11", "01811"),
    ("0.18.12", "01812"),
    ("0.18.13", "01813"),
    ("0.18.11-recheck", "01811_recheck"),
]:
    for size in ("8k", "32k"):
        p = os.path.join(BASE, "ab_%s_prefill_%s.jsonl" % (tag, size))
        if not os.path.exists(p):
            continue
        rows = load(p)
        print(
            "%-16s %-3s  prompt_n %-8s  prompt_ms %-8s  tps %s"
            % (
                arm,
                size,
                "%.0f" % statistics.mean([r["prompt_n"] for r in rows]),
                "%.0f" % statistics.mean([r["prompt_ms"] for r in rows]),
                "%.1f" % statistics.mean([r["prompt_tps"] for r in rows]),
            )
        )
print()

print("== FAIRNESS ==")
for arm, tag in [
    ("0.18.11", "01811"),
    ("0.18.12", "01812"),
    ("0.18.13", "01813"),
    ("0.18.13-flags-off", "01813_flagsoff"),
]:
    p = os.path.join(BASE, "ab_%s_fairness.jsonl" % tag)
    if not os.path.exists(p):
        continue
    rows = load(p)
    nest_ttft = [r["nest"]["short"]["ttft_s"] for r in rows]
    nest_gap = [r["nest"]["short"]["max_gap_s"] for r in rows]
    long_ms = [r["nest"]["long"]["prompt_ms"] for r in rows]
    splice_gap = [r["splice"]["short"]["max_gap_after_trigger_s"] for r in rows]
    splice_long_ms = [r["splice"]["long"]["prompt_ms"] for r in rows]
    print("%-18s nest: short_ttft %s | long_prefill_ms %s" % (arm, stats(nest_ttft), stats(long_ms)))
    print("%-18s       short_max_gap %s" % ("", stats(nest_gap)))
    print("%-18s splice: max_gap_after_long_start %s | long_prefill_ms %s" % (arm, stats(splice_gap), stats(splice_long_ms)))
