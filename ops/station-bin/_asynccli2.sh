#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
def fix(k):
    if k in env: env[k]=env[k].replace('gpt-oss-120b-fable-5-distilled','gpt-oss-120b-MXFP4')
for k in ['ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME',
          'ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL_NAME',
          'ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL_NAME']:
    fix(k)
env['ANTHROPIC_MODEL']='gpt-oss-120b-MXFP4'
d['model']='gpt-oss-120b-MXFP4'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("claude models -> gpt-oss-120b-MXFP4")
PY
echo "== 更新后 key 行 =="
grep -E 'ANTHROPIC_MODEL|gpt-oss-120b-MXFP4|fable' "$CL"