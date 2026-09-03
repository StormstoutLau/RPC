#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
cp "$CL" "$CL.bak-cx5"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
env['ANTHROPIC_AUTH_TOKEN']='sk-unsloth-581f55854cb263e3ebbc3ba7914b9191'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("AUTH_TOKEN -> real unsloth key")
PY
grep 'AUTH_TOKEN' "$CL"