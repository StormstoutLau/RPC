#!/usr/bin/env python3
# b6_smoke_run.py — B6 冒烟首测运行器 (qwen3.8-flash-next @ :8080)
# 题源: spec/model-eval/questions/domain_matrix.md v1.1 组装指南 (A3.1/B2.1/C2 + A1.1/G1 首步)
# DESIGN 约定: temperature=0, JSONL 逐题落盘, reasoning_content 分离不参与判分
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
OUT = "/tmp/b6_smoke_qwen38flash.jsonl"
MODEL = "qwen3.8-flash-next"

QUESTIONS = [
    {
        "id": "dmx-a3", "type": "numeric", "max_tokens": 2048,
        "prompt": ("Kendall 秩相关与线性相关: 对椭圆 copula(含高斯与 t), 总体 Kendall tau = (2/pi)·arcsin(rho)。\n"
                   "给定目标 tau0 = 0.5, 分别为高斯 copula 和 t copula(自由度 nu=4) 解出所需的相关参数 rho。\n"
                   "请在最终答案行写: GAUSS_RHO=<数值>, T_RHO=<数值>, RELATION=<same|different>。\n"
                   "最终答案行必须以 'ANSWER:' 开头。"),
        "answer": {"gauss_rho": 0.7071, "t_rho": 0.7071, "relation": "same", "tolerance": 0.01},
    },
    {
        "id": "dmx-b2", "type": "numeric", "max_tokens": 2048,
        "prompt": ("Heston 模型短到期 ATM 隐含波动率偏斜的经典极限(T->0): d(sigma_imp)/dk|_ATM -> rho·sigma/4。\n"
                   "给定 rho = -0.7, sigma(vov) = 0.9, 计算该极限值(每单位 log-moneyness)。\n"
                   "并在一行内说明该斜率的符号由哪个参数决定。\n"
                   "最终答案行必须以 'ANSWER:' 开头, 格式: ANSWER: SLOPE=<数值>, SIGN_DRIVER=<参数名>。"),
        "answer": {"slope": -0.1575, "tolerance": 0.005},
    },
    {
        "id": "dmx-c2", "type": "code", "max_tokens": 4096,
        "prompt": ("写一段可运行的 Python 函数 solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0):\n"
                   "离散时间最优执行: 单资产, 二次暂时性影响成本 Gamma*sum(v_i^2*dt), 库存惩罚 lam*sum(x_i^2*dt),\n"
                   "终期清仓约束 x_T = 0, v_i >= 0。返回交易速度序列 v(长度 N)。\n"
                   "要求: (1)目标函数离散正确; (2)终期清仓边界被显式执行或约束; (3)不依赖外部求解器(仅 numpy)。\n"
                   "只输出代码块, 不要解释。"),
        "answer": {"rubric": ["目标离散含二次影响+库存项", "终期清仓 x_T=0 显式", "numpy-only 可运行"]},
    },
    {
        "id": "dmx-a1", "type": "rubric", "max_tokens": 3072,
        "prompt": ("概念题(分步作答, <=10 行): 设夹层保费 Phi_k(rho) 连续依赖相关参数 rho。\n"
                   "绝对灵敏度 = |Phi'(rho)|; 相对灵敏度 S = |d ln Phi / d rho| = |Phi'/Phi|。\n"
                   "第一步(本题只答这步): 构造一个具体例子说明 Phi'(rho*) 可以有限而 S(rho*) 任意大,\n"
                   "并指出这依赖什么机制(提示: 支付概率/期望趋小的夹层)。"),
        "answer": {"rubric": ["小分母机制(Phi->0 而导数有限)", "具体例子(senior 夹层/小支付)", "两者是独立事件"]},
    },
    {
        "id": "dmx-g1", "type": "rubric", "max_tokens": 3072,
        "prompt": ("概念题(<=10 行): Epstein-Zin 递归效用将跨期替代弹性(IES, psi)与风险厌恶(gamma)分离,\n"
                   "而 CRRA 中两者互为倒数、被单一参数锁定。\n"
                   "说明: (1)这一分离为何使 EZ 能对'长期增长风险'与'短期波动风险'定出不同的价格;\n"
                   "(2)psi 与 gamma 取什么关系时 EZ 退化为 CRRA 等价定价。"),
        "answer": {"rubric": ["IES 管跨期平滑/增长, gamma 管风险补偿", "psi*gamma=1(或 1/psi=gamma)时退化", "不是'折现率不同'层面的回答"]},
    },
]

def call(q):
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": q["prompt"]}],
        "temperature": 0,
        "max_tokens": q["max_tokens"],
        "stream": False,
    }
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode())
    dt = time.time() - t0
    msg = d["choices"][0]["message"]
    return {"content": msg.get("content", ""),
            "reasoning": msg.get("reasoning_content", ""),
            "usage": d.get("usage", {}), "elapsed_s": round(dt, 1),
            "finish": d["choices"][0].get("finish_reason")}

with open(OUT, "w", encoding="utf-8") as f:
    for q in QUESTIONS:
        try:
            r = call(q)
            rec = {"id": q["id"], "type": q["type"], "answer_ref": q["answer"],
                   "content": r["content"], "usage": r["usage"],
                   "elapsed_s": r["elapsed_s"], "finish": r["finish"]}
            print(f"[{q['id']}] ok {r['elapsed_s']}s finish={r['finish']} "
                  f"content_len={len(r['content'])} reasoning_len={len(r['reasoning'])}")
        except Exception as e:
            rec = {"id": q["id"], "type": q["type"], "error": str(e)}
            print(f"[{q['id']}] ERROR: {e}")
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
print("DONE ->", OUT)
