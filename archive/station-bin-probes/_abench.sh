#!/bin/bash
# 通用 gpt-oss 推理测速 (A站内执行)。用法: bash _abench.sh <logfile> [port] [heuristic_tokens]
LOG=/home/scott-lau/.unsloth/${1:-run-gpt-8080.log}
PORT=${2:-8080}
KEY=$(grep -oE "sk-unsloth-[a-f0-9]+" "$LOG" | tail -1)
echo "log=$LOG key=${KEY:0:14}... port=$PORT"
echo "== [基线步骤] KV 量化形态 =="
grep -oE "cache-type-k [a-z0-9_]+|cache-type-v [a-z0-9_]+" "$LOG" | sort -u || echo "(未指定 => f16)"
echo "== 正确性 2+2 =="
timeout 120 curl -s http://127.0.0.1:$PORT/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"gpt-oss-120b-MXFP4\",\"messages\":[{\"role\":\"user\",\"content\":\"What is 2+2? one number.\"}],\"max_tokens\":60,\"temperature\":0}" 2>&1 \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('content=',repr(d.get('choices',[{}])[0].get('message',{}).get('content')))" 2>&1 | head -c 200
echo
echo "== 解码速度(短, 无强制思考) =="
python3 - "$LOG" "$PORT" <<'PY'
import json,time,urllib.request,re,sys
log,port=sys.argv[1],int(sys.argv[2])
KEY=re.search(r'sk-unsloth-[a-f0-9]+',open(log).read()).group(0)
body=json.dumps({"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"Write a short haiku about silicon chips."}],"max_tokens":200,"temperature":0.7,"stream":True}).encode()
req=urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",data=body,headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"})
t=time.time(); first=None; Lt=0; Lc=0
with urllib.request.urlopen(req,timeout=300) as R:
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
        Lc+=len(c)//4
tot=time.time()-t
dec=max(0.5,tot-(first-t if first else 0))
print(f"short: total_tokens~{Lt} content_tokens~{Lc} first={(first-t) if first else 'NA':.1f}s total={tot:.1f}s decode={Lt/dec:.1f} tok/s")
PY
echo "== 解码速度(长输出 512 tokens) =="
python3 - "$LOG" "$PORT" <<'PY'
import json,time,urllib.request,re,sys
log,port=sys.argv[1],int(sys.argv[2])
KEY=re.search(r'sk-unsloth-[a-f0-9]+',open(log).read()).group(0)
body=json.dumps({"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":"Write a detailed 400-word article about the history and future of semiconductor manufacturing."}],"max_tokens":512,"temperature":0.7,"stream":True}).encode()
req=urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",data=body,headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"})
t=time.time(); first=None; Lt=0; Lc=0
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
        Lc+=len(c)//4
tot=time.time()-t
dec=max(0.5,tot-(first-t if first else 0))
print(f"long: total_tokens~{Lt} content_tokens~{Lc} first={(first-t) if first else 'NA':.1f}s total={tot:.1f}s decode={Lt/dec:.1f} tok/s")
PY
echo "== 内存 =="
free -g | head -2