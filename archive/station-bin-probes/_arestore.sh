#!/bin/bash
set -e
# 恢复原始 settings（此前已备份含原始 fable 模型名），仅更新 BASE_URL
SRC=/home/scott-lau/.claude/settings.json.bak-20260904
CL=/home/scott-lau/.claude/settings.json
cp "$SRC" "$CL"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
d['env']['ANTHROPIC_BASE_URL']='http://127.0.0.1:8087'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("restored fable models, BASE_URL->8087")
PY
echo "== 恢复后 =="
grep -E 'ANTHROPIC_BASE_URL|ANTHROPIC_MODEL|fable|"model"|DEFAULT.*MODEL' "$CL" | head