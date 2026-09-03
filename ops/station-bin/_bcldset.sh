#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
cp "$CL" "$CL.bak-20260904"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
# 清冲突项
for k in ['ANTHROPIC_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL']:
    env.pop(k,None)
# 顶层 model 用 Anthropic 名 + modelOverrides 映射到后端 gpt-oss (当前 unsloth 8080 已加载)
d['model']='claude-opus-4-6'
d['modelOverrides']={
    'claude-opus-4-6':'gpt-oss-120b-MXFP4',
    'claude-sonnet-4-6':'gpt-oss-120b-MXFP4',
    'claude-haiku-4-5':'gpt-oss-120b-MXFP4',
}
# BASE_URL -> B 站 unsloth 8080
env['ANTHROPIC_BASE_URL']='http://127.0.0.1:8080'
env['ANTHROPIC_AUTH_TOKEN']='sk-unsloth-f5ec3cebea66f627889ae59edd8df5e3'
# MAX_CONTEXT 保持 (gpt-oss 131k 内)
env['CLAUDE_CODE_MAX_CONTEXT_TOKENS']='120000'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("B claude: model=claude-opus-4-6 + modelOverrides->gpt-oss-120b-MXFP4 + BASE_URL 8080 unsloth")
PY
echo "== 结果 =="
grep -E '"model"|modelOverrides|claude-|MXFP4|BASE_URL|AUTH_TOKEN|MAX_CONTEXT' "$CL"