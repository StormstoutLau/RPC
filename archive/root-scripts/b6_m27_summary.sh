#!/bin/bash
# b6_m27_summary.sh — 汇总 m27 全部 5 题最终成绩
python3 - <<'PYEOF'
import json

def load(path):
    try:
        return {json.loads(l)["id"]: json.loads(l) for l in open(path)}
    except Exception:
        return {}

main = load('/tmp/b6_smoke_m27.jsonl')       # 首跑: b2/a1/g1 有效
retry = load('/tmp/b6_smoke_m27_retry.jsonl') # retry: 全零
final = load('/tmp/b6_smoke_m27_final.jsonl') # final: 全零

print("=== m27 5 题终局 ===")
for qid in ["dmx-a3", "dmx-b2", "dmx-a1", "dmx-g1", "dmx-c2"]:
    src = None
    for d in (final, retry, main):
        if qid in d and d[qid].get("content"):
            src = d[qid]; break
    if src:
        print(f"[{qid}] OK {src.get('elapsed_s')}s len={len(src['content'])}")
    else:
        print(f"[{qid}] NO_CONTENT (所有尝试零产出)")
PYEOF