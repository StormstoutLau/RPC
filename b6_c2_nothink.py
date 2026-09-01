#!/usr/bin/env python3
# b6_c2_nothink.py — C2 禁思考重跑 (chat_template_kwargs enable_thinking=False)
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
OUT = "/tmp/b6_c2_nothink.jsonl"
PROMPT = ("写一段可运行的 Python 函数 solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0):\n"
          "离散时间最优执行: 单资产, 二次暂时性影响成本 Gamma*sum(v_i^2*dt), 库存惩罚 lam*sum(x_i^2*dt),\n"
          "终期清仓约束 x_T = 0, v_i >= 0。返回交易速度序列 v(长度 N)。\n"
          "要求: (1)目标函数离散正确; (2)终期清仓边界被显式执行或约束; (3)不依赖外部求解器(仅 numpy)。\n"
          "只输出代码块, 不要解释。")

body = {
    "model": "qwen3.8-flash-next",
    "messages": [{"role": "user", "content": PROMPT}],
    "temperature": 0, "max_tokens": 6144, "stream": False,
    "chat_template_kwargs": {"enable_thinking": False},
}
req = urllib.request.Request(API, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=900) as r:
    d = json.loads(r.read().decode())
msg = d["choices"][0]["message"]
rec = {"id": "dmx-c2-nothink", "content": msg.get("content", ""),
       "reasoning_len": len(msg.get("reasoning_content", "")),
       "finish": d["choices"][0].get("finish_reason"), "elapsed_s": round(time.time()-t0, 1)}
print(f"[c2-nothink] {rec['elapsed_s']}s finish={rec['finish']} content_len={len(rec['content'])} reasoning_len={rec['reasoning_len']}")
with open(OUT, "w") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print("DONE ->", OUT)
