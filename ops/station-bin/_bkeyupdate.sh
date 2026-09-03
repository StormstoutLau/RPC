#!/bin/bash
set -e
OC=/home/scott-lau/.config/opencode/opencode.jsonc
CL=/home/scott-lau/.claude/settings.json
KEY=sk-unsloth-0895f5f165a09ae56b871dd52b074b94
python3 - "$OC" "$KEY" <<'PY'
import sys,json,re
p,k=sys.argv[1],sys.argv[2]
d=json.loads(re.sub(r',\s*([}\]])', r'\1', open(p).read()))
d['provider']['cluster-local']['options']['apiKey']=k
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("opencode key updated")
PY
python3 - "$CL" "$KEY" <<'PY'
import sys,json
p,k=sys.argv[1],sys.argv[2]
d=json.load(open(p))
d['env']['ANTHROPIC_AUTH_TOKEN']=k
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("claude key updated")
PY
echo "== 验证 opencode =="
echo 'Reply with exactly the single word B-FINAL-OK' | timeout 90 opencode run -m cluster-local/gpt-oss 2>&1 | tail -2
echo "[oc=${PIPESTATUS[1]}]"