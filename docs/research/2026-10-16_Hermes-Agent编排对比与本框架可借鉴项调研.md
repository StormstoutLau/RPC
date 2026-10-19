# Hermes Agent 编排对比 + 本框架可借鉴项调研与落地步骤

- **日期**: 2026-10-16
- **性质**: **只读调研 + 落地步骤（方案稿）** —— 本文**不含任何写动作**（未改代码、未改站上配置、未建 workspace）
- **证据等级**: **E1** = 本机/本仓实读实测 · **E2** = 前会实测留档 · **E3** = 外部/上游文档
- **真值来源**（本文不造第二定义点）:
  - agent 编排程序真值 → [spec/d6-agent-standard/](../../spec/d6-agent-standard/)（DESIGN / ARCHITECTURE / D7-PROTOCOL-CONTRACT / BLINDSCAN-v2-orchestration）
  - 管理面与脚本纪律 → [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md)
  - 入口/运行时件登记 → [inventory/ops.yaml](../../inventory/ops.yaml)
  - 既有选型裁定 → [Agent-CLI技术选型调研_20260909.md](../Agent-CLI技术选型调研_20260909.md)
- **上游对照对象**: Nous Research **Hermes Agent**（含 `hermes-desktop`）；本机存量 `~/.hermes/`，E1 实读

---

## 0. 一屏结论

| 问题 | 判定 |
|---|---|
| 把 Hermes **引入为运行资产**（换 CLI / 借它的 board 与 daemon） | ⛔ **不做** —— 本仓 2026-09-09 已判「**存量不弃、不复用**」（研究资产非运行资产），且其常驻 dashboard/hooks 与 ADR-0004「零自加载 · 无 daemon」正面冲突 |
| **任务进度跟踪** | ✅ **本框架已具备**（`cluster.py` 的 `agent` 子命令 + `agent-runs.log` 台账 + 站上 `.progress` 节拍 + 证据链审计）⇒ **只需补视图，不需补机制** |
| **管理可视化** | ✅ **本框架已有合规答案**（`ops/cluster_web.py` = ADR-0004 D1 明文「web 形态」，已含 `/api/agent` 卡片）⇒ **只加卡片，不加服务** |
| **人格注入** | ★ **真空白，但价值已被论文级证据「重定」** —— 结论 = **「身份声明近零增益、时而有害；增益来自『流程 + epistemic 约束 + 语域契约』」**（见 §3.5）⇒ 该层应装**约束文件，不是人设文件**（§5.1 已按此改） |
| **工具配置** | ⚠ 本框架约束**更严**（冻结存量 + 四断言）⇒ 只借「渐进披露/白名单」的**形态**，**不借 hooks 机制** |
| **任务板 DAG** | ⏸ **条件触发，本轮不做** —— 现役 1 会话 1 链，无依赖树/并行分支 ⇒ 上是过度工程（见 §5.3 反例） |

**一句话**：**本框架的「编排」是确定性 wrapper（任务卡 + 单槽 + 工作区排它锁 + strong-accept）；Hermes 的「编排」是常驻个人 agent 平台（SOUL + kanban + dashboard）。两者不同层，正确的借鉴不是「换壳」，而是把 Hermes 的 **2 个范式**折射进本框架**既有合规面**：① **约束文件**（不是人设文件；注入 + 入链，见 §3.5）；② 台账真值的只读视图。**

---

## 1. 已有前例（勿重复劳动）

| 既有档 | 结论（E1 实读） |
|---|---|
| [Agent-CLI技术选型调研_20260909.md](../Agent-CLI技术选型调研_20260909.md) | Hermes 已做 **D5 源码实读**（`delegate_tool` / `subagent_lifecycle` / `async_delegation` / `moa_loop` / `batch_runner`）；**§5.2 定位 = 「存量不弃、不复用」**；性能裁定 `HERMES-OPTIM-01` = 边际收益 < 集成成本 |
| [BLINDSCAN-v2-orchestration.md](../../spec/d6-agent-standard/BLINDSCAN-v2-orchestration.md) §8.6 | Hermes 编排机制与社区编排案例已落点映射；结论 = **「无需追这些框架」**，D6 wrapper 维持「保守正确」 |
| [Agent生态升级与多智能体协作架构调研.md](../Agent生态升级与多智能体协作架构调研.md) §9 | Hermes 编排架构**源码实读主体**（社区框架综述同在此档） |

⇒ **「是否引入 Hermes」= 已判否（有据）。** 本轮是**新问题**：借鉴其**管理范式**。

---

## 2. 两边「编排」的本质差异（E1 实读）

| 轴 | Hermes Agent（Nous Research · 桌面版） | 本框架（D6 wrapper / `agent-cli`） |
|---|---|---|
| 定位 | 通用个人 agent 平台（CLI / TUI / 约 20 消息网关 / Electron），**常驻 + 自进化** | **确定性编排层**（任务卡前置 + 单槽 + 工作区排它锁 + strong-accept 权威验收） |
| 任务进度 | `kanban.db`：`tasks`（36 列，含 `claim_lock` / `worker_pid` / `last_heartbeat_at` / `max_runtime_seconds` / `consecutive_failures` / `current_run_id` / `current_step_key`）· `task_runs` · `task_events` · `task_links`（父子 **DAG**）· `kanban_notify_subs`（跨平台投递） | `agent-runs.log` 台账（`ts,proj,model,sens,code,queue_s,run_s`）· 站上 `out/.progress`（5s 一行节拍）· `runDir/.agent-run.json`（**已含 `slot` / `profile` / `accept`**）· 证据链 `chain / verify / audit` |
| 人格 | **`SOUL.md`（身份文件，置 system prompt 第 1 槽位）** + `profiles/<name>/`（独立 home）+ `personas/*.md` + config 内置 13 预设 | **仅「协议角色」**（[D7-PROTOCOL-CONTRACT §1.4](../../spec/d6-agent-standard/D7-PROTOCOL-CONTRACT.md) 主控站/工作站 = 角色，`PRM`/`PRW` 禁项）；**无「人格/声音」层**；`AGENTS.md 运行时注入` 在 [ARCHITECTURE.md](../../spec/d6-agent-standard/ARCHITECTURE.md) 仅列为**「补充角色」（未落地）** |
| 工具配置 | `skills/`（25 类，agentskills.io 标准 + 渐进披露 + bundle）· MCP（按 server 过滤）· `hooks/`（gateway + plugin 拦截） | `inventory/plugins.yaml`（三站同构 + `known_drift` 登记）· 12 定制技能 · `scripts`/`plugins`/`aliases`/`gates` 四断言守护（**只减不增 D2**） |
| 可视化 | `hermes dashboard` @ `127.0.0.1:9119` + Electron 桌面 + Remote gateway（`remoteUrl` + token） | `ops/cluster_web.py`（ADR-0004 **D1 明文「web 形态」**）+ `/api/agent` 卡片（两块 = 运行中节拍 + 派发台账，15s 自刷） |

---

## 3. 社区案例（E3，逐条带出处）

### 3.1 人格 / 身份文件

| 事实 | 出处 |
|---|---|
| **`SOUL.md` = system prompt 的「第 1 个槽位」**；另有 session 级 `/personality` 覆盖层 | [Hermes Personality](https://hermes-agent.nousresearch.com/docs/user-guide/features/personality/) |
| `CLAUDE.md` 按**范围由宽到窄**加载（用户级→项目根→子目录），**session start 只读一次并驻内存**；用 `@AGENTS.md` import 桥接 | [Claude Code memory](https://code.claude.com/docs/en/memory) |
| `AGENTS.md`：OpenAI 2025-08 发布、2025-12 捐 **Linux Foundation AAIF**；合并规则 = **最近文件胜出（proximity）**；Codex 用 `AGENTS.override.md` 硬替换 | [LF AAIF](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation) · [agents.md resolution](https://deepwiki.com/openai/agents.md/5-agents.md-format-documentation) |
| ★★ **prompt cache 纪律**：中途改 `CLAUDE.md` **不失效 cache，但也不生效**（沿用 session start 旧版，默认下个 `/clear`/重启才生效）；而**改工具定义（名/描述/参数）会让整个 cache 失效** | [Claude Code prompt caching](https://code.claude.com/docs/en/prompt-caching) · [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) |
| 显式 **cache breakpoint**：断点后的内容可改而不失效 ⇒ **易变内容必须放在断点之后** | [Azure/OpenAI prompt caching](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching) |
| 「prompt hash 入链」的**未成标准**的草案：Agent Record（append-only + Merkle）、Delegation Receipts（`Model State Commitment` 绑 system prompt hash）、Lineage Tracking | E2/E1（未成标准，**不引为规范**） |

### 3.2 agent 进度可观测

| 事实 | 出处 |
|---|---|
| **OTel GenAI semconv**：span = `invoke_agent` / `create_agent` / `execute_tool`，kind = CLIENT；属性 = `gen_ai.operation.name` · `gen_ai.agent.name` · `gen_ai.agent.id` · `gen_ai.tool.name` · `gen_ai.tool.call.id` · `gen_ai.tool.type` · `gen_ai.usage.input_tokens` | [OTel GenAI registry](https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/2e994c6d59a93bb4fc1752c5378eedb9b8e14d6b/model/gen-ai/registry.yaml) |
| **A2A TaskState 枚举**：`submitted` / `working` / `input-required` / `completed` / `canceled` / `failed` / `rejected` / `auth-required`（`completed/failed/canceled/rejected` 为终止态） | [A2A definitions](https://a2a-protocol.org/latest/definitions/) |
| Claude Code 官方 OTel：`CLAUDE_CODE_ENABLE_TELEMETRY=1` + `OTEL_*_EXPORTER=otlp`，导出 metrics/logs/spans | [Claude Code monitoring](https://code.claude.com/docs/en/monitoring-usage) |
| **append-only → 只读 read-model** 的实现范式：`esaa-core`（`.roadmap/activity.jsonl` 唯一真源 + `event_seq` 无缺口 + 只读视图）· `agentflow`（JSONL + SSE `after=N` 重放）· `agent-log-viewer`（parent→child 树 + tail） | E2（npm/GitHub 项目） |
| **长跑健康字段命名惯例**：Temporal `heartbeatTimeout` / `scheduleToCloseTimeout` / `startToCloseTimeout` + RetryPolicy `initialInterval` / `backoffCoefficient` / `maximumAttempts` | [Temporal timeouts](https://docs.temporal.io/develop/python/activities/timeouts) |

### 3.3 任务板 / DAG

| 事实 | 出处 |
|---|---|
| **「只有存在依赖树或并行分支时才值得上 board，线性流水线用文件协调即可」** —— Kanban 的价值项 = `parallel / named owners / dependencies / review / recovery` | [Hermes Bot Mode vs Kanban](https://dev.to/) · [Why a Markdown File Beats a Message Bus](https://batty.hashnode.dev/why-a-markdown-file-beats-a-message) |
| 机制词对比：LangGraph checkpointer = **node 边界 + `thread_id`，是 resume 非 durable**（崩溃重跑整节点、副作用重放）；Temporal = history replay + RetryPolicy + heartbeat = **真 durable**；OpenAI Agents SDK `Session`（SQLite/Redis/DynamoDB）可 resume；Beads/Gas Town = 基于 Dolt 的**依赖图 issue tracker**（`bd` CRUD / `bv` 只读 triage） | [Gas Town](https://pkg.go.dev/github.com/steveyegge/gastown) · E2 |
| ★ **反例**（上了 board 反而更糟）：乐观锁「只救过一次」· YAML 重排 diff 噪声大 · 看板行政负担致 burnout · **Vibe Kanban 云服务 2026-04 sunset** · 进度虚报/成本失控的卸载帖 | E1（社区帖） |

### 3.4 技能渐进披露

| 事实 | 出处 |
|---|---|
| **agentskills.io 规范** front-matter：必填 `name`（≤64，小写/数字/连字符，**须与目录同名**）、`description`（≤1024）；可选 `license` / `compatibility`（≤500）/ `metadata` / `allowed-tools` | [agentskills.io spec](https://agentskills.io/specification) |
| **预算**：启动只注入 `name` + `description`（**≈100 tokens/技能**），命中后 `load_skill` 拉全文（**建议 <5000 tokens**） | [Anthropic Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) |
| 实测：eager loading 下定义随 N 增长**压倒上下文直至溢出**；正解 = **用工具调用按需加载，而非动态改 system prompt** | [Progressive Disclosure of Agent Skills (arXiv)](https://arxiv.org/pdf/2609.35692) |

**社区调研未找到**（如实）：`GEMINI.md` 的官方合并规范；「改 `SOUL.md` 是否击穿 cache」的专门实测（只有 Claude Code 通用结论）；把 `AGENTS.md` 规定为「system prompt 首项」的硬规范（仅 `SOUL.md` 明文 slot #1）。

---

### 3.5 ★ 人格注入的价值与边界（论文级证据，E3）—— 对本框架三目标的增益判定

> **问题**：对本框架 + 待接入的**学术推理 / 量化金融 / 数学推理**（强调**低幻觉 · 高质量英文 · 深度推理**），人格注入**有没有增益、体现在哪**。

**（1）「身份声明」类人格：对客观任务近零增益，时而有害**

| 方向 | 证据（E3） |
|---|---|
| 正增益（**不稳定**） | `arXiv:2308.07702`（NAACL'24 角色扮演提示）AQuA 53.5→63.8 · Last-Letter 23.8→84.2；`2506.07335` Llama3.1-8B CSQA 31.86→39.80 |
| **反证（更强）** | `2311.10054`（EMNLP'24 Findings）：**162 角色 × 4 模型 × 2410 事实题 ⇒ 加人格不提升**，in-domain 系数仅 **+0.004**；`2512.05858`（Wharton Report 4）：GPQA-Diamond+MMLU-Pro、6 模型×25 样本 ⇒ **专家人格无一致增益**，域不匹配**有时降**；`2603.18507`（PRISM）：专家人格**利写作/安全、损 MMLU/math/coding**；`2408.08631`：角色提示有时降推理 |
| 域匹配 | **必要非充分** —— `2311.10054` in-domain 仅优 ≈**0.4pp**；`2512.05858` 域定专家仍无显著增益 |

**（2）真正有效的是「流程 + 约束」，不是「人设」（低幻觉的真实杠杆）**

| 手段 | 实测（E3） |
|---|---|
| **弃答 / 置信门槛** | `2401.13275`（ICML'24）：纯 Idk 提示 TRUTHFUL **66.93%**、Idk-SFT **74.75%**（代价 = 过度拒答）；`2506.07309` ConfQA：缺「仅在自信时作答」时幻觉仍 **15–25%** |
| **CoVe（验证链）** | `2309.11495`：草稿→自问验证问题→独立作答→修正 ⇒ 一致降幻觉 |
| **self-consistency** | `2203.11171`：算术 **+3–6%**（UL2-20B）/**+9–23%**（LaMDA-137B） |
| **细粒度引用/接地** | ALCE `2305.14627` 立 citation recall/precision；FRONT `2408.04568` 使 LLaMA-2-7B citation quality **+14.21%**（超 ChatGPT） |
| ⚠ **格式契约的反作用** | `2408.02442`《Let Me Speak Freely?》：**约束越严、推理退化越大** ⇒ ★ **推理必须置于格式约束之外** |

**（3）人格注入的风险（对本框架尤其相关）**

- **编造资历/冒充专家**：`2511.21569` 职业人格抑制诚实自述并**编造执业经历**；
- **过度自信**：`2506.00582` 专家角色**抬高过度自信**；
- **人格漂移**：`2402.10962`（EMNLP'24）LLaMA2-70B **8 轮内显著漂移**（归因 attention decay）；
- **谄媚**：`2310.13548`（Anthropic）跨任务一致谄媚，**RLHF 偏好为主因**；
- **安全边界**：`2312.03853` 对抗人格可绕安全；`2505.12692` 人格增脆弱性。

**（4）学术写作与引用（直接命中本框架目标）**

- **编造引用实测**：Walters & Wilder —— GPT-3.5 **55%** / GPT-4 **18%** 引用系编造，真实引用中 43%/24% 有实质错误；`JMIR'25` GPT-4o **19.9%**。
- ⇒ **「先验证再引用」是刚需**；但**「降到具体百分之几」的论文级数字未找到**（如实标注）。

**（5）对本框架三目标的落点判定**

| 目标 | 人格注入能否帮到 | 靠什么 |
|---|---|---|
| **低幻觉** | ⚠ **仅当**人格文件装的是 **epistemic 约束**（不确定即弃答 · 无源不述 · 区分「检索到的」vs「回忆出的」· 逐句给源）—— **装人设无效** | 约束 + 流程（CoVe / 多采样 / 先检索后作答） |
| **高质量英文学术** | ✅ **有据** —— 专家人格对**写作/语域有益**（`2603.18507` PRISM）；但**格式契约害推理** ⇒ **推理放约束外，输出入契约** | 语域/术语契约 + 引用接地 |
| **深度推理（数学/计量）** | ❌ **身份声明无增益、甚至有害** | **流程**（CoVe / self-consistency）+ **结构性验收**（本框架 D7 角色分离 + strong-accept 已有） |

★ **一句话**：**「你是资深 X / 专家」这类身份声明对本框架三目标近零增益，且带来编造资历与过度自信风险；有增益的是「流程 + epistemic 约束 + 语域契约」——即该文件的正确形态 = **约束文件**，不是人设文件。**（且与已知立场一致：把「**拒绝把叙事当因果解释 / 统计客观性优先**」写成约束，属**受证据支持的约束**，而非人设。）

---

## 4. 框架侧「已有 / 缺口」实测（E1）

| 件 | 现状（E1 实读） |
|---|---|
| 进度真值 | `ops/cluster.py`：`agent` 子命令族（`runs` / `live` / `tail` / `chain` / `verify` / `audit` / `audit-judge`），口径**主动对齐 OTel GenAI `invoke_agent` span 与 A2A TaskState** |
| 进度视图 | `ops/cluster_web.py`：`_collect_agent()` + `/api/agent` + 前端「**agent 任务视图**」（运行中节拍 + 派发台账，15s 自刷） |
| 台账/证据 | `agent-runs.log`（一行一 run）· `runDir/.agent-run.json`（终态契约）· `AGENT_EVIDENCE_FILES`（含 `prompt.txt`）· 证据链 `agent-chain.json` + `evidence` 断言（可重放 gap 审计） |
| 人格落点 | ★ **已有**：工作区 `AGENTS.md`（骨架 + tar 分发）与生成式 `CLAUDE.md` 薄壳（`@AGENTS.md`）；`agent-cli` 把 prompt 写入 `out/.prompt.txt` 并以 **stdin** 喂 `opencode run`，跑完 move 成 `prompt.txt`（**在证据链 subjects 内**） |
| **真缺口** | ★ **① 无「人格/声音」层**（D7 只有协议角色）；★ **② 无「任务粒度 DAG」**（台账是 run 粒度 append-only）；③ agent 卡片**未展示证据链审计结论**（现只在门禁输出里） |

---

## 5. 落地步骤（**方案稿，待裁**；未授权不执行）

> **纪律**：写动作一律走 [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md)（默认 `--plan`，`--go` 才动手）；**不新增并列脚本**（D2/D3）；**不引入第二状态源**。

### 5.1 W1 · 约束层（原称「人格层」★ 最高性价比）

**目标**：给 wrapper 一份**版本化、可审计的「约束文件」**（**非人设**）—— 按 §3.5 结论，**内容优先级 = 流程 > epistemic 约束 > 语域/格式契约 > 风格**，**且不写「你是资深 X / 专家」这类身份声明**；由 `agent-cli` 在拼 prompt 时**前置注入**，并把「本次用了哪份」写入终态契约。

| # | 步骤 | 落点 / 判据 |
|---|---|---|
| 1 | 定规范：文件 schema（front-matter `name` / `description` / `version` / `scope`；**单一文件**；**置 prompt 首槽**；**内容三区 = 流程 / 约束 / 契约**；**禁写身份声明**） | 新增 `spec/d6-agent-standard/CONSTRAINTS.md`（★ 建议命名 **CONSTRAINTS** 而非 `PERSONAS` —— 避免「人设」误读；实现对齐 SOUL.md「slot #1」） |
| 2 | 放载体：立 1 份**约束文件**（可移植本机 `~/.hermes/personas/deepscientist.md` 的**阶段图 + truth-source 优先级** —— 那正是「流程 + 约束」非人设）；★ 显式写入 **「区分检索/回忆 · 无源不述 · 不确定即弃答 · 拒绝把叙事当因果解释」** | `spec/d6-agent-standard/personas/<name>.md`（子目录，**已确认不在 `doc-status`/`spec-untested` 射程** ✅） |
| 3 | 注入实现：`Invoke-Task` 拼 `.prompt.txt` 前，读 `--persona <name>`（缺省 = 现状），前置**约束文件**；★ **顺序 = 先自由推理、后入格式契约**（`2408.02442`：格式约束害推理） | 改 `ops/station-bin/agent-cli.ps1`（已在 `station_runtime` 清单 ✅） |
| 4 | 审计：把 `persona` 名 + `persona_sha256` 写入 `runDir/.agent-run.json`（**复用已有 `profile` 位**）；`prompt.txt` 已在证据链 ⇒ **自动覆盖** | 可复算：`sha256(persona 文件) == .agent-run.json.persona_sha256` |
| 5 | ★ **缓存纪律（社区 E3）**：约束文件变更**默认下个 run 生效**，**禁止 run 中途改写**；易变内容放 cache 断点之后 | 写进 `CONSTRAINTS.md` 的「运行期不变式」 |
| 6 | 门禁 | `scripts` 断言（**未新增 ops 脚本** ⇒ 合 D2）· 新 md 过 `doclinks` + `md-tables`（+ 若入 spec 射程则 `doc-status`/`spec-untested`）· 改 `.ps1` 后必过 **BOM + LF**（`syntax` 的 `.ps1-bom` 维度）与 `ps1-golden`（`FM_GOLDEN_TEST`）· `py-tests` 52/52 |
| 7 | 验收（正/负向，可机读） | (a) 带 persona 的 run：`.agent-run.json` 含 `persona`/`persona_sha256` 且 hash 相符 ✔ (b) 不带 persona：行为**逐字**不变（回归）✔ (c) 改 persona 文件后**同一 run 内** prompt 不变、**新 run** 才变 ✔ |
| 8 | 回退 | `--persona none`（或缺省）= 回旧行为；**零迁移成本** |

### 5.2 W2 · agent 进度视图增强（把审计结论搬进卡片）

| # | 步骤 | 落点 / 判据 |
|---|---|---|
| 1 | CLI：`agent` 加 `digest` 子命令 —— 把 `chain` / `verify` / `audit` 的结论聚合成**一行状态**（供看板与 CI 消费） | 改 `ops/cluster.py`（已在 `entry` 清单 ✅） |
| 2 | Web：agent 卡片加**证据链状态列**（`chain A1/A2/A3`、**可重放 gap N**、`judge 校准 fresh`） | 改 `ops/cluster_web.py`（已在 `entry` ✅）；数据仍走 `_collect_agent()` **同一实现**（不造第二取数） |
| 3 | （可选）字段别名：给内部状态列补 **OTel GenAI 属性名**（`gen_ai.operation.name` 等），为将来 OTLP 导出留位 | 只做**命名映射**，不改语义 |
| 4 | 长跑健康字段（`heartbeat_at` / `max_runtime_s` / `attempt` / `consecutive_failures`，借 Temporal 命名） | ⏸ **本轮不做** —— 现役多为同步短跑，属过度工程（V2 再议） |
| 5 | 门禁 | `derived-view`（真值→渲染**逐字节**一致；若为派生渲染须同步源 hash）· `py-tests` · `executor-trace` 机制不变 |
| 6 | 验收 | 卡片同时显示「站上 live 节拍」与「台账尾 N」，且审计结论列与 `agent verify` **输出一致** |

### 5.3 W3 · 任务板 / DAG（**条件触发，本轮不做**）

- **不做的依据**：① 现役负载 = 1 会话 1 链，**无依赖树/无并行分支**（社区判据）② 本机 Hermes `kanban.db` 各表 **rows=0**（连上游桌面版也没被用起来）③ 本仓 V2 fan-out 的前置三门（BLINDSCAN BS-1 `isolate_db` / BS-2 网关放行多 tool call / BS-3 槽 bug）**尚未通过**。
- **触发条件（if-then）**：当且仅当 V2 fan-out 三门通过 **且** 出现跨 run 依赖树时，才按 `task_links` 范式给台账加 **task 粒度 DAG + `task_events` 事件流**（落 `agent-runs.log` 的**演进**，非新库）。

### 5.4 明确不做（附理由）

| 不做项 | 理由 |
|---|---|
| 引入 Hermes **hooks / kanban.db** | = **第二状态源**，违「单一真值 / 不造第二定义点」；且 D2 只减不增 |
| 常驻 **dashboard 服务**（9119 式） | 撞 ADR-0004「**零自加载 · 无 daemon**」；等价能力已由 `cluster_web.py` 的**按需**卡片覆盖 |
| 让 persona **run 中途生效** | 击穿 prompt cache（E3 实测），且破坏「同 run 可复算」 |
| 引入 **agent 沙箱/容器隔离** | [ADR-0004](../../adr/ADR-0004-统一管理入口为唯一管理面.md) L316-329 已裁：**不采用容器化做常规隔离**，OS 级兜底首选**无 daemon 的 Apptainer** |
| 照抄 Hermes 的 **13 个人格预设** | 本框架用途是**确定性编排 + 证据链**，非陪伴/娱乐；人格层只收**1–2 份「研究/工程立场」文件** |

---

## 6. 风险与未确证（如实）

- **未确证**：① `spec/agent-observability/` 调研档的实际路径（`cluster.py` 注释引用了它，但本轮 glob **未命中**）—— 需确认是否改名/移走；② `cluster_web.py` 的 agent 卡片**当前渲染到哪一层**（未实跑页面）；③ ~~`spec/d6-agent-standard/personas/` 是否落在 `doc-status` / `spec-untested` 两断言的 glob 射程内~~ ⇒ **已解（E1）**：两断言自述射程 = **`spec/d6-agent-standard/*.md`（顶层）+ `adr/ADR-*.md`** ⇒ **子目录 `personas/` 不在射程内**，W1 步骤 2 无额外门禁成本；④ 人格层对现役 `ROUTE_TABLE` 与门禁的**影响面**（未测）；⑤ ★ **§3.5 的增益判定全部为 E3（外部论文/规范），本框架内未实测** —— 若 W1 落地，**须先做 A/B（带 / 不带约束文件 × 低幻觉任务）**验证增益，再决定长期保留。
- **风险（★ 新增，来自 §3.5）**：约束文件**若写成「人设」**会引入 ① 编造资历/冒充专家（`2511.21569`）② 过度自信（`2506.00582`）③ 长上下文人格漂移（`2402.10962`）④ **格式契约害推理**（`2408.02442`）⇒ 故 W1 明确 **禁身份声明**、**推理置契约之外**。
- **风险（工程）**：改 `agent-cli.ps1` 触 `ps1-golden` + `.ps1-bom` 双门禁（**必须保 BOM + LF**）；改 `cluster_web.py` 触 `derived-view`（**逐字节**比对）。
- **纪律**：本文为**方案稿**；W1/W2 的每一步均属写动作，**须先给 ADR-0004 的 `--plan` 与门禁**，未授权不落。
