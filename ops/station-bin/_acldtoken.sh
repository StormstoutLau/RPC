#!/bin/bash
# [DEPRECATED 2026-09-13] 密钥脱敏废弃：写 claude settings 配置，重跑污染生产，勿执行
set -e
CL=/home/scott-lau/.claude/settings.json
cp "$CL" "$CL.bak-cx5"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
env['ANTHROPIC_AUTH_TOKEN']='***REMOVED***'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("AUTH_TOKEN -> real unsloth key")
PY
grep 'AUTH_TOKEN' "$CL"