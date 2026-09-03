#!/bin/bash
LOG=/home/scott-lau/.unsloth/run-gpt-8080-minthink.log
KEY=$(grep -oE "sk-unsloth-[a-f0-9]+" "$LOG" | tail -1)
echo "key_len=${#KEY}; key_head=${KEY:0:15}"
echo "== 生成 =="
timeout 180 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"What is 2+2? Answer in one word."}],"max_tokens":200,"temperature":0}' > /tmp/gen.json 2>&1
python3 -c "import json;d=json.load(open('/tmp/gen.json'));print('keys=',list(d.keys()));print('content=',d.get('choices',[{}])[0].get('message',{}).get('content'))" 2>&1 | head -c 300