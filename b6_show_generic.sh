#!/bin/bash
# b6_show_generic.sh — 取回冒烟结果 + C2 沙箱 (参数: $1=输出后缀)
set -u
SUFFIX="${1:?用法: b6_show_generic.sh <suffix>}"
python3 - <<EOF
import json
with open("/tmp/b6_smoke_$SUFFIX.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        print(f"########## {r['id']} ({r['elapsed_s']}s, finish={r['finish']}) ##########")
        print("--- CONTENT ---")
        print(r.get("content", r.get("error", ""))[:1600])
        print("--- REASONING (前400字) ---")
        print((r.get("reasoning") or "(空)")[:400])
        print()
EOF

echo "================ C2 沙箱 ================"
mkdir -p /tmp/b6_c2_$SUFFIX && cd /tmp/b6_c2_$SUFFIX
timeout 600 python3 - <<EOF
import json, re, subprocess, sys
with open("/tmp/b6_smoke_$SUFFIX.jsonl", encoding="utf-8") as f:
    recs = {json.loads(l)["id"]: json.loads(l) for l in f}
code = recs["dmx-c2"]["content"]
m = re.search(r"\`\`\`python\n(.*?)\`\`\`", code, re.S)
if not m:
    print("!! 无 python 代码块, 原文:", code[:300]); sys.exit(1)
open("c2.py", "w").write(m.group(1))
test = '''
import numpy as np, time
from c2 import solve_execution
t0 = time.time()
v = solve_execution(T=1.0, N=100, Gamma=1.0, lam=0.1, X0=100.0)
el = time.time() - t0
v = np.asarray(v); dt = 1.0/100
x = 100.0 - np.cumsum(v) * dt
print("elapsed_s:", round(el, 1))
print("len_v:", len(v))
print("sum_v_dt (应≈100):", round(float(np.sum(v)*dt), 4))
print("x_end (应≈0):", round(float(x[-1]), 6))
print("min_v (应>=0):", round(float(np.min(v)), 6))
print("cost (参照最优≈10326):", round(float(np.sum(v**2)*dt + 0.1*np.sum(x**2)*dt), 4))
'''
open("test_c2.py", "w").write(test)
r = subprocess.run([sys.executable, "test_c2.py"], capture_output=True, text=True, timeout=590)
print(r.stdout)
print("STDERR:", r.stderr[-400:] if r.stderr else "(clean)")
print("rc:", r.returncode)
EOF
