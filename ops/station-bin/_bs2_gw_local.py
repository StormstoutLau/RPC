#!/usr/bin/env python3
# 主控→B:4000 网关探测：sk-unsloth 打 multi-tool 请求，拿 400/200 完整 body（判定剥字段）
import json, urllib.request, urllib.error
GW="http://192.168.1.15:4000/v1/chat/completions"
keys=["sk-unsloth-0895f5f165a09ae56b871dd52b074b94","sk-local-noauth"]
T= {"type":"function","function":{"name":"tool_a","description":"reply A-OK","parameters":{"type":"object","properties":{},"required":[]}}}
T2={"type":"function","function":{"name":"tool_b","description":"reply B-OK","parameters":{"type":"object","properties":{},"required":[]}}}
def post(k,body,timeout=40):
    req=urllib.request.Request(GW,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+k},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return r.status,r.read().decode()[:800]
    except urllib.error.HTTPError as e: return e.code,e.read().decode()[:800]
    except Exception as e: return -1,str(e)[:200]
for k in keys:
    print("### key",k[:20])
    print("  1tool   :",post(k,{"model":"nemotron","messages":[{"role":"user","content":"Reply hi"}],"tools":[T]}))
    print("  2tools  :",post(k,{"model":"nemotron","messages":[{"role":"user","content":"Call tool_a and tool_b now"}],"tools":[T,T2],"parallel_tool_calls":True}))
    print("  no-tool :",post(k,{"model":"nemotron","messages":[{"role":"user","content":"Reply hi"}]}))
print("done")