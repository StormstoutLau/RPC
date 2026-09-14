# 跨项目统一工作规范（CROSS-PROJECT WORK STANDARD）

***
id: d6-agent-standard-CROSS-PROJECT-WORK-STANDARD
type: standard
version: 1.0
status: 成稿（集合既有规范；单一真值仍归各源文档）
date: 2026-09-12
scope: RPC(主控 Agent 编排) / Paper(D:\Paper) / Auto_Prover(F:\Auto_Prover) / Cpp_Hub(F:\Cpp_Hub) 等本地任务，跨 A/B/C 三机集群执行
upstream: [D6 DESIGN v1.3（顶层目标已声明服务上述四项目）]
关联调研: RESEARCH_2026-09-12_Cpp_Hub_3station.md
------------------------------------------------------------------
> **目的**: 将已散落在四个项目里的既有工作规范（spec 驱动 / 数据安全 / bit-exact / D6 派发 / 三机纪律）**统一缝合为一个可操作的"立项→设计→派发→跨站执行→验收→入档"标准**。本规范是**索引与裁决层**：凡子规范已写明的，引用而非重复；凡冲突的，以本规范裁决。
***

## 1. 背景与目标

D6 `DESIGN.md` 顶层目标已声明：为 RPC / Paper / Auto_Prover / Cpp_Hub 等任务项目提供 `agent-cli` 统一调用标准（工作区隔离 / 任务卡 / 并发锁 / 敏感路由）。本规范把该目标兑现为一份跨项目操作标准，并纳入三机集群执行纪律，使"任一本地任务要上多台工作站"不再各写各的。

## 2. 三项目画像（已有规范一律引用，不复制）

| 项目 | 性质 | 语言/范式 | 已有规范（权威文档） |
|---|---|---|---|
| **D:\Paper** (paper2kg) | 论文 PDF 自动分类/重命名 CLI | Python 3.10+ / 单向数据流 / YAML 规则外置 | `checklist.md`（数据安全 A/R §：dry-run 默认、execute 确认、源目录只读→写 `D:\Paper_Organized`、目标幂等、操作前备份 index.db；中文路径 `os.rename(str)`、UTF-8/NFC；perf PERF-01..15） |
| **F:\Auto_Prover** (proof_pipeline) | 形式化证明流水线 | Python / Lean4 / spec 驱动 | `proof_pipeline/docs/SPEC_DEV_PROCESS.md`（6 阶段：调研→设计→实施→跨文档 review→TDD→验收；4 次 Review 排幻觉；P0/P1/P2 强制） |
| **F:\Cpp_Hub** | 量化定价库 | C++20 header-only / TDD / 排幻觉 | `README.md`（方法论）+ `CMakeLists.txt`（构建约束）+ `dispatch/`（跨站派发）+ 本族 `RESEARCH_2026-09-12_Cpp_Hub_3station.md` |

> **原则**: 各项目的领域范式（Paper 的数据安全、Cpp_Hub 的 bit-exact、Auto_Prover 的 spec 驱动）是**最高约束**，本规范不取代，仅在统一入口处强制引用。

## 3. 分层规范模型

```
┌─ 层 1  开发流程（过程）：spec 驱动六阶段 ← Auto_Prover SPEC_DEV_PROCESS（四项目通用）
├─ 层 2  实现质量（领域验收）：数据安全 / bit-exact / 排幻觉 ← 各项目自有权威文档
├─ 层 3  派发执行（编排）：agent-cli wrapper ← D6（workspace/任务卡/golden/评审/槽位门）
├─ 层 4  三站运行（集群）：异构能力 / 并发 / 路径 / 安全路由 / 版本 ← 手册 + 本规范 §5
└─ 层 5  入档持久化：台账单一真值 / DEVELOPMENT-LOG / DECISIONS
```

任一任务必须明确自己落在哪几层；P0/P1/P2 走全层，P3 可简化（援引 Auto_Prover §1 等级表）。

## 4. 统一任务卡契约（层 3）

任何要派发的任务，任务卡 front-matter 必须（D6 schema）：
- `proj`（注册于 `agent-cli.ps1 $PROJECTS`）、`task`、`model`、`cli`、`sensitivity`
- `readonly`、`timeout_s`、`continue-timeout-s`（续跑独立预算）
- `accept-golden`（主控独立断言，`source`+`cmd`；实现/测试分离）
- 可选：`isolate-xdg`（同站并行兜底）、`decompose`（拆片 A/B 并行）

**验收铁律**: 模型不自我盖章——`accept` / `accept-golden` 由主控独立断言；得分/核对由主控侧做，不采信站自报。

## 5. 三站执行规范（层 4，跨项目普遍化）

自 `RESEARCH_2026-09-12_Cpp_Hub_3station.md` §2 提炼，除项目特有约束外，普遍适用于 Paper / Auto_Prover 的跨站执行：

1. **异构能力约束**: 派发前校验目标站是否具备该任务所需工具链（CUDA / nanobind 依赖 / venv / g++ / R 等）；不具备则跳过或用 CPU 回退，勿硬派。
2. **依赖就绪门**: 在站上探测依赖（`import nanobind`、`python3 -m pytest`、`g++ --version` 等），不过即判定环境门失败（O-13 教训：未预置的裸依赖 = rc=127 假失败）。
3. **独立构建/工作区**: 每站 fresh clone/sync + 独立 build 目录；杜绝复用主控污染目录（Cpp_Hub 的 build_cuda 等十余个）或站上残留。
4. **结果块契约**: 远端以固定标记段回传结构化结果，主控解析并独立验收（ctest 计数 / pytest 基线 / 位精确对比）。
5. **并发纪律**: 跨站各 1 并发（O-18），禁止同站叠并发；用站上 LLM 前须 load-gate 且单实例（O-24）。
6. **路径/编码**: 中文文件名/注释 → tar UTF-8、传输排除大产物与 .git/build_*（O-06 教训）。
7. **安全路由**: `sensitivity=local-only` 时评审/生成必须站内模型，禁止 egress 网关外发（O-16 血泪）；本地端子（192.168.1.11/.15:1234）合法。
8. **版本钉定**: 派发钉定 commit，拉回核验 `git rev-parse` + 脏检查。

## 6. 跨项目纪律（贯穿全层）

- **破坏性操作铁律**（各项目通用）: 覆盖/截断/批量替换前先 `.bak` 并验证大小；破坏性 .md 备份至 OneDrive；LF 换行文件禁用 `Get-Content` 截断（PowerShell 5 陷阱）。
- **台账单一真值**: 任一项目状态变更同时回写总览 + 详情节，禁止一处改一处留。
- **决策登记**: 关键决策记入各方 `DECISIONS.md`；演进史记 `DEVELOPMENT-LOG.md`。
- **Sprint 收口**: 验收完成须回填验收证据 + 更新 CHANGELOG/ROADMAP（Auto_Prover §3.7 模板）。

## 7. 变更与演进

- 本规范是**索引层**，版本随其上引用的力源文档（D6 / SPEC_DEV_PROCESS / 各项目 README）演进而复核；新增本地任务时在此注册（§2 表补一行）。
- 边界冲突裁决顺序: **三机安全/资源纪律 > 项目领域范式 > spec 驱动流程 > D6 派发**。

## 8. 与其他文档关系

| 本文档 | 关系 |
|---|---|
| `RESEARCH_2026-09-12_Cpp_Hub_3station.md` | 三站执行规范的调研输入 |
| D6 `DESIGN.md` / `IMPLEMENTATION.md` / `OPEN-ISSUES.md` | 层 3 编排的权威真值 |
| 三机推障手册 / project_memory 硬约束 | 层 4 资源纪律的权威真值 |
| `proof_pipeline/docs/SPEC_DEV_PROCESS.md` | 层 1 流程的权威真值 |

> 首版由 2026-09-12 三项目规范回溯 + Cpp_Hub 三站调研缝合而成；后续随新项目注册持续补行。

## 9. 演进记录

- **2026-09-13 · Auto_Prover 接入 D6（台账↔实现脱节修复）**: D6 审计发现规范 §5 声称 Auto_Prover 由 D6 派发执行，但 `agent-cli.ps1 $PROJECTS` 仅注册 paper/Cpp_Hub，执行 `agent-cli task auto_prover ...` 会抛 `unknown/missing project`。本轮将 `Auto_Prover='F:\Auto_Prover'` 注册进 `$Script:PROJECTS`（agent-cli.ps1 L42），并创建 `F:\Auto_Prover\.agentsync` 专属排除规则（27 条，剔除 `.venv-embed/`、`.hf-embed-cache/`、`download/`、`.trae/` 等本地大目录，规避 G4 200MB 同步上限）。已通过 AST 解析 0 错误 + `_fm_golden_test.ps1` 离线回归全 PASS + `Get-AgentsyncExcludes` 规则读取验证。注：Agent 工具受限无法直接写 `F:\`（沙箱仅限工作目录），.agentsync 经 Shell 落盘。