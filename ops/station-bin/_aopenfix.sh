#!/bin/bash
KEY=sk-unsloth-6fb378896ff67d0c306f59e935a25179
echo "== 1) 确认 Anthropic /v1/messages (curl) =="
timeout 120 curl -s http://127.0.0.1:8080/v1/messages -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","max_tokens":48,"messages":[{"role":"user","content":"Reply with exactly ANTHROPIC-OK"}]}' 2>&1 | head -c 400
echo
echo "== 2) 给 opencode cluster-local 加 apiKey =="
# 备份+插入 apiKey 到 cluster-local options；幂等
python3 - <<'PY'
import json,re,os
p=os.path.expanduser('~/.config/opencode/opencode.jsonc')
s=open(p).read()
key='sk-unsloth-6fb378896ff67d0c306f59e935a25179'
# 只在 cluster-local 块内没有 apiKey 时插入到其 baseURL 之后
import re as _re
def inject(m):
    block=m.group(0)
    if '"apiKey"' in block: return block
    return block.replace('"baseURL": "http://127.0.0.1:8080/v1"', '"baseURL": "http://127.0.0.1:8080/v1",\n      "apiKey": "%s"'%key,1)
s2=_re.sub(r'("cluster-local": \{.*?\n    \})', inject, s, count=1, flags=_re.S)
if s2!=s:
    open(p+'.bak-unsloth','w').write(s)
    open(p,'w').write(s2)
    print('apiKey 注入 OK')
else:
    print('未匹配或已含 apiKey')
PY
echo "== 3) 校验 jsonc 片段 =="
grep -A8 '"cluster-local"' ~/.config/opencode/opencode.jsonc | head -10