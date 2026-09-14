#!/usr/bin/env bash
# B 站 R/sympy 预置（O-13 子项 B，2026-09-14）
# 对齐 _cpp_venv_provision.sh 惯例：幂等、每步打印、末尾 DONE。
# 目标: B 站预置 R (noble-cran40) + python3-sympy，满足 CROSS-PROJECT §5.2 依赖就绪门。
# 执行: ssh scott-lau-GTR-Pro.local 'bash -s' < ops/station-bin/_r_sympy_provision.sh
# 注意: R 需 sudo（apt 安装）；若需交互密码请 sudo -v 预热。
set -euo pipefail

echo "=== [1] python3 + pip availability ==="
python3 --version
python3 -m pip --version 2>/dev/null || echo "(pip via ensurepip if needed)"

echo "=== [2] sympy (apt python3-sympy) ==="
if python3 -c 'import sympy' 2>/dev/null; then
  echo "sympy already present: $(python3 -c 'import sympy; print(sympy.__version__)')"
else
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3-sympy
  echo "sympy installed: $(python3 -c 'import sympy; print(sympy.__version__)')"
fi

echo "=== [3] R (noble-cran40) probe ==="
if command -v R >/dev/null 2>&1; then
  echo "R already present: $(R --version | head -1)"
else
  echo "R missing -> installing via apt (noble-cran40)"
  # 注: 若系统仓库已有 r-base 可免加 CRAN 源；这里走系统 apt 优先，失败再提示 CRAN。
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends r-base-core
  echo "R installed: $(R --version | head -1)"
fi

echo "=== [4] Rscript smoke ==="
Rscript -e 'cat("Rscript OK version:", as.character(getRversion()), "\n")'

echo "=== [5] sympy import smoke (system python3) ==="
python3 -c 'import sympy; print("sympy import OK", sympy.__version__)'

echo "DONE"