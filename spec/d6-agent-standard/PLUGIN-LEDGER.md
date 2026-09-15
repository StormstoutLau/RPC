# A/B/C 三站 Agent CLI 插件台账（2026-09-09 起）

> **状态**: A/B/C 三站实盘盘点（opencode/claude 双 CLI 同构，见 §1-5）｜ A 站 Hermes Agent 插件生态盘点（2026-09-10，见 §6）
> **关联**: [ARCHITECTURE.md](ARCHITECTURE.md) §9（记忆层 + DCP 落地）｜ [DEV-LOG-011](../docs/DEV-LOG-011-d6-agent-standard.md) §8（C 站接入）
> **落档**: Scott ｜ 2026-09-09（opencode/claude）/ 2026-09-10（Hermes）
> **2026-09-15 起**: §1 的"三站同构"**不再靠人工核对** —— 已落成可断言的真值
> `inventory/plugins.yaml` + 门禁 `ops/rpc_check.py` 的 `plugins` 断言（本地）
> 与 `stations` 断言 (h) 子项（站上实况）。**本表的人工结论以门禁为准**。

---

## 1. 三站插件配置全景（实盘核对）

| 组件 | A | B | C | 版本（三站同） |
|---|---|---|---|---|
| opencode | ✅ | ✅ | ✅ | 1.18.25（锁版） |
| claude code | ✅ | ✅ | ✅ | 2.1.258（锁版） |
| opencode.jsonc plugin | ✅ | ✅ | ✅ | `[codex-memory@0.6.5, @tarquinen/opencode-dcp@latest]` |
| tui.json | ✅ | ✅ | ✅ | DCP 注册 |
| dcp.jsonc | ✅ | ✅ | ✅ | 默认配置 |
| DCP 缓存 | ✅ | ✅ | ✅ | `@tarquinen/opencode-dcp@latest` |
| codex-memory 缓存 | ✅ | ✅ | ✅ | `opencode-codex-memory@0.6.5` |
| claude 定制技能 ×12 | ✅ | ✅ | ✅ | `~/.claude/skills/` |
| claude 插件 | ✅ | ✅ | ✅ | superpowers + anthropic-skills（document-skills）|
| CLAUDE.md | ✅ | ✅ | ✅ | 集群铁律（C 站已适配） |
| opencode ARS 链 | ✅ | ✅ | ✅ | skills 4 + agents 4 + commands 16 + plugins 1 |

**三站完全同构**（DCP 安装为 2026-09-09 统一完成）。

### 1.1 ⚠️ 2026-09-15 修正：上表曾把"C 站 ARS 链 ✅"判错

首次做**站上实况对账**（门禁 `stations` 断言 (h) 子项）即发现：

| 项 | A | B | C（修复前） | C（修复后） |
|---|---|---|---|---|
| ARS 落点软链数 | 25 | 25 | 25 | 25 |
| **其中死链数** | 0 | 0 | **25（全断）** | 0 |
| 源目录 `~/tools/opencode-academic-research` | 有 | 有 | **不存在** | 有（1058 文件 / 17M） |

**根因**：C 站只有**落点软链**（2026-09-09 随 B→C 复刻时建的），**源目录从未同步过去**。
于是 25 个软链全部悬空 —— C 站的 ARS 学术链（4 skills + 16 commands + 4 agents + 1 plugin）
**实际完全不可用**，而本表原判据只看"软链是否存在"，个数三站又恰好都是 25，
所以手工核对显示"一致"。

**教训（已写进判据）**：插件面同构必须判**软链可达性**（`ars.broken` 必须为 0），
不能只数个数。这也是 §1 表格此前唯一的真实误判。

**修复**：A → 主控站 SFTP 中转 → C（A→C 免密不通），tar md5 双向一致后解包；
C 站复验 `ars.broken=0`、`ars.source=yes`，与 A 站逐项对齐（169/16/4/1）。

### 1.2 口径澄清：ARS 落点软链到底几个

`~/.config/opencode` 下**递归**共有 32 个软链，此前台账/手册曾直接引用 32，容易被误读：

| 构成 | 个数 | 是否 ARS |
|---|---|---|
| `commands/` | 16 | ✅ |
| `skills/` | 4 | ✅ |
| `agents/` | 4 | ✅ |
| `plugins/` | 1 | ✅ |
| **小计（ARS 落点）** | **25** | — |
| `node_modules/.bin/` | 7 | ❌ npm 依赖的 bin 软链 |

真值表 `inventory/plugins.yaml` 只登记 ARS 落点 25（刻意排除 `node_modules`），
并由 `ars.links.{skills,commands,agents,plugins}` 四项分类计数 + `ars.links` 总数共同锁定。

**另注**：源目录在本集群是**解包产物、非 git checkout**（`git rev-parse` 报"不是 git 仓库"），
故上游 commit `1d3032f` 在站上**无法自证**，真值表刻意不登记该 commit。

---

## 2. 测试状态矩阵

### 2.1 测试过的（✅ 实机验证）

| 插件/组件 | 验证项 | 证据 | 站 |
|---|---|---|---|
| **codex-memory** | 源码审计（机制/边界）| ARCHITECTURE §9.1-9.3（2500-token 摘要 + subagent 提取）| 源码级 |
| **DCP 工具注入** | 模型回答可用 `compress` 工具 | C 站 run 冒烟 `DCP-OK` + 工具询问 | C ✅ |
| **DCP 加载** | `--print-logs` 无插件错误 | C/B/A 站冒烟 | 三站 ✅ |
| **DCP 配置生成** | `dcp.jsonc` 自动创建 | 三站均确认 | 三站 ✅ |
| **opencode 全链路** | `opencode run` 到本地引擎 | C 站 nemotron `PLUGIN-OK` / A/B 历史 | C 全链 ✅ |
| **claude 全链路** | `claude -p` 到本地引擎 | C 站 nemotron `end_turn output_tokens=154` | C ✅ |
| **12 定制技能加载** | skills 目录 12 项 | 三站 `ls` 确认 | 三站 ✅ |
| **superpowers 加载** | settings 引用 + 插件缓存 | 三站 `installed_plugins.json` | 三站 ✅ |
| **CLAUDE.md 注入** | 文件存在 + 内容正确 | C 站已适配 | 三站 ✅ |
| **ARS 链可见** | agents 4 + commands 16 + skills 4 | B 站 `ls` | B（复刻源）✅ |

### 2.2 未测试的（❌/⚠️ 待验证）

| 插件/组件 | 未测项 | 原因/前置 |
|---|---|---|
| **DCP 真实压缩** | 长会话触发 compress 后压缩质量（是否"脑叶切除"）| 需长任务（specaudit 类）真实运行观察；社区本地模型有翻车先例 |
| **codex-memory 记忆生成** | memorize-extract + memorize subagent 实际沉淀 | 需多会话任务验证跨会话记忆取回 |
| **DCP+codex-memory 共存** | 两插件同会话互不干扰 | 需长会话实测 |
| **A/B 站引擎级冒烟** | DCP 工具注入到本地模型 | 两站当前无 llama 引擎运行（C 站已验证） |
| **12 技能内容正确性** | 各技能在本地模型上的实际输出质量 | 依赖具体任务触发（技能是 SKILL.md 声明，触发才加载）|
| **superpowers 6.3.0 具体技能** | using-superpowers 等 14 技能在本地模型触发 | 依赖 superpowers 工作流任务 |

---

## 3. 社区反馈 vs 实际测试对照

### 3.1 DCP（`@tarquinen/opencode-dcp`）

| 维度 | 社区反馈 | 本集群实际 |
|---|---|---|
| 本地模型可用性 | ✅ 实证可用（qwen3.5-35b 正常）；⚠️ 有人报"压缩会崩本地模型"（#552 kecsap）| ✅ 工具注入 + 加载正常（C 站）；**真实压缩质量未测** |
| 已知坑 | ① compress 反馈循环烧 738K tokens（#573）② stale 边界 ID（#551/#555）③ 缓存命中率 -5%（90%→85%）| 未触发（需长会话）；**监控项** |
| 机制特点 | 只改请求副本，不碰会话历史；只折叠 read/grep/glob/bash 成功输出 | 与 codex-memory 互补（会话内 vs 会话间）|

### 3.2 Magic Context（未选型）

| 维度 | 社区反馈 | 本集群决策 |
|---|---|---|
| 本地模型 | ⚠️ **高风险**：qwen 首次压缩"脑叶切除"（写意大利语/只回数字 3 和 33）| ❌ 不采用（本地 120B 模型风险）|
| 机制 | 后台 historian + 向量 DB + 跨会话记忆 + 衰减渲染 | 与 codex-memory 功能重叠，且更激进 |
| Bug | 3 个未修（#212：factCount=0 / git_timeout 崩溃 / workspace_members 空）| — |

### 3.3 codex-memory（`opencode-codex-memory@0.6.5`）

| 维度 | 社区/源码事实 | 本集群实际 |
|---|---|---|
| 机制 | codex 两阶段移植：2500-token 摘要注入 + 按需检索 + 双 subagent | 源码审计确认（ARCHITECTURE §9.1）|
| 能力边界 | **跨会话持久化** ✅ / 单会话长任务部分 / 不解决上下文物理扩大 | 定位明确：跨会话记忆层 |
| 坑 | subagent 整合用同一本地模型 → 记忆质量受模型上限约束；记忆污染风险 | 关键任务须 accept golden（O-12）兜底 |

---

## 4. 插件-任务映射

| 插件/组件 | 适用任务 | 不适用 |
|---|---|---|
| **DCP** | 单会话长任务（读码/重构/调试）——动态压缩旧工具输出 | 短问答（压缩收益为负）|
| **codex-memory** | 跨会话研究/写作（Paper 试点、调研多轮）——持久记忆 | 关键数值/金融正确性任务（记忆污染风险）|
| **superpowers** | 结构化工作流（TDD/写计划/并行 agent/代码评审）| 非工程化任务 |
| **document-skills** | xlsx/docx/pptx/pdf 文档处理 | — |
| **12 定制技能** | 学术研究链（math-finance-reasoning / what-if-oracle / research-* / assertion-audit / cross-examine）| 日常编码（自动触发弱，显式调用）|
| **ARS 链** | 学术论文全流程（plan/outline/revision/citation-check/rebuttal 等 16 命令 + 4 agents）| — |
| **CLAUDE.md** | claude 会话纪律注入（compact 纪律/窗口铁律）| — |

---

## 5. 台账维护规则

1. **单一真值**: 本文件是 agent CLI 插件生态的唯一台账；测试状态变更必须回填
2. **状态标注**: `✅ 已验证` / `⚠️ 部分` / `❌ 未测` / `🔴 社区风险`
3. **坑记录**: 社区坑 vs 实测坑分开列（社区反馈 ≠ 本地实证，本地实证 > 外部案例铁律）
4. **测试触发**: 真实压缩/记忆生成等需长任务的验证，随对应任务自然触发后回填
5. **版本锁定**: opencode 1.18.25 / claude 2.1.258 / codex-memory 0.6.5 / DCP 3.1.15 均为锁定值

---

## 6. A 站 Hermes Agent 插件生态盘点（2026-09-10）

> **版本**: Hermes Agent v0.21.1 (2026.9.7)，安装目录 `~/.hermes/hermes-agent`，Python 3.11(uv 托管)
> **定位**: Hermes 是本机群的 Agent 编排层候选（区别于 opencode/claude 的会话 CLI）。本节盘点其自带插件/技能生态，判断与「本机推理 + 反幻觉工作流」的契合度。
> **状态**: 盘点完成 ｜ 插件/技能均为 **builtin（内置）默认未启用**，未做启用接入

### 6.1 结构

| 层 | 位置 | 内容 |
|---|---|---|
| 插件 Plugins | `hermes-agent/plugins/` | 24 目录，含 model-providers / web / browser / platforms 等 |
| 商店注册 | `hermes plugins list` | **58 项** bundled 插件（全部 not enabled）|
| 技能 Skills | `~/.hermes/skills/`（用户侧）+ 仓库 `hermes-agent/skills/` | 25 分类目录；`hermes skills list` 全部 enabled(builtin) |
| 技能包 Bundles | `~/.hermes/skill-bundles/` | **空**（待用 `hermes bundles create` 编排）|

### 6.2 内置插件分类（58 项，全部 bundled）

| 类别 | 插件 |
|---|---|
| 浏览器/抓取 (4) | browser-use / browserbase / firecrawl / chronos |
| 模型provider (8) | deepinfra / fal / krea / meta-ai-image-gen / **openai / openai-codex** / openrouter / xai |
| 消息平台 (19) | dingtalk / discord / email / **feishu** / google_chat / irc / line / matrix / mattermost / ntfy / photon / raft / simplex / slack / sms / teams / **telegram / wecom / whatsapp** |
| 网络搜索 (10) | web-{brave,ddgs,exa,firecrawl,keenable,parallel,perplexity,searxng,tavily,xai} |
| 其他 | disk-cleanup / google_meet / langfuse(可观测) / security-guidance / spotify / teams_pipeline |

### 6.3 内置技能（builtin，全 enabled）

- **autonomous-ai-agents**: claude-code / codex / hermes-agent / opencode / kanban-codex-lane
- **creative**: architecture-diagram / ascii-art / comfyui / excalidraw / manim-video / p5js / pixel-art / humanizer / ideation 等
- **data-science / devops / email / github / mlops / research / research-workflow / software-development** 等（由 `~/.hermes/skills/` 25 分类体现）

### 6.4 与本机群契合研判

| 插件/组件 | 契合度 | 说明 |
|---|---|---|
| **自定义 provider→本机 llama-server** | ⭐⭐⭐（需自行配置）| hermes 的 provider 插件默认指云端；接本机 M2.7/Q3.8F/Nemotron 端口需自定义 provider（待验证）|
| **web-{ddgs,searxng,exa,parallel}** | ⭐⭐⭐ | 无需 key 或自建，可直接做「反幻觉工作流」检索层（外置知识库佐证）|
| **Bundles（空）** | ⭐⭐⭐ | `hermes bundles create` 可把「本机推理+检索+记忆」编排成可复用技能包 |
| 图像/视频生成插件 | ⭐ | 云端 API，非本机场景 |
| 消息平台 (telegram/whatsapp/wecom/feishu) | ⭐⭐ | 长任务完成通知渠道 |

### 6.5 待办/观察

- [ ] Hermes 自定义 provider 接本机 llama-server 端点（M2.7/Q3.8F/Nemotron）——本机推理接入的关键
- [ ] 用 hermes bundles create 搭建「反幻觉工作流」技能包（本机推理 + web 检索 + 记忆）
- [ ] C 站 hermes CLI 安装完成度（依赖 uv sync，PyPI 下载慢为瓶颈）
- [ ] B 站 hermes CLI 安装待 Nemotron 测试跑完后