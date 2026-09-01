#!/bin/bash
# C2 沙箱验证 (deepseek-v4-flash) — 投影梯度法, 验证收敛/清仓/非负/耗时
set -u
mkdir -p /tmp/b6_c2_ds && cd /tmp/b6_c2_ds
timeout 600 python3 - <<'EOF'
import json, re, subprocess, sys, time

with open("/tmp/b6_smoke_deepseek.jsonl", encoding="utf-8") as f:
    recs = {json.loads(l)["id"]: json.loads(l) for l in f}
code = recs["dmx-c2"]["content"]
m = re.search(r"```python\n(.*?)```", code, re.S)
src = m.group(1) if m else code
open("c2.py", "w").write(src)

test = '''
import numpy as np, time
from c2 import solve_execution
t0 = time.time()
v = solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0)
el = time.time() - t0
v = np.asarray(v)
dt = 1.0/100
x = 100.0 - np.cumsum(v) * dt
print("elapsed_s:", round(el, 1))
print("len_v:", len(v))
print("sum_v_dt (应≈100):", round(float(np.sum(v)*dt), 4))
print("x_end (应≈0):", round(float(x[-1]), 6))
print("min_v (应>=0):", round(float(np.min(v)), 6))
print("cost:", round(float(np.sum(v**2)*dt + 0.1*np.sum(x**2)*dt), 4))
# 参照: TWAP 成本 (均匀 v=100)
v_tw = np.full(100, 100.0)
x_tw = 100.0 - np.cumsum(v_tw)*dt
print("twap_cost (参照):", round(float(np.sum(v_tw**2)*dt + 0.1*np.sum(x_tw**2)*dt), 4))
'''
open("test_c2.py", "w").write(test)
r = subprocess.run([sys.executable, "test_c2.py"], capture_output=True, text=True, timeout=590)
print(r.stdout)
print("STDERR:", r.stderr[-400:] if r.stderr else "(clean)")
print("rc:", r.returncode)
EOF
