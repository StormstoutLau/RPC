#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
cp "$CL" "$CL.bak-20260904-try1"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
# 顶层 model 用官方名（claude 识别通过）
d['model']='claude-opus-4-7'
env['ANTHROPIC_MODEL']='openai/gpt-oss-120b-MXFP4'
# DEFAULT_* 指向实际后端模型
for k in ['ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL']:
    env[k]='openai/gpt-oss-120b-MXFP4'
# 删 MODEL_NAME（避免 provider 严格校验）
for k in ['ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME','ANTHROPIC_DEFAULT_OPUS_MODEL_NAME','ANTHROPIC_DEFAULT_SONNET_MODEL_NAME']:
    env.pop(k,None)
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("model=claude-opus-4-7(top) / ANTHROPIC_MODEL=openai/gpt-oss-120b-MXFP4")
PY
grep -E '"model"|DEFAULT_.*MODEL' "$CL"