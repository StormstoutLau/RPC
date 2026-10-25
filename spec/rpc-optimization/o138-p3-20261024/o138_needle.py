#!/usr/bin/env python3
# 长上下文检索探针：把标记埋在最前，再问它 —— 验证长 ctx 是否"能读进去"而不只是"能开"
import argparse, json, random, secrets, time, urllib.request

VOCAB = ["alpha","bravo","charlie","delta","echo","foxtrot","golf","hotel","india","juliet",
         "kilo","lima","mike","november","oscar","papa","quebec","romeo","sierra","tango",
         "uniform","victor","whiskey","xray","yankee","zulu","system","memory","network",
         "process","thread","buffer","kernel","driver","device","compute","graph","tensor",
         "matrix","vector","stream","packet","socket","server","client","request","response",
         "context","token","model","engine","cache","prompt","decode","prefill","latency"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", type=int, default=150000)
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1/chat/completions")
    ap.add_argument("--model", default="main")
    a = ap.parse_args()

    marker = "ZQX-" + secrets.token_hex(2).upper()
    rng = random.Random(20261025)
    # 经验值：~1 word ≈ 1.4 token ⇒ words ≈ tokens/1.45
    words = int(a.tokens / 1.45)
    body = " ".join(rng.choice(VOCAB) for _ in range(words))
    prompt = ("MEMO: the access code is %s.\n\n%s\n\nQuestion: what is the access code? "
              "Answer with just the code." % (marker, body))

    payload = {"model": a.model,
               "messages": [{"role": "user", "content": prompt}],
               "max_tokens": 32, "temperature": 0,
               "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(a.url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        resp = json.loads(r.read())
    wall = time.time() - t0
    t = resp.get("timings", {}) or {}
    ans = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    print("NEEDLE " + json.dumps({
        "marker_expect": marker,
        "answer": ans.strip()[:80],
        "hit": marker in ans,
        "prompt_n": t.get("prompt_n"),
        "prompt_tps": round(t.get("prompt_per_second") or 0, 1),
        "predicted_n": t.get("predicted_n"),
        "predicted_tps": round(t.get("predicted_per_second") or 0, 2),
        "wall_s": round(wall, 1),
        "drafter": (t.get("speculation") or {}).get("drafter"),
    }, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
