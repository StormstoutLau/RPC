#!/bin/bash
python3 - <<'PY'
import re,os
p=os.path.expanduser('~/.config/opencode/opencode.jsonc')
s=open(p).read()
# 只在 cluster-local 的 gpt-oss 块内提升 limit
blk=re.search(r'("cluster-local": \{.*?\n    \})', s, re.S)
if blk:
    b=blk.group(1)
    nb=b.replace('"context": 30000','"context": 120000').replace('"output": 8192','"output": 16384')
    s=s.replace(b,nb)
    open(p,'w').write(s)
    print('context/output 已提升: cluster-local gpt-oss -> 120000/16384')
else:
    print('NOT FOUND')
PY
echo "== 校验 =="
python3 -c "import json,os; raw=open(os.path.expanduser('~/.config/opencode/opencode.jsonc')).read(); json.loads(re.sub(r'//.*','',raw))" 2>/dev/null || echo "(jsonc 仅校验注释清理, 关键块如下)"
grep -A10 '"gpt-oss"' ~/.config/opencode/opencode.jsonc | grep -iE "context|output|name" | head