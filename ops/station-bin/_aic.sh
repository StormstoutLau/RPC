#!/bin/bash
echo "== opencode cluster-local gpt-oss 当前块 =="
python3 - <<'PY'
import re,os
p=os.path.expanduser('~/.config/opencode/opencode.jsonc')
s=open(p).read()
m=re.search(r'("cluster-local": \{.*?)("cluster-litellm"|$)', s, re.S)
print(m.group(1) if m else 'NOT FOUND')
PY