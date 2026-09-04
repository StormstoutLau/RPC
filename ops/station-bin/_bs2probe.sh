#!/bin/bash
# bs2-probe.sh — BS-2 前置: 确认 opencode 工具面 (task/agent 是否可用) + 当前路由
set -u
echo "== opencode 版本 =="
opencode --version 2>&1 | head -1
echo "== 当前 provider/model 生效 (config 顶层) =="
python3 - <<'PY'
import json,re,os
p=os.path.expanduser("~/.config/opencode/opencode.jsonc")
raw=open(p).read()
# 去注释(行首// 与行尾 ,) 简易: 移除行级注释行
s=re.sub(r'^\s*//.*$','',raw, flags=re.M)
try:
    d=json.loads(s)
except Exception as e:
    print("json parse err:", e); d={}
print("model:", d.get("model"))
print("provider keys:", list(d.get("provider",{}).keys()))
# 测重复 key: 统计顶层 provider 里出现次数
import collections
for k,v in d.get("provider",{}).items():
    pass
print("顶层 provider['cluster-local'] 类型:", type(d.get("provider",{}).get("cluster-local")).__name__)
PY
echo "== opencode 是否有 agent/task 工具 (内置 agent 模式) =="
opencode --help 2>&1 | grep -iE 'agent|task|fork|pipe' || echo "help 无明显 agent/task 项"
echo "== 空闲实测: 单次最小调用, 走默认模型 =="
echo 'Reply with exactly the single word PROBE-OK' | timeout 120 opencode run -m opencode/nemotron-3.5-lightning-free 2>&1 | tail -3
echo "[rc=${PIPESTATUS[1]}]"
echo OK