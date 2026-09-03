#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
env['ANTHROPIC_MODEL']='gpt-oss-120b'
d['model']='gpt-oss-120b'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("model -> gpt-oss-120b (未识别名, MAX_CONTEXT_TOKENS 生效)")
PY
grep -E '"model"|ANTHROPIC_MODEL' "$CL"