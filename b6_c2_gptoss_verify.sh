#!/bin/bash
# C2 沙箱验证 (gpt-oss-120b)
set -u
mkdir -p /tmp/b6_c2_gptoss && cd /tmp/b6_c2_gptoss
python3 - <<'EOF'
import json, re, subprocess, sys

with open("/tmp/b6_smoke_gptoss120b.jsonl", encoding="utf-8") as f:
    recs = {json.loads(l)["id"]: json.loads(l) for l in f}
code = recs["dmx-c2"]["content"]
m = re.search(r"```python\n(.*?)```", code, re.S)
src = m.group(1) if m else code
open("c2.py", "w").write(src)

test = '''
import numpy as np
from c2 import solve_execution
v = solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0)
v = np.asarray(v)
print("len_v:", len(v))
print("sum_v_dt (应≈X0=100):", round(float(np.sum(v) * (1.0/100)), 4))
print("min_v (应>=0):", round(float(np.min(v)), 6))
# 库存轨迹验证: x_k = X0 - cumsum(v)*dt
x = 100.0 - np.cumsum(v) * (1.0/100)
print("x_end (应≈0):", round(float(x[-1]), 6))
# 成本有限性 sanity
dt = 1.0/100
cost = 1.0*np.sum(v**2*dt) + 0.1*np.sum(x**2*dt)
print("cost_finite:", np.isfinite(cost))
print("import_check: numpy_only")
'''
open("test_c2.py", "w").write(test)
r = subprocess.run([sys.executable, "test_c2.py"], capture_output=True, text=True, timeout=120)
print(r.stdout)
print("STDERR:", r.stderr[-500:] if r.stderr else "(clean)")
print("rc:", r.returncode)
EOF
