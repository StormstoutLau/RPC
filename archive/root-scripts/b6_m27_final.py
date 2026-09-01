#!/usr/bin/env python3
# b6_m27_final.py — m27 终局: A3 nothink 2048 + C2 nothink 6144 (短预算 + 看门狗外置)
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
OUT = "/tmp/b6_smoke_m27_final.jsonl"
MODEL = "m27-q4ks"

A3 = ("Kendall 秩相关: 对椭圆 copula(含高斯与 t), Kendall tau = (2/pi)·arcsin(rho)。\n"
      "目标 tau0 = 0.5, 高斯与 t(nu=4) copula 各解 rho。\n"
      "最终行写: ANSWER: GAUSS_RHO=<数值>, T_RHO=<数值>, RELATION=<same|different>。直接给答案。")

C2 = ("写 Python 函数 solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0):\n"
      "二次影响 Gamma*sum(v_i^2*dt) + 库存惩罚 lam*sum(x_i^2*dt), 清仓 x_T=0, v>=0, 返回 v(长度 N)。\n"
      "仅 numpy。只输出代码块, 40 行内, 无解释。")

def call(prompt, mt, timeout=600):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": mt, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    msg = d["choices"][0]["message"]
    return {"content": msg.get("content", ""), "finish": d["choices"][0].get("finish_reason"),
            "dt": round(time.time()-t0, 1)}

with open(OUT, "w", encoding="utf-8") as f:
    for qid, prompt, mt in [("dmx-a3", A3, 2048), ("dmx-c2", C2, 6144)]:
        try:
            r = call(prompt, mt)
            print(f"[{qid}] {r['dt']}s finish={r['finish']} len={len(r['content'])}", flush=True)
            rec = {"id": qid, "content": r["content"], "finish": r["finish"], "elapsed_s": r["dt"], "no_think": True}
        except Exception as e:
            rec = {"id": qid, "error": str(e)}
            print(f"[{qid}] ERROR {e}", flush=True)
        f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
print("DONE ->", OUT)