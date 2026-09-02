# Agent CLI 跨项目调用标准与迁移复用调研

***

date: 2026-09-02（v2，场景澄清后重构：主控站多项目远程调用 + 站上独立工作区）
status: draft（D6 前期调研）
upstream: D5 Agent 生态升级（已 verified 2026-09-02）; 调研 §4.2 五层循环遗留"任务卡协议"口子
-----------------------------------------------------------------------

> **问题（澄清后）**: 主控站（Win10）上有**多个任务项目**（RPC / Article / Textbook / Coding / Open\_Data...），都需要调用 A/B 站的 4 个 agent CLI。当前缺少：① 主控站项目 → 站上 agent CLI 的**整体调用规范**；② **agent 编排规范**；③ 每个主控站项目在站上要有 **agent 独立工作文件（工作区）**——各项目的 agent 会话/记忆/产物互不污染。
> **方法**: 生态标准/官方文档直抓（E1/E2 标注）+ D5 实测基线复用（E1）+ B 站 memory.db 直查（E1）+ 同步链可用性实测（E1，本轮）。

## 0. 速览

| 问题                    | 结论                                                                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 整体拓扑？                 | **主控站 = 编排层（任务源+wrapper+归档），A/B 站 = agent 执行场**。agent CLI 全在站上跑，模型后端不出站（§1.1）                                                                                |
| 为什么"站上独立工作区"是隔离的正确单元？ | 生态机制天然挂 cwd：codex-memory 提取记忆按 **cwd 键控**（E1 memory.db 直查）；AGENTS.md/技能发现从 cwd 向上遍历；claude auto-memory 按项目目录隔离——**工作区 = 记忆/指令/技能/会话四重隔离的最小单元**（§4.1）         |
| 文件怎么同步？               | **tar+scp 推拉**（D5 全程实证路径；本轮实测主控站 Git Bash 无 rsync、站上 rsync 3.2.7 仅用于站内归档）；大项目用 `.agentsync` 排除清单控量（§5.2）                                                     |
| 工作区里放什么？              | 项目文件子集 + **AGENTS.md（指令单源）** + CLAUDE.md 薄壳（`@AGENTS.md` 导入）+ 项目技能/配置（可选）+ `out/` 产物目录（§5.1）                                                                 |
| 跨 CLI 指令单源？           | AGENTS.md 为源 + CLAUDE.md 薄壳——claude code 官方明确不原生读 AGENTS.md（#6235, 5200+ reactions, "not planned"），导入是官方推荐模式（§3.1）                                           |
| 调用入口？                 | 主控站侧 **`agent-cli`** **wrapper**（PowerShell）：`workspace / task / collect / review` 四命令族；封装同步→ssh headless 执行→产物回收全链 + 路由可达性判断（A 站 claude\@32k 不可用，R17）（§5.3） |
| 编排规范？                 | **任务卡生命周期** create→dispatch→execute→collect→archive；`audit: true` 触发 assertion-audit 断言契约；站间互审 `agent-cli review --peer`（cross-examine，对端模型）（§5.5）           |
| 记忆隔离的坑？               | 提取记忆 cwd 天然隔离 ✓；**ad-hoc 笔记全局平铺**——wrapper 必须自动加 `[proj:<name>]` 前缀（§4.1）                                                                                    |
| claude 遮蔽陷阱？          | personal > project（反直觉）——12 件用户级技能会遮蔽项目同名技能，项目技能须带前缀命名（§3.2）                                                                                                 |
| headless 最大的坑？        | claude `--bare` **跳过 CLAUDE.md/插件/记忆**——项目上下文调用禁用（§3.4）                                                                                                      |

## 1. 需求解构（澄清后主场景）

### 1.1 调用拓扑

```
主控站 Win10（编排层, 多任务项目）                A/B 站 Ubuntu（agent 执行场）
┌───────────────────────────┐
│ d:\RPC   d:\Article  ...   │  ① 工作区同步       ┌────────────────────────────────────┐
│ 项目根: AGENTS.md +         │ ─── tar+scp ────→ │ ~/agent-workspaces/<proj>/          │
│   .agentsync (排除清单)     │                    │   ├── (项目文件子集)                 │
│                           │                    │   ├── AGENTS.md + CLAUDE.md(薄壳)   │
│ agent-cli (主控站 wrapper)  │  ② ssh headless    │   ├── .claude/skills/ (可选)        │
│   workspace/task/collect/  │ ─── 执行 ────────→ │   └── out/ (产物目录, 约定)          │
│   review                   │                    │        ↓ cwd = 工作区              │
│ 任务卡 / 产物归档            │  ③ 产物回收         │   agent 会话: opencode | claude      │
│                           │ ←── tar+scp ────── │   记忆: cwd 键控自动隔离              │
└───────────────────────────┘                    │   后端: nemotron / gpt-oss (站内)   │
                                                 └────────────────────────────────────┘
```

要点：agent CLI 与模型后端全在站上（D5 装备所在）；主控站只承担任务源、wrapper 封装、产物归档三职责——**主控站不跑 agent、不起服务**（零自加载纪律不破坏）。

### 1.2 "跨会话迁移复用"的四个正交维度（远程场景）

| 维度                         | 含义            | 已有基础 (D5)                                      | 缺口                        |
| -------------------------- | ------------- | ---------------------------------------------- | ------------------------- |
| **跨时间**（会话→会话）             | 同项目隔日续作，记忆延续  | codex-memory cwd 键控（E1）、`--continue`/`-c` 会话续接 | 工作区生命周期规范（何时建/归档/清理）      |
| **跨项目**（项目↔项目）             | 多项目并行调用互不污染   | 用户级 12 技能共享、md5 对账                             | **站上独立工作区机制**（本轮核心缺口）     |
| **跨 CLI**（claude↔opencode） | 同一工作区两 CLI 生效 | `~/.claude/skills/` 双读（E1 实证）                  | 指令双源统一（AGENTS.md 薄壳模式未实测） |
| **跨站**（A↔B）                | 任务分派两站 + 互审   | 站间互审设计（调研 §8.4）、双端点                            | wrapper 路由可达性判断；A 站无记忆层   |

### 1.3 调用方矩阵

| 调用方          | 场景              | 需要的接口形态                                         |
| ------------ | --------------- | ----------------------------------------------- |
| 人（Scott）在主控站 | 多项目日常派活         | `agent-cli task`（单命令完成同步+执行+回收）                 |
| 主控站脚本/CI     | 定时批处理           | 同上 + 退出码/JSON 契约                                |
| trae（编排层）    | 五层循环派发（调研 §4.2） | 任务卡 + `audit: true` 断言契约 + `review --peer` 站间互审 |
| 人在站上（运维场景）   | 直接进工作区交互续作      | TUI + `-c` 续接（工作区即 cwd）                         |

## 2. 现状基线（D5 后，E1）

- 两站 4 CLI 装备同构：12 定制技能（用户级 `~/.claude/skills/`，双 CLI 读，md5 零差异）、superpowers 6.3.0 + document-skills（claude 插件，本地镜像）、ARS @1d3032f（opencode 侧 symlink）、codex-memory 0.6.5（B 站 opencode）

- headless 已实证：`claude -p`（PONG/技能列表）、`opencode run -m`（PONG/A2 135k 附件）、`opencode run --command`（ARS 命令面）

- 后端边界（实测）：A 站 claude\@32k **不可用**（R17）；B 站 claude 走 LiteLLM nemotron + MAX\_CONTEXT\_TOKENS=120000（R15/R16）；两站 opencode 双 provider

- 窗口预算已声明：opencode limit.context（120000/30000）+ compaction

- 网络边界（实测）：B 站 github 间歇（R18）、npm 稳定、arxiv 间歇、crossref/eutils 稳定

- **同步链实测（本轮 E1）**：主控站 Git Bash **无 rsync**（which 无输出）→ 推拉定案 tar+scp（D5 已全程实证）；站上 rsync 3.2.7 可用于站内归档/清理

## 3. 生态标准与能力盘点

### 3.1 AGENTS.md：跨工具指令标准（E1 直抓 agents.md）

- 开放标准，"README for agents"；**60k+ 开源项目**采用；Linux 基金会 Agentic AI Foundation 首批项目（2025-12，与 MCP 同列）

- 原生读取方：Codex、Cursor、Amp、Copilot coding agent、Junie、opencode 等

- **claude code 不原生读 AGENTS.md**（官方 memory 文档原文 "Claude Code reads CLAUDE.md, not AGENTS.md"；#6235 5200+ reactions 仍 open，官方 "not planned for now"）

- 官方推荐互通模式：CLAUDE.md 首行 `@AGENTS.md` 导入（跨平台，导入链上限 5 跳，路径相对含导入文件的目录）；或 `ln -s AGENTS.md CLAUDE.md`（Unix，不能追加 Claude 专属内容；Windows 需管理员权限——主控站场景**不适用**，导入模式为唯一直径）

- opencode 侧：AGENTS.md 原生优先（无 AGENTS.md 时 fallback CLAUDE.md，D5 调研 §2.2 已录）；**`.agents/skills/`** **已是技能发现一等公民位置**（§3.3）

- JetBrains 调研：双文件（CLAUDE.md+AGENTS.md 各自维护）团队月均损耗 5.3h——薄壳模式是止损正解

### 3.2 claude code 项目级能力（E1 官方 skills 文档直抓）

| 层级          | 路径                               | 适用范围                           |
| ----------- | -------------------------------- | ------------------------------ |
| Enterprise  | managed settings                 | 全组织                            |
| Personal    | `~/.claude/skills/`              | 本人全部项目                         |
| **Project** | `.claude/skills/<name>/SKILL.md` | **仅本项目（=工作区）**                 |
| Plugin      | `<plugin>/skills/`               | 插件启用处（`plugin:skill` 命名空间，不冲突） |

**关键陷阱（同名遮蔽规则，反直觉）**：enterprise > **personal > project**——个人级技能**遮蔽**项目级同名技能。对本集群含义：12 件用户级技能在所有工作区出现；项目想覆盖某件**不能靠同名项目技能**，须改名（项目前缀命名）或 settings 的 skillOverrides。其他：父/嵌套目录发现（嵌套技能 `dir:name` 限定名）；live change detection（改即生效）；`.claude/commands/` 同机制但技能优先。

### 3.3 opencode 项目级能力（E1 官方 config/skills 文档直抓）

**配置优先级**（后覆盖先）：Remote（.well-known）→ Global（\~/.config/opencode/opencode.json）→ `OPENCODE_CONFIG` env → **Project（项目根 opencode.json，标准源中最高）**；启动时从 cwd 向上遍历到 git 根找配置——**工作区根放 opencode.json 即项目级生效**。

**技能发现 6 位置**（项目级从 cwd 遍历到 git 根）：

| 级  | 位置                                                                       |
| -- | ------------------------------------------------------------------------ |
| 项目 | `.opencode/skills/` / `.claude/skills/` / **`.agents/skills/`**          |
| 全局 | `~/.config/opencode/skills/` / `~/.claude/skills/` / `~/.agents/skills/` |

**per-skill 权限模式**（工作区 opencode.json）——项目技能子集化的现成机制：

```json
{ "permission": { "skill": {
    "*": "allow", "internal-*": "deny", "experimental-*": "ask" } } }
```

（allow 立即加载 / deny 对模型隐藏 / ask 提示；通配符；可按 agent 覆盖。）

### 3.4 headless / 程序化调用能力（E1 官方文档直抓 + D5 实测）

**claude code**（`claude -p`，B 站）：`--output-format text|json|stream-json`（json 含 result/session\_id/metadata/cost）；`--bare` **跳过 hooks/插件/auto-memory/CLAUDE.md**（⇒ 项目上下文调用禁用）；逐调用注入面 `--settings`/`--mcp-config`/`--agents`/`--plugin-dir`/`--append-system-prompt(-file)`/`--allowedTools`；`--continue`/`--fork`；stdin 管道上限 10MB；退出码语义明确；SIGTERM 后 resume 续未完回合；Python/TS Agent SDK。

**opencode**（`opencode run`，两站）：`--command <name> -- <args>`（ARS 已实证）、`--format json`、`-f <file>` 附件（A2 已实证）、`-c`/`-s <id>`/`--fork`、`--dir`、`--attach`（接运行中 server）；**SDK** `@opencode-ai/sdk`（`createOpencode()` 起 server+client，默认 4096；client-only 模式）——常驻 server 与零自加载不变式②冲突，维持**按需起停**。

## 4. 跨会话记忆机制实测（E1，B 站直查）

### 4.1 codex-memory 的隔离真相（工作区隔离的机制基础）

memory.db（B 站，sqlite 只读直查）表结构：

| 表                            | 键                                                                       | 隔离性                                        |
| ---------------------------- | ----------------------------------------------------------------------- | ------------------------------------------ |
| `memory_stage1_outputs`      | **含** **`cwd`** **列**（session\_id/raw\_memory/rollout\_summary/cwd/...） | **提取记忆按工作区 cwd 键控**（天然隔离）                  |
| ad-hoc 笔记（memory\_add\_note） | 文件落 `memories/extensions/ad_hoc/notes/*.md` **全局平铺**                    | **无项目隔离**——A5 验证的 D5 笔记（/tmp cwd 写入）任何项目可读 |
| `memory_session_meta`        | session\_id + memory\_mode + polluted                                   | 会话级元数据                                     |

**结论**：工作区（cwd）= 记忆/指令/技能/会话四重隔离单元，但有两个补丁要做——① ad-hoc 笔记无隔离：**wrapper 层自动加** **`[proj:<name>]`** **文本前缀**（agent-cli 注入到 prompt 约定）；② 记忆只在 B 站（A 站无 codex-memory）——**B 站 = 记忆主站**写进路由规则。

### 4.2 会话续接面

- claude code：`--continue`/`--fork` + session 元数据（json 输出含 session\_id）

- opencode：`run -c`/`-s <id>`/`--fork`；SDK 可编程操作会话

- claude auto-memory（`~/.claude/projects/<proj>/memory/`）按项目目录隔离——与工作区模型同构

## 5. 标准规范草案：RPC Agent 调用与编排标准（建议名 d6-agent-standard）

### 5.1 L0 工作区规范（每项目在站上的独立工作文件）

**位置**：`~/agent-workspaces/<proj>/`（两站同构；`<proj>` = 主控站项目目录名小写）

```
~/agent-workspaces/<proj>/
├── AGENTS.md          # 指令单一源（从主控站项目根同步, 唯一编辑点在主控站）
├── CLAUDE.md          # 薄壳: 首行 @AGENTS.md + Claude 专属追加(≤10行)
├── .claude/skills/    # 项目技能(可选; 命名带 proj- 前缀防用户级遮蔽)
├── opencode.json      # 项目配置(可选; skill permission 子集/provider 覆盖)
├── .agentsync         # 同步排除清单(在主控站项目根维护, git 提交)
├── out/               # 产物目录(约定; 回收対象=此目录+git diff)
└── (项目文件子集)
```

**生命周期**：`create`（首次同步建区）→ `sync`（增量推送）→ `run`（headless 执行, cwd=工作区）→ `collect`（产物回收）→ `archive`（可选归档: tar 时间戳快照 + 清理, 记忆留站上 cwd 键控不删）。

**规则**：AGENTS.md 唯一编辑点在主控站项目根（站上是部署产物, 同 station-bin 约定）；工作区不建 git 仓库（避免与主控站 git 双源——产物靠 out/ + diff 回收, 主控站侧重新 commit）。

### 5.2 L1 同步链规范

| 环节   | 机制                                                                                     | 依据                                      |
| ---- | -------------------------------------------------------------------------------------- | --------------------------------------- |
| 推送   | 主控站 tar（按 .agentsync 排除）→ scp → 站上解包                                                   | D5 全程实证；主控站无 rsync（E1 本轮）               |
| 排除清单 | `.agentsync`（语法同 .gitignore 语义）——默认排除 `node_modules/ .git/ *.duckdb __pycache__/ out/` | 大项目（Textbook/Coding）控量刚需                |
| 回收   | `out/` 目录整包 + `git diff`（工作区有 git 时）tar → scp 拉回                                       | 双通道：约定产物 + 源码修改                         |
| 冲突   | **单向流**（主控站→站上覆盖推送仅限源文件; out/ 不被覆盖）——不做双向合并                                            | 简化优先; 源码修改走 diff 回收→主控站 review 后 commit |

### 5.3 L2 agent-cli wrapper 规范（主控站侧, PowerShell）

```
agent-cli workspace <proj> [--create|--sync|--archive]      # L0/L1 封装
agent-cli task <proj> --model nemotron|gpt-oss [--cli auto|claude|opencode]
                   [--card <task.md>] [--attach <file>...] [--continue <sid>]
                   [--timeout <s>]                           # = sync→run→collect 单命令
agent-cli collect <proj> [--out-only]                        # 手动回收
agent-cli review <proj> --peer [--card <task.md>]             # 站间互审
```

**wrapper 内建规则**（吸收 D5 全部实测坑）：

1. **路由可达性**：`gpt-oss + claude` 组合直接拒绝（R17）；模型→CLI→站映射：nemotron→B 站（记忆主站）优先；gpt-oss→A 站 opencode
2. **CLI 分派**：默认 opencode（长上下文/ARS/技能面完整）；claude 仅 B 站短任务
3. **headless 封装**：项目上下文**不用** **`--bare`**；`--output-format json`（claude）/ `--format json`（opencode）→ 归一化契约 `{proj, cli, model, session_id, exit_code, content, duration_s}`（JSON 落 `out/.agent-run.json`，幂等可追溯）
4. **笔记命名空间**：task prompt 自动前缀 `[proj:<name>]`（§4.1 补丁）
5. **PowerShell→ssh 铁律**：远端命令一律本地写脚本→scp→执行（R14 三次实证）
6. **二进制全路径**注入（A/B 站路径差异已台账化, 手册 §2a.4）

### 5.4 L3 任务卡与断言契约

任务卡（task.md，主控站编写，随 sync 进工作区）：

```markdown
---
proj: <name>
task: <一句话目标>
audit: true          # 触发 assertion-audit 断言契约
model: nemotron      # 建议; wrapper 可覆写
accept:              # 验收判据(可执行/可核验)
  - <判据1>
  - <判据2>
---
## 任务描述
...（干净室: 只含任务+判据, 禁止预装结论/预消化证据, #704 规范）
```

`audit: true` 时 wrapper 在 prompt 尾部注入 assertion-audit 契约（断言表+证据等级+证明力边界声明），产物验收走 cross-examine。

### 5.5 L4 编排规范（多 agent 协作）

- **单任务**：`agent-cli task`（上述全链）

- **串行流水**：任务卡 A 产物 → 任务卡 B 附件（wrapper 链式, 同工作区续接 `-c`）

- **站间互审**：`agent-cli review --peer`——产出方模型与审查方模型强制异站异构（nemotron 产出→gpt-oss 审, 反之亦然; adlc trust-root tier 同构实证, 调研 §8.4）——cross-examine 干净室协议

- **并行 fan-out**：多任务卡×多工作区（读密集并行, 调研 §2.3 共识③; 写密集单线程）

- **编排方**：人（命令行）或 trae（五层循环第 2 层派发——任务卡即接口, D6 先打通人肉路径, trae 对接列 D7）

## 6. 缺口清单与 D6 建议

| #  | 缺口                                                             | 严重度 | D6 处置建议                                                                                                  |
| -- | -------------------------------------------------------------- | --- | -------------------------------------------------------------------------------------------------------- |
| G1 | agent-cli wrapper 未实现（L2 核心）                                   | 高   | D6 主体：PowerShell MVP——`workspace --create/--sync` + `task`（单模型 opencode 路径）先行；claude 路径与 `--continue` 二期 |
| G2 | 工作区规范未实测（AGENTS.md 薄壳导入行为/claude 遮蔽/codex-memory cwd 键控在工作区场景） | 高   | D6 V0 验证门：用 d:\RPC 自身当试点项目（AGENTS.md 已有雏形）建首个工作区实测                                                       |
| G3 | ad-hoc 笔记无隔离                                                   | 中   | wrapper `[proj:]` 前缀注入（L2-4）+ 手册纪律                                                                       |
| G4 | 大项目同步量（Textbook/Coding 全量推不现实）                                 | 中   | `.agentsync` 默认模板 + 首同步大小预警（wrapper 检查 tar 体积, >200MB 拒绝并提示补排除清单）                                        |
| G5 | A 站无记忆层                                                        | 低   | 路由规则内建"记忆主站=B 站"；A 站 codex-memory 复制试点列 P2                                                               |
| G6 | 提取记忆路径（6h 闲置）未测（D5 §7-4 遗留）                                    | 低   | 工作区日常使用自然覆盖                                                                                              |
| G7 | trae 派发对接（五层循环 2→3 层）                                          | 低   | D7 范围; D6 留任务卡接口                                                                                         |

**建议路径**：本调研（RESEARCH）→ Scott review → D6 spec（DESIGN→IMPLEMENTATION→CHECKLIST）。D6 范围 = agent-cli MVP（workspace+task 两命令, opencode 单路径）+ 试点工作区（d:\RPC 或小项目）+ G2 验证门；claude 路径/`--continue`/review --peer/trae 对接按缺口分期。

## 参考源

- [agents.md](https://agents.md)（标准主页, E1 直抓 2026-09-02）

- [Claude Code: Run programmatically/headless](https://code.claude.com/docs/en/headless)（E1 直抓: --bare/--output-format/注入面/退出码/10MB/SDK）

- [Claude Code: Skills](https://code.claude.com/docs/en/skills)（E1 直抓: 四级层级/遮蔽规则/嵌套发现）

- [Claude Code memory docs + AGENTS.md 立场（"not planned", #6235）](https://code.claude.com/docs/en/memory)（E2, 经 yurukusa field guide 2026-06-03 核对转述 + #34235 issue 直抓佐证）

- [opencode: Config](https://opencode.ai/docs/config/)（E1 直抓: 优先级/project 最高/向上遍历）

- [opencode: Skills](https://opencode.ai/docs/skills/)（E1 直抓: 6 发现位置/permission 模式/名称规则）

- [opencode: SDK](https://opencode.ai/docs/sdk/)（E1 直抓: createOpencode/client-only/4096）

- B 站 memory.db 直查 + memories/ 目录布局（E1, 2026-09-02）

- 主控站/站上 rsync 可用性实测（E1, 本轮 2026-09-02: 主控站 Git Bash 无, 站上 3.2.7）

- D5 交付物（E1）: CHECKLIST §3/§6 台账、手册 §2a、ars-migrate-verify.sh / a5-nextday-verify.sh 实测记录

- JetBrains 2025 调研（双文件维护损耗月均 5.3h; E2 转述）

