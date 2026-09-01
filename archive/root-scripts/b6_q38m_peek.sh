#!/bin/bash
# 核对 q38m 已产出 3 题原文 (B 站)
python3 - <<'EOF'
import json
with open("/tmp/b6_smoke_q38m.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        c = (r.get("content") or r.get("error", "")).replace("\n", " ")
        print(f"### {r['id']} ({r.get('finish')}): {c[:250]}")
EOF
