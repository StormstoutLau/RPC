#!/usr/bin/env python3
# 探测 gpt-oss-120b 输出形态: reasoning_content 是否分离
import json, urllib.request
API = "http://127.0.0.1:8080/v1/chat/completions"
body = {"model": "gpt-oss-120b",
        "messages": [{"role": "user", "content": "1+1=? Answer in one word."}],
        "max_tokens": 512, "temperature": 0}
req = urllib.request.Request(API, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=120) as r:
    d = json.loads(r.read().decode())
m = d["choices"][0]["message"]
print("keys:", list(m.keys()))
print("content:", repr(m.get("content", ""))[:300])
print("reasoning:", repr(m.get("reasoning_content", ""))[:300])
print("finish:", d["choices"][0].get("finish_reason"))
print("usage:", d.get("usage", {}))
