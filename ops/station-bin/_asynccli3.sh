#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
env['ANTHROPIC_MODEL']='openai/gpt-oss-120b-MXFP4'
d['model']='openai/gpt-oss-120b-MXFP4'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("model -> openai/gpt-oss-120b-MXFP4")
PY
grep -E '"model"|ANTHROPIC_MODEL' "$CL"