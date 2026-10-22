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


b = load("baseline.jsonl")
m = load("mtp.jsonl")
b_tps = statistics.mean(r["predicted_tps"] for r in b)
m_tps = statistics.mean(r["predicted_tps"] for r in m)
draft = sum(r["draft_n"] or 0 for r in m)
accepted = sum(r["draft_n_accepted"] or 0 for r in m)
print("baseline: n=%d decode %.3f t/s (%s)" % (len(b), b_tps, [round(r["predicted_tps"], 2) for r in b]))
print("mtp     : n=%d decode %.3f t/s (%s)" % (len(m), m_tps, [round(r["predicted_tps"], 2) for r in m]))
print("delta   : %+.1f%%" % ((m_tps / b_tps - 1.0) * 100.0))
print("draft   : accepted %d / %d = %.1f%%" % (accepted, draft, 100.0 * accepted / draft if draft else 0.0))

b1 = load("one_worker_baseline.jsonl")
m1 = load("one_worker_mtp.jsonl")
b1_tps = statistics.mean(r["predicted_tps"] for r in b1)
m1_tps = statistics.mean(r["predicted_tps"] for r in m1)
d1 = sum(r["draft_n"] or 0 for r in m1)
a1 = sum(r["draft_n_accepted"] or 0 for r in m1)
print("1w baseline: n=%d decode %.3f t/s (vs 2w %+.1f%%)" % (len(b1), b1_tps, (b1_tps / b_tps - 1.0) * 100.0))
print("1w mtp     : n=%d decode %.3f t/s (vs 2w %+.1f%%)" % (len(m1), m1_tps, (m1_tps / m_tps - 1.0) * 100.0))
print("1w draft   : accepted %d / %d = %.1f%%" % (a1, d1, 100.0 * a1 / d1 if d1 else 0.0))
