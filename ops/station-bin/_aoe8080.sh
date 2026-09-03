#!/bin/bash
set -e
OC=/home/scott-lau/.config/opencode/opencode.jsonc
CL=/home/scott-lau/.claude/settings.json
cp "$OC" "${OC}.bak-20260904-8080"
cp "$CL" "${CL}.bak-20260904-8080"
echo "== 更新 opencode cluster-local -> 8080 =="
python3 - "$OC" <<'PY'
import sys,json,re
p=sys.argv[1]
d=json.loads(re.sub(r',\s*([}\]])', r'\1', open(p).read()))
d['provider']['cluster-local']['options']['baseURL']='http://127.0.0.1:8080/v1'
d['provider']['cluster-local']['options']['apiKey']='sk-unsloth-3ea8ee000acbc1db06dcce310125d691'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("opencode ok")
PY
echo "== 更新 claude -> 8080 =="
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
d['env']['ANTHROPIC_BASE_URL']='http://127.0.0.1:8080'
d['env']['ANTHROPIC_AUTH_TOKEN']='sk-unsloth-3ea8ee000acbc1db06dcce310125d691'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("claude ok")
PY
echo "== 验证 opencode =="
echo 'Reply with exactly the single word A-8080-OK' | timeout 90 opencode run -m cluster-local/gpt-oss 2>&1 | tail -3
echo "[oc_rc=${PIPESTATUS[1]}]"