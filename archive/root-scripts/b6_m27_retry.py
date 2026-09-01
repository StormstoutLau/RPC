#!/usr/bin/env python3
# b6_m27_retry.py — m27 补跑 a3 (16384+精简) + c2 (禁思考 16384)
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
OUT = "/tmp/b6_smoke_m27_retry.jsonl"
MODEL = "m27-q4ks"

A3 = ("Kendall 秩相关与线性相关: 对椭圆 copula(含高斯与 t), 总体 Kendall tau = (2/pi)·arcsin(rho)。\n"
      "给定目标 tau0 = 0.5, 分别为高斯 copula 和 t copula(自由度 nu=4) 解出所需的相关参数 rho。\n"
      "请在最终答案行写: GAUSS_RHO=<数值>, T_RHO=<数值>, RELATION=<same|different>。\n"
      "最终答案行必须以 'ANSWER:' 开头。请高效作答, 思考尽量精简。")

C2 = ("写一段可运行的 Python 函数 solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0):\n"
      "离散时间最优执行: 单资产, 二次暂时性影响成本 Gamma*sum(v_i^2*dt), 库存惩罚 lam*sum(x_i^2*dt),\n"
      "终期清仓约束 x_T = 0, v_i >= 0。返回交易速度序列 v(长度 N)。\n"
      "要求: (1)目标函数离散正确; (2)终期清仓边界被显式执行或约束; (3)不依赖外部求解器(仅 numpy)。\n"
      "只输出代码块, 不要解释。")

def call(prompt, mt, no_think=False):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": mt, "stream": False}
    if no_think:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=2400) as r:
        d = json.loads(r.read().decode())
    msg = d["choices"][0]["message"]
    return {"content": msg.get("content", ""), "finish": d["choices"][0].get("finish_reason"),
            "dt": round(time.time()-t0, 1)}

with open(OUT, "w", encoding="utf-8") as f:
    for qid, prompt, mt, nt in [("dmx-a3", A3, 16384, False), ("dmx-c2", C2, 16384, True)]:
        r = call(prompt, mt, no_think=nt)
        print(f"[{qid}] {'NOTHINK' if nt else 'THINK'} {r['dt']}s finish={r['finish']} len={len(r['content'])}")
        f.write(json.dumps({"id": qid, "content": r["content"], "finish": r["finish"],
                            "elapsed_s": r["dt"], "no_think": nt}, ensure_ascii=False) + "\n")
        f.flush()
print("DONE ->", OUT)
