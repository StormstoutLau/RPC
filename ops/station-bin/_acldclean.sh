#!/bin/bash
CL=/home/scott-lau/.claude/settings.json
cp "$CL" "$CL.bak-cx2"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
env.pop('ANTHROPIC_MODEL',None)
# 顶层 model 移除
if 'model' in d: d.pop('model')
# DEFAULT_* 统一后端模型名（不带 provider 前缀，claude 当作自定义模型）
env['ANTHROPIC_DEFAULT_HAIKU_MODEL']='gpt-oss-120b-MXFP4'
env['ANTHROPIC_DEFAULT_OPUS_MODEL']='gpt-oss-120b-MXFP4'
env['ANTHROPIC_DEFAULT_SONNET_MODEL']='gpt-oss-120b-MXFP4'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("cleaned: no top model, DEFAULT_*=gpt-oss-120b-MXFP4 (no prefix)")
PY
echo "== settings env model 相关 =="
grep -E 'DEFAULT|MODEL|"model"' "$CL"