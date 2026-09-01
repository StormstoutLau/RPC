#!/bin/bash
# b6_c2_verify.sh — 提取代码 + 沙箱执行验证 (三锚点)
set -e
python3 - <<'PYEOF'
import json, re, subprocess, tempfile, os

rec = json.loads(open('/tmp/b6_c2_nothink.jsonl').read().strip())
code = rec['content']
# 提取 ```python 块
m = re.search(r'```(?:python)?\s*\n(.*?)```', code, re.S)
src = m.group(1) if m else code

# 锚点1: 目标函数含二次影响 + 库存项
a1 = ('**v**' in src or 'v_i' in src or 'v**2' in src or 'v*v' in src) and \
     ('lam' in src or 'lam*' in src or 'lambda' in src.lower())
# 锚点2: 终期清仓 x_T=0 显式
a2 = ('x[-1]' in src or 'x[-1]' in src.replace(' ', '') or 'X0' in src or
      'x_N' in src or re.search(r'x\[\s*-1\s*\]\s*=\s*0', src) is not None or
      'terminal' in src.lower() or 'clearance' in src.lower() or 'x_T' in src)
# 锚点3: numpy only
a3 = ('numpy' in src or 'np.' in src) and ('cvx' not in src.lower() and 'scipy' not in src)

print(f'ANCHOR1 目标离散(二次影响+库存): {a1}')
print(f'ANCHOR2 终期清仓显式:          {a2}')
print(f'ANCHOR3 numpy-only:            {a3}')

# 沙箱执行: 跑函数 + 检查输出
test = src + '''

import numpy as np
v = solve_execution()
v = np.asarray(v)
print("SANITY: len(v) =", len(v))
print("SANITY: sum(v)>0 =", float(v.sum()) > 0)
print("SANITY: v>=0 all =", bool((v >= -1e-9).all()))
# 清仓检验: 累积执行量 ≈ X0 (若速度和=库存则是绝对清仓; 弱约束也接受)
print("SANITY: sum(v) =", round(float(v.sum()), 2), " (X0=100)")
'''
with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, dir='/tmp') as f:
    f.write(test); path = f.name
r = subprocess.run(['python3', path], capture_output=True, text=True, timeout=120)
print('--- 沙箱输出 ---')
print(r.stdout[-800:])
if r.returncode != 0:
    print('STDERR:', r.stderr[-400:])
os.unlink(path)
PYEOF