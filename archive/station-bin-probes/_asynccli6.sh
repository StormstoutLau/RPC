#!/bin/bash
set -e
CL=/home/scott-lau/.claude/settings.json
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
env.pop('ANTHROPIC_MODEL',None)   # 移除，避免顶层 model 校验
d.pop('model',None)               # 移除顶层 model 字段
# DEFAULT_* 用无前缀 CL-style 名字（claude 视为自定义模型）
for k in ['ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL']:
    env[k]='gpt-oss-120b-MXFP4'
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("ANTHROPIC_MODEL/顶层model 移除; DEFAULT_* 保留")
PY
echo "== 更新后 =="
grep -E 'DEFAULT|MODEL|"model"' "$CL"