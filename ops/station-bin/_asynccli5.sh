#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
S=/home/scott-lau/.claude/settings.json.bak-20260904-verify
cp "$CL" "$S"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
# 移除带 provider 前缀的值模型列表，改无前缀; 并删除 *_MODEL_NAME 四键
for k in ['ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL']:
    env[k]='gpt-oss-120b-MXFP4'
for k in ['ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME','ANTHROPIC_DEFAULT_OPUS_MODEL_NAME','ANTHROPIC_DEFAULT_SONNET_MODEL_NAME']:
    env.pop(k,None)
env['ANTHROPIC_MODEL']='gpt-oss-120b-MXFP4'
d['model']='gpt-oss-120b-MXFP4'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("postfix: 无前缀 MXFP4, MODEL_NAME 已删, 备份",open('/home/scott-lau/.claude/settings.json.bak-20260904-verify','r') and 'ok')
PY
echo "== 更新后 =="
grep -E 'DEFAULT|MODEL|model' "$CL" | head -14