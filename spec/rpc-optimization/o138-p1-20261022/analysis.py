#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import statistics

BASE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    rows = []
    with open(os.path.join(BASE, path), encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line.startswith("RESULT "):
                rows.append(json.loads(line[7:]))
    return rows


def summarize(label, short, long):
    s = load(short)
    l = load(long)

    def mean(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return statistics.mean(vals) if vals else float("nan")

    print("%-28s short: n=%d decode %.2f t/s (prefill %.1f, prompt_n %.0f) | long: n=%d decode %.2f t/s (prefill %.1f, prompt_n %.0f)" % (
        label,
        len(s), mean(s, "predicted_tps"), mean(s, "prompt_tps"), mean(s, "prompt_n"),
        len(l), mean(l, "predicted_tps"), mean(l, "prompt_tps"), mean(l, "prompt_n"),
    ))


summarize("A ncmoe0/fa-on/8k", "o138_A_short.jsonl", "o138_A_long.jsonl")
summarize("A-recheck ncmoe0/fa-on", "o138_A_recheck_short.jsonl", "o138_A_recheck_long.jsonl")
summarize("B ncmoe8/fa-on/8k", "o138_B_short.jsonl", "o138_B_long.jsonl")
summarize("C ncmoe0/KVq8/fa-on", "o138_C_short.jsonl", "o138_C_long.jsonl")
summarize("D ncmoe0/fa-off", "o138_D_short.jsonl", "o138_D_long.jsonl")
summarize("E ncmoe8/fa-on/262k", "o138_E_short.jsonl", "o138_E_long.jsonl")
