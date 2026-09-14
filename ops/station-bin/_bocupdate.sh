#!/bin/bash
# [DEPRECATED 2026-09-13] 密钥脱敏废弃：生成 opencode 配置块含占位符，重跑污染生产，勿执行
set -e
OC=/home/scott-lau/.config/opencode/opencode.jsonc
cp "$OC" "$OC.bak-20260904"
python3 - "$OC" <<'PY'
import sys,json,re
p=sys.argv[1]
s=open(p).read()
if 'cluster-local' in s:
    print('already present'); sys.exit(0)
# 定位 provider 对象结尾：找 compaction 前的顶层 provider 闭合
# 解析：在 'compaction' 之前的最后一个顶层 "}" 是 provider 的闭合
idx= s.find('"compaction"')
provider_region = s[:idx]
# provider 最后闭合 brace 位置（最后一个 '}' 在 provider_region 中即 provider 块结尾）
last_brace = provider_region.rstrip().rfind('}')
if last_brace == -1:
    print('cannot find provider close'); sys.exit(1)
# 在 provider 块末尾 '} 之后插入 ",  "cluster-local": {...}"
insert_at = last_brace
block = ',' + '\n    "cluster-local": {\n      "name": "B 站本地 unsloth gpt-oss",\n      "npm": "@ai-sdk/openai-compatible",\n      "options": {\n        "baseURL": "http://127.0.0.1:8080/v1",\n        "apiKey": "***REMOVED***"\n      },\n      "models": {\n        "gpt-oss": {\n          "name": "GPT-OSS 120B MXFP4 (B 站 unsloth q8_0)",\n          "limit": {\n            "context": 120000,\n            "output": 16384\n          }\n        }\n      }\n    }'
s2 = s[:insert_at+1] + block + s[insert_at+1:]
open(p,'w').write(s2)
print('cluster-local provider appended after cluster-litellm')
PY
echo "== 语法校验 (node) =="
node -e "const fs=require('fs');let s=fs.readFileSync('$OC','utf8');s=s.replace(/,\s*([}\]])/g,'$1');JSON.parse(s);console.log('valid JSONC(去trailing comma)')" 2>&1 | tail -2
echo "== provider keys =="
grep -oE '"[a-z-]+": \{' "$OC"