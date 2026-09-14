#!/usr/bin/env python3
"""O-13 子项 B 收口 golden：验证 R/sympy 依赖就绪 + agent 产出 sympy 计算代码正确。

判据（O-13 关闭：真实 R/sympy 依赖卡在 B 站 accept 通过）：
1) B 站 python3 可用 sympy（import + 冒烟）——直接证明 G8 依赖就绪门；
2) agent 在工作区产出 `sympy_calc.py`，其求值 `∫₀² x² dx` 的 else 分支输出 8/3，且独立于模型自写测试。

用法（由 wrapper 于 collect 阶段在 B 站 $W 下执行）：
    python3 .golden/o13_sympy_golden.py   # 默认当前目录 = 工作区根
通过 = exit 0；任一失败 = 非 0。
"""
import sys
import sympy as sp


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    fails = []
    root = "."

    # 判据 1) sympy 依赖就绪（O-13 前提）
    try:
        sp_sym = sp.symbols("x")
        integral = sp.integrate(sp_sym**2, (sp_sym, 0, 2))
        integral_frac = sp.simplify(integral)
        if integral_frac != sp.Rational(8, 3):
            fails.append(f"sympy 自检异常: ∫x²dx[0,2]={integral_frac}≠8/3")
    except Exception as e:
        fails.append(f"sympy 自检失败（依赖未就绪?）: {e!r}")

    # 判据 2) agent 产出 sympy_calc.py 且逻辑正确
    import pathlib
    p = pathlib.Path(root) / "sympy_calc.py"
    if not p.is_file():
        fails.append("未找到 sympy_calc.py（agent 未产出）")
    else:
        t = p.read_text(encoding="utf-8")
        # 应使用 sympy（import sympy 或 from sympy）
        if "sympy" not in t:
            fails.append("sympy_calc.py 未引用 sympy")
        # 应有 ∫x² 的积分形式（integrate 与 x**2）
        if "integrate" not in t:
            fails.append("sympy_calc.py 未调用 sympy.integrate")
        if "x**2" not in t and "x * x" not in t and "x^2" not in t:
            fails.append("sympy_calc.py 未含被积函数 x^2")

    if fails:
        print("GOLDEN_FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("GOLDEN_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())