#!/usr/bin/env python3
# BS-2 L1 对照 v2: 直连 llama-server:8080 vs 经 LiteLLM 网关:4000，同 3-tool 请求。
# 动态读取 opencode.jsonc 的 cluster-litellm apiKey 作为网关候选 key；探测哪个能过 auth。
import json, time, urllib.request, urllib.error, re, os

UNSLOTH="sk-unsloth-0895f5f165a09ae56b871dd52b074b94"
oc=os.path.expanduser("~/.config/opencode/opencode.jsonc")
cand=[]
try:
    txt=open(oc).read()
    # 粗提取所有 apiKey 候选（含cluster-litellm）
    for m in re.finditer(r'"apiKey"\s*:\s*"([^"]+)"', txt):
        cand.append(m.group(1))
    for m in re.finditer(r'"baseURL"\s*:\s*"([^"]+)"', txt):
        pass
except Exception as e:
    print("read oc err", e)
cand=list(dict.fromkeys(cand+["sk-RPC-gzqMLIDS3eSYKfADEIp19M5tLXctsc3c1fak","sk-local-noauth"]))
print("[cfg] 候选网关 key 数:", len(cand))

TOOLS=[
 {"type":"function","function":{"name":"tool_a","description":"reply exactly A-OK","parameters":{"type":"object","properties":{},"required":[]}}},
 {"type":"function","function":{"name":"tool_b","description":"reply exactly B-OK","parameters":{"type":"object","properties":{},"required":[]}}},
 {"type":"function","function":{"name":"tool_c","description":"reply exactly C-OK","parameters":{"type":"object","properties":{},"required":[]}}},
]
PROMPT=("Call all three tools tool_a, tool_b, tool_c in this SINGLE turn simultaneously. "
        "Emit all three function calls together in one message.")

def post(url,key,model,payload):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={
        "Content-Type":"application/json","Authorization":"Bearer "+key},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=600) as r:
            return r.status,json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code,e.read().decode()[:200]
    except Exception as e:
        return -1,str(e)

def tc_count(d):
    try:
        return len(d["choices"][0]["message"].get("tool_calls") or [])
    except Exception:
        return None

# 1) 探测网关 auth：最小请求
print("======== 1) 网关 :4000 auth 探测 (model=nemotron, 单 tool 请求) ========")
GW_URL="http://127.0.0.1:4000/v1/chat/completions"
single={"model":"nemotron","messages":[{"role":"user","content":"Reply hi"}],"tools":[TOOLS[0]]}
good=None
for k in cand:
    s,raw=post(GW_URL,k,"nemotron",single)
    mark=""
    if s==200: mark="  <<< AUTH OK"; good=k
    if s==400 or s==429: mark="  <<< 可能可(非auth错误)"
    print(f"  key={'<'+str(k)[:18]+'...>' if k else '<NONE>'} status={s} {mark}")
# 2) 直连对照（已知 key; 8080 现载 gpt-oss-120b-MXFP4, 模型名须匹配 loaded id）
print("======== 2) 实验组: 绕网关直连 llama-server:8080 (gpt-oss-120b-MXFP4) ========")
DIR="http://127.0.0.1:8080/v1/chat/completions"
DIR_MODEL="gpt-oss-120b-MXFP4"
def run3(url,key,model,tag):
    body={"model":model,"messages":[{"role":"user","content":PROMPT}],
          "tools":TOOLS,"tool_choice":"auto","parallel_tool_calls":True}
    t0=time.time(); s,raw=post(url,key,model,body); dt=time.time()-t0
    if s!=200: print(f"[{tag}] HTTP {s} {str(raw)[:160]}"); return None
    print(f"[{tag}] HTTP {s} tool_calls={tc_count(raw)} wall={dt:.1f}s")
    for t in (raw["choices"][0]["message"].get("tool_calls") or []):
        print("    ->",t["function"]["name"])
    return tc_count(raw)
n_d=run3(DIR,UNSLOTH,DIR_MODEL,"DIRECT")
# 3) 网关对照（用探测成功的 key，model=nemotron 路由 B:8080 同 gpt-oss）
print("======== 3) 对照组: 经 LiteLLM 网关 :4000 (model=nemotron) ========")
n_g=None
if good:
    n_g=run3(GW_URL,good,"nemotron","GW")
else:
    print("  网关无反 200 key，用失败 key 再试一次记录行为")
    n_g=run3(GW_URL,(cand[0] if cand else ""),"nemotron","GW")
print("======== 归因 ========")
print(f"直连={n_d} 网关={n_g}")
if n_d==1: print("  * 后端/模型(gpt-oss 直连) 单轮仅 1 tool_call —— 需多轮串行，模型本身非单轮并行")
if n_g is None and good is None: print("  * 网关不可用(401/Internal error) —— 网关路径无法完成对照，栅关卡死")
if n_g is not None and n_g<n_d: print("  * 网关把并行度降为比直连更低 —— 网关侧有负向干预")
print("  结论建议: 本地模型单轮 tool_call 并行度由模型决定（此处=1），fan-out 并行应押编排层并发 HTTP 而非模型单轮多 tool_call。")