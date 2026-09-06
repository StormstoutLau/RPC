#!/usr/bin/env python3
"""C2 沙箱验证: 运行 qwen 生成的 solve_execution, 检查离散目标/终期清仓/v>=0"""
import json, numpy as np

import sys
SRC = sys.argv[1] if len(sys.argv) > 1 else '/tmp/b6_smoke_qwen38_27b.jsonl'
q = [json.loads(l) for l in open(SRC) if l.strip()]
c = [r for r in q if r['id'] == 'dmx-c2'][0]['content']
code = c.split('```python')[1].split('```')[0]
ns = {}
exec(compile(code, '<c2>', 'exec'), ns)
f = ns['solve_execution']
v = f()
N = len(v)
dt = 1.0 / N
T = 1.0

# 离散目标: Gamma*sum(v^2*dt) + lam*sum(x^2*dt), 终期 x_N=0
x = 100.0
inv = [x]
for vi in v:
    x = x - vi * dt
    inv.append(x)
xarr = np.array(inv)
cost = 1.0 * (v ** 2 * dt).sum() + 0.1 * (xarr[:-1] ** 2 * dt).sum()

print(f"len(v)={N}")
print(f"v 范围: min={v.min():.6f} max={v.max():.6f}")
print(f"v>=0 全成立: {bool((v >= -1e-12).all())}")
print(f"总清仓 sum(v*dt)={float((v * dt).sum()):.6f} (期望≈100=X0)")
print(f"终期库存 x_N={float(xarr[-1]):.9f} (期望≈0)")
print(f"离散目标函数值 J={cost:.6f}")