#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
cp "$CL" "$CL.bak-cx4"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
# 清理之前设的冲突项
for k in ['ANTHROPIC_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL',
          'ANTHROPIC_CUSTOM_MODEL_OPTION','ANTHROPIC_CUSTOM_MODEL_OPTION_NAME','CLAUDE_CODE_SUBAGENT_MODEL',
          'ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME','ANTHROPIC_DEFAULT_OPUS_MODEL_NAME','ANTHROPIC_DEFAULT_SONNET_MODEL_NAME']:
    env.pop(k,None)
# 顶层 model = Anthropic 名义（会被 modelOverrides 映射到后端）
d['model']='claude-opus-4-6'
# modelOverrides: Anthropic ID -> 后端 gpt-oss
d['modelOverrides']={
    'claude-opus-4-6':'gpt-oss-120b-MXFP4',
    'claude-sonnet-4-6':'gpt-oss-120b-MXFP4',
    'claude-haiku-4-5':'gpt-oss-120b-MXFP4',
}
# 保证 BASE_URL/TOKEN
env['ANTHROPIC_BASE_URL']='http://127.0.0.1:8087'
env['ANTHROPIC_AUTH_TOKEN']='dummy'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("model=claude-opus-4-6 + modelOverrides->gpt-oss-120b-MXFP4")
PY
echo "== 结果 =="
grep -E '"model"|modelOverrides|claude-|gpt-oss-120b|BASE_URL|AUTH' "$CL"