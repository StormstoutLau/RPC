#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
cp "$CL" "$CL.bak-cx3"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
# 移除冲突项
for k in ['ANTHROPIC_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME','ANTHROPIC_DEFAULT_OPUS_MODEL_NAME','ANTHROPIC_DEFAULT_SONNET_MODEL_NAME']:
    env.pop(k,None)
if 'model' in d: d.pop('model')
# 设置推荐组合
env['ANTHROPIC_BASE_URL']='http://127.0.0.1:8087'
env['ANTHROPIC_AUTH_TOKEN']='dummy'
env['ANTHROPIC_CUSTOM_MODEL_OPTION']='gpt-oss-120b-MXFP4'
env['ANTHROPIC_CUSTOM_MODEL_OPTION_NAME']='GPT-OSS 120B MXFP4 (A 站)'
env['ANTHROPIC_DEFAULT_HAIKU_MODEL']='gpt-oss-120b-MXFP4'
env['ANTHROPIC_DEFAULT_OPUS_MODEL']='gpt-oss-120b-MXFP4'
env['ANTHROPIC_DEFAULT_SONNET_MODEL']='gpt-oss-120b-MXFP4'
env['CLAUDE_CODE_SUBAGENT_MODEL']='gpt-oss-120b-MXFP4'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("set NIM-style custom model config")
PY
echo "== 应用后 env 模型键 =="
grep -E 'ANTHROPIC_(MODEL|DEFAULT|CUSTOM|BASE|AUTH)|CLAUDE_CODE_SUBAGENT|"model"' "$CL"