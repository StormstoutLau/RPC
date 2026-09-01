#!/bin/bash
# b6_m27_retry2.sh — 受控重跑 m27 A3/C2 (看门狗: A 失联即中止)
pkill -f 'b6_m27_retry[.]py' 2>/dev/null; sleep 1
echo "=== 旧进程清理完毕, A 站存活基线 ==="
ping -c 2 -W 2 10.10.10.1 | tail -1

cat > /tmp/b6_m27_retry2.py <<'PYEOF'
#!/usr/bin/env python3
# b6_m27_retry2.py — m27 A3(16384 think) + C2(12288 nothink), 单题 900s 超时
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
OUT = "/tmp/b6_smoke_m27_retry2.jsonl"
MODEL = "m27-q4ks"

A3 = ("Kendall 秩相关与线性相关: 对椭圆 copula(含高斯与 t), 总体 Kendall tau = (2/pi)·arcsin(rho)。\n"
      "给定目标 tau0 = 0.5, 分别为高斯 copula 和 t copula(自由度 nu=4) 解出所需的相关参数 rho。\n"
      "请在最终答案行写: GAUSS_RHO=<数值>, T_RHO=<数值>, RELATION=<same|different>。\n"
      "最终答案行必须以 'ANSWER:' 开头。请高效作答, 思考尽量精简。")

C2 = ("写一段可运行的 Python 函数 solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0):\n"
      "离散时间最优执行: 单资产, 二次暂时性影响成本 Gamma*sum(v_i^2*dt), 库存惩罚 lam*sum(x_i^2*dt),\n"
      "终期清仓约束 x_T = 0, v_i >= 0。返回交易速度序列 v(长度 N)。\n"
      "要求: (1)目标函数离散正确; (2)终期清仓边界被显式执行或约束; (3)不依赖外部求解器(仅 numpy)。\n"
      "只输出代码块, 不要解释。代码务必精简, 不超过 60 行。")

def call(prompt, mt, no_think=False, timeout=900):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0, "max_tokens": mt, "stream": False}
    if no_think:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    msg = d["choices"][0]["message"]
    return {"content": msg.get("content", ""), "finish": d["choices"][0].get("finish_reason"),
            "dt": round(time.time()-t0, 1)}

with open(OUT, "w", encoding="utf-8") as f:
    for qid, prompt, mt, nt in [("dmx-a3", A3, 16384, False), ("dmx-c2", C2, 12288, True)]:
        try:
            r = call(prompt, mt, no_think=nt)
            print(f"[{qid}] {'NOTHINK' if nt else 'THINK'} {r['dt']}s finish={r['finish']} len={len(r['content'])}", flush=True)
            rec = {"id": qid, "content": r["content"], "finish": r["finish"], "elapsed_s": r["dt"], "no_think": nt}
        except Exception as e:
            rec = {"id": qid, "error": str(e)}
            print(f"[{qid}] ERROR {e}", flush=True)
        f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
print("DONE ->", OUT)
PYEOF

# 看门狗: 后台每 20s ping A, 连续 3 失败 → 杀测试进程 + 警报标记
cat > /tmp/b6_watchdog.sh <<'WDEOF'
#!/bin/bash
FAIL=0
while true; do
  if ! ping -c 1 -W 2 10.10.10.1 >/dev/null 2>&1; then
    FAIL=$((FAIL+1))
    echo "$(date '+%H:%M:%S') A_UNREACHABLE fail=$FAIL" >> /tmp/b6_watchdog.log
    if [ $FAIL -ge 3 ]; then
      echo "$(date '+%H:%M:%S') WATCHDOG_ABORT killing test" >> /tmp/b6_watchdog.log
      pkill -f 'b6_m27_retry2[.]py'
      exit 9
    fi
  else
    FAIL=0
  fi
  sleep 20
done
WDEOF

bash /tmp/b6_watchdog.sh &
WD=$!
echo "watchdog pid=$WD"
python3 /tmp/b6_m27_retry2.py
RC=$?
kill $WD 2>/dev/null
echo "=== 测试结束 rc=$RC, watchdog 日志: ==="
cat /tmp/b6_watchdog.log 2>/dev/null || echo "(无失联记录)"