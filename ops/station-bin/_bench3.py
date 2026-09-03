#!/usr/bin/env python
import json, time, urllib.request
BASE="http://127.0.0.1:8083/v1"
KEY="sk-unsloth-9ebf2659eab2fc9464cb40f9d49f0615"
def est(t): return max(1,len(t)//4)
def run(prompt, max_tokens):
    body=json.dumps({"model":"NVIDIA-Nemotron-3-Super-120B-A12B-Q4_K_M",
        "messages":[{"role":"user","content":prompt}],
        "max_tokens":max_tokens,"temperature":0.7,"stream":True}).encode()
    req=urllib.request.Request(BASE+"/chat/completions",data=body,
        headers={"Content-Type":"application/json","Authorization":"Bearer "+KEY})
    start=time.time(); first=None; content=""; reasoning=""; extra=set()
    try:
        with urllib.request.urlopen(req,timeout=600) as r:
            for raw in r:
                line=raw.decode().strip()
                if not line.startswith("data:"): continue
                d=line[6:].strip()
                if d=="[DONE]": break
                try: obj=json.loads(d)
                except: continue
                ch=obj.get("choices",[{}])
                if not ch: continue
                delta=ch[0].get("delta",{})
                for k in delta:
                    if isinstance(delta[k],str): extra.add(k)
                c=delta.get("content"); rc=delta.get("reasoning_content") or delta.get("reasoning") or delta.get("thinking")
                if first is None and (c or rc): first=time.time()
                if c: content+=c
                if rc: reasoning+=rc
    except Exception as e:
        print("ERR",e)
    end=time.time()
    nc=est(content); nr=est(reasoning); nt=nc+nr; total=end-start; ttft=(first-start) if first else total
    print("="*70)
    print(f"delta_fields={sorted(extra)}")
    print(f"reasoning~{nr} content~{nc} TOTAL~{nt}")
    print(f"TTFT={ttft:.2f}s total={total:.2f}s")
    print(f"throughput={nt/total:.2f} tok/s | decode_only~{nt/(total-ttft):.2f} tok/s")
    print("content_head="+content[:140].replace("\n"," "))
if __name__=="__main__":
    p=("Design a single-file Python tool `find_dup.py` that scans a directory, finds files with "
       "identical content by content hash, and prints groups of duplicate paths. Handle large files "
       "by reading in chunks. Give complete code with a main() that takes the dir via argv.")
    run(p,1200)