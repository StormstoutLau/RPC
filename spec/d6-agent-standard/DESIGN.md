# 设计文档：D6 Agent 跨项目调用标准与 agent-cli MVP

***

id: d6-agent-standard-DESIGN
type: design
version: 1.4
status: approved（Step 3-4 通过，Scott 签字 2026-09-03；v1.4 对齐审计回灌：BP-1 契约补 readonly / BP-2 别名映射表，均为 schema 补全非行为变更）
date: 2026-09-03
depends: \[Agent跨项目调用标准与迁移复用调研 (docs/, v3.4.1 2026-09-03 含幻觉审计轮: 1 项剔除 + 2 项决策链断裂修复 + 7 项证据强度修正)]
upstream: \[D5 Agent 生态升级 (verified 2026-09-02), ADR-0001]
----------------------------------------------------------

> **Feature**: D6 agent-cli wrapper MVP（主控站→两站 agent CLI 的跨项目调用标准：工作区 + 任务卡 + 并发锁 + 敏感路由）
> **创建日期**: 2026-09-03
> **状态**: Review 通过（v1.3，Step 4 gate + F1 定案，待签字）；v1.0 曾为草稿
> **Review 记录（v1.0→v1.3）**: 6 项 minor 发现全处理——F1 后端并发探测降级 **已获 Scott 批准并定案为后续升级项目**（2026-09-03：MVP 观测先行 queue\_s；**后端并发探测单独立项，随 V2/并发 fan-out 阶段升级**）/ F2 补 sanitized scrubber 归属 / F3 .agentsync 四型移交 IMPLEMENTATION / F4 TUI 并发边界登记为已知限制 / F6 架构图补免费档出站 / F7 重试语义适配注记。无 major、无幻觉、无断裂（引用核验全部命中）。待文末签字。
> **Spec 步骤**: Step 3-4
> **基于调研**: [Agent跨项目调用标准与迁移复用调研.md](../../docs/Agent跨项目调用标准与迁移复用调研.md)（v3.4.1 审计后版；**本文真值源约定：模型路由与 CLI 边界以调研 §2.1/§9.4 实测层为准，§0/§5 仅作导览**——审计元教训 R11/R3）
> **G1-G14 缺口清单**: 调研 §6（本文逐条收编或显式移交）

***

## 1. 设计目标

主控站多个任务项目（RPC/Paper/Spec\_Workflow/Auto\_Prover/Cpp\_Hub）需要调用两站 4 个 agent CLI，当前无统一调用规范、无项目间隔离、无并发保护、无敏感内容路由。本设计交付 **`agent-cli`** **wrapper MVP**（PowerShell）：单命令完成"工作区同步 → ssh headless 执行 → 产物回收"全链，内建并发锁（flock 双层）、任务卡状态机（孤儿锁可检测）、敏感内容三档硬路由（local-only 不可覆写）。为后续站间互审（D7+）与 trae 五层循环对接（D7）预留任务卡接口。

**核心设计立场**（继承调研五公理 §8.5 + 双源定案 §9.7.4）：

1. **确定性编排**（公理 1）：路由/超时/重试/锁全部是 wrapper 代码，不是模型判断
2. **协议层抄 Anthropic，强制层抄 Codex**（§9.7.4）：交接契约（.agent-run.json）吸收 task-notification 字段；并发与重试语义按 RwLock/二段式升级实现
3. **MVP 纵切**：只做 opencode 单路径 + workspace/task 两命令；claude 路径/--continue/review --peer 按缺口分期（G1 二期）
4. **验证先行**：G2 五项假设设 V0 验证门，不通过则改道

## 2. 预期效果

| 维度   | 现状                            | 预期（MVP 完成后）                                                          |
| ---- | ----------------------------- | -------------------------------------------------------------------- |
| 调用入口 | 手敲 ssh + 手拼 stdin 管道命令（三铁律易忘） | `agent-cli task paper "任务描述"` 单命令全链                                  |
| 项目隔离 | 无（各项目会话/记忆/产物互相污染）            | `~/agent-workspaces/<proj>/` 四重隔离（记忆 cwd 键控 + AGENTS.md + 技能 + out/） |
| 并发安全 | 无保护（人 TUI 与脚本并行写同目录）          | 工作区 flock + 任务卡 readonly 字段双层                                        |
| 失败恢复 | 中断后状态不可知，半成品污染下次运行            | 状态机 + 孤儿锁机械可检（running 带 PID/时间戳）                                     |
| 敏感路由 | 靠人记忆"敏感内容走本地"                 | 任务卡 `sensitivity` 三档硬路由，local-only wrapper 层拒绝远端                     |
| 额度观测 | 无（打到限额才报错）                    | .agent-run.json 记 queue\_s/run\_s/tokens 三元组，本地 log 累计               |

**非目标**：不实现 claude 路径与 `--continue`（二期）；不实现 review --peer 站间互审（D7+）；不实现 trae 派发对接（D7，仅留任务卡接口）；不做站内 coordinator 模式（D7+ 候选）；不装 R/Mathematica 环境（G8 执行列 T0 预置，独立批次）；不改两站 CLI 配置（D5 已定）。

## 3. 设计依据

### 3.1 调研结论 → 设计决策（每条可追溯）

| 调研发现（v3.4.1 审计后）                                                              | 设计决策                                                             | 引用            |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------- |
| 工作区 = 记忆/指令/技能/会话四重隔离最小单元（memory.db cwd 键控 E1 实证）                             | L0 工作区规范按调研 §5.1 落地，AGENTS.md 单一编辑点在主控站                          | §4.1          |
| tar+scp 是唯一实证同步链（主控站 Git Bash 无 rsync）                                        | L1 同步链定案 tar+scp + .agentsync 排除                                 | §5.2          |
| opencode 必须 stdin 管道形式（位置参数 1.18.25 挂死，日志实证）；claude 必须 `< /dev/null`          | wrapper 内建调用铁律，硬编码不允许绕过                                          | §2.1/§9.1     |
| wrapper 永远显式 -m（A 站默认曾漂移到外网模型——安全边界）                                          | task 命令必填 `--model` 或任务卡 `model` 字段，无隐式默认                        | §9.1-3        |
| 四档模型分层实测：分层轴是窗口与隐私非智力（免费档不劣质，13s 快于本地旗舰 3 倍）                                  | 模型路由表按 §9.4 落地 wrapper 路由层                                       | §9.4          |
| 免费模型数据用于改进训练（官方 Privacy 节明文）                                                  | sensitivity 三档硬路由：public→免费档 / sanitized→脱敏后远端 / local-only→强制本地 | §2.1 敏感内容路由   |
| Codex RwLock：读锁并行/写锁全局独占，MCP readOnly 注解声明式                                   | G11 双层锁：工作区 flock（粗，MVP）+ 任务卡 readonly 字段（细，V2）                  | §9.7.1        |
| Anthropic 纪律：write-heavy one at a time **per set of files**（第三方验证+粒度细化）       | 锁粒度设计目标注明文件集方向，MVP 先工作区级                                         | §9.6-2        |
| "Bash 不锁"系未验证假设（exec\_command=true 归因是推断；opencode 内部序列化未测）                    | 列入 V0 验证门第 5 项，不通过则 Bash 调用也入锁                                   | 审计 R6/§9.7.1  |
| dsh 孤儿锁语义：崩溃中断产生可检测孤儿（有 start 无 end）而非假称完成                                    | G12 状态机：running 标记带 PID/时间戳，done 最后写；残留 running 机械可检可清           | §9.8.1        |
| "Model-visible means logged" 不变量                                              | wrapper 发给 agent 的一切（prompt/附件/audit 注入）落 .agent-run.json        | §9.8.1        |
| Codex 二段式升级重试（恰好一次）+ 批准缓存 + owner 策略不可升级绕过                                    | 重试 ≤2 转人工；门禁缓存；sensitivity: local-only 不可被任何 CLI 参数覆写            | §9.7.2        |
| task-notification usage 三元组（tokens/tool\_uses/duration）+ queue\_s/run\_s 分离计量 | .agent-run.json 契约吸收双方字段（G13 观测）                                 | §9.6-2/§9.7.2 |
| Anthropic Continue-vs-Spawn 六行决策表                                             | wrapper --continue 路由规则（二期实现，规则表先进文档）                            | §9.6-2        |
| 四项目四象限（读密集/文档/编排/编译）                                                          | .agentsync 分四型模板（Python/C++/文档/Lean4）                            | §7.5          |
| 试点建议 Paper 起步（177 pytest 验收判据现成）                                              | V0 试点项目 = Paper（第二试点 Cpp\_Hub 列 T 后期）                            | §9.3          |

### 3.2 相关 ADR

| ADR      | 决策                | 对本设计的影响                                     |
| -------- | ----------------- | ------------------------------------------- |
| ADR-0001 | 收尾→重构→聚合→加固；运维层补全 | D6 属调用标准层，不触碰 infer-load/网关/CLI 配置（D1/D5 域） |

### 3.3 职责边界

**职责内**：agent-cli wrapper（主控站 PowerShell）；工作区生命周期管理；任务卡 schema 与状态机；并发锁协议；敏感路由；.agent-run.json 契约；.agentsync 模板；V0 验证门。
**职责外**：两站 CLI 生态装备（D5 已 verified）；模型加载与网关（infer-load 域 + D1）；R/Mathematica/sympy 预置（G8 → T0 独立批次，本文仅登记接口）；trae 派发与站间互审（D7）；模型选型（model-eval 域）。

## 4. 架构设计

### 4.1 G11 并发模型（设计第一约束——审计定案：先写并发再写命令面）

**双层锁**：

```
层 1（粗，MVP）: 工作区级排它锁
  ~/agent-workspaces/<proj>/.agent-lock（flock 文件锁）
  任何 agent-cli task 执行前必须获取；执行期间持有；释放即写 done
  人 TUI 直接进工作区不受锁约束（纪律告知：task 运行中勿手动进同工作区——
  V0 验证门第 5 项若证伪"Bash 不锁"，则把 TUI 互斥也列入 V2）
  ⚠ 已知边界（Review F4）：flock 只互斥 wrapper-vs-wrapper，不互斥 wrapper-vs-手动TUI；
  缓解 = 纪律告知 + V0-5 联动验证，接受为 MVP 风险（同工作区手动作业与任务并发的写冲突概率低）

层 2（细，V2，MVP 仅留字段）: 任务卡 readonly 声明
  readonly: true  → 共享语义（research/分析/审查可并行 fan-out）
  readonly: false → 排它语义（implementation 独占）
  MVP 阶段 readonly 字段仅记录不生效（全部按排它处理），V2 按 Codex RwLock 语义细化
```

**依据**：Codex parallel.rs RwLock 模式（§9.7.1，E1 源码直读）+ Anthropic 文件集粒度纪律（§9.6-2 第三方验证）。**锁粒度演进方向**：文件集级（"write-heavy one at a time per set of files"），MVP 从工作区级起步是简化非终点。

**llama-server 单槽注意**：后端 slots=1（is\_processing 互斥），两站各自的单并发槽意味着"同站并行任务在后端排队"——wrapper 不做后端并发探测（G11 原案降级：观测先行，.agent-run.json 的 queue\_s 字段天然记录排队时长，MVP 后按数据决定是否加探测）。**⚠ 批准项（Review F1）**：调研 G11 处置原建议 wrapper MVP 内建"后端并发探测"；本设计明确降级为"观测先行（queue\_s）+ 按数据再定"，属对调研建议的有意简化——**需 Scott 确认接受此降级**，否则 V2 需补探测模块。

### 4.2 整体架构

```
主控站 Win10                                    A/B 站 Ubuntu
┌────────────────────────────┐                 ┌─────────────────────────────────┐
│ agent-cli.ps1 (PowerShell)  │   ① tar+scp    │ ~/agent-workspaces/<proj>/        │
│  workspace / task           │ ─────────────→ │   ├── .agent-lock      (flock)   │
│  ├─ 路由层（§9.4 表+敏感性）    │                 │   ├── .agent-state.json (状态机)  │
│  ├─ 锁协调（4.1）             │   ② ssh 脚本    │   ├── AGENTS.md + CLAUDE.md(薄壳) │
│  └─ 契约归一（.agent-run.json）│ ─────────────→ │   ├── .agentsync (排除清单)      │
│ 任务卡 <proj>/task-*.md      │                 │   ├── out/                (产物)  │
│ 台账 agent-runs.log          │   ③ tar+scp    │   └── (项目文件子集)               │
└────────────────────────────┘ ←───────────── │  cwd=工作区 → opencode (stdin 管道)│
                                                │  记忆: cwd 键控自动隔离            │
                                                └─────────────────────────────────┘
      ╔══ 免费档（sensitivity: public 时，Review F6 补绘）══╗
      ║ M3 路由 → opencode/<free-model> → 经 Zen 网关出站（美国托管）║
      ║ 隐私边界：免费模型数据用于改进训练，local-only 永不走此路径 ║
      ╚══════════════════════════════════════════════════════════╝
```

### 4.3 模块划分

| 模块            | 职责                                                                           | 输入                      | 输出                        | 依赖             |
| ------------- | ---------------------------------------------------------------------------- | ----------------------- | ------------------------- | -------------- |
| M1 workspace  | 建区/同步/归档（tar+scp 推拉 + .agentsync 过滤）                                         | proj 名, .agentsync      | 站上工作区目录                   | scp/ssh        |
| M2 task       | 全链编排：sync→lock→run→collect→unlock                                            | 任务卡/命令行参数               | .agent-run.json + out/ 产物 | M1, M3, M4, M5 |
| M3 router     | 模型→CLI→站映射 + sensitivity 三档 + 拒绝规则 + **sanitized 前置 scrubber（Review F2 补充）** | model, sensitivity, cli | 目标站+调用参数                  | §9.4 表（编译进代码）  |
| M4 lock/state | flock 获取/释放 + 状态机（孤儿检测）                                                      | 工作区路径                   | 锁句柄/状态文件                  | ssh            |
| M5 collect    | out/ 整包回收 + git diff 拉回                                                      | 工作区路径                   | 主控站产物目录                   | tar+scp        |

### 4.4 数据流（task 单次执行）

```
任务卡解析 → M3 路由（sensitivity 检查 → model→站映射 → 调用参数拼装）
  → M1 sync（tar 排除 .agentsync → scp → 解包; 首次则 --create 建区）
  → M4 取锁（flock; 失败→报占用者 PID 退出）
  → M4 写状态 running{pid, ts, task_id}
  → ssh 执行（脚本落盘铁律 R14: 本地生成远端脚本→scp→bash）
     opencode: echo "<prompt>" | opencode run -m <model> --format json
     [prompt 注入: [proj:<name>] 前缀 + audit 契约(audit:true 时)]
  → ⑤ 契约归一 .agent-run.json 落 out/（§6.2 schema）
  → M5 collect（out/ tar+scp 拉回主控站 <proj>/agent-out/<ts>/）
  → M4 写状态 done + 释放锁
  → 本地台账 agent-runs.log 追加一行（G13 观测）
```

### 4.5 控制流（异常路径）

- **锁占用**：立即退出（退出码 3），报占用者 PID/任务 ID

- **超时**（默认 900s 可配）：kill 远端进程 → 状态写 failed{reason:timeout} → 释放锁

- **失败重试**：仅网络类失败（ssh 断）自动重试 1 次；模型输出失败不重试（转人工）——总计 ≤2 次尝试（Codex 二段式语义，§9.7.2）。**适配注记（Review F7）**：Codex 原语义是"沙箱拒绝→恰好一次去沙箱升级重试"；本设计无沙箱概念，故把"升级尝试"重释为"仅网络类失败重试"，模型/文件系统失败直接转人工——语义等价（都不无限重试）、更贴合 CLI 场景，非调研结论偏差

- **孤儿检测**：task 启动时若见 running 态且 PID 不存活 → 标记 orphaned 归档 out/（不删除）→ 重新取锁

- **sensitivity: local-only + 免费/远端 model 参数**：M3 直接拒绝（退出码 4），无覆写通道（owner 策略不可升级绕过语义，§9.7.2）

## 5. 接口定义

### 5.1 命令面（PowerShell agent-cli.ps1）

```powershell
# MVP 两命令（G1 范围）
agent-cli workspace <proj> [--create | --sync | --archive]   # M1
agent-cli task <proj> [--card <task.md>] [--model <m>] [--cli auto|opencode]
    [--sensitivity public|sanitized|local-only] [--timeout <s>] [--attach <f>...]
    # = sync→lock→run→collect 单命令（M2 全链）

# 二期（本文档定义，不在 MVP 实施）
# agent-cli collect <proj> [--out-only]
# agent-cli review <proj> --peer [--card <task.md>]
# agent-cli task --continue <session_id>（路由规则按 §9.6-2 决策表）
```

**M3 拒绝规则**（编译期固定）：

- `--model` 缺失且任务卡无 `model` 字段 → 拒绝（退出码 2，防默认漂移，§9.1-3）

- `sensitivity: local-only` + model ∈ {opencode/\*} → 拒绝（退出码 4）

- model 不在 §9.4 路由表 → 拒绝（退出码 2）

- **sanitized 前置**（Review F2 补充）：`sensitivity: sanitized` 时 M3 先跑机械 scrubber（regex + gitleaks，§2.1 敏感路由定义），命中即拦截并报脱敏项；**未通过 scrubber 的任务绝不进入远端路径**（消毒正确性是机械可验证门禁，非 LLM 自查）

### 5.2 远端执行脚本契约（R14 铁律）

wrapper 不拼 ssh 内联命令；本地生成 `/tmp/agent-cli-run-<ts>.sh` → scp → `ssh host 'bash /tmp/...'`。脚本内容含：cd 工作区 → flock 等价（flock 命令行）→ 状态写 → stdin 管道调用 opencode（铁律 1）→ JSON 落盘。

## 6. 数据结构

### 6.1 任务卡 schema（Markdown front-matter，随 sync 进工作区）

```yaml
---
proj: paper
task: 一句话目标
model: nemotron | gpt-oss | lightning | ultra | free-1m   # 必填（M3 拒绝规则）
cli: opencode | auto                                     # MVP 仅 opencode 路径
sensitivity: public | sanitized | local-only              # 默认 public
audit: true | false                                       # true 时 prompt 尾注 assertion-audit 契约
readonly: true | false                                    # MVP 仅记录（4.1 层2）
timeout_s: 900                                            # 可选覆盖
accept:                                                   # 验收判据（可执行）
  - python -m pytest paper_cli/tests/ -q
---
## 任务描述
（干净室：只含任务+判据，禁止预装结论/预消化证据）
```

**model 别名 → 完整 ID 映射**（对齐审计 BP-2 补，2026-09-03；别名与完整 ID 两套表示在此统一，M3 路由与拒绝规则按完整 ID 判定）：

| 别名（任务卡/命令行友好形式） | 完整 ID（opencode -m 实参） | 站/网关 | 依据 |
| --- | --- | --- | --- |
| `nemotron` | `cluster-litellm/nemotron` | B 站 LiteLLM | 调研 §9.4 |
| `gpt-oss` | `cluster-litellm/gpt-oss`（B 网关）或 `cluster-local/gpt-oss`（A 本地）——默认前者 | A/B | 调研 §9.4 |
| `lightning` | `opencode/nemotron-3.5-lightning-free` | Zen 免费网关 | 调研 §2.1/§9.4 |
| `ultra` | `opencode/nemotron-3-ultra-free` | Zen 免费网关 | 调研 §9.4 |
| `free-1m` | `opencode/nemotron-3-ultra-free`（1M ctx 同款）——`ultra` 语义别名，保留枚举完整性 | Zen 免费网关 | 调研 §9.4 |

M3 接受两种表示：完整 ID 直接查路由表；别名先经本表解析再查。解析失败（未知别名/未知 ID）→ 退出码 2。

### 6.2 .agent-run.json（契约归一，吸收 task-notification + Codex 遥测）

```json
{
  "proj": "paper", "task_id": "task-20260903-001",
  "cli": "opencode", "model": "cluster-litellm/nemotron",
  "sensitivity": "local-only",
  "readonly": false,
  "session_id": "<opencode session>",
  "exit_code": 0, "status": "completed | failed | timeout | orphaned",
  "content_digest": "sha256:...",           # 全文不落（防敏感内容二次落盘），摘要+站上 out/ 原文
  "usage": {"total_tokens": 0, "tool_uses": 0},  // Anthropic task-notification 字段（§9.6-2）
  "queue_s": 0, "run_s": 0,                 // Codex 分离计量（§9.7.2-5：获锁后才起 run 计时）
  "timestamp_start": "", "timestamp_end": "",
  "prompt_sha256": "", "attach": []        // Model-visible means logged（§9.8.1）：一切注入留哈希
}
```

> readonly 字段（对齐审计 BP-1 补，2026-09-03）：任务卡 §6.1 的 readonly 解析后写入本契约——MVP 仅记录（全部按排它处理，4.1 层 2 语义），V2 激活共享/排它语义时无需改 schema。

### 6.3 .agent-state.json（状态机，dsh 孤儿锁语义 §9.8.1）

```json
{"state": "running | done | failed | orphaned",
 "pid": 12345, "ts_start": "...", "task_id": "...",
 "host": "主控站名"}   // done 最后写；崩溃残留 running + 死 PID = 机械可检孤儿
```

## 7. 替代方案

### 7.1 方案 A：PowerShell wrapper + 站上 flock（选择）

- 描述：主控站薄 wrapper 编排，锁与状态在站上文件系统，agent 全在站上执行

- 优点：零常驻服务（零自加载不破坏）；锁用 OS 原语；tar+scp 全实证链；审计痕迹完整（任务卡+.agent-run.json+state 三件套）

- 缺点：PowerShell→ssh 有 R14 引用陷阱（已铁律化）；Windows 侧无原生 flock（锁全在站上，主控站不持锁——崩溃时靠孤儿检测兜底）

- 选择理由：公理 1 确定性编排的最小实现；与集群既有纪律（零自加载/tar+scp/台账）全部兼容

### 7.2 方案 B：opencode SDK 常驻 server 编排（否决）

- 描述：站上起 @opencode-ai/sdk server，主控站 client 编程调用

- 优点：编程接口丰富（会话/消息 API）

- 否决理由：**常驻 server 违反零自加载不变式②**（调研 §3.4 已定按需起停）；新增常驻进程即新增挂死面（A 站 KFD bug 族史）

### 7.3 方案 C：Anthropic coordinator 模式做编排层（否决 MVP，D7+ 候选）

- 描述：B 站 claude 开 CLAUDE\_CODE\_COORDINATOR\_MODE=1，LLM 在编排席

- 优点：零开发量；官方维护的 prompt 纪律

- 否决理由：实测仅证提示注入生效（worker spawn 未测，§9.6.1 审计标注）；LLM 编排违反公理 1；无任务卡审计痕迹（涉密场景不可用）。定位为 D7+ 单站探索型任务选项

### 7.4 方案 D：dsh（DeepSeek Harness）整体引入（否决）

- 描述：装 dsh 做编排框架

- 否决理由：TS 全栈 developer preview 声明破坏性变更；与 PowerShell wrapper 路线不同构；其价值（孤儿锁/日志不变量语义）已作为设计模式吸收而非组件引入（§9.8.1）

## 8. 错误处理

| 错误场景                          | 处理方式                             | 退出码    |
| ----------------------------- | -------------------------------- | ------ |
| 锁被占用                          | 报占用者 PID/task\_id 即退             | 3      |
| sensitivity 冲突（local-only+远端） | 拒绝，无覆写通道                         | 4      |
| model 缺失/不在路由表                | 拒绝                               | 2      |
| ssh 断连                        | 自动重试 1 次（门禁缓存不重审，Codex §9.7.2-1） | 5      |
| 超时                            | kill → failed{timeout} → 释放锁     | 6      |
| 孤儿状态（running+死 PID）           | 归档 out/ → orphaned → 允许重取锁       | 0（附警告） |
| zen 限额报错（429/quota）           | 不重试远端 → 提示切本地模型命令（降级路径定义，G13）    | 7      |

## 9. 不变式（ADD 审计依据）

1. **锁不变式**：任何 task 执行期间必持工作区 flock；done/failed 写入先于锁释放（孤儿可检测语义）
2. **路由不变式**：sensitivity: local-only 的 prompt 字节永不离开主控站→站内本地模型路径（M3 是唯一出口，编译期拒绝规则）
3. **显式模型不变式**：无 model 参数的任务永不执行（防默认漂移复现——A 站外泄教训）
4. **调用形式不变式**：opencode 只经 stdin 管道；claude 只带 `< /dev/null`（G10 规避固化）
5. **日志完备不变式**：到达 agent 的一切输入（prompt/附件/注入）在 .agent-run.json 留哈希（Model-visible means logged）
6. **单向流不变式**：主控站→站上覆盖推送仅限源文件；out/ 永不被反向推送覆盖
7. **门禁缓存不变式**：重试不重触发 audit/审批（Codex already\_approved 语义）

## 10. 幻觉排除审查（Step 4 Review）

### 10.1 设计基于已验证的调研结论

- [x] 全部设计决策引用调研章节（§3.1 表 16 行逐条可溯）

- [x] 无未标注假设：唯一假设"Bash 不锁"已显式列 V0 验证门第 5 项（审计 R6 遗产）

- [x] 真值源约定显式（头部声明：§2.1/§9.4 实测层为准——审计 R3/R11 遗产）

### 10.2 替代方案审查

- [x] 4 个替代方案，各有否决理由（7.2 零自加载冲突 / 7.3 实测边界 / 7.4 架构不同构）

### 10.3 职责边界审查

- [x] 不吞并 D5（CLI 装备）/infer-load（模型加载）/model-eval（选型）/D7（trae 对接）

## 11. 对实施的输入

### 11.1 关键工程约束（V0 验证门——试点 Paper，G2 收编+1）

| #    | 验证项                                     | 通过判据                       | 不通过改道                    |
| ---- | --------------------------------------- | -------------------------- | ------------------------ |
| V0-1 | AGENTS.md 薄壳导入（CLAUDE.md 首行 @AGENTS.md） | opencode 会话可见指令内容          | 站上双文件各自维护（止损模式）          |
| V0-2 | claude 遮蔽（personal>project）             | proj- 前缀项目技能生效             | skillOverrides 配置        |
| V0-3 | codex-memory cwd 键控在工作区场景               | 换工作区后记忆不串                  | wrapper 层强隔离（每次清 cwd 标记） |
| V0-4 | A 站记忆功能路径（G5 遗留）                        | A 站 memory\_add\_note 写入成功 | A 站任务全路由 B 站             |
| V0-5 | "Bash 不锁"假设（审计 R6）                      | 双 opencode 并行 Bash 写同目录无冲突 | Bash 调用入锁（性能损）           |
| V0-6 | flock 在 Ubuntu 跨 ssh 会话语义               | A 会话持锁时 B 会话取锁失败           | 改 mkdir 原子锁              |

### 11.2 风险与缓解

| 风险                       | 缓解                                  |
| ------------------------ | ----------------------------------- |
| PowerShell→ssh 引用陷阱（R14） | 全部远端逻辑走脚本落盘；CI 冒烟含一条端到端 task        |
| llama-server 单槽排队致超时     | timeout 默认 900s 宽裕 + queue\_s 观测定位  |
| zen 免费档限额无预警             | G13：本地 log 累计 + 降级提示（错误码 7）         |
| 站断电状态残留                  | 孤儿检测（6.3）+ out/ 归档不删                |
| .agentsync 误排除导致任务缺文件    | task 失败时 agent 报缺文件路径 → 修排除清单重 sync |

### 11.3 分期移交（本文定义接口，不在 MVP 实施）

- claude 路径 + `--continue`（G1 二期）：Continue-vs-Spawn 决策表（§9.6-2）为路由规则

- review --peer（D7+）：站间互审协议

- trae 派发（D7）：任务卡即接口（6.1 schema 冻结）

- readonly 层 2 锁（V2）：按任务卡字段细化（4.1）

- G8 环境预置（T0 独立批次）：R/CRAN noble-cran40 + sympy；wrapper 不感知，仅登记

- **.agentsync 四型模板（Review F3 移交）**：§3.1 决策引用 §7.5 已定"分四型"（Python/C++/文档/Lean4），四个模板的具体排除清单为 IMPLEMENTATION 阶段产出（M1 workspace 落地时随建）

- **后端并发探测（F1 升级项，登记待排期）**：MVP 观测先行（queue\_s 被动记录）；探测模块（调 /slots + 槽位占用则拒/等）**单独立项，随 V2/并发 fan-out 阶段实施**（触发条件：queue\_s 数据显示排队成为常态时）

- G14 升级回归三件套：agent-cli-smoke.sh + 插件加载 + 记忆读写（并入既有升级窗口流程）

***

**Review 签字**: Scott（2026-09-03 会话批准："执行吧" = 批准 v1.3 全部内容，含 F1 定案为后续升级项目） 日期: 2026-09-03
