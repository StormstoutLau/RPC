#!/bin/bash
echo "=== B opencode.jsonc 行数 + provider 区域 =="
python3 - <<'PY'
import re
s=open('/home/scott-lau/.config/opencode/opencode.jsonc').read()
print("lines:", s.count('\n'))
# 打印 provider 对象完整括号
pi=s.find('"provider"')
# 找 provider 后的第一个 { 到与其配平的 }
stack=[]
start=None
for i,c in enumerate(s):
    if i<pi: continue
    if c=='{': 
        if start is None: start=i
        stack.append(i)
    elif c=='}':
        if stack:
            o=stack.pop()
            if not stack:
                end=i
                print("provider block:", s[start:end+1][:2000])
                break
PY