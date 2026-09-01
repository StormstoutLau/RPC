#!/bin/bash
# kfd_stress_test.sh — KFD 压力复测: 精确重演事故条件 (m27 + 16384 think)
# 验收目标: A 站 6.17.0-40 下长生成压力不再触发 KFD workqueue 饿死
# 监控: ① 看门狗 (A 失联止损) ② B 站 kernel log (hogged 警告追踪 — 事故签名)

# 生成一段要求长思考的 prompt (复刻事故: dmx-a3 数值题 16384 think)
cat > /tmp/kfd_stress.py <<'PYEOF'
#!/usr/bin/env python3
import json, time, urllib.request

API = "http://127.0.0.1:8080/v1/chat/completions"
OUT = "/tmp/kfd_stress_result.jsonl"

PROMPT = ("请详细推导: 对椭圆 copula, Kendall tau = (2/pi)·arcsin(rho) 的关系式如何从 concordance 概率导出。"
          "给出完整推导步骤, 包括 concordance 概率 P(X_i>u, X_j>v) 在二元高斯下的表达式、"
          "正态积分的对称性化简、以及最终 arcsin 形式的得出过程。每一步都要写出中间量。")

# 三连发: 持续 ~15min 生成压力 (复刻事故时长)
for i in range(1, 4):
    body = {"model": "m27-q4ks", "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0, "max_tokens": 16384, "stream": False}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=1200) as r:
            d = json.loads(r.read().decode())
        msg = d["choices"][0]["message"]
        rec = {"run": i, "elapsed_s": round(time.time()-t0,1),
               "finish": d["choices"][0].get("finish_reason"),
               "content_len": len(msg.get("content",""))}
    except Exception as e:
        rec = {"run": i, "error": str(e), "elapsed_s": round(time.time()-t0,1)}
    print(f"[run {i}] {rec}", flush=True)
    with open(OUT, "a") as f:
        f.write(json.dumps(rec) + "\n")
print("STRESS_DONE")
PYEOF

# 看门狗 (同事故防护规格)
cat > /tmp/kfd_watchdog.sh <<'WDEOF'
#!/bin/bash
FAIL=0
while true; do
  if ! ping -c 1 -W 2 10.10.10.1 >/dev/null 2>&1; then
    FAIL=$((FAIL+1))
    echo "$(date '+%H:%M:%S') A_UNREACHABLE fail=$FAIL" >> /tmp/kfd_watchdog.log
    if [ $FAIL -ge 3 ]; then
      echo "$(date '+%H:%M:%S') WATCHDOG_ABORT" >> /tmp/kfd_watchdog.log
      pkill -f 'kfd_stress[.]py'
      exit 9
    fi
  else
    FAIL=0
  fi
  sleep 20
done
WDEOF

rm -f /tmp/kfd_watchdog.log /tmp/kfd_stress_result.jsonl
T0=$(date '+%H:%M:%S')
echo "=== 压测开始 $T0 (3×16384 tokens think 生成) ==="
bash /tmp/kfd_watchdog.sh & WD=$!
python3 /tmp/kfd_stress.py
RC=$?
kill $WD 2>/dev/null

echo "=== 压测结束 rc=$RC ==="
echo "--- 看门狗日志 (A 失联记录): ---"
cat /tmp/kfd_watchdog.log 2>/dev/null || echo "(零失联 ✓)"
echo "--- B 站 kernel log 压测期间 hogged/挂死签名: ---"
sudo dmesg -T | awk -v t="$T0" 'BEGIN{found=0} /00:57|workqueue.*hogged|kfd|amdkfd/{print}' | tail -5
journalctl -k --since "$T0" --no-pager 2>/dev/null | grep -iE "hogged|kfd|amdkfd|hang|reset" | tail -8 || echo "(压测期间零 KFD 警告 ✓)"
echo "--- A 站存活终态: ---"
ping -c 2 -W 2 10.10.10.1 | tail -1