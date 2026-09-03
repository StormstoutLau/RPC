#!/usr/bin/env python
# unsloth ROCm gpt-oss-120b benchmark via OpenAI-compat streaming on 8081
import json, time, urllib.request, sys

BASE="http://127.0.0.1:8081/v1"
KEY="sk-unsloth-5ce1db5e532f4a3404118a7f2143ce93"

def tokens_of(s):
    # rough token estimate by whitespace+ CJK-ish heuristic; not exact
    return max(1, len(s) // 4)

def stream(prompt, max_tokens, temperature=0.7):
    body=json.dumps({"model":"gpt-oss-120b-MXFP4","messages":[{"role":"user","content":prompt}],
                     "max_tokens":max_tokens,"temperature":temperature,"stream":True}).encode()
    req=urllib.request.Request(BASE+"/chat/completions", data=body,
        headers={"Content-Type":"application/json","Authorization":"Bearer "+KEY})
    start=time.time(); t0=time.time(); first=None; content=[]; usage=None
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            line=raw.decode().strip()
            if not line.startswith("data:") : continue
            data=line[6:].strip()
            if data=="[DONE]": break
            try: obj=json.loads(data)
            except: continue
            if obj.get("usage"): usage=obj["usage"]
            d=obj.get("choices",[{}])[0].get("delta",{})
            c=d.get("content")
            if c:
                if first is None: first=time.time()
                content.append(c)
    end=time.time()
    text="".join(content)
    return dict(first=first, start=start, end=end, text=text,
                usage=usage or {}, ctokens=len(text))

def report(prompt, max_tokens):
    r=stream(prompt, max_tokens)
    ttft=(r["first"]-r["start"]) if r["first"] else None
    total=r["end"]-r["start"]
    # output tokens: prefer usage, fallback to estimate
    out_tok = r["usage"].get("completion_tokens") or r["ctokens"]
    in_tok  = r["usage"].get("prompt_tokens") or tokens_of(prompt)
    decode_tok = max(1, out_tok)
    print("="*70)
    print(f"IN~{in_tok} tok | OUT={out_tok} | TTFT={ttft:.2f}s | total={total:.2f}s")
    if ttft:
        print(f"avg_decode={decode_tok/(total-ttft):.2f} tok/s (decode-only)") 
    print(f"overall={out_tok/total:.2f} tok/s (incl prefill)")
    print("usage=", json.dumps(r["usage"]))
    print("sample_out="+r["text"][:120].replace("\n"," "))

if __name__=="__main__":
    # case 1: short prompt, short output
    report("Write one line: the capital of France and its population.", 64)
    # case 2: medium code prompt, medium output
    code="""Write a Python function `is_well_formed_code(code: str|None)->bool` that validates an internal literature ID: non-empty, exactly two parts split by '-', PREFIX is 2-5 UPPERCASE ascii letters, NUM is 3-8 decimal digits, total length <=40, no surrounding whitespace. Return True iff all hold. Show the full function only."""
    report(code, 320)