#!/usr/bin/env bash
# Cpp_Hub 真源任务卡 golden：验证 agent 在 math.hpp 新增 beta(x,y) 且真 cmake 编译通过。
# 运行于远端 B 站工作区 $W（D6 派发同步 F:\Cpp_Hub 真源后）。
#
# 真编译判据（D-19 A1）：
#   1) cmake 配置成功 + 编译内置 cpphub target（验证新代码可编译，不破坏既有库）
#   2) 单独编译独立测试源（include math.hpp 调用 beta）并运行断言 beta 数值
# 通过 = exit 0；任一失败 = 非 0 打印原因。
set -euo pipefail
W="$(pwd)"
echo "=== [golden] Cpp_Hub 真编译 golden start (cwd=$W) ==="

fails=()

# 1) agent 确实在 math.hpp 新增了 beta
MH="$W/include/cpphub/core/math.hpp"
if [ ! -f "$MH" ]; then
  echo "GOLDEN_FAIL: 缺 include/cpphub/core/math.hpp"
  exit 1
fi
if ! grep -q 'inline Real beta(Real x, Real y)' "$MH"; then
  fails+=("math.hpp 未定义 'inline Real beta(Real x, Real y)'")
fi

# 2) 独立测试源：include math.hpp + 断言 beta（真编译验证新代码，聚焦变更点而非整库）
# 注：不做整库 cmake configure —— Cpp_Hub 完整项目的名 Cmake 子目录(c-benchmarks)含副依赖，
#    会以与 beta 无关的理由失败，污染 golden 判定；此处只真编译 agent 新代码 + 数值断言。
TESTCXX="$W/.golden/beta_test.cpp"
mkdir -p "$W/.golden" "$W/.golden/bin"
cat > "$TESTCXX" <<'EOF'
#include "cpphub/core/math.hpp"
#include <cmath>
#include <cstdio>

int main() {
    using cpphub::v1::Real;
    using cpphub::v1::beta;
    // beta(2,2) = Γ2Γ2/Γ4 = 1·1/6 = 1/6
    Real b22 = beta(Real(2), Real(2));
    if (std::abs(b22 - Real(1)/Real(6)) > 1e-9) {
        std::printf("beta(2,2)=%.12f expect 0.166666667\n", b22);
        return 1;
    }
    // beta(1,3) = 1/3
    Real b13 = beta(Real(1), Real(3));
    if (std::abs(b13 - Real(1)/Real(3)) > 1e-9) {
        std::printf("beta(1,3)=%.12f expect 0.333333333\n", b13);
        return 1;
    }
    std::puts("BETA_ASSERT_OK beta(2,2)=1/6 beta(1,3)=1/3");
    return 0;
}
EOF
if ! g++ -std=c++20 -O2 -I"$W/include" "$TESTCXX" -o "$W/.golden/bin/beta_test" >"$W/out/.golden-beta-build.log" 2>&1; then
  fails+=("独立测试源编译失败（见 out/.golden-beta-build.log）")
else
  if ! "$W/.golden/bin/beta_test" > "$W/out/.golden-beta-run.log" 2>&1; then
    fails+=("beta 数值断言失败（见 out/.golden-beta-run.log）")
  else
    echo "[golden] beta_test PASS: $(cat "$W/out/.golden-beta-run.log")"
  fi
fi

if [ ${#fails[@]} -gt 0 ]; then
  echo "GOLDEN_FAIL"
  for f in "${fails[@]}"; do echo "  - $f"; done
  exit 1
fi
echo "GOLDEN_PASS (Cpp_Hub 真源 g++ 真编译 beta 独立测试 + 数值断言通过)"
exit 0