# RESEARCH: F:\Cpp_Hub 调用三台工作站执行之规范调研

***
id: d6-agent-standard-RESEARCH-CppHub-3station
type: research
version: 1.0
status: 成稿（输入：CROSS-PROJECT-WORK-STANDARD 统一规范）
date: 2026-09-12
scope: 仅 F:\Cpp_Hub 主项目跨站执行规范；三项目统一规范见 CROSS-PROJECT-WORK-STANDARD.md
------------------------------------------------------------------
> **问题**: F:\Cpp_Hub（C++ header-only 量化库）如何安全、可复现地调用主控 + A + B（+C）三台工作站执行构建/验证？需要遵守哪些规范？
> **方法**: 调研项目现状（CMake 结构 / dispatch / validation_results）+ 三机集群既有纪律（D6 / project_memory），提炼规范并标注现存缺口。
***

## 1. 项目现状（2026-09-12 实查）

- **定位**: C++20 header-only 量化定价库（BS/Heston/PDE/Tree/MC/AAD Greeks/VaR/SVI + HFE 高频计量），nanobind Python 绑定 + 可选 CUDA MC。阶段 1-5 全 pass，跨平台 1412/1412 bit-exact。
- **验收哲学**: 跨平台浮点确定 = 标准合规测试；`-ffp-contract=off`(GCC) + `/fp:precise`(MSVC) 保证 IEEE-754 严格模式；对抗 R `highfrequency` 等采用初始 1e-12/1e-10 源码级排幻觉对标。
- **三站异构**（决定派发边界）：

| 站 | 环境 | 能力 | CUDA MC |
|---|---|---|---|
| 主控（F:\Cpp_Hub 所在） | Win10 + MSVC | 全套 + nanobind | ✅ RTX4060 (arch 89) |
| A scott-lau-NEX | Ubuntu + GCC13 + CMake≥3.25 | GCC 全套 | ❌ 自动回退 CPU stub |
| B scott-lau-GTR-Pro | Ubuntu + GCC13 | GCC 全套 | ❌ 同上 |
| C（如需） | Ubuntu | GCC 全套 | ❌ 同上（runner/骨架未建） |

- **既有跨站实践**（`dispatch/` + `validation_results/`）：A/B 站含各自 `TASK_*.md + run_*.sh`；`dispatch_phase6_m4.ps1` 已实现并行派发 A/B + 远端 fresh clone+rebuild+ctest + 结果块（`M4_VERIFY_RESULT...END_RESULT`）回主控解析。早期另经 LM Studio 端子（192.168.1.11/.15:1234）调站上模型做生成验证（`summary.json` 记录 model/url/tokens）。

## 2. 规范化要点（七条）

### 2.1 异构能力边界
- CUDA MC **只在主控**构建（`-DCPPHUB_ENABLE_CUDA=ON`）；派发到 A/B 时**禁止**传 CUDA/O 之外 flag，由 `if(CMAKE_CUDA_COMPILER)` 自动回退 CPU stub。
- nanobind Python 绑定只派给已装 `nanobind`+Python dev 头的站（先探测 `import nanobind`，不过即环境门失败，勿裸跑）。

### 2.2 浮点确定性纪律
- 三站编译标志**锁定同一套**：GCC `-O3 -march=x86-64-v3 -ffp-contract=off` / MSVC `/O2 /arch:AVX2 /fp:precise`；C++20 + `CMAKE_EXTENSIONS=OFF`。
- **任一站在此之外改优化/架构/fast-math = 违规**（破坏 bit-exact，且差异成假线索）。配置命令写入任务卡，主控以命令哈希核验，不做软等效。
- 依赖版本锁定：CMake≥3.25、GCC13+、googletest v1.14.0（FetchContent URL 已钉）。

### 2.3 派发与回收流程（沿既有 dispatch 固化为规范）
- 每站独立 `TASK_*.md + run_*.sh` 落盘远端；远端逻辑一律脚本落盘（R14，勿 ssh 内联 PS 引号）。
- 每站 **fresh clone + submodule + 独立 build 目录**；禁止复用主控本地 `build_capi/build_cuda/build_M2/...` 十余个污染目录或站上残留。
- **结果块契约**回主控解析（等同主控侧 golden），主控独立验收（ctest 计数 + 位精确对比），不采信站自报"通过"。
- `validation_results/<station>_<model|local>/` 每站独立归档（原始日志 + 解析 + raw_response + summary.json），单一真值。

### 2.4 并发纪律
- 跨站各 1 并发（O-18）；**禁止同站叠并发构建**（带宽顶起 ~2.8×）。A/B 并行 OK，主控本地 gate 不占用推理站。
- 若用站上 LLM（评审/生成），先过 load-gate + 确认单实例（O-24），禁止并行起多 llama-server（A 站 panic 根因）。

### 2.5 路径与传输纪律
- 任务卡/注释含中文 → **tar 强制 UTF-8**（O-06 教训）；同步用既有 `cpphub_sync.tar.gz` 增量，`--exclude` .git / build_* / *.obj / validation_results。
- ssh/scp 走 Win10 OpenSSH；远端命令脚本落盘。

### 2.6 安全路由
- 敏度 `local-only` 时评审必须站内模型，禁止经 egress 网关发云端（O-16 G1 血泪）；LM Studio 端子直连（192.168.1.11/.15:1234）为合法本地路径。

### 2.7 版本溯源
- 派发钉定 commit（如 `b278151`），拉回 `git rev-parse` 核验 + 脏检查，防脏工作区伪验收。

## 3. 现存缺口

1. **dispatch/ 仅覆盖 A+B** —— C 站 runner/build 骨架未建；主控自身 Linux 侧 gate 亦未在 dispatch 补全 →"三台"目前实为 A+B 两站 + 主控约束。
2. **主控本地 build 目录污染**（build_cuda/build_M2/build_phase2/build_v141 等十余个）——建议派发/验收固定在独立 `build_HUB` 空目录避免互扰。
3. **现役 dispatch 脚本是手工 PS（Start-Job + ssh）**，尚未与 D6 `agent-cli`（任务卡 front-matter / golden / 槽位门 / 敏感路由）打通；未来跨项目三站派发应并入 D6 编排层（详见 CROSS-PROJECT-WORK-STANDARD §5）。

## 4. 结论

F:\Cpp_Hub 三站执行规范可归纳为「**异构能力约束 + 位精确确定性 + 独立 build + 结果块契约 + 跨站各 1 并发 + 站内安全路由 + 版本钉定**」七条。其中 2.1/2.2 为项目特有硬约束，2.3-2.7 与 D6/三机集群纪律同源，可推广到手册与统一工作规范。

> 关联: F:\Cpp_Hub\README.md / CMakeLists.txt / dispatch\dispatch_phase6_m4.ps1 / validation_results\summary.json；D6 OPEN-ISSUES O-06/O-12/O-13/O-16/O-18/O-24；三机推障手册。