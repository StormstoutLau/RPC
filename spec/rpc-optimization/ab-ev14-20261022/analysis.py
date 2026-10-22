#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import statistics

BASE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    rows = []
    with open(os.path.join(BASE, name), encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line.startswith("RESULT "):
                rows.append(json.loads(line[7:]))
    return rows


def summarize(tag, name):
    rows = load(name)
    pre = [r for r in rows if r["mode"] == "prefill"]
    dec = [r for r in rows if r["mode"] == "decode"]
    fix = [r for r in rows if r["mode"] == "fixed"]
    print("== %s ==" % tag)
    for label, vals in [
        ("prefill_tps", [r["prompt_tps"] for r in pre]),
        ("prefill_prompt_n", [r["prompt_n"] for r in pre]),
        ("decode_tps", [r["predicted_tps"] for r in dec]),
    ]:
        print("%-18s mean %.3f  min %.3f  max %.3f  n=%d" % (
            label, statistics.mean(vals), min(vals), max(vals), len(vals)))
    print("fixed:", [(r["content"], r["predicted_n"], r["finish"]) for r in fix])
    print()


summarize("shadow e197cef4", "shadow.jsonl")
summarize("baseline 23b0202a", "baseline.jsonl")
