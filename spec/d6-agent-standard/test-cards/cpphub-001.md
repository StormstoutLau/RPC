---
proj: Cpp_Hub
task: 在 src/因子计算_核心.cpp 的核心库 cpphub 命名空间中新增"向量均值"纯函数 double 向量均值(const std::vector<double>& v)，并让 src/因子计算_run.cpp 支持无参"均值模式"调用；只修改既有源文件，不新增文件
model: gpt-oss
cli: opencode
sensitivity: local-only
readonly: false
timeout_s: 900
accept-golden:
  source: ops/station-bin/golden/cpphub_golden.py
  cmd: python3 .golden/cpphub_golden.py
status: retired (2026-09-16) —— 样本专用卡, 勿派发
note: 目标源目录是 spec/d6-agent-standard/Cpp_Hub 轻量样本; 但 PROJECTS['Cpp_Hub'] 自 cc3b75c (2026-09-14) 起已改指 F:\Cpp_Hub 真项目, 且 wrapper 无 per-card 源目录覆盖键 => 直接派发必 golden FAIL。真源卡见 cpphub-beta.md。另: 该样本已被 2026-09-12 试点本身改过 (源码已含 向量均值), 不再是干净 fixture, 即使重指也无法作回归用。(wrapper 的 front-matter 白名单会忽略 status/note 两键, 故二者只是人工标记, 不进 prompt、不影响解析。)
---
## 任务描述

你必须**实际修改** `src/因子计算_核心.cpp`，为核心库新增能力；并**修改** `src/因子计算_run.cpp` 支持调用。禁止只分析/只解释/只总结——完成标准是源码真实变更且通过主控站 golden 判据（由 wrapper 在任务结束后以独立断言验证，非模型自写测试）。除修改这两个既有源文件外，**不得新增任何文件，不得修改其他文件**。

本工作区刻意含**中文文件名**（`因子计算_核心.cpp` / `因子计算_run.cpp`）——既是优化，也是主题。请**按原中文名**直接编辑，不要重命名、不要新建 ASCII 替代文件。

### 1. `src/因子计算_核心.cpp`：新增 `double 向量均值(const std::vector<double>& v)`

在 `cpphub` 命名空间内，新增**头文件内联**纯函数（该文件当前以"头 + inline"方式被 run 包含，函数须为 `inline` 以避免重复定义，或直接声明如下）：

```cpp
#include <vector>
inline double 向量均值(const std::vector<double>& v) {
  // v 非空 → 返回元素均值（double 精度）；v 为空 → 返回 0.0（判据按此）
  ...
}
```

判据约定（主控站 golden 按此独立断言）：
1. v 非空 → 返回 `sum(v)/v.size()`（double）
2. v 空（`{}`）→ 返回 `0.0`（不允许 NaN/除零异常）

### 2. `src/因子计算_run.cpp`：支持"均值模式"

保持既有求和模式不变（`cpphub_run 3 4` → `7`）。在此基础上，当调用参数个数为 1 且该参数为 `--mean` 时，改走"均值模式"：读取剩余全部 stdin 的空白分隔 double（可用 `std::cin`），交给 `cpphub::向量均值`，打印 `均值=<value>`（`<value>` 用默认 `std::cout` double 格式即可，golden 只断言数值）。示例：

```bash
echo "1.0 2.0 3.0" | ./build/cpphub_run --mean   # → 均值=2
```

此时累积逻辑不含法，规避既有求和的歧义。

> 提示：`因子计算_核心.cpp` 是"头 + inline 定义"被 run 直接 `#include` 的方式，`向量均值` 保持与 `因子求和` 一致的 `inline` 定义风格即可；记得把 `#include <vector>` 加在同一个文件。

完成后直接报告"cpphub 向量均值 created"即可，不要附加与其无关的内容。