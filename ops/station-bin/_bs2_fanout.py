#!/usr/bin/env python3
# BS-2 L1 fan-out 探针: 编排层并发 HTTP 的客观判据 = 墙钟收敛 (3 并行 wall ≈ max ≪ 3 串行之和)
# 直连 B 站 llama-server:8080 (gpt-oss-120b-MXFP4)。若后端单 slot 则 3 并发被槽位串行化,
# wall_par ≈ wall_ser(和), 反证需跨站扇出; 若 wall_par ≈ max 则数据面真并行成立。
import json, time, urllib.request, urllib.error, threading
URL="http://127.0.0.1:8080/v1/chat/completions"
KEY="sk-unsloth-0895f5f165a09ae56b871dd52b074b94"
MODEL="gpt-oss-120b-MXFP4"
TOOLS=[{"type":"function","function":{"name":"tool_%s"%c,"description":"reply exactly %s-OK"%c.upper(),"parameters":{"type":"object","properties":{},"required":[]}}} for c in "abc"]
PROMPT=("Call all three tools tool_a, tool_b, tool_c in this SINGLE turn simultaneously. "
        "Emit all three function calls together in one message.")
def one(body):
    req=urllib.request.Request(URL,data=json.dumps(body).encode(),headers={
        "Content-Type":"application/json","Authorization":"Bearer "+KEY},method="POST")
    t0=time.time()
    try:
        with urllib.request.urlopen(req,timeout=600) as r:
            d=json.loads(r.read().decode())
        return r.status,time.time()-t0,d
    except urllib.error.HTTPError as e:
        return e.code,time.time()-t0,e.read().decode()[:150]
    except Exception as e:
        return -1,time.time()-t0,str(e)[:150]
def mkc():
    return {"model":MODEL,
            "messages":[{"role":"user","content":PROMPT}],
            "tools":TOOLS,"tool_choice":"auto","parallel_tool_calls":True}
# ---- 串行基线: 3 个单 tool 请求顺序发 (每请求 tool_choice 固定 tool_a/b/c? 不, 用同一 3-tool body 观察 tool_calls)
# 串行 = 同一请求发 3 次, 取均值; 代表"一个 sibling 一轮"的耗时
ser=[]
for i in range(3):
    s,dt,d=one(mkc()); tc=len(d["choices"][0]["message"].get("tool_calls") or []) if s==200 else None
    ser.append(dt); print(f"[ser#{i+1}] s={s} dt={dt:.1f}s tool_calls={tc}")
print(f"SERIAL: sum={sum(ser):.1f}s n={len(ser)}")
# ---- 编排层并行: 3 线程同时发同一请求
res=[None]*3; t0=time.time()
def w(i): res[i]=one(mkc())
ts=[threading.Thread(target=w,args=(i,)) for i in range(3)]
for t in ts: t.start()
for t in ts: t.join()
par_wall=time.time()-t0
print(f"PARALLEL: wall={par_wall:.1f}s")
for i,(s,dt,d) in enumerate(res):
    tc=len(d["choices"][0]["message"].get("tool_calls") or []) if s==200 else None
    print(f"  [par#{i+1}] s={s} dt={dt:.1f}s tool_calls={tc}")
print("="*40)
print(f"墙钟观察: ser_sum={sum(ser):.1f}s ser_avg={sum(ser)/len(ser):.1f}s par_wall={par_wall:.1f}s")
if par_wall < sum(ser)*0.7:
    print("判据: par_wall<<ser_sum -> 后端并发被部分接受, 数据面有并行度")
elif par_wall >= sum(ser)*0.8:
    print("判据: par_wall≈ser_sum -> 后端单 slot 串行化, 同站扇出不收敛; 支持跨站扇出方案")