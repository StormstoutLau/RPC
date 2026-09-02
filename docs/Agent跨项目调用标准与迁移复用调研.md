# Agent CLI 跨项目调用标准与跨会话迁移复用调研

---
date: 2026-09-02
status: draft（D6 前期调研）
upstream: D5 Agent 生态升级（已 verified 2026-09-02）; 调研 §4.2 五层循环遗留"任务卡协议"口子
---

> **问题**: D5 之后两站 4 个 agent CLI（A/B × claude code / opencode）已装备。假设**其他工作项目**需要调用这 4 个 CLI，如何建立标准规范实现**跨会话迁移复用**？
> **方法**: 生态标准/官方文档直抓（E1/E2 标注）+ D5 实测基线复用（E1）+ B 站 memory.db 直查（E1，本轮）。

## 0. 速览

| 问题 | 结论 |
| --- | --- |
| 跨 CLI 指令单源怎么做？ | **AGENTS.md 为源 + CLAUDE.md 薄壳 `@AGENTS.md` 导入**——claude code 官方明确不原生读 AGENTS.md（#6235, 5200+ reactions, "not planned"），导入是官方推荐模式（§3.1） |
| 项目级技能隔离？ | 两 CLI 都支持项目级 `.claude/skills/`；**但 claude code 个人级 > 项目级（同名遮蔽，反直觉）**；opencode 用 permission 模式可 deny/ask 精确子集化（§3.2/3.3） |
| 跨会话记忆按项目隔离吗？ | **部分**：codex-memory 提取记忆带 `cwd` 键（E1 memory.db 直查）；**但 ad-hoc 笔记（memory_add_note）全局平铺无隔离**——需命名空间约定（§4.1） |
| 其他项目怎么调用 4 CLI？ | **统一 wrapper 协议**（L1）：两 CLI headless 均支持 JSON 输出但语义不同——claude `-p --output-format json` / opencode `run --format json`；封装成 `agent-cli` 单入口 + 统一 JSON 契约 + 退出码（§5.2） |
| headless 最大的坑？ | claude `--bare` 会**跳过 CLAUDE.md/插件/auto-memory**——纯计算快，但项目上下文调用**禁用 --bare**（§3.4） |
| A 站 claude 能用吗？ | 不能（R17：裸系统提示 33k > CTX 32k）——调用标准必须内建**模型路由可达性判断**（§5.2） |

## 1. 需求解构

### 1.1 "跨会话迁移复用"的四个正交维度

| 维度 | 含义 | 已有基础 (D5) | 缺口 |
| --- | --- | --- | --- |
| **跨时间**（会话→会话） | 同项目隔日/隔周续作 | codex-memory（B 站）、CLAUDE.md 骨架 | 提取路径未测；A 站无记忆层 |
| **跨项目**（项目↔项目） | 不同工作项目共享/隔离资产 | 用户级 12 技能双 CLI、手册纪律 | 项目级约定未标准化；技能子集机制未用 |
| **跨 CLI**（claude↔opencode） | 一套资产两 CLI 生效 | `~/.claude/skills/` 双读（E1 实证） | 指令文件双源（CLAUDE.md vs AGENTS.md）待统一 |
| **跨站**（A↔B） | 两站一致 + 互审 | md5 对账部署、站间互审设计（调研 §8.4） | 派发侧无标准入口；路由可达性差异未封装 |

### 1.2 调用方矩阵（谁要调 4 CLI）

| 调用方 | 场景 | 需要的接口形态 |
| --- | --- | --- |
| 人（Scott）在站上 | 日常交互 TUI | 已就绪（D5） |
| 主控站脚本/CI | 定时任务、批处理 | headless + JSON 输出 + 退出码 |
| 其他项目代码 | 把 CLI 当本地 LLM 执行引擎 | 稳定命令面 + 项目上下文注入 + 输出契约 |
| trae（编排层） | 五层循环派发（调研 §4.2） | 任务卡 + 断言契约（assertion-audit 已备）+ 站间互审 |

## 2. 现状基线（D5 后，E1）

- 两站 4 CLI 装备同构：12 定制技能（用户级 `~/.claude/skills/`，双 CLI 读，md5 零差异）、superpowers 6.3.0 + document-skills（claude 插件，本地镜像）、ARS @1d3032f（opencode 侧 symlink）、codex-memory 0.6.5（B 站 opencode）
- headless 已实证：`claude -p`（PONG/技能列表）、`opencode run -m`（PONG/A2 135k 附件）、`opencode run --command`（ARS 命令面）
- 后端边界（实测）：A 站 claude@32k **不可用**（R17）；B 站 claude 走 LiteLLM nemotron + MAX_CONTEXT_TOKENS=120000（R15/R16）；两站 opencode 双 provider
- 窗口预算已声明：opencode limit.context（120000/30000）+ compaction
- 网络边界（实测）：B 站 github 间歇（R18）、npm 稳定、arxiv 间歇、crossref/eutils 稳定

## 3. 生态标准与能力盘点

### 3.1 AGENTS.md：跨工具指令标准（E1 直抓 agents.md）

- 开放标准，"README for agents"；**60k+ 开源项目**采用；Linux 基金会 Agentic AI Foundation 首批项目（2025-12，与 MCP 同列）
- 原生读取方：Codex、Cursor、Amp、Copilot coding agent、Junie、opencode 等
- **claude code 不原生读 AGENTS.md**（官方 memory 文档原文 "Claude Code reads CLAUDE.md, not AGENTS.md"；#6235 5200+ reactions 仍 open，官方"not planned for now"）
- 官方推荐互通模式：CLAUDE.md 首行 `@AGENTS.md` 导入（跨平台，导入链上限 5 跳，路径相对含导入文件的目录）；或 `ln -s AGENTS.md CLAUDE.md`（Unix，不能追加 Claude 专属内容；Windows 需管理员权限）
- opencode 侧：AGENTS.md 原生优先（无 AGENTS.md 时 fallback CLAUDE.md，D5 调研 §2.2 已录）；**`.agents/skills/` 已是技能发现一等公民位置**（§3.3）

### 3.2 claude code 项目级能力（E1 官方 skills 文档直抓）

| 层级 | 路径 | 适用范围 |
| --- | --- | --- |
| Enterprise | managed settings | 全组织 |
| Personal | `~/.claude/skills/` | 本人全部项目 |
| **Project** | `.claude/skills/<name>/SKILL.md` | **仅本项目** |
| Plugin | `<plugin>/skills/` | 插件启用处（`plugin:skill` 命名空间，不冲突） |

**关键陷阱（同名遮蔽规则，反直觉）**：enterprise > **personal > project**——个人级技能**遮蔽**项目级同名技能。对本集群含义：12 件用户级技能会在所有项目出现；项目想覆盖某件（如定制 research-scout 行为）**不能靠同名项目技能**，须改名或走 settings 的 skillOverrides。

其他：父/嵌套目录发现（嵌套技能以 `dir:name` 限定名出现）；live change detection（改 SKILL.md 即时生效）；`.claude/commands/` 同机制但技能优先。

### 3.3 opencode 项目级能力（E1 官方 config/skills 文档直抓）

**配置优先级**（后覆盖先）：Remote（.well-known）→ Global（~/.config/opencode/opencode.json）→ `OPENCODE_CONFIG` env → **Project（项目根 opencode.json，标准源中最高）**；启动时从 cwd 向上遍历到 git 根找配置。

**技能发现 6 位置**（项目级从 cwd 遍历到 git 根）：

| 级 | 位置 |
| --- | --- |
| 项目 | `.opencode/skills/` / `.claude/skills/` / **`.agents/skills/`** |
| 全局 | `~/.config/opencode/skills/` / `~/.claude/skills/` / `~/.agents/skills/` |

**per-skill 权限模式**（项目 opencode.json）——项目技能子集化的现成机制：

```json
{ "permission": { "skill": {
    "*": "allow", "internal-*": "deny", "experimental-*": "ask" } } }
```

（allow 立即加载 / deny 对模型隐藏 / ask 提示确认；支持通配符；可按 agent 覆盖，如 plan agent 单独授权。）

### 3.4 headless / 程序化调用能力（E1 官方文档直抓 + D5 实测）

**claude code**（`claude -p`）：

- `--output-format text|json|stream-json`（json 含 result/session ID/metadata/cost）
- `--bare`：**跳过 hooks/插件/auto-memory/CLAUDE.md/plugin sync**——脚本调用提速用；⇒ **项目上下文调用禁用**（会丢项目指令），纯计算调用推荐
- 逐调用注入面：`--settings <file-or-json>` / `--mcp-config` / `--agents <json>` / `--plugin-dir <path>` / `--append-system-prompt(-file)` / `--allowedTools`
- `--continue` 续会话；`--fork` 分叉；stdin 管道（上限 10MB）；退出码 0/非 0 语义明确；SIGTERM 后 resume 续未完回合
- Python/TypeScript Agent SDK（结构化输出 + 工具审批回调 + 原生消息对象）

**opencode**（`opencode run`，D5 实测 + 官方 SDK 文档）：

- `--command <name> -- <args>`（ARS 命令面已实证）、`--format json`（raw JSON 事件流）、`-f <file>` 附件（A2 已实证）、`-c/--continue`、`-s/--session`、`--fork`、`--dir`（远程路径）、`--attach`（接运行中 server，如 http://localhost:4096）
- **SDK**：`@opencode-ai/sdk`，`createOpencode()` 同时起 server+client（默认 127.0.0.1:4096），支持 client-only 模式接既有 server——**常驻 server + 多项目客户端**的现成形态
- server 模式含 mDNS 发现（`opencode.local`）与 CORS——跨机调用面已有，但 D5 不变式②（零自加载）约束下**按需起停**，不开常驻

## 4. 跨会话记忆机制实测（E1，本轮 B 站直查）

### 4.1 codex-memory 的隔离真相

memory.db（B 站，sqlite 只读直查）表结构：

| 表 | 键 | 隔离性 |
| --- | --- | --- |
| `memory_stage1_outputs` | **含 `cwd` 列**（session_id/raw_memory/rollout_summary/cwd/...） | **提取记忆按项目 cwd 键控**（天然隔离） |
| ad-hoc 笔记（memory_add_note） | 文件落 `memories/extensions/ad_hoc/notes/*.md` **全局平铺** | **无项目隔离**——跨项目复用需命名空间约定 |
| `memory_session_meta` | session_id + memory_mode + polluted | 会话级元数据 |

含义：A5 验证的"显式笔记路径"是**全局共享**的——不同项目的新会话都能读到 D5 部署笔记（当时在 /tmp cwd 写入，无项目归属）。多项目标准必须补：**ad-hoc note 文本首部带 `[proj:<name>]` 标签**（写入方约定），检索侧按标签过滤。

### 4.2 会话续接面

- claude code：`--continue`/`--fork` + session 元数据（json 输出含 session_id）
- opencode：`run -c`/`-s <id>`/`--fork`；SDK 可编程操作会话
- claude code auto-memory（`~/.claude/projects/<proj>/memory/MEMORY.md`）——**按项目目录隔离**（官方），与 codex-memory 的 cwd 键控同构

## 5. 标准规范草案：RPC Agent CLI 调用标准（建议名 d6-agent-standard）

### 5.1 L0 项目侧目录约定（每个接入项目，全部 git 提交）

```
<project-root>/
├── AGENTS.md            # 指令单一源（技术栈/构建测试命令/约束/禁止项）
├── CLAUDE.md            # 薄壳: 首行 @AGENTS.md + Claude 专属少量追加
├── .claude/skills/      # 项目技能（注意 §3.2 遮蔽陷阱：勿与用户级 12 件同名）
├── opencode.json        # 项目配置（标准源最高优先级）: provider 覆盖/skill 权限子集
└── .agents/skills/      # 可选（跨工具标准位，opencode 原生读）
```

规则：AGENTS.md 为唯一事实源（跨 CLI/跨工具）；CLAUDE.md 只做导入壳不写实质内容（防双源漂移——JetBrains 调研称双文件维护月均损耗 5.3h）；项目技能命名带项目前缀（如 `projx-`）规避 claude 遮蔽。

### 5.2 L1 统一调用协议（station-bin 新增 `agent-cli` wrapper）

```
agent-cli ask --project <path> --model nemotron|gpt-oss [--cli auto|claude|opencode]
             [--profile <skill-profile>] [--attach <file>...] [--continue <sid>] <prompt>
agent-cli task --project <path> --taskcard <card.md>        # 断言契约任务（对接 assertion-audit）
agent-cli review --project <path> --peer                    # 站间互审（对端模型跑 cross-examine）
```

wrapper 职责（吸收 D5 全部实测坑）：

1. **路由可达性内建**：`--model gpt-oss` + `--cli claude` 组合直接拒绝（R17）；模型→CLI→站映射表硬编码
2. **CLI 分派**：默认 opencode（长上下文/ARS 命令面/技能面完整）；claude 仅短任务（B 站）
3. **headless 封装**：项目上下文调用**不用 `--bare`**；统一 `--output-format json`（claude）/ `--format json`（opencode）→ 归一化输出契约：
   `{cli, model, session_id, exit_code, content, duration_s, cost_est?}`
4. **PowerShell→ssh 铁律继承**：主控站远程调用走本地脚本→scp→执行（R14 三次实证）
5. **环境注入**：二进制全路径（A 站 `/snap/bin/opencode`、nvm claude 路径差异已台账化）

### 5.3 L2 隔离规范

| 隔离面 | 机制 |
| --- | --- |
| 指令 | 项目 AGENTS.md 天然隔离；用户级 CLAUDE.md 铁律全局（层级注入） |
| 技能 | 用户级 12 件全局共享；项目子集：opencode 用 permission deny/ask（§3.3），claude 用 skillOverrides/命名规避（§3.2） |
| 记忆 | 提取记忆 cwd 天然隔离（§4.1）；**ad-hoc note 强制 `[proj:<name>]` 前缀约定**；claude auto-memory 按项目目录隔离 |
| 后端 | 项目 opencode.json 可覆盖 provider（如项目专属小模型实验）；conf CTX↔limit 联动铁律不变 |

### 5.4 L3 派发与互审（对接五层循环）

- **任务卡协议**：card.md 头部 `audit: true` 触发 assertion-audit 契约（产出方）——审查侧 `agent-cli review --peer` 用对端模型跑 cross-examine（nemotron 产出→gpt-oss 审，反之亦然；adlc trust-root tier 外部同构实证）
- **干净室**：任务卡只含任务描述+验收判据，**禁止预装结论/预消化证据**（#704 规范，cross-examine Step 0 自检兜底）
- **收敛判据**：两连干轮 + ≥3 独立 lens（已入 cross-examine 契约）

## 6. 缺口清单与 D6 建议

| # | 缺口 | 严重度 | D6 处置建议 |
| --- | --- | --- | --- |
| G1 | agent-cli wrapper 未实现（L1 核心） | 高 | D6 主体；先 ask 子命令 MVP，task/review 二期 |
| G2 | ad-hoc note 无隔离（全局平铺） | 中 | 命名空间约定写入 agent-cli（自动加 `[proj:]` 前缀）+ 手册 |
| G3 | A 站无记忆层（codex-memory 仅 B 站） | 低 | 调用标准默认 B 站为记忆主站；A 站复制试点列 P2 |
| G4 | claude personal>project 遮蔽未在站上实测 | 低 | D6 实施时单件验证（同名件放项目级，观察遮蔽） |
| G5 | AGENTS.md 薄壳模式未实测（@导入 5 跳上限/批准对话框行为） | 中 | D6 V0 验证门首项（模式已官方背书，站上行为待验） |
| G6 | opencode SDK server 常驻与零自加载不变式②冲突 | 中 | 维持按需起停（`--attach` 接临时 server）；常驻列豁免清单评估流程 |
| G7 | 提取记忆路径（6h 闲置）仍未测（D5 §7-4 遗留） | 低 | 正常使用自然覆盖，不阻塞 |

**建议路径**: 本调研 → Scott review → D6 spec（RESEARCH=本文档 / DESIGN→IMPLEMENTATION→CHECKLIST），D6 范围 = agent-cli MVP（ask + 路由 + 输出契约）+ L0 目录约定落地一个试点项目 + G4/G5 验证门；task/review 子命令与五层循环对接列 D7。

## 参考源

- [agents.md](https://agents.md)（标准主页，E1 直抓 2026-09-02）
- [Claude Code: Run programmatically/headless](https://code.claude.com/docs/en/headless)（E1 直抓：--bare/--output-format/--settings/注入面/退出码/10MB/SDK）
- [Claude Code: Skills](https://code.claude.com/docs/en/skills)（E1 直抓：四级层级/遮蔽规则/嵌套发现）
- [Claude Code memory docs + AGENTS.md 立场（"not planned"，#6235）](https://code.claude.com/docs/en/memory)（E2，经 yurukusa field guide 2026-06-03 核对转述 + #34235 issue 直抓佐证）
- [opencode: Config](https://opencode.ai/docs/config/)（E1 直抓：优先级/project 最高/向上遍历）
- [opencode: Skills](https://opencode.ai/docs/skills/)（E1 直抓：6 发现位置/permission 模式/名称规则）
- [opencode: SDK](https://opencode.ai/docs/sdk/)（E1 直抓：createOpencode/client-only/4096）
- B 站 memory.db 直查 + memories/ 目录布局（E1，本轮 2026-09-02）
- D5 交付物（E1）：CHECKLIST §3/§6 台账、手册 §2a、ars-migrate-verify.sh/a5-nextday-verify.sh 实测记录
