# Agent 生态升级与多智能体协作架构调研

> 日期: 2026-09-01 · 作者: Scott (鹏) + Trae
> 状态: **调研完成, 待用户裁决执行范围**
> 前置: [ClaudeCode本地集群与子代理框架分析.md](ClaudeCode本地集群与子代理框架分析.md) (阶段2 GO)、[双端点部署与opencode混合框架调研.md](双端点部署与opencode混合框架调研.md) (双端点已落地)
> 配套: [spec/vulkan-version-control/](spec/vulkan-version-control/) 五阶段 spec 模板链

***

## 0. 两个问题的答案速览

| 问题 | 答案 |
|---|---|
| 插件生态是否需要更新? | **是, 且空间巨大**: 两站 4 个 agent 全部裸装 (无 MCP/skills/subagents/自定义 agents)。关键事实: **Skills/MCP/subagents 全是 CLI 客户端机制, 与后端无关** — 经 ANTHROPIC_BASE_URL 指向本地 nemotron/gpt-oss 后整套生态完全可用 (tool-use 已 PASS 实锤)。opencode 1.18+ 更是**直接读 `.claude/skills/`**, 一份 skills 两 CLI 零成本共用 |
| 4 agent × trae 如何高效协作? | **五层循环**: trae 规划(生成 spec) → 派发(SSH headless 任务卡) → 本地执行(检索/编码/编译/测试) → 执行锚定验证(编译器+测试+数值输出, 零 LLM 成本拦幻觉) → trae ADD 审计回环。成本分配: 本地 80% 流量(无限 token), trae 20% 高价值轮次(规划+审计) |

***

## 1. 现状盘点 (2026-09-01 实测)

### 1.1 两站 4 agent 版本与生态

| 站 | Agent | 版本 | MCP | Skills | 自定义 Agents | 诊断 |
|---|---|---|---|---|---|---|
| A (NEX) | opencode | **1.18.25** (最新) | ❌ | ❌ | ❌ | 裸装 |
| A (NEX) | claude code | 2.1.220 | ❌ | ❌ | ❌ | 裸装, 有 plugins 目录(marketplaces)未启用 |
| B (GTR-Pro) | opencode | **1.18.9** (落后 16 版) | ❌ | ❌ | ❌ | 裸装, plugin SDK 1.17.11 |
| B (GTR-Pro) | claude code | 2.1.252 | ❌ | ❌ | ❌ | 裸装, ~/.claude 只有 theme 配置 |

### 1.2 后端能力 (已验证)

- nemotron (B 站单机 20.9 t/s) / gpt-oss (A 站 58-64 t/s) 双端点 E2E 全通
- claudecode 经 LiteLLM anthropic 转换层 tool-use **PASS** (stats.cpp 写码→编译→测试闭环) — 这是 skills 可用的充分条件
- opencode 双 provider (cluster-local + cluster-litellm) PONG 验证通过

### 1.3 主控站既有方法论资产

- spec 五阶段模板链: RESEARCH → DESIGN → IMPLEMENTATION → CHECKLIST → ADR ([模板](spec/vulkan-version-control/DESIGN_TEMPLATE.md))
- CHECKLIST.md 本质就是文档间对齐审计 (§1.1-1.4 RESEARCH↔DESIGN↔IMPL 交叉验收) — ADD 审计的雏形
- trae 侧大量专业 skill 可作为蓝本 (statistical-analysis / peer-review / deep-research 等)

***

## 2. 生态调研核心发现

### 2.1 Skills 在本地模型后端完全可用 (关键结论)

**原理**: skills/subagents/hooks/MCP 全部是 Claude Code CLI **客户端侧机制** — skill 正文由 CLI 本地拼装进请求, hooks 本地执行, MCP 本地拉起进程, 与后端是谁无关。只要后端说 Anthropic Messages API (LiteLLM 转换层已实现), 整套扩展生态即可用。

已验证的社区后端: Ollama / LM Studio / llama.cpp / DeepSeek / GLM / Kimi / OpenRouter — **llama.cpp 原生支持已在被广泛复制的方案列表里**。

**已知限制 (120B 本地模型适配)**:
1. 模型名映射: 需 `ANTHROPIC_DEFAULT_SONNET_MODEL` 等环境变量指向本地模型名
2. skill 自动触发依赖指令遵循 — 小模型对 description 语义匹配弱 → **关键 skill 用 `/` 手动触发或 `disable-model-invocation`**
3. 内置 WebSearch 是 Anthropic 服务端工具, 本地后端不可用 → **用 web-search 类 MCP 替代** (MCP 工具本地执行, 不受后端影响)
4. 无 prompt caching → 长会话每轮重编码 (本地免费, 可接受)

### 2.2 opencode 对 Claude Code 生态的兼容性 (第一梯队)

| 资产 | 复用成本 | 说明 |
|---|---|---|
| `.claude/skills/` | **零成本** | opencode 原生扫描 `.claude/skills/*/SKILL.md` 与 `~/.claude/skills/` |
| CLAUDE.md | 零成本 | 无 AGENTS.md 时自动 fallback 读 CLAUDE.md |
| MCP server 本体 | 一次性转换 | server 复用, 但 `.mcp.json` → `opencode.json` 的 `mcp` 字段需手改 |
| `.claude/agents/` | 轻量搬移 | frontmatter 字段调整 (tools CSV → 权限对象, model 名格式) |
| Hooks | 需重写 | settings.json 范式 → JS/TS 插件范式 |

**战略含义**: 以 `.claude/` 目录为**单一事实源**, claudecode 直接用, opencode 兼容读取 — 两 CLI 一套资产。

### 2.3 社区多 agent 降幻觉十大模式 (精选与本集群相关的)

| # | 模式 | 核心机制 | 本集群映射 |
|---|---|---|---|
| 1 | **Orchestrator-Worker** | 强模型规划 + 隔离上下文弱模型并行 + 结构化 artifact 回传 | trae=orchestrator, 本地=worker |
| 2 | **Planner-Generator-Evaluator** | 生成者不验证自己 | trae 审计本地产出 |
| 3 | **Draft-Verify 级联** | 便宜模型起草 → 验证门 → 贵模型接受/增强 | PayPal 生产: 88.8% 请求停在草稿层, 省 45.8% 成本且质量 100% vs 原生 95% |
| 4 | **Spec 门控流水线** | Constitution→Specify→Plan→Tasks→Implement | spec_workflow 已有, 补 Constitution 层 |
| 5 | **Rigor 拦截器** (Curie) | 动作级拦截→验证→转发 | 3.4x 超最强基线 |
| 6 | **证据外部锚定** (Co-Scientist) | 数值声明 vs 执行日志比对 | 幻觉率 4% (Nature 2026); **回测场景是社区空白 → 本集群的机会** |
| 7 | **对抗辩论 + Elo 排名** | 多空辩论消除确认偏误 | nemotron vs gpt-oss 交叉审 |
| 8 | **否决权风控层** (TradingAgents) | 风控 agent 一等公民可否决 | 量化场景治理 |
| 9 | **验证门 fallback 链** | 超时/schema 失败/低置信 → 升级 | 本地失败 → trae 接管 |
| 10 | **记忆增强迭代** | 历史决策向量化检索 | topics.md/project_memory 人工版已有 |

**社区共识三支柱**: ① 幻觉根源是"未锁定的决策" (Qodo: 给足上下文幻觉 54%→16%); ② 读密集任务 fan-out 并行, 写密集任务单线程; ③ ~80% 真实请求简单到本地模型即可处理。

**ADD 审计印证**: 社区 "AI Decision Audit" (unhallucinate 项目) 与 Scott 的 ADD 审计方法论**独立收敛** — 枚举 AI 需要做的每个决策, 验证答案是否存在于 spec 中, 不存在则必然被幻觉。

***

## 3. 问题一: 插件生态更新清单

### 3.1 版本更新

| 项 | 动作 | 优先级 |
|---|---|---|
| B 站 opencode 1.18.9 → 1.18.25 | `opencode upgrade` | P0 (子代理失败可恢复/v1.18.20、深度限制/v1.18.2 都是协作刚需) |
| A 站 claude code 2.1.220 → 最新 | npm 全局更新 | P1 |
| B 站 claude code 2.1.252 | 已近最新 | — |

### 3.2 Skills 部署 (单一事实源 `~/.claude/skills/`, 两站 git 同步)

按 Scott 场景筛选 (宁缺毋滥, 本地 120B 的 skill 自动触发弱 → 手动 `/` 调用为主):

| Skill | 来源 | 场景 | 理由 |
|---|---|---|---|
| `code-review` | claude code 内置 | 编程 | 已有, 零成本 |
| `superpowers` 子集 | obra/superpowers | 编程 | 挑 TDD + systematic-debugging 两个, 给本地 agent 注入工程纪律; 全套 14 个对 120B 过重 |
| `quant-analysis` | 定制 (参考 quant-mcp) | 金融计量 | Sharpe/VaR/回测/Greeks 的操作规范 |
| `paper-search` | 定制 (MCP 配套 skill) | 学术推理 | 教 agent "该怎么用检索工具" (Anthropic 官方建议 MCP 配 skill) |
| `spec-compliance` | 定制 | 全场景 | ADD 审计的客户端形态: 枚举决策→比对 spec |

**定制 skill 示例** (`~/.claude/skills/spec-compliance/SKILL.md`):

```markdown
---
name: spec-compliance
description: Audit work output against spec before delivery. Use when a task
  card specifies a spec_ref, or before marking any task complete.
allowed-tools: Read, Grep, Glob
---
## Procedure
1. Read the task card (JSON): task_id, spec_ref, acceptance_criteria
2. Enumerate every decision the implementation made
3. For each decision, locate its answer in the spec
4. Classify: ANCHORED (in spec) / ASSUMED (not in spec)
5. Output verdict table; any ASSUMED decision = FAIL with rationale
```

### 3.3 MCP servers (本地 stdio, 不依赖外网 API key 的优先)

| MCP | 安装 | 场景 | 落点 |
|---|---|---|---|
| **duckdb** | `uvx mcp-server-duckdb` | 金融计量 | 直连 factor_db.duckdb — **最高对口度** |
| **quant-mcp** | `uvx quant-mcp` | 金融数学 | 20 工具: Sharpe/VaR/CVaR/回测/HMM/Greeks/Fama-French/组合优化 |
| **paper-search** | `uvx paper-search-mcp` | 学术推理 | arXiv/PubMed/Semantic Scholar/CrossRef |
| **context7** | `npx -y @upstash/context7-mcp` | 编程+计量 | statsmodels/PyTorch 等库文档实时拉取 |
| filesystem | 不装 | — | CLI 已有文件工具, 冗余 |

**opencode 配置** (`opencode.jsonc` 增加):

```jsonc
{
  "mcp": {
    "duckdb": {
      "type": "local",
      "command": ["uvx", "mcp-server-duckdb", "--db-path", "/data/factor_db.duckdb"]
    },
    "quant": {
      "type": "local",
      "command": ["uvx", "quant-mcp"]
    },
    "paper-search": {
      "type": "local",
      "command": ["uvx", "paper-search-mcp"]
    }
  }
}
```

**claudecode 配置**: `claude mcp add duckdb -- uvx mcp-server-duckdb --db-path /data/factor_db.duckdb` (同 server 两 CLI 复用)。

### 3.4 自定义 Agents (`.claude/agents/`, 定向用途)

| Agent | 模型 | 工具白名单 | 职责 |
|---|---|---|---|
| `research-worker` | 本地 | Read/Grep/Glob + paper-search MCP | 文献检索/代码考古, 只读 |
| `code-executor` | 本地 | 全工具 | 编码/编译/测试闭环 (stats.cpp 模式复制) |
| `quant-analyst` | 本地 | duckdb + quant MCP | 数据查询/指标计算 |
| `auditor` | 本地 | 只读 | 初审: 结构化验收 (终审留 trae) |

### 3.5 不建议的项

- ~~Agent Teams / tmux 多会话~~ — 主控站单人操作, 收益低于复杂度
- ~~ARIS 全套学术流水线~~ — 重, 且与 trae 侧 deep-research 重复
- ~~Hooks 体系~~ — opencode 侧需 JS 插件重写, 维护税 > 收益, 等 V2 稳定再说

***

## 4. 问题二: 4 agent × trae 协作架构

### 4.1 当前交互方式 (事实)

```
主控站 trae (付费 GLM, 深度规划)
   │ SSH (paramiko, 免密已通) + headless CLI
   ├── A 站: claude -p / opencode run  → gpt-oss (:8080) / 免费模型
   └── B 站: claude -p / opencode run  → nemotron (:8080 经 LiteLLM :4000)
```

交互本质: **trae 生成任务文本 → SSH 派发 → 本地 agent 执行 → stdout 回传 → trae 读结果**。已跑通但无协议 — 任务交接是自由文本, 这正是幻觉和传话损耗的入口。

### 4.2 目标架构: 五层循环 (Spec-Anchored Loop)

```
┌─────────────────────────────────────────────────────────┐
│ L1 规划层  trae (付费, ~20% 轮次)                          │
│    需求 → RESEARCH → DESIGN → 任务卡切片                   │
│    产出: TASKS.md (含 Constitution: 不可协商原则)           │
├─────────────────────────────────────────────────────────┤
│ L2 派发层  主控站脚本 (SSH headless)                       │
│    任务卡 = JSON: {task_id, spec_ref, acceptance,          │
│                    artifact_path, model, agent}           │
│    路由: 检索→opencode免费模型 / 编码→claudecode本地模型      │
├─────────────────────────────────────────────────────────┤
│ L3 执行层  本地 4 agent (无限 token, ~80% 流量)             │
│    A: gpt-oss (快, 58 t/s) + opencode 免费模型            │
│    B: nemotron (深, 1M ctx) + opencode 免费模型           │
│    自修复循环: 编译失败→读错误→改→重试 (本地免费无限轮)         │
├─────────────────────────────────────────────────────────┤
│ L4 锚定层  零 LLM 成本验证 (编译器/测试/数值输出)             │
│    硬门: 编译过? 测试绿? 数值对? — 不过不上报                │
│    (Co-Scientist 模式: 数值声明 vs 执行日志强制比对)          │
├─────────────────────────────────────────────────────────┤
│ L5 审计层  trae ADD 审计 (~高价值轮次)                     │
│    枚举实现决策 → 比对 spec → ANCHORED/ASSUMED 判定         │
│    PASS → git merge; FAIL → patch 任务卡重派 L2            │
└─────────────────────────────────────────────────────────┘
```

### 4.3 降幻觉五机制 (逐条落地)

| 机制 | 社区证据 | 本集群落地 |
|---|---|---|
| ① spec 锁定决策 | Qodo: 54%→16% | L1 的 Constitution + 任务卡 acceptance 字段 |
| ② 生成者不验证自己 | RLM-Cascade 质量 100%>95% | 本地只执行, trae 只审计, 角色永不分饰 |
| ③ 结构化交接 | 消灭传话效应 | 任务卡 JSON + artifact 落盘 (非 stdout 口信) |
| ④ 执行锚定 | Co-Scientist 幻觉 4% | L4 硬门: 编译/测试/数值, 零 LLM 成本 |
| ⑤ 上下文隔离 | Anthropic: 子agent=智能过滤器 | 本地 agent 只拿任务卡, 不拿全局上下文 |

### 4.4 成本与能力分工

| 资源 | 角色 | 占比 |
|---|---|---|
| trae 付费模型 | 规划 / ADD 审计 / 最终合成 / 失败兜底 (fallback 链终点) | ~20% 轮次, 100% 高价值轮次 |
| 本地 4 agent | 信息检索 / 多轮试错 / 编码执行 / 数据处理 / 初审 | ~80% 轮次, 无限 token |
| 编译器+测试+DuckDB | 锚定验证 | 0 LLM 成本 |

### 4.5 实施路线

**P0 (立即, ~1h)**: B 站 opencode 升级 + `.claude/skills/` 共享骨架 + duckdb MCP (最高对口) + `research-worker`/`code-executor` 两个 agent 定义
**P1 (半天)**: 任务卡 JSON 协议 + 派发脚本 (PowerShell/bash) + `spec-compliance` skill + 端到端走一个真实任务
**P2 (可选)**: quant-mcp / paper-search MCP / 对抗辩论双模型交叉审 / 回测数值锚定工具 (社区空白 = 论文素材)

***

## 5. 风险与边界

1. **本地模型 skill 自动触发弱**: 全部关键 skill 设 `disable-model-invocation` 或在任务卡 prompt 里显式 `/skill-name` 调用
2. **MCP 进程开销**: 每个 opencode/claudecode 会话拉起 MCP 子进程 — duckdb 文件锁与 LM Studio 无关, 但并发查询注意 duckdb 单写者限制
3. **免费模型配额波动**: opencode 免费模型是外部服务, 任务路由脚本需有 fallback 到本地端点的分支
4. **spec 维护税**: 按海拔采纳 — 跨会话/跨 agent 的工作必须 spec 化, 一行修改跳过全部仪式 (社区批评 SDD "Waterfall in a Hoodie" 的解药)
