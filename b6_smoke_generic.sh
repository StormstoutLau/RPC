#!/bin/bash
# b6_smoke_generic.sh — B6 通用冒烟 (参数: $1=model alias, $2=输出后缀, $3=是否RPC需看门狗 1/0)
set -u
ALIAS="${1:?用法: b6_smoke_generic.sh <alias> <suffix> <rpc_flag>}"
SUFFIX="${2:?}"
RPCF="${3:-1}"
exec 2>&1

echo "=== 通用冒烟: $ALIAS -> b6_smoke_$SUFFIX.jsonl (rpc_watchdog=$RPCF) ==="

cat > /tmp/b6_gen_$SUFFIX.py <<PYEOF
#!/usr/bin/env python3
# B6 冒烟 (同套件同参数, DESIGN v1.1 决策 6 分型规则)
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
OUT = "/tmp/b6_smoke_$SUFFIX.jsonl"
MODEL = "$ALIAS"

Q_NUMERIC = [
    {"id": "dmx-a3", "max_tokens": 2048, "think": True,
     "prompt": ("Kendall 秩相关与线性相关: 对椭圆 copula(含高斯与 t), 总体 Kendall tau = (2/pi)·arcsin(rho)。\n"
                "给定目标 tau0 = 0.5, 分别为高斯 copula 和 t copula(自由度 nu=4) 解出所需的相关参数 rho。\n"
                "请在最终答案行写: GAUSS_RHO=<数值>, T_RHO=<数值>, RELATION=<same|different>。\n"
                "最终答案行必须以 'ANSWER:' 开头。请高效作答。")},
    {"id": "dmx-b2", "max_tokens": 2048, "think": True,
     "prompt": ("Heston 模型短到期 ATM 隐含波动率偏斜的经典极限(T->0): d(sigma_imp)/dk|_ATM -> rho·sigma/4。\n"
                "给定 rho = -0.7, sigma(vov) = 0.9, 计算该极限值(每单位 log-moneyness)。\n"
                "并在一行内说明该斜率的符号由哪个参数决定。\n"
                "最终答案行必须以 'ANSWER:' 开头, 格式: ANSWER: SLOPE=<数值>, SIGN_DRIVER=<参数名>。请高效作答。")},
]
Q_RUBRIC = [
    {"id": "dmx-a1", "max_tokens": 16384,
     "prompt": ("概念题(分步作答, <=10 行): 设夹层保费 Phi_k(rho) 连续依赖相关参数 rho。\n"
                "绝对灵敏度 = |Phi'(rho)|; 相对灵敏度 S = |d ln Phi / d rho| = |Phi'/Phi|。\n"
                "第一步(本题只答这步): 构造一个具体例子说明 Phi'(rho*) 可以有限而 S(rho*) 任意大,\n"
                "并指出这依赖什么机制(提示: 支付概率/期望趋小的夹层)。请高效作答, 思考尽量精简。")},
    {"id": "dmx-g1", "max_tokens": 16384,
     "prompt": ("概念题(<=10 行): Epstein-Zin 递归效用将跨期替代弹性(IES, psi)与风险厌恶(gamma)分离,\n"
                "而 CRRA 中两者互为倒数、被单一参数锁定。\n"
                "说明: (1)这一分离为何使 EZ 能对'长期增长风险'与'短期波动风险'定出不同的价格;\n"
                "(2)psi 与 gamma 取什么关系时 EZ 退化为 CRRA 等价定价。\n"
                "请高效作答, 思考尽量精简。")},
]
Q_CODE = [
    {"id": "dmx-c2", "max_tokens": 6144,
     "prompt": ("写一段可运行的 Python 函数 solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0):\n"
                "离散时间最优执行: 单资产, 二次暂时性影响成本 Gamma*sum(v_i^2*dt), 库存惩罚 lam*sum(x_i^2*dt),\n"
                "终期清仓约束 x_T = 0, v_i >= 0。返回交易速度序列 v(长度 N)。\n"
                "要求: (1)目标函数离散正确; (2)终期清仓边界被显式执行或约束; (3)不依赖外部求解器(仅 numpy)。\n"
                "只输出代码块, 不要解释。")},
]

def call(q, no_think=False):
    body = {"model": MODEL, "messages": [{"role": "user", "content": q["prompt"]}],
            "temperature": 0, "max_tokens": q["max_tokens"], "stream": False}
    if no_think:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        d = json.loads(r.read().decode())
    msg = d["choices"][0]["message"]
    return {"content": msg.get("content", ""), "reasoning": msg.get("reasoning_content") or "",
            "finish": d["choices"][0].get("finish_reason"),
            "dt": round(time.time()-t0, 1), "usage": d.get("usage", {})}

TASKS = [(q, False) for q in Q_NUMERIC] + [(q, False) for q in Q_RUBRIC] + [(q, True) for q in Q_CODE]
with open(OUT, "w", encoding="utf-8") as f:
    for q, nt in TASKS:
        try:
            r = call(q, no_think=nt)
            print(f"[{q['id']}] {'NOTHINK' if nt else 'THINK'} {r['dt']}s finish={r['finish']} "
                  f"len={len(r['content'])} reasoning_len={len(r['reasoning'])}", flush=True)
            rec = {"id": q["id"], "content": r["content"], "reasoning": r["reasoning"][:2000],
                   "finish": r["finish"], "elapsed_s": r["dt"], "no_think": nt,
                   "usage": r.get("usage")}
        except Exception as e:
            rec = {"id": q["id"], "error": str(e)}; print(f"[{q['id']}] ERROR {e}", flush=True)
        f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
print("DONE ->", OUT)
PYEOF

# 看门狗 (RPC 模型 A 站满载才需要)
WD=0
if [ "$RPCF" = "1" ]; then
  cat > /tmp/b6_gen_wd_$SUFFIX.sh <<WDEOF
#!/bin/bash
FAIL=0
while true; do
  if ! ping -c 1 -W 2 10.10.10.1 >/dev/null 2>&1; then
    FAIL=\$((FAIL+1))
    echo "\$(date '+%H:%M:%S') A_UNREACHABLE fail=\$FAIL" >> /tmp/b6_gen_wd_$SUFFIX.log
    if [ \$FAIL -ge 3 ]; then
      echo "\$(date '+%H:%M:%S') WATCHDOG_ABORT" >> /tmp/b6_gen_wd_$SUFFIX.log
      pkill -f 'b6_gen_$SUFFIX[.]py'
      exit 9
    fi
  else
    FAIL=0
  fi
  sleep 20
done
WDEOF
  bash /tmp/b6_gen_wd_$SUFFIX.sh &
  WD=$!
  echo "watchdog pid=$WD"
fi

python3 /tmp/b6_gen_$SUFFIX.py
RC=$?
[ $WD -ne 0 ] && kill $WD 2>/dev/null
echo "=== 测试结束 rc=$RC ==="
[ "$RPCF" = "1" ] && { cat /tmp/b6_gen_wd_$SUFFIX.log 2>/dev/null || echo "(无失联记录)"; }
touch /tmp/b6_gen_${SUFFIX}_done
