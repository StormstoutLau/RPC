#!/bin/bash
echo "=== B host ==="
hostname
echo "=== unsloth 后端配置 ==="
grep -iE "LLAMA_SERVER_PATH" ~/.bashrc ~/.profile 2>/dev/null
echo "=== opencode 完整 provider 配置 ==="
python3 -c "import json,sys; d=json.load(open('/home/scott-lau/.config/opencode/opencode.jsonc')); print(json.dumps(d.get('provider',{}), indent=1)[:1500])" 2>/dev/null || cat ~/.config/opencode/opencode.jsonc 2>/dev/null
echo "=== claude settings env ==="
python3 -c "import json;d=json.load(open('/home/scott-lau/.claude/settings.json'));print('env:',json.dumps({k:v for k,v in d.get('env',{}).items() if 'MODEL' in k or 'BASE' in k or 'AUTH' in k or 'TOKEN' in k},indent=1));print('model:',d.get('model'));print('modelOverrides:',json.dumps(d.get('modelOverrides')))" 2>/dev/null
echo "=== 运行中的 unsloth/模型 ==="
ps -eo pid,etime,cmd | grep -E "unsloth|llama" | grep -v grep | head -5
echo "=== 8080 端口 ==="
ss -tln 2>/dev/null | grep -E ":8080|:8081|:8084|:8087" | awk '{print $4}'