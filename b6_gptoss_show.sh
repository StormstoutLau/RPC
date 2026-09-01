#!/bin/bash
# 取回 gpt-oss-120b 冒烟结果 (B 站执行)
set -u
python3 - <<'EOF'
import json
with open("/tmp/b6_smoke_gptoss120b.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        print(f"########## {r['id']} ({r['elapsed_s']}s, finish={r['finish']}) ##########")
        print("--- CONTENT ---")
        print(r.get("content", r.get("error", "")))
        print("--- REASONING (前600字) ---")
        print((r.get("reasoning") or "")[:600])
        print()
EOF
