#!/bin/bash
LOG=/home/scott-lau/.unsloth/run-gpt-kvq.log
KEY=$(grep -oE "sk-unsloth-[a-f0-9]+" "$LOG" | tail -1)
echo "key=${KEY:0:14}..."
echo "== 正确性: 2+2 =="
timeout 120 curl -s http://127.0.0.1:8080/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"What is 2+2? One word."}],"max_tokens":60,"temperature":0}' 2>&1 \
  | python3 -c "import sys,json;d=json.load(sys.stdin);m=d.get('choices',[{}])[0].get('message',{});print('content=',repr(m.get('content')))" 2>&1 | head -c 200
echo; echo "== 解码速度（低 think，60 tokens 预算） =="
python3 - <<'PY'
import json,time,urllib.request
KEY=__import__('re').search(r'sk-unsloth-[a-f0-9]+',open('/home/scott-lau/.unsloth/run-gpt-kvq.log').read()).group(0)
body=json.dumps({"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"Write a short haiku about silicon chips."}],"max_tokens":200,"temperature":0.7,"stream":True}).encode()
req=urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",data=body,headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"})
t=time.time(); first=None; L=0
with urllib.request.urlopen(req,timeout=300) as R:
    for raw in R:
        s=raw.decode().strip()
        if not s.startswith("data:"): continue
        d=s[6:].strip()
        if d=="[DONE]": break
        import json as j
        try:o=j.loads(d)
        except:continue
        c=o.get("choices",[{}])[0].get("delta",{}).get("content") or ""
        rc=o.get("choices",[{}])[0].get("delta",{}).get("reasoning_content") or ""
        if first is None and (c or rc): first=time.time()
        L+=len(c)//4 + len(rc)//4
tot=time.time()-t
print(f"~tokens={L} total={tot:.1f}s decode~{L/max(0.5,tot-(first-t if first else 0)):.1f} tok/s ; first={ (first-t) if first else 'NA':.1f}s")
PY
echo "== 内存（q8_0 + 8k ctx） =="
free -g | head -2