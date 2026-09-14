---
proj: paper
task: 在 paper 工作区根目录新增一个 Python 脚本 sympy_calc.py，用 sympy 精确计算定积分 ∫₀² x² dx 并输出 8/3。脚本必须真实调用 sympy 的 integrate，禁止仅打印常数或自造近似值
model: gpt-oss-20b
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 600
accept-golden:
  source: ops/station-bin/golden/o13_sympy_golden.py
  cmd: python3 .golden/o13_sympy_golden.py
---
## 任务描述
在**工作区根目录**（不是子目录）新增一个可执行脚本 `sympy_calc.py`。它使用 Python 的 **sympy** 库完成一次精确符号计算，作为本任务的交付判据。

### 必须满足
1. `import sympy`（或 `import sympy as sp` / `from sympy import ...`）。
2. 用 sympy 的 `integrate` 计算 **∫₀² x² dx**（积分变量 x，上下限 0 和 2）。
3. 输出该定积分的精确值 **8/3**（sympy 会给出符 `8/3`，不是 `2.666...` 浮点近似）。
4. 脚本可直接用 `python3 sympy_calc.py` 运行且不报错。

### 判定（主控 golden 独立断言，非模型自写测试）
- 若 B 站 python3 能 `import sympy` 并算出 ∫₀² x² dx = 8/3（依赖就绪门）→ golden 判据①通过；
- 若 `sympy_calc.py` 存在且含 `sympy` + `integrate` + 被积函数 `x**2` → golden 判据②通过。

**不要**编造复杂的无关内容，不要生成多个文件，只产出这一个 `sympy_calc.py`。完成后回报「o13 sympy 卡完成」即可。

示例（仅作说明，请按你实际实现）：
```python
import sympy as sp
x = sp.symbols("x")
result = sp.integrate(x**2, (x, 0, 2))
print(result)   # 期望输出 8/3
```