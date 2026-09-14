---
proj: Cpp_Hub
task: 在源文件 include/cpphub/core/math.hpp 中，位于 namespace cpphub::v1 内，新增一个内联函数 inline Real beta(Real x, Real y)，实现贝塔函数 β(x,y)=Γ(x)Γ(y)/Γ(x+y)。可依赖现有工具（如 std::lgamma）或自己实现。不要删除或改动其他已有函数；不要新增其他文件
model: gpt-oss-20b
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 900
continue-timeout-s: 900
accept-golden:
  source: ops/station-bin/golden/cpphub_beta_golden.sh
  cmd: bash .golden/cpphub_beta_golden.sh
---
## 任务描述

你必须**实际修改** `include/cpphub/core/math.hpp`，为该核心数学库新增**贝塔函数**。

### 必须满足
1. 在 `cpHub` 的 `inline namespace v1` 内新增：
   ```cpp
   inline Real beta(Real x, Real y) noexcept {
     // β(x,y) = Γ(x)·Γ(y) / Γ(x+y)
     ...
   }
   ```
   - `Real` 已在同文件通过 `cpphub::v1::Real`（doublde）可用，直接调用即可。
   - 可用现成 `std::lgamma`，或复用本库的 `regularized_lower_gamma`/`lgamma` 相关能力；实现方式不限，但必须是**实际计算 β**，不得返回常量。
   - 添加 `noexcept`（若实现不抛）。
2. 除修改 `math.hpp` 追加 `beta` 外，**不得新增/删除/修改任何其他文件**。
3. 保持 C++20 风格，不引入新 include 除非必要。

### 判定（主控 golden 真编译独立断言，非模型自写测试）
- 方法将在**远端 B 站**执行：先 `cmake configure+build` 验证整库可编译（含你的新代码），再独立编译一个测试源 `include cpphub/core/math.hpp`、调用 `beta` 断言数值：
  - `beta(2,2) = Γ2Γ2/Γ4 = 1/6 ≈ 0.1666667`
  - `beta(1,3) = 1/3 ≈ 0.3333333`

若任意数值偏差 >1e-9，golden 判失败。

完成标准是源码真实变更 + 真编译 + 数值断言通过。完成后回报「cpphub beta(x,y) created」即可，不要附加无关内容。