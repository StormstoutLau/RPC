#!/usr/bin/env python3
# _ctx_overflow_probe.py — O-21 决定性"错误消失"对照（服务端侧）
# 直接向引擎 port POST 一个明确 >旧64k 上限的请求（量取 65k<size<131k 区间），
# 旧引擎( -c 65536 )会 400 "exceeds the available context size (65536)"；
# 新引擎( -c 131072 )应 200。用 requests 避免手写 HTTP。
import sys, json, urllib.request, urllib.error

port = sys.argv[1]
nwords = int(sys.argv[2]) if len(sys.argv) > 2 else 50000  # 每词约1-2 token
text = ("lorem " * nwords).strip()

body = json.dumps({
    "model": "gpt-oss-120b-MXFP4",
    "messages": [{"role": "user", "content": text}],
    "max_tokens": 1,        # 只看到达服务端即止，输出压到最小
}).encode("utf-8")

req = urllib.request.Request(
    "http://127.0.0.1:%s/v1/chat/completions" % port,
    data=body,
    headers={"Content-Type": "application/json"},
)
print("POST %s words(len=%d chars) -> n_ctx 探测" % (nwords, len(text)), flush=True)
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        raw = r.read().decode("utf-8", "replace")
        print("HTTP %s  <- 接受 (200)" % r.status, flush=True)
        try:
            j = json.loads(raw)
            u = j.get("usage", {})
            pt = u.get("prompt_tokens")
            print("prompt_tokens = %s" % pt, flush=True)
            if pt is not None and int(pt) > 65536:
                print("RESULT_CONFIRM_GT64K prompt_tokens=%s" % pt, flush=True)
            else:
                print("RESULT_ACCEPT", flush=True)
        except Exception as e:
            print("parse use err:", e, flush=True)
            print("RESULT_ACCEPT", flush=True)
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8", "replace")
    print("HTTP %s <- 拒绝" % e.code, flush=True)
    print("BODY: %s" % err[:300], flush=True)
    if "65536" in err:
        print("RESULT_HIT_65536", flush=True)
    elif "131072" in err or "available context" in err:
        print("RESULT_HIT_NEWLIMIT", flush=True)
    else:
        print("RESULT_OTHER", flush=True)