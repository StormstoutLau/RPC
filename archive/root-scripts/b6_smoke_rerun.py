#!/usr/bin/env python3
# b6_smoke_rerun.py — 重跑 c2/g1 (max_tokens 16384, 修复 reasoning 耗尽)
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
OUT = "/tmp/b6_smoke_qwen38flash_rerun.jsonl"
MODEL = "qwen3.8-flash-next"

QUESTIONS = [
    {"id": "dmx-c2", "type": "code", "max_tokens": 16384,
     "prompt": ("写一段可运行的 Python 函数 solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0):\n"
                "离散时间最优执行: 单资产, 二次暂时性影响成本 Gamma*sum(v_i^2*dt), 库存惩罚 lam*sum(x_i^2*dt),\n"
                "终期清仓约束 x_T = 0, v_i >= 0。返回交易速度序列 v(长度 N)。\n"
                "要求: (1)目标函数离散正确; (2)终期清仓边界被显式执行或约束; (3)不依赖外部求解器(仅 numpy)。\n"
                "只输出代码块, 不要解释。请高效作答, 思考尽量精简。")},
    {"id": "dmx-g1", "type": "rubric", "max_tokens": 16384,
     "prompt": ("概念题(<=10 行): Epstein-Zin 递归效用将跨期替代弹性(IES, psi)与风险厌恶(gamma)分离,\n"
                "而 CRRA 中两者互为倒数、被单一参数锁定。\n"
                "说明: (1)这一分离为何使 EZ 能对'长期增长风险'与'短期波动风险'定出不同的价格;\n"
                "(2)psi 与 gamma 取什么关系时 EZ 退化为 CRRA 等价定价。\n"
                "请高效作答, 思考尽量精简。")},
]

def call(q):
    body = {"model": MODEL, "messages": [{"role": "user", "content": q["prompt"]}],
            "temperature": 0, "max_tokens": q["max_tokens"], "stream": False}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.loads(r.read().decode())
    msg = d["choices"][0]["message"]
    return {"content": msg.get("content", ""), "reasoning": msg.get("reasoning_content", ""),
            "finish": d["choices"][0].get("finish_reason"), "dt": round(time.time()-t0, 1)}

with open(OUT, "w", encoding="utf-8") as f:
    for q in QUESTIONS:
        r = call(q)
        rec = {"id": q["id"], "type": q["type"], "content": r["content"], "finish": r["finish"], "elapsed_s": r["dt"]}
        print(f"[{q['id']}] {r['dt']}s finish={r['finish']} content_len={len(r['content'])}")
        f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
print("DONE ->", OUT)
