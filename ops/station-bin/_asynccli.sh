#!/bin/bash
# 同步 A 站 CLI 端点到当前 unsloth gpt-oss 实例 (q8_0 KV, port 8087, key sk-unsloth-581f...)
set -e
OC=/home/scott-lau/.config/opencode/opencode.jsonc
CL=/home/scott-lau/.claude/settings.json

echo "== 更新前 opencode cluster-local =="
grep -E '127.0.0.1:808[0-9]|apiKey' -A1 "$OC" | head -20

# 用 python 做安全字典级更新（保留注释困难，jsonc 兼容：python 无法解析 trailing comma/jsonc）
# opencode.jsonc 含 trailing comma (非strict JSON)，改用 sed 精准替换
# cluster-local baseURL: 8080 -> 8087 (仅第一处 cluster-local 的 127.0.0.1:8080)
python3 - "$OC" <<'PY'
import re,sys
p=sys.argv[1]
s=open(p).read()
# 替换 cluster-local 的 baseURL（127.0.0.1:8080 -> 127.0.0.1:8087）
new, n = re.subn(r'(cluster-local[^}]*baseURL"\s*:\s*)"http://127\.0\.0\.1:8080/v1"',
                 r'\1"http://127.0.0.1:8087/v1"', s, count=1)
# 替换 apiKey（任意 sk-unsloth-* -> 最新）
new, nk = re.subn(r'(cluster-local[^}]*apiKey"\s*:\s*)"sk-unsloth-[a-f0-9]+"',
                  r'\1"sk-unsloth-581f55854cb263e3ebbc3ba7914b9191"', new, count=1)
open(p,'w').write(new)
print(f"baseURL replaced={n} apiKey replaced={nk}")
PY

echo "== 更新后 opencode cluster-local =="
grep -E '127.0.0.1:808[0-9]|sk-unsloth' -A1 "$OC" | head -20

echo
echo "== claude settings BASE_URL =="
grep 'ANTHROPIC_BASE_URL' "$CL"
python3 - "$CL" <<'PY'
import sys,json
p=sys.argv[1]
d=json.load(open(p))
env=d.get('env',{})
if 'ANTHROPIC_BASE_URL' in env:
    env['ANTHROPIC_BASE_URL']="http://127.0.0.1:8087"
d.setdefault('env',env)
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("claude BASE_URL -> 8087")
PY
echo "== 更新后 =="
grep 'ANTHROPIC_BASE_URL' "$CL"