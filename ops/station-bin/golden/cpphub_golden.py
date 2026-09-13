#!/usr/bin/env python3
"""Cpp_Hub-001 主控侧 golden 判据（O-12：独立于模型自写测试）。

用法（由 wrapper 在 collect 阶段于主控站调用）：
    python cpphub_golden.py <Cpp_Hub_src_dir>

断言目标：以"源码静态级"独立验证模型是否真实修改了既有文件并达成契约，
无需主控站具备 g++（Win10 主控无编译链）。强度不弱于编译，但避开平台依赖。
通过 = exit 0；任一不满足 = 非 0 并打印原因。
"""
import re
import sys
from pathlib import Path


def _load_core(src):
    return (src / "src" / "因子计算_核心.cpp").read_text(encoding="utf-8")


def main(argv):
    if len(argv) > 2:
        print("usage: cpphub_golden.py [<Cpp_Hub_src_dir>]  (default: current dir)")
        return 2
    # 远端在 $W 下执行时无参数 → 默认当前目录即 Cpp_Hub 工作区根
    src = Path(argv[1]) if len(argv) == 2 else Path(".")
    fails = []

    # 1) 文件存在（中文路径，O-06）
    core = src / "src" / "因子计算_核心.cpp"
    run = src / "src" / "因子计算_run.cpp"
    if not core.is_file():
        fails.append(f"缺少 src/因子计算_核心.cpp ({core}) —— 中文文件未到达或未同步")
    if not run.is_file():
        fails.append(f"缺少 src/因子计算_run.cpp ({run})")
    if fails:
        return _report(fails)

    t_core = core.read_text(encoding="utf-8")

    # 2) 函数 向量均值 定义存在，且为 inline，带 <-vector> 头
    if "inline double 向量均值" not in t_core and "inline double 向量均值" not in re.sub(r"\s+", " ", t_core):
        fails.append("未找到 'inline double 向量均值(...)' 定义（需为 inline，避免重复定义）")
    if "#include <vector>" not in t_core:
        fails.append("缺少 '#include <vector>'")

    # 3) 空处理判据：返回 0.0（不允许 NaN/除零）
    body = re.search(r"inline\s+double\s+向量均值\s*\([^)]*\)\s*\{(.*?)\}", t_core, re.S)
    if not body:
        fails.append("无法解析 向量均值 函数体")
    else:
        if "0.0" not in body.group(1):
            fails.append("函数体内未出现 '0.0'（空向量返回 0.0 判据缺失）")
        if "size()" not in body.group(1) and "/" not in body.group(1):
            fails.append("函数体内未见均值计算依据（size() 或 '/'）")

    # 4) run 支持 --mean 模式
    t_run = run.read_text(encoding="utf-8")
    if "--mean" not in t_run:
        fails.append("因子计算_run.cpp 未包含 '--mean' 分支（均值模式入口）")
    if "向量均值" not in t_run:
        fails.append("因子计算_run.cpp 未调用 cpphub::向量均值")

    # 5) 中文路径完整性（O-06）：文件未被重命名/替代
    ascii_core = src / "src" / "core.cpp"
    if ascii_core.is_file():
        fails.append("检测到 ASCII 替代文件 core.cpp，疑似模型规避中文文件名 —— 违反 O-06 本意")

    return _report(fails)


def _report(fails):
    if fails:
        print("GOLDEN_FAIL")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("GOLDEN_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))