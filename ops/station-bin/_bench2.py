#!/usr/bin/env python
# gpt-oss ROCm benchmark v2: accumulate reasoning+content, large max_tokens, plus timing
import json, time, urllib.request, sys

BASE="http://127.0.0.1:8081/v1"
KEY="sk-unsloth-5ce1db5e532f4a3404118a7f2143ce93"

def est(text): return max(1,len(text)//4)

def run(prompt, max_tokens):
    body=json.dumps({"model":"gpt-oss-120b-MXFP4",
        "messages":[{"role":"user","content":prompt}],
        "max_tokens":max_tokens,"temperature":0.7,"stream":True}).encode()
    req=urllib.request.Request(BASE+"/chat/completions", data=body,
        headers={"Content-Type":"application/json","Authorization":"Bearer "+KEY})
    start=time.time(); first=None; content=""; reasoning=""; usage=None; extra_keys=set()
    with urllib.request.urlopen(req, timeout=600) as r:
        for raw in r:
            line=raw.decode().strip()
            if not line.startswith("data:"): continue
            d=line[6:].strip()
            if d=="[DONE]": break
            try: obj=json.loads(d)
            except: continue
            if obj.get("usage"): usage=obj["usage"]
            ch=obj.get("choices",[{}])
            if not ch: continue
            delta=ch[0].get("delta",{})
            for k in delta:
                if isinstance(delta[k],str):
                    extra_keys.add(k)
            c=delta.get("content"); rc=(delta.get("reasoning_content") or delta.get("reasoning") or delta.get("thinking"))
            if first is None and (c or rc): first=time.time()
            if c: content+=c
            if rc: reasoning+=rc
    end=time.time()
    n_content=est(content); n_rsn=est(reasoning); n_total=n_content+n_rsn
    total=end-start; ttft=(first-start) if first else total
    print("="*70)
    print(f"delta_fields={sorted(extra_keys)}")
    print(f"reasoning_tokens~{n_rsn} content_tokens~{n_content} TOTAL~{n_total}")
    print(f"TTFT(first token)={ttft:.2f}s | total={total:.2f}s")
    print(f"throughput={n_total/total:.2f} tok/s (all incl reasoning+prefill)")
    if total>ttft and n_total>0:
        print(f"decode_only~{n_total/(total-ttft):.2f} tok/s")
    print("usage=",json.dumps(usage))
    print("content_head="+content[:150].replace("\n"," "))
    return n_total, total, ttft

if __name__=="__main__":
    prompt=("Write a Python function is_well_formed_code(code:str|None)->bool validating an internal "
            "literature code: non-empty, exactly two parts split by '-', PREFIX 2-5 UPPERCASE letters, "
            "NUM 3-8 decimal digits, total length<=40, no surrounding whitespace. Only output the function.")
    run(prompt, 1400)