#!/bin/bash
LOG=/home/scott-lau/.unsloth/run-gpt-bkvq.log
KEY=$(grep -oE "sk-unsloth-[a-f0-9]+" "$LOG" | tail -1)
echo "key=${KEY:0:14}... port 8080"
echo "== 正确性 2+2 =="
timeout 60 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"What is 2+2? one number."}],"max_tokens":40,"temperature":0}' | python3 -c "import sys,json;print(repr(json.load(sys.stdin)['choices'][0]['message']['content']))" 2>&1 | head -c 120
echo
echo "== 解码速度 (长 512) =="
python3 - "$LOG" <<'PY'
import json,time,urllib.request,re,sys
KEY=re.search(r'sk-unsloth-[a-f0-9]+',open(sys.argv[1]).read()).group(0)
body=json.dumps({"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"Write a detailed 400-word article about the history of semiconductor manufacturing."}],"max_tokens":512,"temperature":0.7,"stream":True}).encode()
req=urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",data=body,headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"})
t=time.time(); first=None; Lt=0
with urllib.request.urlopen(req,timeout=600) as R:
    for raw in R:
        s=raw.decode().strip()
        if not s.startswith("data:"): continue
        d=s[6:].strip()
        if d=="[DONE]": break
        try:o=json.loads(d)
        except:continue
        c=o.get("choices",[{}])[0].get("delta",{}).get("content") or ""
        rc=o.get("choices",[{}])[0].get("delta",{}).get("reasoning_content") or ""
        if first is None and (c or rc): first=time.time()
        Lt+=(len(c)+len(rc))//4
tot=time.time()-t
dec=max(0.5,tot-(first-t if first else 0))
print(f"B gpt-oss q8_0: tokens~{Lt} total={tot:.1f}s decode={Lt/dec:.1f} tok/s")
PY
echo "== 内存 =="
free -g | head -2