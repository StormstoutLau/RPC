# Agent CLI 跨项目调用标准与迁移复用调研

***

date: 2026-09-03（v3.3，增补五：Codex orchestrator/parallel 逆向分析——G11 定案 RwLock 双层锁 + 五段流水升级重试 + 双源对照表（Anthropic 语法/Codex 法律/D6 合并）；v3.2：Anthropic coordinator 模式逆向分析（泄漏源码 E1 直读 + B 站实测门禁已开）——八条可借鉴模式；v3.1：模型分层路由四档实测 + 协同充分性自审（G11-G14）；v3：四项目实例场景适配 + 开源编排案例对照 + 4 CLI 实测定版；v2：场景澄清后重构：主控站多项目远程调用 + 站上独立工作区）
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

## 2. 现状基线（D5 后，E1；2026-09-02 晚增补 CLI 定版实测）

- 两站 4 CLI 装备同构：12 定制技能（用户级 `~/.claude/skills/`，双 CLI 读，md5 零差异）、superpowers 6.3.0 + document-skills（claude 插件，本地镜像）、ARS @1d3032f（opencode 侧 symlink）、codex-memory 0.6.5（B 站 opencode）

- headless 已实证：`claude -p`（PONG/技能列表）、`opencode run -m`（PONG/A2 135k 附件）、`opencode run --command`（ARS 命令面）

- 后端边界（实测）：A 站 claude\@32k **不可用**（R17）→ 已被后续修复推翻（见下）；B 站 claude 走 LiteLLM nemotron + MAX\_CONTEXT\_TOKENS=120000（R15/R16）；两站 opencode 双 provider

- 窗口预算已声明：opencode limit.context（120000/30000）+ compaction

- 网络边界（实测）：B 站 github 间歇（R18）、npm 稳定、arxiv 间歇、crossref/eutils 稳定

- **同步链实测（本轮 E1）**：主控站 Git Bash **无 rsync**（which 无输出）→ 推拉定案 tar+scp（D5 已全程实证）；站上 rsync 3.2.7 可用于站内归档/清理

### 2.1 4 CLI 定版实测（2026-09-02 晚，`ops/station-bin/agent-cli-smoke.sh` 4/4 PASS）

| CLI                  | 路由                                       | 实测                   | 关键调用铁律                                                                                                      |
| -------------------- | ---------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------- |
| B-claude (2.1.258)   | LiteLLM(4000)→nemotron                   | **PASS** 热缓存 30-120s | **`< /dev/null`** **显式关闭 stdin**（否则可能长时间等 stdin）；冷缓存 \~20min（33k 系统提示预填，8 专家 CPU 卸载），首次调用需预热或接受慢启动          |
| B-opencode (1.18.25) | LiteLLM→nemotron/gpt-oss                 | **PASS**             | **必须 stdin 管道形式** `echo "<prompt>" \| opencode run -m <model>`——位置参数形式挂死（init 后无任何 LLM 调用，日志实证；1.18.25 bug） |
| A-claude (2.1.258)   | 直连本机 llama-server(8080) gpt-oss          | **PASS** 3s          | 同 `< /dev/null`；**CLAUDE\_CODE\_DISABLE\_TOOLS=1 = 纯文本模式无工具调用**（A-claude 只适合文本任务，文件级 agent 任务走 opencode）    |
| A-opencode (1.18.25) | cluster-litellm(10.10.10.2:4000)/gpt-oss | **PASS**             | 同 stdin 管道形式；provider 三件套 lm-studio-local(禁)/cluster-local/cluster-litellm                                  |

- 主控站 ssh 调度链路全程畅通（冒烟脚本从主控站发起，heredoc 传远端脚本规避 PowerShell 引用陷阱——R14 铁律在 ssh 场景的等价形式：**远端命令一律** **`ssh host 'bash -s' <<'EOF'`** **或脚本落盘**）

- **配置漂移 2 处（本轮发现并修复，均留 .bak）**：① A 站 opencode 无默认 `model` 键 → 默认解析到**外网免费模型 nemotron-3-ultra-free**（prompt 外泄 + 外部依赖）→ 先钉 `"model": "cluster-local/gpt-oss"`（本地直连），**当晚用户决策"免费做默认+本地备选"后改为** **`opencode/nemotron-3.5-lightning-free`**（两站统一，实测 B 15s / A 20s 最稳；隐私纪律：敏感内容显式 -m 走本地——免费模型数据用于改进训练，官方 Privacy 节明文）；② B 站 claude settings 缺 `CLAUDE_CODE_MAX_CONTEXT_TOKENS=120000`（台账记录应有而实缺）→ 已恢复写入

- **免费模型实测（Zen 网关，两站 2026-09-02）**：5/6 可用（nemotron-3-ultra-free 1M ctx / nemotron-3.5-lightning-free 262k / ling-3.0-flash-fin-free 金融版 / mimo-v2.5-free / big-pickle stealth）；**muse-spark-contributor-free 两站均地区封锁（中国 IP）**；全免费 $0 无 key、限时提供、每日限额未文档化（非官方源称 \~100 请求/天，E3）

- **Qwen OAuth 插件实测（B 站 2026-09-02，装后即删）——链路已死，勿重试**：`opencode-qwencode-auth@1.3.0`（gustavodiasdev 主版本，npm 末次发布 2026-02-12）安装正常、provider 注册正常（qwen-code/coder-model 等 4 模型）、device code 端点仍发码，但**授权闭环不可达**——证据链五重：① `/authorize` 同意页已下线（用户已登录状态下打开 `chat.qwen.ai/authorize?user_code=...&client=qwen-code` 两轮均跳回聊天主页，同意 UI 不存在）；② token 端点轮询返回 **504 Gateway Time-out**（alibaba-ga 网关层）；③ 官方 qwen-code 文档明文"Qwen OAuth free tier was discontinued on **2026-04-15**"，`/auth` 菜单已移除该选项，官方引导转向 Coding Plan/API Key；④ 插件 issue #14 社区确认停用（2026-04-23）；⑤ 常量溯源：插件 client\_id（`f0304373...`）即原 qwen-code CLI 公共 ID，端点为逆向所得而非官方合作。**结论：免费 Qwen 档不可用；若需 Qwen 走官方 Alibaba Cloud Coding Plan（$ 月费订阅制，opencode 侧自定义 provider 接 DashScope 端点）**。插件已回滚移除（配置恢复 codex-memory 单插件，默认模型回归 lightning，冒烟 OK）。

- **敏感内容路由（"转述学术格式"诉求的落档结论）**：转述/学术化只保护**标识符**（凭据/路径/文件名，机械脱敏可解），不保护**思想**（未发表方法论/因子逻辑/新定理——学术格式化恰是蒸馏成最可复用训练语料的形式，泄露面与格式无关）。正解是任务卡 `sensitivity` 三档硬路由（wrapper 层机械执行，不依赖 LLM 自查）：`public`（已发表/通用编程 → 免费档）→ `sanitized`（机械 scrubber 正则+gitleaks 脱敏后走远端）→ `local-only`（强制 -m 本地模型，wrapper 拒绝远端路由）。与 Spec\_Workflow 哲学同构：机械可验证的门禁优于依赖人的转述纪律。

- 推论：**wrapper 必须永远显式** **`-m`** **指定模型**（防默认漂移复现 + 敏感内容路由控制）；免费默认只覆盖"人在站上裸调用"场景

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

| #   | 缺口                                                             | 严重度       | D6 处置建议                                                                                                                                                             |
| --- | -------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1  | agent-cli wrapper 未实现（L2 核心）                                   | 高         | D6 主体：PowerShell MVP——`workspace --create/--sync` + `task`（单模型 opencode 路径）先行；claude 路径与 `--continue` 二期                                                            |
| G2  | 工作区规范未实测（AGENTS.md 薄壳导入行为/claude 遮蔽/codex-memory cwd 键控在工作区场景） | 高         | D6 V0 验证门：用 d:\RPC 自身当试点项目（AGENTS.md 已有雏形）建首个工作区实测                                                                                                                  |
| G3  | ad-hoc 笔记无隔离                                                   | 中         | wrapper `[proj:]` 前缀注入（L2-4）+ 手册纪律                                                                                                                                  |
| G4  | 大项目同步量（Textbook/Coding 全量推不现实）                                 | 中         | `.agentsync` 默认模板 + 首同步大小预警（wrapper 检查 tar 体积, >200MB 拒绝并提示补排除清单）                                                                                                   |
| G5  | A 站无记忆层                                                        | ~~低~~ 已解除 | P1 批次 L6 已装 A 站 codex-memory（两站记忆层同构, 2026-09-02）；本轮实测 A 站 opencode.jsonc 含 plugin 条目佐证。路由仍以 B 站为记忆主站不变                                                             |
| G6  | 提取记忆路径（6h 闲置）未测（D5 §7-4 遗留）                                    | 低         | 工作区日常使用自然覆盖                                                                                                                                                         |
| G7  | trae 派发对接（五层循环 2→3 层）                                          | 低         | D7 范围; D6 留任务卡接口                                                                                                                                                    |
| G8  | 站上无 Mathematica / R 环境（Auto\_Prover 注入点 B/D、Cpp\_Hub R 基准对拍需要） | 中         | 降级矩阵（注入点留主控站执行 / R 基准转 Python 复算）或站上 apt 预置 r-base（v3 §7）                                                                                                           |
| G9  | 重资产预置策略（Cpp\_Hub third\_party、Auto\_Prover mathlib/.lake 缓存）   | 中         | `.agentsync` 排除 + 站上一次性 tar 预置（不计入常规同步量）（v3 §7）                                                                                                                     |
| G10 | opencode 位置参数 bug（1.18.25 实证）上游未报/未修                           | 低         | wrapper 已规避（stdin 管道形式）；升级窗口评估时回归验证该行为是否修复                                                                                                                          |
| G11 | **并发与互斥**：同工作区双写无锁协议；llama-server 单槽下多任务排队未测（v3 §9.5）          | **高**     | **方案定案（双源合并）**：工作区级 flock（粗）+ 任务卡 readonly 字段（细，Codex RwLock 模式 §9.7-1）双层；MVP 先工作区级。Anthropic 官方纪律独立验证 + 文件集粒度细化（§9.6-2）。Bash 调用不锁（CLI 内部序列化，exec\_command=true 先例） |
| G12 | 失败恢复：任务中断状态残留/续跑未定义（v3 §9.5）                                   | 中         | 任务卡状态机 + wrapper 幂等回收；进 wrapper MVP 需求                                                                                                                              |
| G13 | 成本/额度观测：zen 日限额无预警（v3 §9.5）                                    | 中         | wrapper 本地 log 记调用次数；限额触发降级路径（→本地档）定义                                                                                                                               |
| G14 | 版本协同矩阵：升级回归面未清单化（v3 §9.5）                                      | 低         | 升级窗口回归三件套：agent-cli-smoke.sh + 插件加载 + 记忆读写（与 G10 合并）                                                                                                                |

**建议路径**：本调研（RESEARCH）→ Scott review → D6 spec（DESIGN→IMPLEMENTATION→CHECKLIST）。D6 范围 = agent-cli MVP（workspace+task 两命令, opencode 单路径）+ 试点工作区（d:\RPC 或小项目）+ G2 验证门；claude 路径/`--continue`/review --peer/trae 对接按缺口分期。

## 7. 四项目实例场景适配（v3 增补，E1 目录结构 + 关键文档直读）

> 用户主控站四个真实开发实例——D:\Paper、F:\Spec\_Workflow、F:\Auto\_Prover、F:\Cpp\_Hub——分别代表四类典型 agent 任务形态。逐一分析"agent 在站上干什么活、同步什么、怎么验收、缺什么环境"。

### 7.1 D:\Paper（paper2kg）— 数据密集型 Python CLI，机械验收齐备

**性质**：论文 PDF 知识库工具（扫描/分类/重命名/GROBID 抽取/arXiv-CrossRef 元数据 fallback）+ pilot\_distill 数学技能蒸馏（多 LLM NLI 等价验证 + Lean4 spot 检查）。Python 3.10+，pyproject 管理，**177 个 pytest**。

**agent 场景**：① 分类规则迭代（YAML 规则 + 测试回归）；② pilot\_distill 的"LLM 生成 → 独立验证"循环（NLI 等价、数值复算 d2\_numerical\_replication）——本身就是断言契约的样板间。

**适配**：

- 同步轻：源码 + rules YAML 体积小；`raw_md/`、`new_papers/` 论文正文目录按 `.agentsync` 排除（按需附指定文件）

- **机械验收判据现成**：任务卡 `accept: python -m pytest paper_cli/tests/ -q`（177 例秒级）

- 依赖边界：GROBID 需 Docker（站上无）→ phase2 抽取功能降级；arXiv API 间歇（B 站网络边界）→ 元数据 fallback 链有文件名兜底，天然容错

- 模型分工：分类/整理类读密集任务 → gpt-oss 速度档；蒸馏质量评估 → nemotron 长上下文

### 7.2 F:\Spec\_Workflow — 方法论母体（给 agent 立法，不被 agent 执行）

**性质**：纯文档仓库（无源码无构建）：10 步 Spec 流程宪法 + 四件套模板 + 6 份 ADR + 断言 A/B/C 分级 + M7 证据账本（方法论自实证）。

**agent 场景**：它不是"被调用的执行对象"，而是**调用标准本身的宪法来源**——

- 任务卡生命周期 ↔ 10 步流程的 Review 门禁

- `audit: true` 断言契约 ↔ ASSERTION\_EVIDENCE\_FRAMEWORK

- 站间互审 ↔ 异构基座复审（M7 第 4 条复发规律：审计修正自身含计数错误，异基座复验才能发现）

- **所有工作区的 AGENTS.md 骨架应从 SPEC\_PROCESS.md + spec/templates/ 衍生**（模板即 agent 指令的标准化产物）

**适配**：纯 md 同步零成本；机械验收 = 文档契约 DC1-DC4 校验（dc\_validator.py 已有）。**这是四项目中唯一"agent 读它、而非它用 agent"的——D6 wrapper 的验收协议直接复用其分级体系**。

### 7.3 F:\Auto\_Prover（proof\_pipeline）— 已自建编排层的多 LLM 流水线（最复杂案例）

**性质**：自动定理证明 6 阶段流水线（知识检索→NL→LaTeX 多 LLM 独立翻译+共识→数值证伪→Lean4 翻译→agentic proving）+ 6 个 MCP server + Mathematica 桥 + ATLAS 桥（subprocess stdin/stdout JSON 协议）。

**agent 场景**——本项目**已经自建了 mini 编排层**，是 D6 标准最重要的先例：

- `model_gateway.py` 定义 4 模型角色（orchestrator/reasoner/tactician/auxiliary）——与集群双端点**天然对齐**：reasoner→nemotron（120k 窗口长推导），tactician→gpt-oss（高频低延迟 tactic 采样，Pass\@k 并行）

- Stage 1"3-5 个 LLM 独立翻译 + 交叉验证共识度"= **站间互审的天然需求方**（nemotron 翻译 → gpt-oss 复核，异构模型族）

- Stage 3b Lean4 REPL 逐步执行 = 执行锚定（机械验证先于 LLM 判断）的完整实例

- agent\_runner.py 的 stdin/stdout JSON 协议 = 轻量 agent 接口的现成参考（MCP 归调用方、CLI 归被调用方——O7 决策方案 B2）

**适配**：

- Mathematica 桥站上不可用（Linux 无授权）→ 注入点 B/D（FindInstance/verify\_latex\_identity）降级或留主控站执行（G8）

- Lean4 工具链重资产：mathlib 编译缓存 `.lake/` 极大 → `.agentsync` 排除 + 站上一次性预置（G9）

- MCP servers（Python）站上 uv 可装；128G 统一内存正好跑 lake build 循环

- **双向编排**：主控站 Trae ↔ 站上 agent CLI ↔ proof\_pipeline MCP servers——D6 任务卡需要预留"工具型 MCP 挂载"位

### 7.4 F:\Cpp\_Hub — 编译密集型 C++ 库（吃满站上算力）

**性质**：C++ 量化金融库（8 Phase + ADR + 基准对齐：R/Stata/论文基准 1e-10 容差三源交叉验证）+ pybind11 + CUDA GPU MC。

**agent 场景**：LLM 生成初稿（阶段 1）→ 站上编译 + ctest 回归（阶段 2 基准对齐是护城河）——**编译任务正好利用 A/B 站 16 核 + 128G 统一内存，比主控站 Win10 快**；三源交叉验证策略已制度化 = 任务卡 accept 判据样板（`cmake --build && ctest` + 基准对齐脚本）。

**适配**：

- `third_party/`（Eigen 全量 + autodiff + BLAS）体积大 → `.agentsync` 排除 + 站上一次性 tar 预置（G9）

- R 基准脚本（fixtures/\*.R 生成 baseline .inc）→ 站上需 r-base（G8，apt 可装）；CUDA GPU MC → 站上是 AMD 集成显卡，**CUDA 不可用 → gpu\_mc.cu 排除或 HIP 移植另列任务**

- C++ 工具链（gcc/cmake）站上齐备；建议站上预置 ccache 加速增量编译

- 模型分工：代码初稿/迭代 → gpt-oss（快）；长上下文跨模块 review → nemotron（120k）

### 7.5 场景适配矩阵（汇总）

| 项目             | 任务形态              | 推荐路由                       | `.agentsync` 要点             | 机械验收判据               | 环境缺口               |
| -------------- | ----------------- | -------------------------- | --------------------------- | -------------------- | ------------------ |
| Paper          | 数据整理/规则迭代/蒸馏验证    | 读密集→gpt-oss；质量评→nemotron   | 排除 raw\_md/、new\_papers/    | pytest 177 例         | GROBID(Docker)→降级  |
| Spec\_Workflow | 文档/方法论（被读不被执行）    | 任一站                        | 纯 md 无需排除                   | DC1-DC4 契约校验         | 无                  |
| Auto\_Prover   | 多 LLM 编排/形式化/证明搜索 | 双站协作（翻译共识+互审）              | 排除 .lake/（预置）               | lake build + REPL 逐步 | Mathematica→降级（G8） |
| Cpp\_Hub       | 编译/基准对齐           | 初稿→gpt-oss；review→nemotron | 排除 third\_party/（预置）、gpu MC | ctest + 基准对齐         | R 可装（G8）；CUDA 排除   |

**矩阵推论**：四项目恰好覆盖"读密集/文档/编排密集/编译密集"四象限——D6 wrapper 的 `.agentsync` 默认模板应按此**分型四份**（Python 型/C++ 型/文档型/Lean4 型），而非单一模板。

## 8. 开源社区案例对照（v3 增补，E2 web 调研 2026-09-02）

> 41 条事实（来源见参考源 v3 增补），按"机制 ↔ 本集群对应物"提炼。目的不是照搬，而是**验证 D6 草案方向 + 吸收可落地的编排规则细节**。

### 8.1 编排规则框架

| 开源机制                           | 事实要点                                      | 对 D6 标准的启示                                                  |
| ------------------------------ | ----------------------------------------- | ----------------------------------------------------------- |
| LangGraph interrupt/checkpoint | 任意节点暂停 + 状态持久化 + `Command(resume=...)` 恢复 | 任务卡生命周期应有**显式暂停点**（人工审查位）；wrapper `--continue` 对应 resume 语义 |
| LangGraph Functional API       | Retry Policy + 任务级超时 + 工具调用前审批            | wrapper `--timeout`（已规划）+ **失败重试上限 2 次转人工**（Stripe 同款纪律）    |
| CrewAI max\_iter / max\_rpm    | 单任务迭代数与频率硬限流                              | 与本集群"长会话 <50 轮"O(N²) 纪律同构；rpm 网关已在 LiteLLM 落地               |
| AutoGen SelectorGroupChat      | LLM 动态选下一个发言者                             | **不采纳**——群聊式编排失控面大；维持本集群"编排方中心化星型分派"（确定性路由是代码不是模型）          |
| MetaGPT "Code = SOP(Team)"     | 结构化中间产物（PRD/数据结构/API）抑制级联幻觉               | 与 Spec\_Workflow 四件套**同一哲学**；任务卡 = 结构化交接单元（第三方独立印证方法论方向）    |

### 8.2 自动化科研流水线

| 案例                         | 事实要点                                                                                                         | 对 D6 标准的启示                                                              |
| -------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| AI Scientist v1/v2（Sakana） | 端到端四环节 + 自动评审 + Docker 沙箱 + 3600s 超时；**第三方复现（Beel & Kan）：12 实验中 5 个（42%）因编码错误失败**、幻觉数值与陈旧引用、单篇仍需 \~3.5h 人工介入 | 无人值守科研不可信；**`audit: true`** **+ 人工审收口必须有**（实证支撑）；站上工作区 = 沙箱等价物；任务级超时制度化 |
| Agent Laboratory（AMD）      | 人给 idea + 各阶段人类反馈使论文质量 +0.58（NeurIPS 评分）；检查点恢复                                                               | 五层循环"人工层"价值的第三方实证；wrapper 长任务应支持断点续跑（任务卡状态持久化）                          |
| AutoSurvey                 | 引用可溯源 + LLM evaluator 四维打分（coverage/structure/relevance/citation）                                            | 调研类任务卡的 accept 判据模板：**引用四档标注 + 可溯源**（与 E1-E5 分级同构）                      |

### 8.3 agentic coding 工程化

| 案例                                 | 事实要点                                             | 对 D6 标准的启示                                                           |
| ---------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------- |
| Claude Code subagents              | `.claude/agents/*.md` 独立上下文窗口 + description 自动委派 | 工作区隔离与 subagent 隔离**同构**（上下文边界 = 隔离单元）；站上可用 `.claude/agents/` 定义项目角色 |
| Claude Code hooks                  | 生命周期确定性脚本拦截，退出码 2 阻断工具调用                         | precommit-dc-validator 已是此模式；**任务卡验收可挂 PostToolUse 型 hook**（确定性收口）   |
| claude-code-action                 | `@claude` 触发 + actor 权限校验 + 不可信输入须用带权限检查版本       | D7 trae 派发的雏形：任务卡触发 + 身份校验；**信任边界设计**（base-action 无信任边界的前车之鉴）        |
| git worktrees 并行（官方 best practice） | 每 agent 独立 worktree + 独立分支，避免文件碰撞/上下文污染          | 站间 A/B 并行 fan-out 的 git 版；**工作区模型是其集群推广**（A/B 站 = 两个物理 worktree）     |
| Backlog.md 三检查点                    | 审 spec → 审 plan → 审 code（一任务 = 一上下文 = 一 PR）      | 任务卡 create→dispatch→collect 的人工收口对齐；**"一任务一工作区会话"纪律**                |
| Task Master                        | PRD→tasks.json 持久上下文 + 主/研究/备用三档模型               | 任务卡 JSON 化持久（wrapper 已规划）；主/备模型路由 = LiteLLM fallbacks 已落地            |

### 8.4 自托管 LLM + agent 集群（同构案例）

| 案例                                            | 事实要点                                                                  | 对 D6 标准的启示                                                                 |
| --------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| LiteLLM Router                                | 负载均衡/冷却/回退链/指数退避                                                      | **已落地**（D1 fallbacks）——方向正确                                                |
| Claude Code 自托管网关                             | 仅 ANTHROPIC\_BASE\_URL + TOKEN 双变量即可重定向                               | A-claude 实证（llama-server 原生 anthropic 端点直连）；B-claude 走网关——**双形态并存已在本集群实现** |
| OpenHands + 集群内 LiteLLM（Stripe "Minion" 模式复述） | 每 agent 独立沙箱 + 确定性编排器预取上下文 + lint 快反馈 + **重试 ≤2 次后转人工** + 输出 PR 留人工审查 | **与本集群"工作区 + 任务卡 + 人审收口"高度同构**——独立第三方验证了 D6 架构方向                           |

### 8.5 提炼：五条通用编排公理（跨案例收敛）

1. **确定性编排器 + LLM 执行者**：路由/超时/重试是代码不是模型判断（LangGraph、Stripe Minion、CrewAI max\_iter 共同指向）
2. **结构化交接抑制级联幻觉**：中间产物必须结构化（MetaGPT SOP、Spec\_Workflow 四件套、任务卡）
3. **执行锚定先于 LLM 判断**：编译/测试/基准/REPL 是验收真值源（SWE-agent ACI、Cpp\_Hub 基准对齐、Lean4 REPL）
4. **人工审查点不可全撤**：质量增益有实证（Agent Laboratory +0.58），无人值守失败率有实证（AI Scientist 42%）——审计收口是必要成本不是可选项
5. **隔离单元 = 上下文边界**：subagent/worktree/工作区/沙箱 pod 本质同构——站上工作区是本集群的隔离原语

## 9. 环境适配修订（v3 增补：对 §5 草案的 delta）

结合 §7 四项目实例 + §8 开源公理 + 本轮 CLI 实测，对 §5 标准草案追加修订：

### 9.1 L2 wrapper 规范追加（吸收 §2.1 实测铁律）

1. **opencode 调用形式**：一律 `echo "<prompt>" | opencode run -m <provider/model>`（stdin 管道；位置参数形式 1.18.25 挂死——G10）
2. **claude 调用形式**：一律 `claude -p "<prompt>" < /dev/null`（显式关 stdin）
3. **永远显式** **`-m`/模型映射**：不依赖任何站上默认模型（A 站默认曾漂移到外网模型——安全边界）
4. **B-claude 预热策略**：wrapper `task` 首次调用 B-claude 前自动发一次轻量 PING 预热（冷缓存 \~20min → 预热后 30-120s）；或任务卡声明 `coldstart: true` 接受慢启动
5. **任务级超时 + 重试上限**：默认 timeout 可配；失败重试 ≤2 次后转人工（§8.5 公理 1；Stripe 纪律）

### 9.2 L0 工作区规范追加（吸收 §7 矩阵）

- `.agentsync` 默认模板**按项目形态分四型**：Python 型（排 `__pycache__/*.egg-info/.venv/raw 数据目录`）、C++ 型（排 `third_party/build/ccache 缓存`）、文档型（几乎不排）、Lean4 型（排 `.lake/`）

- 重资产（third\_party/mathlib 缓存）走"站上一次性预置"通道，不进常规同步

- 工作区可选挂载项目 MCP server（Auto\_Prover 型项目）——任务卡预留 `tools:` 字段

### 9.3 D6 范围修订建议

原范围（agent-cli MVP + 试点工作区 + G2 验证门）维持，追加：

- wrapper MVP 直接吸收 §9.1 全部铁律（冒烟脚本 `ops/station-bin/agent-cli-smoke.sh` 已固化调用形式，wrapper 复用其远端执行模式）

- 试点项目建议从 **Paper（Python 型，验收判据现成）** 起步，第二试点 Cpp\_Hub（验证重资产预置通道）

- G8/G9 处置进 D6 DESIGN 的风险表；G10 记入升级窗口回归清单

### 9.4 模型分层路由（v3 增补三：2026-09-02 四档同题实测，E1）

**问题**：复杂任务需要切更大模型——但"更大"在哪一层？实测同一中等推理任务（概率题，4 档全对）的延迟与能力矩阵：

| 档位    | 模型                                         | 延迟 (B 站)        | 窗口     | 成本 | 定位               |
| ----- | ------------------------------------------ | --------------- | ------ | -- | ---------------- |
| 免费·快  | `opencode/nemotron-3.5-lightning-free`（默认） | **13s**         | 262k   | $0 | 日常轻任务（默认档）       |
| 免费·大  | `opencode/nemotron-3-ultra-free`           | 39s（A 站 45s 波动） | **1M** | $0 | 长文档/大代码库理解       |
| 本地·旗舰 | `cluster-litellm/nemotron`（120B-A12B）      | 38-43s          | 120k   | 电费 | 深度推理/敏感内容（数据不出站） |
| 本地·快  | `cluster-litellm/gpt-oss`（120B MXFP4）      | **18s**         | 30k    | 电费 | 代码迭代/高频调用        |

**关键事实**（实测推翻直觉）：

1. **免费档不是劣质档**——四档同题全对；zen lightning 13s 比**本地旗舰快 3 倍**（云端算力 vs 395 单卡）。"复杂任务必须切本地大模型"不成立；真正的分层轴是**窗口需求**与**隐私边界**，不是智力。
2. **本地档的不可替代价值 = 数据不出站 + 无限额**——深度任务时长会打满 zen 未文档化的日限额（E3 \~100 请求/天）；敏感内容（sensitivity: local-only）只有本地档合规。
3. **切档是显式** **`-m`** **一步的事**，无需改配置——wrapper `task --model` 字段已预留（§5.3）。

**路由规则建议**（写进 wrapper 路由表 + 手册）：

| 任务特征                      | 路由            |
| ------------------------- | ------------- |
| 默认/问答/轻整理                 | lightning（免费） |
| 单文件 >262k token / 多文件聚合分析 | ultra（免费 1M）  |
| 敏感内容 / 长会话高频打满限额 / 离线纪律   | 本地 nemotron   |
| 代码高频迭代（30k 内）             | 本地 gpt-oss    |
| 站间互审（review --peer）       | 产出方与审查方强制异档异站 |

### 9.5 agent CLI 协同调研充分性自审（v3 增补三）

**结论：已覆盖 7 层，存在 4 个真缺口（G11-G14）**。

已充分覆盖（有实测或文档依据）：

- 调用层：4 CLI 调用形式铁律 + 冒烟脚本（4/4 PASS）

- 路由层：模型→CLI→站映射 + R17 边界 + §9.4 分层路由（新）

- 隔离层：工作区四重隔离机制（memory.db cwd 键控 E1）+ `.agentsync` 四型

- 交接层：任务卡生命周期 + audit 断言契约

- 审查层：站间互审（异站异构）+ 开源五公理印证

- 同步层：tar+scp 推拉（D5 全程实证）

- 记忆层：codex-memory 两站同构 + ad-hoc 前缀补丁

**真缺口**（按严重度）：

| #   | 缺口                                                                                                            | 严重度 | 说明                                                                                     |
| --- | ------------------------------------------------------------------------------------------------------------- | --- | -------------------------------------------------------------------------------------- |
| G11 | **并发与互斥**：两 CLI 同时写同一工作区（人 TUI + wrapper task 并行）无锁协议；llama-server 单并发槽（slots=1, is\_processing 互斥）下多任务排队行为未测 | 高   | 串行流水已定义，但并行 fan-out 的写冲突与后端排队是真实风险；D6 wrapper MVP 须内建工作区锁（flock）+ 后端并发探测               |
| G12 | **失败恢复**：任务中断（ssh 断/超时/站断电）后的状态残留与续跑未定义——任务卡停在哪个态、半成品 out/ 是否污染下次 sync                                        | 中   | 需要任务卡状态机（pending/running/done/failed）+ wrapper 幂等回收；对应 LangGraph checkpoint 公理（§8.5-1） |
| G13 | **成本/额度观测**：zen 免费档日限额未文档化且无用量反馈——打到限额才有报错，无预警                                                                | 中   | wrapper 记录每次远端调用次数（本地 log 就够）；限额触发时的降级路径（→本地档）待定义                                      |
| G14 | **版本协同矩阵**：升级窗口的回归面未清单化——opencode 升级会否破坏 stdin 管道形式（G10）、plugin API、codex-memory 兼容                           | 低   | 升级窗口评估时跑 agent-cli-smoke.sh + 插件加载 + 记忆读写三件套                                           |

**自审定论**：G1（wrapper 未实现）仍是主缺口，G11 是**新增的最高优先级设计约束**——D6 DESIGN 必须先写并发模型（单工作区单写者原则）再写命令面；G12/G13 进 wrapper MVP 需求；G14 进升级窗口回归清单（与 G10 合并）。

### 9.6 Anthropic coordinator 模式逆向分析（v3.2 增补：泄漏源码 E1 直读 + B 站实测）

> 来源：`D:\ds\claude-code-haha-main\src\coordinator\coordinatorMode.ts`（claude-code 泄漏/反混淆源码，E1 直读全文 368 行 + constants/tools.ts 工具面交叉核对）。这是 Anthropic 官方的多 worker 编排设计——**单文件浓缩了他们关于"一个主脑调度多个执行者"的全部工程决策**，与 D6 是同构问题。

#### 9.6.1 可用性实测（E1，B 站 2026-09-03）

| 断言                              | 实测                                                                                                                                                                                                |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| coordinator 模式在 2.1.258 构建中是否可用 | **可用**——`CLAUDE_CODE_COORDINATOR_MODE=1 claude -p '...'` 后模型自认 "Yes, I am running in coordinator mode"；对照组（无 env）明确 "No, I am running as the main agent"。feature flag `COORDINATOR_MODE` 在现役构建中已开 |
| 启用代价                            | 零成本：单 env var，会话级（matchSessionMode 支持恢复会话时自动对齐模式）                                                                                                                                                 |
| 定位                              | **B 站站内编排层**——一个 claude 会话内 spawn 多个 async worker（各带 Bash/Read/Edit/Write/Grep/Glob/Skill 工具面），coordinator 不亲自碰文件                                                                                 |

#### 9.6.2 对 D6 的八条可借鉴模式（按价值排序）

1. **task-notification 结构化交接协议**——worker 结果以 `<task-notification>` XML 回流：`task-id / status(completed|failed|killed) / summary / result / usage{total_tokens, tool_uses, duration_ms}`。**直接吸收进** **`.agent-run.json`** **归一化契约**——usage 三元组正是 G13（额度观测）需要的遥测字段，Anthropic 已定义好 schema。
2. **并发纪律的独立第三方验证**——官方明文 "Read-only tasks run in parallel freely; **Write-heavy tasks one at a time per set of files**"（§4 Concurrency）+ "Verification can sometimes run alongside implementation **on different file areas**"。与我们 G11"单工作区单写者"结论一致但更精细：**锁粒度是文件集不是工作区**（读并行/写串行/验证可与实现并行若文件区不交叠）——D6 flock 设计按此细化。
3. **Continue vs Spawn 决策表**（§5）——六行决策矩阵，其中两条直接命中我们的设计：**"Verifying code a different worker just wrote → Spawn fresh（Verifier should see the code with fresh eyes, not carry implementation assumptions）"= 站间互审/异构复审的 fresh-eyes 原理**（第三方独立表述）；"Wrong approach entirely → Spawn fresh（wrong-approach context pollutes the retry; avoids anchoring）"= 失败任务换 agent 重试而非续跑。wrapper `--continue` 路由规则照此表实现。
4. **反懒惰委派铁律**——"Never write 'based on your findings'… You never hand off understanding to another worker"（§5）：编排方必须先消化 worker 产出（Synthesis 阶段是 coordinator 本职）才能派生后续任务，prompt 必须带具体文件路径/行号/错误消息。**这是任务卡"干净室+自包含"规范的官方版**，也与我们"审计者不采信引文/双盲重推导"同构。
5. **两阶段 QA 结构**——worker 自验（"Run relevant tests and typecheck, then commit"——第一层）+ 独立验证 worker（第二层）；验证哲学 "proving the code works, not confirming it exists / don't rubber-stamp"。= 执行锚定公理（§8.5-3）的官方表述。
6. **Scratchpad 跨 worker 共享记忆**——专用目录（免权限提示读写），"durable cross-worker knowledge — structure files however fits the work"。工作区设计吸收：`out/` 之外加 `notes.md` 共享黑板（wrapper 同步时排除、站上持久）。
7. **会话模式持久化**——matchSessionMode：恢复会话时对比存储的模式与当前 env，不匹配则翻转 env 并告警（"Entered coordinator mode to match resumed session"）。G12 失败恢复参考：**任务卡状态应随会话持久并在 resume 时对齐**。
8. **Worker prompt 工程五要点**（§5 提炼）：自包含（worker 看不到 coordinator 对话）、声明 done 判据（=accept 字段）、purpose statement 校准深度、git 操作精确到 branch/draft/reviewer、"fix the root cause, not the symptom"。

#### 9.6.3 架构差异与取舍（诚实披露）

Anthropic 把 **LLM 放在编排席**（spawn/continue/stop 是模型经 prompt 纪律驱动的工具调用决策）；D6 公理 1 是**确定性 wrapper 编排**（路由/超时/重试是代码）。维持我们的立场——G11 并发保护必须代码强制（flock），不能靠 prompt 纪律（Anthropic 的 "one at a time per set of files" 是提示词约束，无强制力）。**分工定案：结构协议照抄 Anthropic（task-notification/决策表/prompt 规范），强制机制照抄我们（代码锁/机械门禁）**。coordinator 模式本身作为 B 站站内复杂任务的第三编排选项（wrapper 跨站编排、trae 五层循环之外），D7+ 候选——适用场景：单站内多文件探索型任务（research fan-out 天然并行），不适用：跨站/涉密/需审计追溯的任务（会话内编排无任务卡痕迹）。

#### 9.6.4 泄漏源码的其他编排相关资产（目录扫描 E1）

tools/ 下存在完整编排工具族：AgentTool（spawn）/ SendMessageTool（continue）/ TaskStopTool / TaskCreate/Get/List/Update/Output（任务簿）/ TeamCreate/Delete（团队生命周期）/ WorkflowTool（feature('WORKFLOW\_SCRIPTS') 门控）/ EnterWorktree/ExitWorktree（worktree 并行——印证 §8.3 worktree 模式官方化）。ALL\_AGENT\_DISALLOWED\_TOOLS 揭示隔离边界：subagent 禁 AskUserQuestion/TaskStop/递归 Agent（防套娃），worker 工具面 = ASYNC\_AGENT\_ALLOWED\_TOOLS（read/write/grep/glob/shell/skill/worktree）+ 可选 MCP 注入——**站上 worker 的工具面子集化设计可直接参考此清单**。

### 9.7 Codex orchestrator/parallel 逆向分析（v3.3 增补：开源源码 E1 直读）

> 来源：`D:\ds\codex-main\codex-rs\core\src\tools\orchestrator.rs`（553 行全文直读）+ `parallel.rs`（核心段直读）+ `registry.rs` 并行判定交叉核对。**与 §9.6 Anthropic 泄漏源码形成完美对照实验**：Anthropic 把 LLM 放编排席（纪律靠 prompt），Codex 把编排全部写成 Rust 确定性代码（纪律靠锁）——**Codex 才是与 D6 公理 1 同哲学的参考实现**。

#### 9.7.1 G11 的官方代码级答案：RwLock 并发门（parallel.rs）

Codex 的工具并发控制核心是**一把 tokio RwLock**（`parallel_execution: Arc<RwLock<()>>`）：

```
supports_parallel == true  → lock.read().await   // 读锁: 多工具同时持锁执行
supports_parallel == false → lock.write().await  // 写锁: 全局独占, 排空所有并行工具
```

**判定面三级**（registry.rs + 各工具声明实测汇总）：

| 层级           | 机制                                                                 | 例                                                                                                                                                                     |
| ------------ | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 工具自声明        | 每工具实现 `supports_parallel_tool_calls()`                             | exec\_command=**true**、list/read\_mcp=true、view\_image=true、tool\_search=true、write\_stdin=true；list\_available\_plugins=**false**、request\_plugin\_install=**false** |
| 隐藏工具排除       | `exposure != Hidden && runtime.supports_parallel()`                | 隐藏工具永不并行                                                                                                                                                              |
| **MCP 注解驱动** | `tool_info.supports_parallel_tool_calls \|\| annotations.readOnly` | 外部工具凭 MCP 标准注解 readOnlyHint 声明读安全——**声明式而非启发式**                                                                                                                       |

**对 D6 的直接映射**：wrapper 任务卡加 `readonly: true|false` 字段（MCP 注解模式的任务卡版）——research/分析/审查类任务持共享锁并行 fan-out，implementation 类任务持排它锁独占工作区。**比 Anthropic 的 prompt 纪律（"write-heavy one at a time per set of files"）硬一个量级：RwLock 是 OS 级强制**。与 §9.6-2 的文件集粒度合并定案：**工作区级 flock（粗）+ 任务卡 readonly 声明（细）双层**——MVP 先做工作区级，V2 按任务卡字段细化。

值得注意的实测发现：**exec\_command=true**（shell 命令可并行）——因为 Codex 的 shell 在沙箱内进程受管、输出不落盘冲突；对我们：站上 opencode 的 Bash 调用天然由 CLI 内部序列化，wrapper 层面只锁"工作区文件写"即可，不必锁整 CLI 会话。

#### 9.7.2 orchestrator.rs 五段流水与升级重试（对照 D6 wrapper 生命周期）

```
approval（批准） → select sandbox（选沙箱） → attempt（执行）
   → 拒绝时: escalate retry（升级重试: 无沙箱再试, 批准已缓存不重问）
```

五条可吸收语义：

1. **批准缓存**——首次批准后重试**不再重新请求批准**（`already_approved` 标志）；wrapper 的 audit 门/敏感路由同理：任务卡进 running 态后重试跳过重审
2. **升级重试是二段式而非无限重试**——sandbox 拒绝 → 恰好一次升级尝试（去沙箱），失败即终态。**印证"重试 ≤2 次转人工"纪律的官方实现形态**
3. **owner 策略不可升级绕过**——"attachment-owned network policy cannot be bypassed by sandbox escalation"：归属策略（如附件带的网络策略）直接 Rejected，无升级路径。**= sensitivity: local-only 不可被任何 wrapper 参数覆写**（D6 硬边界语义的官方同款）
4. **严格模式重批**——strict\_auto\_review 下"批准只覆盖沙箱内尝试，无沙箱重试需 fresh guardian review"（代码注释原文）：升级重试须重新审批。审计任务的降级运行须重新过 audit 门
5. **遥测内建**——sandbox\_outcome(denied/escalated/timed\_out/signal, initial\_duration, escalated\_duration)：**排队等待与执行时长分离计量**（`execution_started_at: OnceLock` 在获锁后才设置）——wrapper 遥测照抄：`.agent-run.json` 记 queue\_s 与 run\_s 两字段（G13 观测的精确形态）

#### 9.7.3 取消语义（G12 补充）

取消令牌触发时先查 `terminal_outcome_reached || is_finished()`——**已完成的工具不取消，等待其结果**；只有真正在跑的才 abort 并发 `notify_tool_aborted` 事件。D6 task abort 语义照抄：中断前先收终态，避免把已完成产物误标 aborted。

#### 9.7.4 双源对照总结（Anthropic vs Codex vs D6 定案）

| 维度   | Anthropic coordinator（§9.6）                          | Codex orchestrator（§9.7）      | D6 定案                           |
| ---- | ---------------------------------------------------- | ----------------------------- | ------------------------------- |
| 编排哲学 | LLM 在编排席，纪律靠 prompt                                  | 代码编排，纪律靠锁                     | **代码编排（公理 1）**                  |
| 并发控制 | 提示词："write-heavy one at a time **per set of files**" | **RwLock + 工具声明 + MCP 注解**    | 工作区 flock + 任务卡 readonly 字段（双层） |
| 交接协议 | task-notification XML（usage 遥测）                      | ResponseInputItem + 失败按工具类型分流 | .agent-run.json（吸收双方字段）         |
| 重试   | 失败续跑（SendMessage 带 error context）                    | **二段式升级重试（恰好一次）+ 批准缓存**       | ≤2 次转人工 + 门禁缓存                  |
| 硬边界  | worker 工具面白名单                                        | **owner 策略不可升级绕过**            | sensitivity: local-only 不可覆写    |
| 适用场景 | 单站内多文件探索 fan-out                                     | 单会话内工具级安全/并发                  | 跨站任务卡编排（两者都不覆盖的层）               |

**定论**：Anthropic 给了编排的"语法"（怎么交接、怎么写 prompt、何时 continue/spawn），Codex 给了编排的"法律"（怎么强制、怎么锁、怎么升级重试）——D6 DESIGN 直接合并：**协议层抄 Anthropic §9.6-2，强制层抄 Codex §9.7-1/9.7-2，两者拼出完整的 wrapper 规范**。

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

v3 增补（E2 web 调研 2026-09-02，经调研子代理聚合；关键源）：

- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts.md) / [LangGraph Functional API](https://docs.langchain.com/oss/python/langgraph/use-functional-api)（interrupt/checkpoint/resume + Retry Policy/审批）

- [CrewAI HITL 文档](https://docs.crewai.com/en/learn/human-in-the-loop)（human\_input/Webhook 暂停-恢复模式）+ CrewAI 源码（max\_iter/max\_rpm, E2）

- [AutoGen 0.4 GroupChat](http://microsoft.github.io/autogen/0.4.8/user-guide/core-user-guide/design-patterns/group-chat.html) / [SelectorGroupChat](http://microsoft.github.io/autogen/0.5.4/user-guide/agentchat-user-guide/selector-group-chat.html)（事件驱动 Actor + 状态保存恢复）

- [MetaGPT](https://github.com/FoundationAgents/MetaGPT)（[arXiv:2308.00352](https://arxiv.org/pdf/2308.00352), Code=SOP(Team) 结构化中间产物）

- [AI Scientist v1](https://arxiv.org/pdf/2408.06292) / [AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2)（BFTS/自动评审；v2 相关工作 2026 年见 Nature, [sakana.ai/ai-scientist-nature](https://sakana.ai/ai-scientist-nature/)）

- [Beel & Kan 对 AI Scientist 的复现评估](https://www.comp.nus.edu.sg/~kanmy/papers/papers/2502.14297v2.pdf)（42% 实验失败/幻觉引用/3.5h 人工介入——人工审必要性实证）

- [Agent Laboratory](https://arxiv.org/pdf/2501.04227.pdf)（AMD/Schmidgall, 三阶段 + 人类反馈 +0.58 + 检查点恢复）

- [AutoSurvey](https://arxiv.org/pdf/2406.10252v2)（四阶段 + 引用溯源 + evaluator 打分）

- [Claude Code Subagents](https://docs.anthropic.com/en/docs/claude-code/sub-agents) / [claude-code-action](https://github.com/anthropics/claude-code-action/blob/main/docs/usage.md)（.claude/agents 定义/权限校验）

- [Claude Code best practices（worktree 并行）](https://www.anthropic.com/engineering/claude-code-best-practices)

- [Backlog.md](https://github.com/MrLesk/Backlog.md)（三人工检查点）/ [Task Master](https://github.com/eyaltoledano/claude-task-master)（tasks.json 持久 + 三档模型）

- [SWE-agent ACI](https://arxiv.org/pdf/2405.15793v2)（Agent-Computer Interface + guardrails 消融）

- [OpenHands Runtime](https://docs.openhands.dev/openhands/usage/architecture/runtime)（沙箱 client-server）

- [自托管 Claude Code 指南](https://www.developersdigest.tech/blog/self-hosting-claude-code-on-your-own-infra)（ANTHROPIC\_BASE\_URL 双变量重定向）

- OpenHands+LiteLLM 自托管实践（[homelab RFC, Stripe Minion 模式复述](https://github.com/jomcgi/homelab/blob/main/docs/decisions/agents/001-background-agents.md)：重试≤2 转人工/PR 留审）

v3 增补二（2026-09-02 晚，Qwen OAuth 插件实测轮）：

- [gustavodiasdev/opencode-qwencode-auth](https://github.com/gustavodiasdev/opencode-qwencode-auth)（插件本体，E1 直抓 + npm 包源码解剖）

- [OpenCode issue #11557](https://github.com/anomalyco/opencode/issues/11557)（插件进官方生态文档的提交记录，E1）

- [qwen-code 官方 auth 文档](https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/auth.md)（E1 直抓：**"Qwen OAuth free tier was discontinued on 2026-04-15"**，/auth 菜单已移除 OAuth 选项）

- [qwen-code troubleshooting](https://qwenlm.github.io/qwen-code-docs/de/users/support/troubleshooting/)（E1：官方引导转 Coding Plan/API Key）

- [插件 issue #14 "Stopped working"](https://github.com/gustavodiasdev/opencode-qwencode-auth/issues/14)（E1：社区确认停用，2026-04-23）

- B 站实测记录（E1 2026-09-02）：device code 端点 form-encoded+PKCE 复刻仍发码；`/authorize` 同意页两轮跳回主页；token 端点 504（alibaba-ga）

v3.2 增补（2026-09-03，Anthropic coordinator 逆向轮）：

- `D:\ds\claude-code-haha-main\src\coordinator\coordinatorMode.ts`（E1 本地泄漏源码直读全文 + `src/constants/tools.ts` 工具面交叉核对——注意：本地泄漏源码，非公开文档，**不得外引 URL，只作设计参考**）

- B 站 coordinator 模式门禁实测（E1 2026-09-03）：`CLAUDE_CODE_COORDINATOR_MODE=1` 生效（模型自认 coordinator），对照组为 main agent——2.1.258 构建已开放该 feature flag

v3.3 增补（2026-09-03，Codex 逆向轮）：

- `D:\ds\codex-main\codex-rs\core\src\tools\orchestrator.rs`（E1 开源源码直读全文 553 行——codex-rs 为 Apache-2.0 开源，可正常引用其公开仓库）

- `D:\ds\codex-main\codex-rs\core\src\tools\parallel.rs` + `registry.rs` 并行判定三级面交叉核对（工具自声明/Hidden 排除/MCP annotations.readOnly 注解驱动）

