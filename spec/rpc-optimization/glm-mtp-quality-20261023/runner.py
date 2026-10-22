#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GLM-5.3-Flash MTP on/off：质量 + 确定性探针（2026-10-23）。

题源 = spec/model-eval/questions/domain_matrix.md 的冒烟 5 题
（与 archive/root-scripts/b6_smoke_run.py 同题同口径：A3/B2 数值 + C2 代码 + A1/G1 rubric）。

设计要点：
  · 唯一变量 = conf 的 `--spec-type draft-mtp`；两臂使用同一 prompt、temp=0、seed=42。
  · 每臂跑两遍 ⇒ 可区分「MTP 引起的差异」与「同配置固有的非确定性」。
  · reasoning_content 与 content 分开保存；判分只看 content（与既有冒烟口径一致）。
  · 同时保存 timings，作为附带吞吐读数（不参与质量判定）。

用法（在 B 站运行，服务面 127.0.0.1:8080）：
    python3 runner.py --out mtp_on_r1.jsonl
    python3 runner.py --out mtp_on_r2.jsonl --ids dmx-a3,dmx-b2   # 单题调试
"""
import argparse
import json
import time
import urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
MODEL = "glm-5.3-flash"

QUESTIONS = [
    {
        "id": "dmx-a3", "type": "numeric", "max_tokens": 4096,
        "prompt": ("Kendall 秩相关与线性相关: 对椭圆 copula(含高斯与 t), 总体 Kendall tau = (2/pi)·arcsin(rho)。\n"
                   "给定目标 tau0 = 0.5, 分别为高斯 copula 和 t copula(自由度 nu=4) 解出所需的相关参数 rho。\n"
                   "请在最终答案行写: GAUSS_RHO=<数值>, T_RHO=<数值>, RELATION=<same|different>。\n"
                   "最终答案行必须以 'ANSWER:' 开头。"),
        "answer": {"gauss_rho": 0.7071, "t_rho": 0.7071, "relation": "same", "tolerance": 0.01},
    },
    {
        "id": "dmx-b2", "type": "numeric", "max_tokens": 4096,
        "prompt": ("Heston 模型短到期 ATM 隐含波动率偏斜的经典极限(T->0): d(sigma_imp)/dk|_ATM -> rho·sigma/4。\n"
                   "给定 rho = -0.7, sigma(vov) = 0.9, 计算该极限值(每单位 log-moneyness)。\n"
                   "并在一行内说明该斜率的符号由哪个参数决定。\n"
                   "最终答案行必须以 'ANSWER:' 开头, 格式: ANSWER: SLOPE=<数值>, SIGN_DRIVER=<参数名>。"),
        "answer": {"slope": -0.1575, "tolerance": 0.005},
    },
    {
        "id": "dmx-c2", "type": "code", "max_tokens": 8192,
        "prompt": ("写一段可运行的 Python 函数 solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0):\n"
                   "离散时间最优执行: 单资产, 二次暂时性影响成本 Gamma*sum(v_i^2*dt), 库存惩罚 lam*sum(x_i^2*dt),\n"
                   "终期清仓约束 x_T = 0, v_i >= 0。返回交易速度序列 v(长度 N)。\n"
                   "要求: (1)目标函数离散正确; (2)终期清仓边界被显式执行或约束; (3)不依赖外部求解器(仅 numpy)。\n"
                   "只输出代码块, 不要解释。"),
        "answer": {"rubric": ["目标离散含二次影响+库存项", "终期清仓 x_T=0 显式", "numpy-only 可运行"]},
    },
    {
        "id": "dmx-a1", "type": "rubric", "max_tokens": 4096,
        "prompt": ("概念题(分步作答, <=10 行): 设夹层保费 Phi_k(rho) 连续依赖相关参数 rho。\n"
                   "绝对灵敏度 = |Phi'(rho)|; 相对灵敏度 S = |d ln Phi / d rho| = |Phi'/Phi|。\n"
                   "第一步(本题只答这步): 构造一个具体例子说明 Phi'(rho*) 可以有限而 S(rho*) 任意大,\n"
                   "并指出这依赖什么机制(提示: 支付概率/期望趋小的夹层)。"),
        "answer": {"rubric": ["小分母机制(Phi->0 而导数有限)", "具体例子(senior 夹层/小支付)", "两者是独立事件"]},
    },
    {
        "id": "dmx-g1", "type": "rubric", "max_tokens": 4096,
        "prompt": ("概念题(<=10 行): Epstein-Zin 递归效用将跨期替代弹性(IES, psi)与风险厌恶(gamma)分离,\n"
                   "而 CRRA 中两者互为倒数、被单一参数锁定。\n"
                   "说明: (1)这一分离为何使 EZ 能对'长期增长风险'与'短期波动风险'定出不同的价格;\n"
                   "(2)psi 与 gamma 取什么关系时 EZ 退化为 CRRA 等价定价。"),
        "answer": {"rubric": ["IES 管跨期平滑/增长, gamma 管风险补偿", "psi*gamma=1(或 1/psi=gamma)时退化", "不是'折现率不同'层面的回答"]},
    },
]


def call(q, seed=42, max_tokens=None, no_think=False, effort=""):
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": q["prompt"]}],
        "temperature": 0,
        "seed": seed,
        "max_tokens": max_tokens or q["max_tokens"],
        "stream": False,
    }
    kw = {}
    if no_think:
        kw["enable_thinking"] = False
    if effort:
        # GLM chat_template 支持 reasoning_effort ∈ {low, high, max}（默认 max）。
        kw["reasoning_effort"] = effort
    if kw:
        body["chat_template_kwargs"] = kw
    req = urllib.request.Request(
        API, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    msg = d["choices"][0]["message"]
    return {
        "content": msg.get("content", ""),
        "reasoning": msg.get("reasoning_content", ""),
        "usage": d.get("usage", {}),
        "timings": d.get("timings", {}),
        "elapsed_s": round(dt, 3),
        "finish": d["choices"][0].get("finish_reason"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--ids", default="", help="逗号分隔的题号；空 = 全部")
    ap.add_argument("--max", type=int, default=0, help="覆盖 max_tokens（调试用）")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-think", action="store_true",
                    help="尝试关闭思考（GLM 模板可能忽略；先小样本验证）")
    ap.add_argument("--effort", choices=["low", "high", "max"], default="",
                    help="GLM reasoning_effort（默认 max；本实验用 low 控制预算）")
    args = ap.parse_args()

    wanted = set(x.strip() for x in args.ids.split(",") if x.strip())
    qs = [q for q in QUESTIONS if not wanted or q["id"] in wanted]
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for q in qs:
            rec = {"id": q["id"], "type": q["type"], "seed": args.seed,
                   "answer_ref": q["answer"]}
            try:
                r = call(q, seed=args.seed, max_tokens=args.max or None,
                         no_think=args.no_think, effort=args.effort)
                rec.update(r)
                print(f"[{q['id']}] ok {r['elapsed_s']}s finish={r['finish']} "
                      f"content={len(r['content'])} reasoning={len(r['reasoning'])} "
                      f"tps={(r['timings'] or {}).get('predicted_per_second')}", flush=True)
            except Exception as e:  # noqa: BLE001 — 探针需保留失败样本而非中断
                rec["error"] = str(e)
                print(f"[{q['id']}] ERROR: {e}", flush=True)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    print("DONE ->", args.out)


if __name__ == "__main__":
    main()
